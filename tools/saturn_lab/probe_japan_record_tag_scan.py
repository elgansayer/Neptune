#!/usr/bin/env python3
"""Execute original Japanese record-tag scan composed with its latch helper."""
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
SCAN_ENTRY = 0x0600AAEA
SCAN_END = 0x0600AB2A
LATCH_ENTRY = 0x0600AACC
LATCH_END = 0x0600AAEA
LITERAL = 0x0600AB2C
LITERAL_END = 0x0600AB30
RECORD_BASE = 0x060BCEEC
STRIDE = 88
COUNT = 18
RECORD_BYTES = STRIDE * COUNT
STACK_TOP = 0x060FFFF0
STACK_BASE = STACK_TOP - 28
MAX_STEPS = 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scenarios():
    out = []
    for index in range(COUNT):
        for active in (False, True):
            tags = [0xFE] * COUNT
            flags = [0] * COUNT
            tag = 20 + index
            tags[index] = tag
            flags[index] = int(active)
            out.append((f"single_{index}_{'active' if active else 'inactive'}", tag, tags, flags))
    out.append(("no_match", 0xFF, [0xFE] * COUNT, [int(i % 2 == 0) for i in range(COUNT)]))
    tags = [0xFE] * COUNT
    flags = [0] * COUNT
    for index, active in ((0, False), (7, True), (17, True)):
        tags[index] = 0x55
        flags[index] = int(active)
    out.append(("multiple_matches", 0x55, tags, flags))
    out.append(("all_matches", 0x22, [0x22] * COUNT, [int(i % 2 == 1) for i in range(COUNT)]))
    return out


def expected_table(tags, flags):
    data = bytearray((0x47 + i * 29) & 0xFF for i in range(RECORD_BYTES))
    for i in range(COUNT):
        start = i * STRIDE
        data[start:start + 4] = (0xC0100000 + i).to_bytes(4, "big")
        data[start + 80] = flags[i]
        data[start + 81] = tags[i]
    return data


