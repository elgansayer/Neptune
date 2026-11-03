#!/usr/bin/env python3
"""Bounded CPU replay of the original USA kernel RNG draw helper.

Uses original kernel-resident SH-2 code and the normalized high Work RAM from a
verified existing checkpoint. Entry registers and a pre-wrap index are explicit
constructed inputs; this is not natural caller evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import probe_kernel as pinned
import state_graphics

ENTRY = 0x0600A0EC
NEXT_ENTRY = 0x0600A08C
INDEX = 0x060BF4F4
TABLE = 0x060BF4F8
SELECTED_WORD = 0x060BF5D4
SHIFT_PC = 0x0600A102
STACK = 0x060FF000
LIMIT = 512
BOUNDS = (0, 1, 2, 10, 255, 256)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def formula(word: int, bound: int) -> int:
    if type(word) is not int or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("word must be uint32")
    if type(bound) is not int or not 0 <= bound <= 0xFFFFFFFF:
        raise ValueError("bound must be uint32")
    return ((((word & 0xFF) * bound) & 0xFFFFFFFF) >> 8) & 0xFF


def checkpoint_memory(checkpoint: Path) -> tuple[dict, bytes]:
    metadata = json.loads(pinned.read_bounded(checkpoint, 2 * 1024**2))
    relative = Path(metadata["state_path"])
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("Checkpoint state path must be a sibling filename")
    state_path = checkpoint.parent / relative
    state = pinned.read_bounded(state_path, state_graphics.MAX_STATE)
    if (len(state) != metadata["state_bytes"] or sha(state) != metadata["state_sha256"]):
        raise ValueError("Checkpoint state size/digest mismatch")
    parsed = state_graphics.parse(state)
    ram = state_graphics.cpu_words(
        state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little")
    return metadata, ram


def execute(emu, ram: bytes, bound: int, mutation: int | None = None) -> dict:
    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.writes = []

        def write(self, address, size, value):
            address &= 0xFFFFFFFF
            if not ((address == INDEX and size == 4) or
                    (STACK - 0x100 <= address and address + size <= STACK)):
                raise ValueError(f"Unexpected write at 0x{address:08x}/{size}")
            self.writes.append([address, size, value & ((1 << (8 * size)) - 1)])
            return super().write(address, size, value)

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.instructions = []

        def exec(self, instruction, pc, in_slot=False):
            self.instructions.append([pc, instruction.word, instruction.op, bool(in_slot)])
            if not ((ENTRY <= pc < 0x0600A10E) or
                    (NEXT_ENTRY <= pc < 0x0600A0B4)):
                raise ValueError(f"Original instruction escaped inspected helper at 0x{pc:08x}")
            return super().exec(instruction, pc, in_slot)

    memory = Memory()
    backing = memory.add(0x06000000, 0x100000, ram)
    memory.write(INDEX, 4, 54)  # Explicit pre-wrap counterfactual from captured 55.
    if mutation is not None:
        offset = SHIFT_PC - 0x06000000
        backing[offset:offset + 2] = mutation.to_bytes(2, "big")
    before = bytes(backing)
    memory.writes.clear()
    cpu = CPU(memory)
    cpu.r[15] = STACK
    result = cpu.call(ENTRY, max_steps=LIMIT, r4=bound)
    if cpu.steps > LIMIT:
        raise ValueError("Instruction limit exceeded")
    after = bytes(backing)
    changed = [i for i, (left, right) in enumerate(zip(before, after)) if left != right]
    ranges = []
    for offset in changed:
        if not ranges or offset > ranges[-1][1]:
            ranges.append([offset, offset + 1])
        else:
            ranges[-1][1] = offset + 1
    return {
        "bound": bound,
        "return_r0": result,
        "steps": cpu.steps,
        "trace_sha256": sha(json.dumps(cpu.instructions, separators=(",", ":")).encode()),
        "instructions": [[f"0x{pc:08x}", f"0x{word:04x}", op, slot]
                         for pc, word, op, slot in cpu.instructions],
        "writes": [[f"0x{address:08x}", size, f"0x{value:0{size * 2}x}"]
                   for address, size, value in memory.writes],
        "changed_ranges": [{"start": f"0x{0x06000000 + lo:08x}",
                            "end_exclusive": f"0x{0x06000000 + hi:08x}",
                            "bytes": hi - lo} for lo, hi in ranges],
        "mutation_opcode": None if mutation is None else f"0x{mutation:04x}",
    }


def run(kernel_path: Path, checkpoint: Path, source_root: Path) -> dict:
    kernel = pinned.kernel_bytes(kernel_path)
    metadata, ram = checkpoint_memory(checkpoint)
    if ram[0xA4B0:0xA4F0] != kernel[0x44B0:0x44F0]:
        raise ValueError("Original kernel residency witness mismatch")
    for start, end in ((NEXT_ENTRY, 0x0600A0B4), (ENTRY, 0x0600A10C)):
        if ram[start - 0x06000000:end - 0x06000000] != kernel[start - pinned.BASE:end - pinned.BASE]:
            raise ValueError(f"Inspected original helper is not resident at 0x{start:08x}")
    emu = pinned.interpreter(source_root)
    checkpoint_index = int.from_bytes(ram[INDEX - 0x06000000:INDEX - 0x06000000 + 4], "big")
    if checkpoint_index != 55:
        raise ValueError(f"Expected candidate checkpoint index55; found {checkpoint_index}")
    word = int.from_bytes(ram[SELECTED_WORD - 0x06000000:SELECTED_WORD - 0x06000000 + 4], "big")
    cases = []
    for bound in BOUNDS:
        case = execute(emu, ram, bound)
        case["expected"] = formula(word, bound)
        case["match"] = case["return_r0"] == case["expected"]
        cases.append(case)
    control = execute(emu, ram, 10, mutation=0x4009)  # shlr2 replaces original shlr8.
    control["expected_wrong_shift"] = ((((word & 0xFF) * 10) & 0xFFFFFFFF) >> 2) & 0xFF
    control["rejected"] = control["return_r0"] != formula(word, 10)
    return {
        "schema": "neptune.original-rng-bounded-draw-contract.v1",
        "status": "success" if all(case["match"] for case in cases) and control["rejected"] else "failure",
        "game": "USA MK-81070 V1.003",
        "kernel_sha256": sha(kernel),
        "kernel_range": {"start": f"0x{ENTRY:08x}", "end_exclusive": "0x0600A10C",
                         "sha256": sha(kernel[ENTRY - pinned.BASE:0x0600A10C - pinned.BASE])},
        "nested_next_index_range": {"start": f"0x{NEXT_ENTRY:08x}", "end_exclusive": "0x0600A0B4",
                                    "sha256": sha(kernel[NEXT_ENTRY - pinned.BASE:0x0600A0B4 - pinned.BASE])},
        "checkpoint": str(checkpoint),
        "checkpoint_frame": metadata["frame"],
        "checkpoint_state_sha256": metadata["state_sha256"],
        "input_lock_sha256": metadata["identity"]["lock_sha256"],
        "residency_witness": {"status": "matched", "address": "0x0600A4B0",
                              "kernel_offset": "0x44B0", "bytes": 64},
        "interpreter_revision": pinned.INTERPRETER_REVISION,
        "interpreter_sources": pinned.SOURCE_HASHES,
        "scope": "original kernel CPU-only helper replay; constructed bound/stack/other registers and pre-wrap index; remaining mapped high Work RAM comes from retained frame1800 checkpoint; no natural caller or wrap return proved",
        "state": {"index_address": f"0x{INDEX:08x}", "checkpoint_index": checkpoint_index,
                  "constructed_index": 54, "next_index": 55,
                  "selected_word_address": f"0x{SELECTED_WORD:08x}",
                  "selected_word": f"0x{word:08x}", "selected_low_byte": word & 0xFF},
        "abi": {"bound_register": "r4", "stack_pointer": f"0x{STACK:08x}",
                "other_registers": "zero initialized; constructed"},
        "contract": "for tested bounds0..256: ((selected_word & 0xff) * bound >> 8) & 0xff; A08C advances index once and returns the indexed state word",
        "cases": cases,
        "negative_control": control,
        "limitations": ["CPU-only interpreter, no timing or hardware semantics",
                        "index55->54 is an explicit counterfactual to avoid the long wrap helper",
                        "ABI registers are constructed, not captured at a natural caller",
                        "seed routine, full recurrence, wrap path, call order and regional differences remain open"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.report.exists():
        print("FAIL: report already exists; choose a fresh path", file=sys.stderr)
        return 2
    try:
        report = run(args.kernel, args.checkpoint, args.saturn_recomp)
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "cases": len(report["cases"]), "negative_control_rejected": report["negative_control"]["rejected"]}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
