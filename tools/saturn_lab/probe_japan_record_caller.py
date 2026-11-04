#!/usr/bin/env python3
"""Execute a bounded original call site to the Japan record-address helper.

This starts at an original caller continuation with a constructed incoming
index and saved return word. It maps the literal pools, callee bytes, caller
bytes, one record, and exact stack slots; it is not a natural runtime capture.
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
KERNEL_SIZE = 786432
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
CALLER_ENTRY, CALLER_END = 0x0600CC5C, 0x0600CC6C
CALLEE_ENTRY, CALLEE_END = 0x0600AEF2, 0x0600AF04
CALLER_TARGET_LITERAL = 0x0600CCA4
CALLBACK_LITERAL = 0x0600CCA8
CALLEE_BASE_LITERAL = 0x0600AF04
RECORD_BASE = 0x060BCEEC
RECORD_STRIDE = 88
RECORD_SIZE = 88
RECORD_CALLBACK_OFFSET = 12
CALLBACK = 0x0600CB96
STACK_TOP = 0x060FFFF0
STACK_BYTES = 8
MAX_STEPS = 40
INDICES = tuple(range(18))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_address(index: int) -> int:
    return RECORD_BASE + index * RECORD_STRIDE


def load_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_SIZE)
    if len(data) != KERNEL_SIZE or digest(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def execute(kernel: bytes, emu, index: int,
            mutation: tuple[int, int] | None = None) -> dict:
    if type(index) is not int or index not in INDICES:
        raise ValueError("Caller fixture only supports the 18 original record indices")
    caller = bytearray(kernel[CALLER_ENTRY - BASE:CALLER_END - BASE])
    callee = bytearray(kernel[CALLEE_ENTRY - BASE:CALLEE_END - BASE])
    literals = {
        CALLER_TARGET_LITERAL: kernel[CALLER_TARGET_LITERAL - BASE:CALLER_TARGET_LITERAL - BASE + 4],
        CALLBACK_LITERAL: kernel[CALLBACK_LITERAL - BASE:CALLBACK_LITERAL - BASE + 4],
        CALLEE_BASE_LITERAL: kernel[CALLEE_BASE_LITERAL - BASE:CALLEE_BASE_LITERAL - BASE + 4],
    }
    if len(caller) != CALLER_END - CALLER_ENTRY or len(callee) != CALLEE_END - CALLEE_ENTRY:
        raise ValueError("Original caller/callee byte range incomplete")
    if any(len(value) != 4 for value in literals.values()):
        raise ValueError("Original call-site literal incomplete")
    if mutation:
        address, opcode = mutation
        if address == CALLER_ENTRY + 4:  # delay slot that supplies r4 to the callee
            target, buf = address, caller
            start = CALLER_ENTRY
        elif address == CALLEE_ENTRY:
            target, buf = address, callee
            start = CALLEE_ENTRY
        elif address == CALLER_ENTRY + 14:  # RTS delay-slot record-field store
            target, buf = address, caller
            start = CALLER_ENTRY
        else:
            raise ValueError("Mutation address outside inspected caller/callee instructions")
        offset = target - start
        buf[offset:offset + 2] = opcode.to_bytes(2, "big")

    record_start = record_address(index)
    initial_record = bytes((i * 37 + index * 11 + 3) & 0xFF for i in range(RECORD_SIZE))
    caller_target = int.from_bytes(literals[CALLER_TARGET_LITERAL], "big")
    callback_target = int.from_bytes(literals[CALLBACK_LITERAL], "big")
    callee_data = int.from_bytes(literals[CALLEE_BASE_LITERAL], "big")
    if caller_target != CALLEE_ENTRY or callback_target != CALLBACK or callee_data != RECORD_BASE:
        raise ValueError("Original literal values disagree with inspected call graph")

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.stack_reads = []
            self.stack_writes = []
            self.record_writes = []
            self.literal_reads = []

        def read(self, address, size):
            address &= 0xFFFFFFFF
            if (CALLER_ENTRY <= address and address + size <= CALLER_END or
                    CALLEE_ENTRY <= address and address + size <= CALLEE_END):
                return super().read(address, size)
            if address in literals and size == 4:
                self.literal_reads.append((address, size))
                return super().read(address, size)
            if address == STACK_TOP - 4 and size == 4:
                if len(self.stack_reads) == 0 and len(self.stack_writes) == 1:
                    self.stack_reads.append((address, size))
                    return super().read(address, size)
            if address == STACK_TOP and size == 4 and len(self.stack_reads) == 1:
                self.stack_reads.append((address, size))
                return super().read(address, size)
            raise ValueError(f"Unexpected original caller read 0x{address:08x}/{size}")

        def write(self, address, size, value):
            if address == STACK_TOP - 4 and size == 4 and not self.stack_writes:
                self.stack_writes.append((address, size, value & 0xFFFFFFFF))
                return super().write(address, size, value)
            expected = record_start + RECORD_CALLBACK_OFFSET
            if address == expected and size == 4 and not self.record_writes:
                self.record_writes.append((address, size, value & 0xFFFFFFFF))
                return super().write(address, size, value)
            raise ValueError(f"Unexpected original caller write 0x{address:08x}/{size}")

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.executed = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.executed) >= MAX_STEPS:
                raise RuntimeError("Original caller/callee exceeded instruction bound")
            if not (CALLER_ENTRY <= pc < CALLER_END or CALLEE_ENTRY <= pc < CALLEE_END):
                raise ValueError(f"PC escaped exact original caller/callee ranges at 0x{pc:08x}")
            self.executed.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    memory = Memory()
    memory.add(CALLER_ENTRY, len(caller), caller)
    memory.add(CALLEE_ENTRY, len(callee), callee)
    for address, value in literals.items():
        memory.add(address, len(value), value)
    stack = memory.add(STACK_TOP - 4, STACK_BYTES, bytes(4) + emu.RETURN_SENTINEL.to_bytes(4, "big"))
    record = memory.add(record_start, RECORD_SIZE, initial_record)
    cpu = CPU(memory)
    cpu.r = [(0xA5A50000 + n * 0x101) & 0xFFFFFFFF for n in range(16)]
    cpu.r[15] = STACK_TOP
    cpu.r[0] = index  # constructed return value from the preceding, unvalidated A946 call
    cpu.r[1] = 0x13572468
    cpu.macl = (0x2468ACE0 ^ index) & 0xFFFFFFFF
    cpu.sr = 0x3F0
    before_r, before_macl, before_sr = cpu.r.copy(), cpu.macl, cpu.sr
    result = cpu.call(CALLER_ENTRY, max_steps=MAX_STEPS)

    expected_result = record_start
    expected_record = bytearray(initial_record)
    expected_record[RECORD_CALLBACK_OFFSET:RECORD_CALLBACK_OFFSET + 4] = CALLBACK.to_bytes(4, "big")
    if result != expected_result:
        raise ValueError(f"Caller return mismatch at index {index}: {result:08x} != {expected_result:08x}")
    if bytes(record) != bytes(expected_record):
        raise ValueError("Original RTS delay-slot callback store differs")
    if (cpu.r[15] != STACK_TOP + 4 or cpu.pr != emu.RETURN_SENTINEL or
            cpu.macl != before_macl or cpu.sr != before_sr):
        raise ValueError("Caller/callee return, MACL, SR, or stack contract mismatch")
    if any(cpu.r[n] != before_r[n] for n in range(16) if n not in (0, 2, 3, 4, 15)):
        raise ValueError("Unexpected caller/callee general-register clobber")
    if (len(memory.stack_writes) != 1 or len(memory.stack_reads) != 2 or
            len(memory.record_writes) != 1 or len(memory.literal_reads) != 3):
        raise ValueError("Original call-site stack/literal/write footprint mismatch")
    if memory.stack_writes[0][2] != before_macl or bytes(stack[:4]) != before_macl.to_bytes(4, "big"):
        raise ValueError("Callee did not preserve MACL through its exact stack spill")
    if memory.record_writes[0] != (record_start + 12, 4, CALLBACK):
        raise ValueError("Callback pointer was not stored by the original caller delay slot")
    return {"index": index, "record_address": f"0x{record_start:08x}",
            "helper_result": f"0x{result:08x}", "callback_store": f"0x{CALLBACK:08x}",
            "instructions": len(cpu.executed),
            "executed_pcs": [f"0x{pc:08x}" for pc in cpu.executed],
            "stack_writes": len(memory.stack_writes), "stack_reads": len(memory.stack_reads),
            "record_writes": len(memory.record_writes), "literal_reads": len(memory.literal_reads),
            "record_sha256_before": digest(initial_record), "record_sha256_after": digest(bytes(record))}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = load_kernel(kernel_path)
    emu = pinned.interpreter(source_root)
    rows = []
    for index in INDICES:
        first = execute(kernel, emu, index)
        second = execute(kernel, emu, index)
        if first != second:
            raise ValueError("Repeated original caller/callee execution differed")
        rows.append(first)
    controls = []
    for name, mutation in (("wrong_delay_slot_argument", (CALLER_ENTRY + 4, 0x6413)),
                           ("changed_callee_stride", (CALLEE_ENTRY, 0xE057)),
                           ("wrong_record_field_offset", (CALLER_ENTRY + 14, 0x1423))):
        try:
            execute(kernel, emu, 2, mutation)
        except (ValueError, RuntimeError) as error:
            controls.append({"name": name, "changed_pc": f"0x{mutation[0]:08x}",
                             "replacement_opcode": f"0x{mutation[1]:04x}",
                             "rejected": True, "reason": f"{type(error).__name__}: {error}"})
        else:
            raise ValueError(f"Mutated original caller/callee passed: {name}")
    return {"schema": "neptune.japan-kernel-record-address-caller.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": digest(Path(__file__).read_bytes()),
            "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "caller_entry": f"0x{CALLER_ENTRY:08x}",
            "caller_code_range": [f"0x{CALLER_ENTRY:08x}", f"0x{CALLER_END:08x}"],
            "callee_entry": f"0x{CALLEE_ENTRY:08x}",
            "callee_code_range": [f"0x{CALLEE_ENTRY:08x}", f"0x{CALLEE_END:08x}"],
            "literal_addresses": [f"0x{x:08x}" for x in (CALLER_TARGET_LITERAL, CALLBACK_LITERAL, CALLEE_BASE_LITERAL)],
            "caller_edge": "CC5C loads literal target AEF2; CC5E JSR; CC60 delay slot supplies prior R0 in R4; AEF2 returns computed record address; CC6A RTS delay slot stores literal callback CB96 at record+12",
            "cases_per_report": len(rows), "repetitions_per_case": 2, "cases": rows,
            "mutation_controls": controls,
            "limits": ["Incoming R0 is constructed as the unvalidated preceding A946 result", "Single explicit record and two-word stack mapping", "Pinned CPU interpreter only; no natural caller, BIOS/MMIO/device timing, or gameplay", "Only original instruction ranges stated above were executed"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-record-address-caller.v1", "status": "failure"}
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
                      "cases_per_report": report.get("cases_per_report", 0),
                      "mutation_controls": len(report.get("mutation_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
