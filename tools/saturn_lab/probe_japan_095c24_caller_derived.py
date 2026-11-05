#!/usr/bin/env python3
"""Probe original Japan KRNL 095C24 from captured F040 caller state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE = 0x06000000
KERNEL_BASE = 0x0600A000
ENTRY, END = 0x06095C24, 0x06095C8C
ENTRY_SP = 0x06001F24
STACK_LO, STACK_HI = 0x06001EE4, 0x06001F30
POINTER = 0x060FC5A0
SECOND_POINTER = 0x060FC560
MUTATION_PC, MUTATION_REPLACEMENT = 0x06095C7E, 0x0009
INSTRUCTION_LIMIT = 512
INPUT_WORDS = (0x00000000, 0x00000001, 0x80000000, 0xFFFFFFFF)
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA256 = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
WORKRAM_SHA256 = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CALLER_REPORT_SHA256 = "e1b3dde078c3fe20bbd23b850dbacdc44ba1c506f0e129c6765e6587d0cd3609"
CALLER_SLICE_SHA256 = "4d43fa36164881d49f7a766f9d71cb116edc4a02086e984171cffa9b4b6258e2"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def allowed_data(address: int, width: int) -> bool:
    if STACK_LO <= address and address + width <= STACK_HI:
        return True
    if 0x060FC560 <= address and address + width <= 0x060FC564:
        return True
    if POINTER <= address and address + width <= POINTER + 4:
        return True
    return False


def execute(kernel: bytes, ram: bytes, emu, run: dict, snapshot: dict,
            input_word: int, mutate: bool = False) -> dict:
    work = bytearray(ram)
    if mutate:
        offset = MUTATION_PC - KERNEL_BASE
        replacement = MUTATION_REPLACEMENT.to_bytes(2, "big")
        kernel = kernel[:offset] + replacement + kernel[offset + 2:]
        work[MUTATION_PC - BASE:MUTATION_PC - BASE + 2] = replacement
    work[POINTER - BASE:POINTER - BASE + 4] = input_word.to_bytes(4, "big")

    registers = [int(value, 16) for value in snapshot["registers"]]
    if registers[15] != ENTRY_SP:
        raise ValueError("captured caller stack pointer differs")
    reads: list[list[int]] = []
    writes: list[list[int]] = []
    pcs: list[int] = []

    class Memory(emu.Memory):
        fetching = False

        def read(self, address, width):
            if self.fetching:
                offset = address - KERNEL_BASE
                if width != 2 or not ENTRY <= address < END or address & 1:
                    raise ValueError(f"source fetch fence {address:08x}/{width}")
                if work[address - BASE:address - BASE + 2] != kernel[offset:offset + 2]:
                    raise ValueError(f"original code mismatch at {address:08x}")
            elif not allowed_data(address, width):
                raise ValueError(f"data read fence {address:08x}/{width}")
            value = super().read(address, width)
            reads.append([address, width, value])
            return value

        def write(self, address, width, value):
            if width not in (1, 2, 4) or not allowed_data(address, width):
                raise ValueError(f"data write fence {address:08x}/{width}")
            value &= (1 << (width * 8)) - 1
            writes.append([address, width, value])
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(BASE, len(work), work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if not ENTRY <= pc < END:
                raise ValueError(f"PC fence {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= INSTRUCTION_LIMIT:
                raise ValueError("instruction budget")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = registers
    cpu.pc = ENTRY
    cpu.pr = emu.RETURN_SENTINEL
    cpu.mach = int(snapshot["mach"], 16)
    cpu.macl = int(snapshot["macl"], 16)
    cpu.sr = int(run["sr"], 16)
    cpu.vbr = int(run["vbr"], 16)
    stack_before = bytes(work[STACK_LO - BASE:STACK_HI - BASE])
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()

    output_word = int.from_bytes(mapped[POINTER - BASE:POINTER - BASE + 4], "big")
    changed_registers = [index for index in range(15) if cpu.r[index] != registers[index]]
    return {"seed": run["seed"], "input_word": hex(input_word),
            "expected_word": hex(input_word | 0x80000000),
            "output_word": hex(output_word), "mutation": mutate,
            "steps": cpu.steps, "pcs": [hex(pc) for pc in pcs],
            "reads": reads, "writes": writes,
            "changed_gpr_indices_r0_to_r14": changed_registers,
            "sp_restored": cpu.r[15] == ENTRY_SP,
            "stack_window_restored": bytes(work[STACK_LO - BASE:STACK_HI - BASE]) == stack_before,
            "returned_to_sentinel": cpu.pc == emu.RETURN_SENTINEL,
            "buffer_words_after": {
                "060FC560": bytes(mapped[SECOND_POINTER - BASE:SECOND_POINTER - BASE + 4]).hex(),
                "060FC5A0": bytes(mapped[POINTER - BASE:POINTER - BASE + 4]).hex()}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--caller-report", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    report = {"schema": "neptune.original-japan-095c24-caller-derived.v1", "status": "failure"}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        print(f"FAIL: fresh private report path required: {error}")
        return 1

    with os.fdopen(fd, "w", encoding="utf-8") as output:
        try:
            kernel = pinned.read_bounded(args.kernel, 786432)
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            caller_bytes = pinned.read_bounded(args.caller_report, 4 * 1024 * 1024)
            metadata = json.loads(args.checkpoint.read_text())
            caller = json.loads(caller_bytes)
            if sha(kernel) != KERNEL_SHA256:
                raise ValueError("original Japan kernel identity differs")
            if (sha(state) != STATE_SHA256 or metadata.get("frame") != 1200 or
                    metadata.get("state_sha256") != STATE_SHA256):
                raise ValueError("frame-1200 state/checkpoint identity differs")
            if sha(caller_bytes) != CALLER_REPORT_SHA256:
                raise ValueError("F040 caller report identity differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", 0x100000), "little")
            if sha(ram) != WORKRAM_SHA256:
                raise ValueError("normalized WorkRAM-H identity differs")
            slice_bytes = bytes.fromhex(caller["results"][0]["snapshots"][0]["wram_060FC500_060FC700"])
            if (sha(slice_bytes) != CALLER_SLICE_SHA256 or
                    slice_bytes != ram[0xFC500:0xFC700]):
                raise ValueError("caller data slice differs from captured WorkRAM")

            emu = pinned.interpreter(args.saturn_recomp)
            results = []
            for word in INPUT_WORDS:
                for run in caller["results"]:
                    snapshot = next(item for item in run["snapshots"]
                                    if item["pc"] == hex(ENTRY))
                    results.append(execute(kernel, ram, emu, run, snapshot, word))

            mutation_run = caller["results"][0]
            mutation_snapshot = next(item for item in mutation_run["snapshots"]
                                     if item["pc"] == hex(ENTRY))
            mutant = execute(kernel, ram, emu, mutation_run, mutation_snapshot, 0, mutate=True)
            if mutant["output_word"] == mutant["expected_word"]:
                raise ValueError("removed result store survived comparator")
            if mutant["writes"] and any(row[0] == POINTER for row in mutant["writes"]):
                raise ValueError("removed result store still wrote target word")
            for row in results:
                if row["output_word"] != row["expected_word"]:
                    raise ValueError("original output differs from input with bit 31 set")
                if (row["steps"] != 220 or row["changed_gpr_indices_r0_to_r14"] or
                        not row["sp_restored"] or not row["stack_window_restored"] or
                        not row["returned_to_sentinel"]):
                    raise ValueError("return/register/stack contract differs")
                pointer_writes = [event for event in row["writes"]
                                  if event[0] == POINTER and event[1] == 4]
                if len(pointer_writes) != 1 or pointer_writes[0][2] != int(row["expected_word"], 16):
                    raise ValueError("expected one longword result store")

            report.update(
                status="success", release="Japan T-14302G V1.000", module="KRNL",
                entry=hex(ENTRY), end=hex(END), kernel_sha256=KERNEL_SHA256,
                state_sha256=STATE_SHA256, normalized_workram_sha256=WORKRAM_SHA256,
                caller_report_sha256=CALLER_REPORT_SHA256,
                caller_slice_sha256=CALLER_SLICE_SHA256,
                interpreter_revision=pinned.INTERPRETER_REVISION,
                interpreter_sources=pinned.SOURCE_HASHES,
                probe_sha256=sha(Path(__file__).read_bytes()),
                input_words=[hex(value) for value in INPUT_WORDS],
                instruction_limit=INSTRUCTION_LIMIT,
                contract=("Using GPRs captured at the original F040-path entry to 095C24 and captured "
                    "frame-1200 WorkRAM, the routine reads and writes one longword through R2, "
                    "setting bit 31. R0-R14 and SP are preserved; five stack longwords are restored; "
                    "the harness replaces PR with a return sentinel."),
                limitations=["Four constructed longword values, not exhaustive over 32-bit inputs",
                    "Caller GPRs are captured from a direct-entry F040 execution; this is not a natural game caller",
                    "No hardware timing, device service, gameplay, or full-program claim"],
                results=results,
                mutation_control={"pc": hex(MUTATION_PC), "original_word": "0x2252",
                    "replacement_word": "0x0009", "input_word": "0x00000000",
                    "expected_word": "0x80000000", "mutant_output": mutant["output_word"],
                    "rejected": True})
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", len(report.get("results", []))),
                      "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