def load_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_BYTES)
    if len(data) != KERNEL_BYTES or digest(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def execute(kernel: bytes, emu, tag: int, tags: list[int], flags: list[int],
            mutation: tuple[int, int] | None = None) -> dict:
    if type(tag) is not int or not 0 <= tag <= 0xFFFFFFFF:
        raise ValueError("Tag input must be an explicit 32-bit value")
    if (len(tags) != COUNT or len(flags) != COUNT or
            any(type(v) is not int or not 0 <= v <= 255 for v in tags + flags)):
        raise ValueError("Constructed table must contain exactly 18 byte tags and flags")
    scan = bytearray(kernel[SCAN_ENTRY - BASE:SCAN_END - BASE])
    latch = bytearray(kernel[LATCH_ENTRY - BASE:LATCH_END - BASE])
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    if len(scan) != SCAN_END - SCAN_ENTRY or len(latch) != LATCH_END - LATCH_ENTRY or len(literal) != 4:
        raise ValueError("Original scan/latch bytes or literal are incomplete")
    if mutation:
        address, opcode = mutation
        if SCAN_ENTRY <= address < SCAN_END and not address & 1:
            start = address - SCAN_ENTRY
            scan[start:start + 2] = opcode.to_bytes(2, "big")
        elif LATCH_ENTRY <= address < LATCH_END and not address & 1:
            start = address - LATCH_ENTRY
            latch[start:start + 2] = opcode.to_bytes(2, "big")
        else:
            raise ValueError("Mutation address lies outside inspected instructions")

    initial = expected_table(tags, flags)
    expected = bytearray(initial)
    matched = [i for i, value in enumerate(tags) if value == tag]
    for i in matched:
        expected[i * STRIDE + 81] = 0
        if flags[i] != 0:
            expected[i * STRIDE:i * STRIDE + 4] = (1).to_bytes(4, "big")

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.record_reads = []
            self.record_writes = []
            self.stack_reads = []
            self.stack_writes = []
            self.literal_reads = 0

        def read(self, address, size):
            address &= 0xFFFFFFFF
            if ((SCAN_ENTRY <= address and address + size <= SCAN_END) or
                    (LATCH_ENTRY <= address and address + size <= LATCH_END)):
                return super().read(address, size)
            if address == LITERAL and size == 4:
                self.literal_reads += 1
                return super().read(address, size)
            if RECORD_BASE <= address and address + size <= RECORD_BASE + RECORD_BYTES:
                offset = (address - RECORD_BASE) % STRIDE
                if size != 1 or offset not in (80, 81):
                    raise ValueError(f"Unexpected record read 0x{address:08x}/{size}")
                self.record_reads.append((address, size))
                return super().read(address, size)
            if STACK_BASE <= address and address + size <= STACK_TOP and size == 4 and address % 4 == 0:
                self.stack_reads.append((address, size))
                return super().read(address, size)
            raise ValueError(f"Read outside original code/literal, record fields, or exact stack: 0x{address:08x}/{size}")

        def write(self, address, size, value):
            address &= 0xFFFFFFFF
            if STACK_BASE <= address and address + size <= STACK_TOP and size == 4 and address % 4 == 0:
                self.stack_writes.append((address, size, value & 0xFFFFFFFF))
                return super().write(address, size, value)
            if RECORD_BASE <= address and address + size <= RECORD_BASE + RECORD_BYTES:
                offset = (address - RECORD_BASE) % STRIDE
                if not ((offset == 81 and size == 1) or (offset == 0 and size == 4)):
                    raise ValueError(f"Unexpected record write 0x{address:08x}/{size}")
                self.record_writes.append((address, size, value & 0xFFFFFFFF))
                return super().write(address, size, value)
            raise ValueError(f"Write outside record tag/active word or exact stack: 0x{address:08x}/{size}")

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.executed = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.executed) >= MAX_STEPS:
                raise RuntimeError("Original scan exceeded instruction bound")
            if not ((SCAN_ENTRY <= pc < SCAN_END) or (LATCH_ENTRY <= pc < LATCH_END)) or pc & 1:
                raise ValueError(f"PC escaped original scan/latch code at 0x{pc:08x}")
            self.executed.append(pc)
            target = super().exec(instruction, pc, in_slot=in_slot)
            return target

    memory = Memory()
    memory.add(SCAN_ENTRY, len(scan), scan)
    memory.add(LATCH_ENTRY, len(latch), latch)
    memory.add(LITERAL, len(literal), literal)
    record = memory.add(RECORD_BASE, len(initial), initial)
    stack = memory.add(STACK_BASE, STACK_TOP - STACK_BASE, bytes.fromhex("a1b2c3d4" * 7))
    cpu = CPU(memory)
    cpu.r = [(0xD1000000 + i * 0x111) & 0xFFFFFFFF for i in range(16)]
    cpu.r[15] = STACK_TOP
    cpu.r[4] = tag
    cpu.macl = 0x2468ACE0 ^ tag
    cpu.sr = 0x3F0
    before_r = cpu.r.copy()
    before_macl, before_sr = cpu.macl, cpu.sr
    result = cpu.call(SCAN_ENTRY, max_steps=MAX_STEPS, r4=tag)

    if mutation is None and bytes(record) != bytes(expected):
        mismatch = next(i for i, (left, right) in enumerate(zip(record, expected)) if left != right)
        raise ValueError(f"Original scan/latch table mismatch at offset 0x{mismatch:x}: got 0x{record[mismatch]:02x}, expected 0x{expected[mismatch]:02x}")
    if (cpu.r[15] != STACK_TOP or cpu.macl != before_macl or
            (cpu.sr & ~1) != (before_sr & ~1) or cpu.pr != emu.RETURN_SENTINEL):
        raise ValueError("SP, MACL, non-T SR, or return-sentinel contract mismatch")
    if any(cpu.r[i] != before_r[i] for i in range(16) if i not in (0, 2, 3, 4)):
        raise ValueError("Unexpected caller-saved/callee-saved register modification")
    nested_calls = sum(1 for _, size, _ in memory.record_writes if size == 1)
    if memory.literal_reads != 1 + nested_calls:
        raise ValueError("Original helper literal-read count differs from scan plus matched latch calls")
    read_tags = [a for a, n in memory.record_reads if (a - RECORD_BASE) % STRIDE == 81]
    if mutation is None and read_tags != [RECORD_BASE + i * STRIDE + 81 for i in range(COUNT)]:
        raise ValueError("Original scan did not read all 18 tag bytes once in order")
    if mutation is None:
        read_flags = [a for a, n in memory.record_reads if (a - RECORD_BASE) % STRIDE == 80]
        expected_flags = [RECORD_BASE + i * STRIDE + 80 for i in matched]
        if read_flags != expected_flags:
            raise ValueError("Nested latch helper did not read exactly the matched records' activity bytes")
        expected_writes = []
        for i in matched:
            expected_writes.append((RECORD_BASE + i * STRIDE + 81, 1, 0))
            if flags[i]:
                expected_writes.append((RECORD_BASE + i * STRIDE, 4, 1))
        if memory.record_writes != expected_writes:
            raise ValueError("Original record writes differ from matched tag and active latch contract")

    matches = len(matched)
    nested_calls = sum(1 for _, size, _ in memory.record_writes if size == 1)
    loop_count = cpu.executed.count(0x0600AB00)
    if mutation is None and loop_count != COUNT:
        raise ValueError(f"Original scan executed {loop_count} loop iterations instead of {COUNT}")
    expected_stack_writes = 6 + nested_calls
    expected_stack_reads = loop_count + 5 + nested_calls
    if len(memory.stack_writes) != expected_stack_writes or len(memory.stack_reads) != expected_stack_reads:
        raise ValueError(f"Unexpected bounded stack traffic: reads={len(memory.stack_reads)}/{expected_stack_reads}, writes={len(memory.stack_writes)}/{expected_stack_writes}, matches={matches}, nested_calls={nested_calls}, loop_heads={loop_count}")
    stack_words = {address: int.from_bytes(stack[address - STACK_BASE:address - STACK_BASE + 4], "big")
                   for address in range(STACK_BASE, STACK_TOP, 4)}
    for offset, reg in ((4, 14), (8, 13), (12, 12), (16, 11)):
        if stack_words[STACK_TOP - offset] != before_r[reg]:
            raise ValueError(f"Stacked r{reg} value was not retained")
    if stack_words[STACK_TOP - 20] != emu.RETURN_SENTINEL or stack_words[STACK_TOP - 24] != tag:
        raise ValueError("Original PR or scan tag stack word differs")
    if nested_calls and stack_words[STACK_TOP - 28] != before_macl:
        raise ValueError("Nested latch did not restore the exact MACL spill")
    if not nested_calls and bytes(stack[0:4]) != bytes.fromhex("a1b2c3d4"):
        raise ValueError("No-match path unexpectedly touched nested MACL spill slot")
    return {"tag": tag, "scenario_matches": matched, "loop_iterations": loop_count, "returned_r0": result,
            "instructions": len(cpu.executed), "executed_pcs": [f"0x{x:08x}" for x in cpu.executed],
            "record_reads": [[f"0x{a:08x}", n] for a, n in memory.record_reads],
            "record_writes": [[f"0x{a:08x}", n, f"0x{v:08x}"] for a, n, v in memory.record_writes],
            "record_sha256": digest(bytes(record)), "stack_sha256": digest(bytes(stack)),
            "stack_reads": len(memory.stack_reads), "stack_writes": len(memory.stack_writes)}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = load_kernel(kernel_path)
    emu = pinned.interpreter(source_root)
    results = []
    inputs = scenarios()
    for name, tag, tags, flags in inputs:
        first = execute(kernel, emu, tag, tags, flags)
        second = execute(kernel, emu, tag, tags, flags)
        if first != second:
            raise ValueError(f"Repeated original scan execution differed for {name}")
        results.append({"name": name, **first})
    controls = []
    control_cases = (
        ("inverted_tag_branch", (0x0600AB0A, 0x8903), inputs[-3]),
        ("skip_late_slot", (0x0600AB14, 0x7E02), inputs[34]),
    )
    for name, mutation, (scenario, tag, tags, flags) in control_cases:
        altered = execute(kernel, emu, tag, tags, flags, mutation)
        reference = execute(kernel, emu, tag, tags, flags)
        if altered["record_sha256"] == reference["record_sha256"]:
            raise ValueError(f"Mutation control failed to detect {name} scenario={scenario}, altered_writes={altered['record_writes']}, reference_writes={reference['record_writes']}")
        controls.append({"name": name, "changed_pc": f"0x{mutation[0]:08x}",
                         "replacement_opcode": f"0x{mutation[1]:04x}", "scenario": scenario,
                         "rejected": True})
    scan = kernel[SCAN_ENTRY - BASE:SCAN_END - BASE]
    latch = kernel[LATCH_ENTRY - BASE:LATCH_END - BASE]
    literal = kernel[LITERAL - BASE:LITERAL_END - BASE]
    return {"schema": "neptune.japan-kernel-record-tag-scan.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": digest(Path(__file__).read_bytes()),
            "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "scan_entry": f"0x{SCAN_ENTRY:08x}", "scan_range": [f"0x{SCAN_ENTRY:08x}", f"0x{SCAN_END:08x}"],
            "latch_entry": f"0x{LATCH_ENTRY:08x}", "latch_range": [f"0x{LATCH_ENTRY:08x}", f"0x{LATCH_END:08x}"],
            "literal_range": [f"0x{LITERAL:08x}", f"0x{LITERAL_END:08x}"],
            "scan_sha256": digest(scan), "latch_sha256": digest(latch), "literal_sha256": digest(literal),
            "unique_scenarios": len(results), "calls_per_report": len(results) * 2,
            "mutation_controls": controls, "results": results,
            "contract": "Scan 18 constructed records for byte tag r4; each match clears byte +81 to zero and calls original AACC with its table index, which sets the first longword to 1 only when byte +80 is nonzero. Preserve r11-r15, non-T SR bits, MACL, and exact stack saves.",
            "limits": ["Constructed 18-record table and stack; input tags are bounded scenarios, not all 32-bit values", "Pinned SH-2 interpreter; no natural caller, MMIO, BIOS, timing, or gameplay"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-record-tag-scan.v1", "status": "failure"}
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
                      "scenarios": report.get("unique_scenarios", 0),
                      "mutation_controls": len(report.get("mutation_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
