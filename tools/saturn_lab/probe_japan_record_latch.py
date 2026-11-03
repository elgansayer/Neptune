#!/usr/bin/env python3
"""Execute the original Japanese kernel's bounded record latch helper."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

try:
    from . import probe_kernel as pinned
except ImportError:
    import probe_kernel as pinned

BASE = 0x0600A000
KERNEL_BYTES = 786432
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
ENTRY = 0x0600AACC
CODE_END = 0x0600AAEA
LITERAL = 0x0600AB2C
LITERAL_END = 0x0600AB30
RECORD_BASE = 0x060BCEEC
STRIDE = 88
RECORD_COUNT = 18
RECORD_BYTES = STRIDE * RECORD_COUNT
STACK_TOP = 0x060FFFF0
STACK_SLOT = STACK_TOP - 4
MAX_STEPS = 32


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_address(index: int) -> int:
    product = ((index & 0xFFFF) - (0x10000 if index & 0x8000 else 0)) * STRIDE
    low = product & 0xFFFF
    signed = low - 0x10000 if low & 0x8000 else low
    return (RECORD_BASE + signed) & 0xFFFFFFFF


def load_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_BYTES)
    if len(data) != KERNEL_BYTES or digest(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def execute(kernel: bytes, emu, index: int, active: bool,
            mutation: tuple[int, int] | None = None) -> dict:
    if type(index) is not int or not 0 <= index < RECORD_COUNT:
        raise ValueError("Record index must be in the explicit 0..17 table")
    code = bytearray(kernel[ENTRY - BASE:CODE_END - BASE])
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    if len(code) != CODE_END - ENTRY or len(literal) != 4:
        raise ValueError("Original code or literal range is incomplete")
    if mutation:
        address, opcode = mutation
        if not ENTRY <= address < CODE_END or address & 1:
            raise ValueError("Mutation address is outside the inspected instructions")
        offset = address - ENTRY
        code[offset:offset + 2] = opcode.to_bytes(2, "big")

    target = selected_address(index)
    initial = bytearray((0x31 + i * 17) & 0xFF for i in range(RECORD_BYTES))
    for n in range(RECORD_COUNT):
        start = n * STRIDE
        initial[start:start + 4] = (0xA0B00000 + n).to_bytes(4, "big")
        initial[start + 80] = 0
    initial[index * STRIDE + 80] = 1 if active else 0
    expected = bytearray(initial)
    if active:
        expected[index * STRIDE:index * STRIDE + 4] = (1).to_bytes(4, "big")

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.record_reads = []
            self.record_writes = []
            self.stack_reads = 0
            self.stack_writes = 0
            self.literal_reads = 0

        def read(self, address, size):
            address &= 0xFFFFFFFF
            if ENTRY <= address and address + size <= CODE_END:
                return super().read(address, size)
            if address == LITERAL and size == 4:
                self.literal_reads += 1
                return super().read(address, size)
            if RECORD_BASE <= address and address + size <= RECORD_BASE + RECORD_BYTES:
                if address != target + 80 or size != 1:
                    raise ValueError(f"Unexpected record read 0x{address:08x}/{size}")
                self.record_reads.append((address, size))
                return super().read(address, size)
            if address == STACK_SLOT and size == 4 and self.stack_writes == 1 and self.stack_reads == 0:
                self.stack_reads += 1
                return super().read(address, size)
            raise ValueError(f"Read outside original code/literal, selected flag, or exact stack slot: 0x{address:08x}/{size}")

        def write(self, address, size, value):
            address &= 0xFFFFFFFF
            if address == STACK_SLOT and size == 4 and self.stack_writes == 0:
                self.stack_writes += 1
                return super().write(address, size, value)
            if address == target and size == 4 and len(self.record_writes) == 0:
                self.record_writes.append((address, size, value & 0xFFFFFFFF))
                return super().write(address, size, value)
            raise ValueError(f"Write outside exact MACL spill or selected record word: 0x{address:08x}/{size}")

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.executed = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.executed) >= MAX_STEPS:
                raise RuntimeError("Original helper exceeded instruction bound")
            if not ENTRY <= pc < CODE_END or pc & 1:
                raise ValueError(f"PC escaped inspected instructions at 0x{pc:08x}")
            self.executed.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    memory = Memory()
    memory.add(ENTRY, len(code), code)
    memory.add(LITERAL, len(literal), literal)
    record = memory.add(RECORD_BASE, len(initial), initial)
    stack = memory.add(STACK_SLOT, 4, bytes.fromhex("a1b2c3d4"))
    cpu = CPU(memory)
    cpu.r = [(0xC3000000 + i * 0x101) & 0xFFFFFFFF for i in range(16)]
    cpu.r[15] = STACK_TOP
    cpu.macl = 0x76543210 ^ index
    cpu.sr = 0x3F0
    before_r = cpu.r.copy()
    before_macl, before_sr = cpu.macl, cpu.sr
    result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=index)
    expected_writes = [(target, 4, 1)] if active and mutation is None else []
    if mutation is None and bytes(record) != bytes(expected):
        raise ValueError("Record table differs from the bounded active/inactive contract")
    if (cpu.r[15] != STACK_TOP or cpu.r[4] != target or cpu.macl != before_macl or
            (cpu.sr & ~1) != (before_sr & ~1) or cpu.pr != emu.RETURN_SENTINEL):
        raise ValueError(f"Register, stack, MACL, SR, or return-sentinel contract mismatch: SP=0x{cpu.r[15]:08x}, R4=0x{cpu.r[4]:08x}, MACL=0x{cpu.macl:08x}, SR=0x{cpu.sr:08x}, PR=0x{cpu.pr:08x}")
    if any(cpu.r[i] != before_r[i] for i in range(16) if i not in (0, 2, 3, 4)):
        raise ValueError("Unexpected general-register clobber")
    if ((memory.stack_writes, memory.stack_reads, memory.literal_reads, len(memory.record_reads)) != (1, 1, 1, 1) or
            (memory.record_writes != expected_writes if mutation is None else len(memory.record_writes) > 1)):
        raise ValueError("Unexpected literal, record, or stack access")
    if bytes(stack) != before_macl.to_bytes(4, "big"):
        raise ValueError("Stack slot does not retain the exact MACL spill")
    return {"index": index, "active": active, "result": result,
            "instructions": len(cpu.executed), "executed_pcs": [f"0x{x:08x}" for x in cpu.executed],
            "record_reads": [[f"0x{a:08x}", n] for a, n in memory.record_reads],
            "record_writes": [[f"0x{a:08x}", n, f"0x{v:08x}"] for a, n, v in memory.record_writes],
            "record_sha256": digest(bytes(record)), "stack_slot_sha256": digest(bytes(stack))}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = load_kernel(kernel_path)
    emu = pinned.interpreter(source_root)
    rows = []
    for index in range(RECORD_COUNT):
        for active in (False, True):
            first = execute(kernel, emu, index, active)
            second = execute(kernel, emu, index, active)
            if first != second:
                raise ValueError("Repeated original helper execution differed")
            rows.append(first)
    controls = []
    for name, mutation, index, active in (
        ("inverted_active_branch", (0x0600AAE0, 0x8B01), 0, False),
        ("changed_latched_value", (0x0600AAE2, 0xE302), 1, True),
    ):
        altered = execute(kernel, emu, index, active, mutation)
        if altered["record_sha256"] == execute(kernel, emu, index, active)["record_sha256"]:
            raise ValueError(f"Mutation control failed to alter record for {name}")
        controls.append({"name": name, "changed_pc": f"0x{mutation[0]:08x}",
                         "replacement_opcode": f"0x{mutation[1]:04x}", "rejected": True})
    code = kernel[ENTRY - BASE:CODE_END - BASE]
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    return {"schema": "neptune.japan-kernel-record-latch.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": digest(Path(__file__).read_bytes()),
            "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "entry": f"0x{ENTRY:08x}", "code_range": [f"0x{ENTRY:08x}", f"0x{CODE_END:08x}"],
            "literal_range": [f"0x{LITERAL:08x}", f"0x{LITERAL_END:08x}"],
            "code_sha256": digest(code), "literal_sha256": digest(literal),
            "cases": len(rows), "calls_per_report": len(rows) * 2, "cases_per_index": 2,
            "mutation_controls": controls, "results": rows,
            "contract": "For each constructed record index 0..17, R4 becomes the selected record address; read only record+80; if nonzero, store longword 1 at record base; otherwise leave table unchanged. R0/R2/R3/R4 and the SR T bit may change. Preserve other SR bits and MACL through exact [SP-4] spill/RTS delay restore.",
            "limits": ["Constructed 18-record table, active flag, registers and one exact stack slot", "Pinned CPU interpreter; no natural caller, MMIO, BIOS, timing or gameplay"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-record-latch.v1", "status": "failure"}
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with args.report.open("x", encoding="utf-8") as out:
            try:
                report.update(run(args.kernel, args.saturn_recomp))
            except Exception as error:
                report["error"] = f"{type(error).__name__}: {error}"
            out.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        args.report.chmod(0o600)
    except OSError as error:
        print(f"FAIL: cannot create fresh report: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "cases": report.get("cases", 0),
                      "mutation_controls": len(report.get("mutation_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
