#!/usr/bin/env python3
"""Bounded original-byte execution of a Japanese kernel record-address helper.

The probe maps only the inspected instructions, the original literal, and a
four-byte MACL spill slot. It does not model callers, MMIO, BIOS, or gameplay.
"""
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
ENTRY = 0x0600AEF2
CODE_END = 0x0600AF04
LITERAL = 0x0600AF04
LITERAL_END = 0x0600AF08
RECORD_BASE = 0x060BCEEC
STRIDE = 88
STACK_TOP = 0x060FFFF0
STACK_SLOT = STACK_TOP - 4
MAX_STEPS = 32
CASES = tuple(range(19)) + (-65536, -32769, -32768, -1000, -19, -1, 255,
                            32767, 32768, 65535, 65536, 0x7FFFFFFF,
                            0x80000000, 0xFFFFFFFE, 0xFFFFFFFF)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def expected(index: int) -> int:
    product_low = (signed16(index) * STRIDE) & 0xFFFF
    return (RECORD_BASE + signed16(product_low)) & 0xFFFFFFFF


def load_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_BYTES)
    if len(data) != KERNEL_BYTES or digest(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def execute(kernel: bytes, emu, index: int, mutation: tuple[int, int] | None = None) -> dict:
    if type(index) is not int or not -(1 << 31) <= index < (1 << 32):
        raise ValueError("Index must be an explicit 32-bit constructed value")
    code = bytearray(kernel[ENTRY - BASE:CODE_END - BASE])
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    if len(code) != CODE_END - ENTRY or len(literal) != 4:
        raise ValueError("Original code or literal range is incomplete")
    if mutation:
        address, opcode = mutation
        if not ENTRY <= address < CODE_END or address & 1:
            raise ValueError("Mutation address lies outside inspected instructions")
        offset = address - ENTRY
        code[offset:offset + 2] = opcode.to_bytes(2, "big")

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.stack_reads = 0
            self.stack_writes = 0
            self.literal_reads = []

        def read(self, address, size):
            address &= 0xFFFFFFFF
            if ENTRY <= address and address + size <= CODE_END:
                return super().read(address, size)
            if address == LITERAL and size == 4:
                self.literal_reads.append((address, size))
                return super().read(address, size)
            if address == STACK_SLOT and size == 4 and self.stack_writes == 1 and self.stack_reads == 0:
                self.stack_reads += 1
                return super().read(address, size)
            raise ValueError(f"Read outside original code/literal or exact stack slot: 0x{address:08x}/{size}")

        def write(self, address, size, value):
            if address != STACK_SLOT or size != 4 or self.stack_writes:
                raise ValueError(f"Write outside exact MACL spill slot: 0x{address:08x}/{size}")
            self.stack_writes += 1
            return super().write(address, size, value)

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
    stack = memory.add(STACK_SLOT, 4, bytes.fromhex("a1b2c3d4"))
    cpu = CPU(memory)
    cpu.r = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(16)]
    cpu.r[15] = STACK_TOP
    cpu.r[4] = index & 0xFFFFFFFF
    cpu.macl = (0x13579BDF ^ index) & 0xFFFFFFFF
    cpu.sr = 0x3F0
    before_r = cpu.r.copy()
    before_macl, before_sr = cpu.macl, cpu.sr
    result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=index & 0xFFFFFFFF)
    if mutation is None and result != expected(index):
        raise ValueError(f"Return mismatch for index 0x{index & 0xFFFFFFFF:08x}: {result:08x} != {expected(index):08x}")
    if (cpu.r[15] != STACK_TOP or cpu.r[4] != before_r[4] or cpu.macl != before_macl or
            cpu.sr != before_sr or cpu.pr != emu.RETURN_SENTINEL):
        raise ValueError("Register, stack, MACL, SR, or return-sentinel contract mismatch")
    if any(cpu.r[i] != before_r[i] for i in range(16) if i not in (0, 3)):
        raise ValueError("Unexpected general-register clobber")
    if (memory.stack_writes, memory.stack_reads, len(memory.literal_reads)) != (1, 1, 1):
        raise ValueError("Unexpected literal or stack access count")
    if bytes(stack) != before_macl.to_bytes(4, "big"):
        raise ValueError("Stack slot does not retain the exact MACL spill")
    return {"index": index & 0xFFFFFFFF, "result": result, "instructions": len(cpu.executed),
            "executed_pcs": [f"0x{pc:08x}" for pc in cpu.executed],
            "clobbered_gprs": [f"r{i}" for i in range(16) if cpu.r[i] != before_r[i]],
            "stack_slot_sha256": digest(bytes(stack)), "stack_reads": memory.stack_reads,
            "stack_writes": memory.stack_writes, "literal_reads": len(memory.literal_reads)}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = load_kernel(kernel_path)
    emu = pinned.interpreter(source_root)
    code = kernel[ENTRY - BASE:CODE_END - BASE]
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    rows = []
    for index in CASES:
        first = execute(kernel, emu, index)
        second = execute(kernel, emu, index)
        if first != second:
            raise ValueError("Repeated original helper execution differed")
        rows.append(first)
    controls = []
    for name, mutation, value in (("changed_stride", (ENTRY, 0xE057), 2),
                                  ("byte_sign_extension", (0x0600AEFC, 0x600E), 2)):
        altered = execute(kernel, emu, value, mutation)
        if altered["result"] == expected(value):
            raise ValueError(f"Mutation control failed to change {name} result")
        controls.append({"name": name, "changed_pc": f"0x{mutation[0]:08x}",
                         "replacement_opcode": f"0x{mutation[1]:04x}",
                         "original_result": expected(value), "altered_result": altered["result"],
                         "rejected": True})
    return {"schema": "neptune.japan-kernel-record-address.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": digest(Path(__file__).read_bytes()),
            "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "entry": f"0x{ENTRY:08x}", "code_range": [f"0x{ENTRY:08x}", f"0x{CODE_END:08x}"],
            "literal_range": [f"0x{LITERAL:08x}", f"0x{LITERAL_END:08x}"],
            "code_sha256": digest(code), "literal_sha256": digest(literal),
            "contract": "r0 = 0x060BCEEC + sign16(low16(sign16(r4) * 88)); only r0/r3 are clobbered; MACL is spilled to [SP-4] and restored by RTS delay slot",
            "cases_repeated": len(rows), "cases": rows, "mutation_controls": controls,
            "limits": ["Constructed register values and one exact stack slot", "CPU interpreter only; no natural caller, MMIO, BIOS, timing, or gameplay", "Not exhaustive over all 32-bit indices or aliasing"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-record-address.v1", "status": "failure"}
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
                      "cases_repeated": report.get("cases_repeated", 0),
                      "mutation_controls": len(report.get("mutation_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
