#!/usr/bin/env python3
"""Probe all captured-table non-refresh indices in the original USA kernel.

Each case uses original frame-1800 WorkRAM with one constructed index value.
This covers helper selection semantics, not natural caller order or RNG seeding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_kernel as pinned
import state_graphics

BASE = 0x06000000
ENTRY = 0x0600A0EC
NEXT_ENTRY = 0x0600A08C
INDEX = 0x060BF4F4
TABLE = 0x060BF4F8
STACK = 0x060FF000
LIMIT = 512
INDICES = tuple(range(55))
BOUND = 10
DEFAULT_CHECKPOINT = Path(
    "/home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json"
)
DEFAULT_KERNEL = Path("/home/dev/neptune-research-private/483/0KRNL.BIN")
DEFAULT_INTERPRETER = Path("/home/dev/neptune-tools/saturn-recomp-f20de94")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def formula(word: int, bound: int) -> int:
    return ((((word & 0xFF) * bound) & 0xFFFFFFFF) >> 8) & 0xFF


def read_checkpoint(checkpoint: Path) -> tuple[dict, bytes]:
    metadata = json.loads(pinned.read_bounded(checkpoint, 2 * 1024**2))
    relative = Path(metadata["state_path"])
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("Checkpoint state path must be a sibling filename")
    state = pinned.read_bounded(checkpoint.parent / relative, state_graphics.MAX_STATE)
    if len(state) != metadata["state_bytes"] or sha(state) != metadata["state_sha256"]:
        raise ValueError("Checkpoint state size/digest mismatch")
    parsed = state_graphics.parse(state)
    ram = state_graphics.cpu_words(
        state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little"
    )
    return metadata, ram


def execute(emu, ram: bytes, index: int, bound: int, mutation: int | None = None) -> dict:
    class Memory(emu.Memory):
        def __init__(self) -> None:
            super().__init__()
            self.writes: list[list[int]] = []

        def write(self, address: int, size: int, value: int) -> None:
            address &= 0xFFFFFFFF
            if not ((address == INDEX and size == 4)
                    or (STACK - 0x100 <= address and address + size <= STACK)):
                raise ValueError(f"Unexpected write at 0x{address:08x}/{size}")
            self.writes.append([address, size, value & ((1 << (8 * size)) - 1)])
            return super().write(address, size, value)

    class CPU(emu.CPU):
        def __init__(self, memory) -> None:
            super().__init__(memory)
            self.instructions: list[list[object]] = []

        def exec(self, instruction, pc: int, in_slot: bool = False):
            if not ((ENTRY <= pc < 0x0600A10E)
                    or (NEXT_ENTRY <= pc < 0x0600A0B4)):
                raise ValueError(f"Original instruction escaped inspected helper at 0x{pc:08x}")
            self.instructions.append([pc, instruction.word, instruction.op, bool(in_slot)])
            return super().exec(instruction, pc, in_slot)

    memory = Memory()
    backing = memory.add(BASE, 0x100000, ram)
    memory.write(INDEX, 4, index)
    if mutation is not None:
        offset = 0x0600A102 - BASE
        backing[offset:offset + 2] = mutation.to_bytes(2, "big")
    before = bytes(backing)
    memory.writes.clear()
    cpu = CPU(memory)
    cpu.r[15] = STACK
    result = cpu.call(ENTRY, max_steps=LIMIT, r4=bound)
    if cpu.steps > LIMIT:
        raise ValueError("Instruction limit exceeded")
    after = bytes(backing)
    changed = [offset for offset, (old, new) in enumerate(zip(before, after)) if old != new]
    ranges: list[list[int]] = []
    for offset in changed:
        if not ranges or offset > ranges[-1][1]:
            ranges.append([offset, offset + 1])
        else:
            ranges[-1][1] = offset + 1
    selected = int.from_bytes(
        ram[TABLE + 4 * (index + 1) - BASE:TABLE + 4 * (index + 2) - BASE], "big"
    )
    return {
        "index_before": index,
        "index_after": int.from_bytes(after[INDEX - BASE:INDEX - BASE + 4], "big"),
        "bound": bound,
        "table_word": f"0x{selected:08x}",
        "return_r0": result,
        "expected": formula(selected, bound),
        "match": result == formula(selected, bound),
        "steps": cpu.steps,
        "instructions": [[f"0x{pc:08x}", f"0x{word:04x}", op, slot]
                         for pc, word, op, slot in cpu.instructions],
        "trace_sha256": sha(json.dumps(cpu.instructions, separators=(",", ":")).encode()),
        "writes": [[f"0x{address:08x}", size, f"0x{value:0{size * 2}x}"]
                   for address, size, value in memory.writes],
        "changed_ranges": [{"start": f"0x{BASE + start:08x}",
                            "end_exclusive": f"0x{BASE + end:08x}",
                            "bytes": end - start} for start, end in ranges],
        "mutation_opcode": None if mutation is None else f"0x{mutation:04x}",
    }


def run(kernel_path: Path, checkpoint_path: Path, interpreter_path: Path) -> dict:
    kernel = pinned.kernel_bytes(kernel_path)
    checkpoint, ram = read_checkpoint(checkpoint_path)
    index_checkpoint = int.from_bytes(ram[INDEX - BASE:INDEX - BASE + 4], "big")
    if index_checkpoint != 55:
        raise ValueError(f"Expected frame-1800 index 55, found {index_checkpoint}")
    for start, end in ((NEXT_ENTRY, 0x0600A0B4), (ENTRY, 0x0600A10C),
                       (0x0600A4B0, 0x0600A4F0)):
        if ram[start - BASE:end - BASE] != kernel[start - pinned.BASE:end - pinned.BASE]:
            raise ValueError(f"Inspected original helper is not resident at 0x{start:08x}")
    emu = pinned.interpreter(interpreter_path)
    cases = [execute(emu, ram, index, BOUND) for index in INDICES]
    control = execute(emu, ram, 54, BOUND, mutation=0x4009)
    control["expected_wrong_shift"] = ((((int(cases[-1]["table_word"], 16) & 0xFF) * BOUND) & 0xFFFFFFFF) >> 2) & 0xFF
    control["rejected"] = control["return_r0"] != formula(int(cases[-1]["table_word"], 16), BOUND)
    return {
        "schema": "neptune.original-kernel-rng-indices.v1",
        "original_game_bytes_executed": True,
        "kernel_sha256": sha(kernel),
        "kernel_mapping": "0x06006000",
        "source_ranges": [
            {"start": "0x0600A08C", "end_exclusive": "0x0600A0B4",
             "sha256": sha(kernel[0x0600A08C - pinned.BASE:0x0600A0B4 - pinned.BASE])},
            {"start": "0x0600A0EC", "end_exclusive": "0x0600A10C",
             "sha256": sha(kernel[0x0600A0EC - pinned.BASE:0x0600A10C - pinned.BASE])},
            {"start": "0x0600A4B0", "end_exclusive": "0x0600A4F0",
             "sha256": sha(kernel[0x0600A4B0 - pinned.BASE:0x0600A4F0 - pinned.BASE])},
        ],
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_frame": checkpoint["frame"],
        "checkpoint_state_sha256": checkpoint["state_sha256"],
        "index_checkpoint": index_checkpoint,
        "interpreter_revision": pinned.INTERPRETER_REVISION,
        "interpreter_sources": pinned.SOURCE_HASHES,
        "abi": {"entry": f"0x{ENTRY:08x}", "bound_r4": BOUND,
                "stack_r15": f"0x{STACK:08x}", "index_values_constructed": [0, 54]},
        "instruction_limit_per_call": LIMIT,
        "case_count": len(cases),
        "cases": cases,
        "negative_control": control,
        "limitations": [
            "each index is constructed independently; no natural call order",
            "one captured USA table state only; index 55 refresh is reported separately",
            "one bound per index; this does not recover the full RNG or seed recurrence",
            "interpreter execution is not independent hardware validation",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=DEFAULT_KERNEL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--saturn-recomp", type=Path, default=DEFAULT_INTERPRETER)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.kernel, args.checkpoint, args.saturn_recomp)
    raw = json.dumps(result, indent=2) + "\n"
    args.report.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.report.write_text(raw)
    print(json.dumps({"cases": result["case_count"], "all_match": all(c["match"] for c in result["cases"]),
                      "negative_control_rejected": result["negative_control"]["rejected"],
                      "report_sha256": sha(raw.encode())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
