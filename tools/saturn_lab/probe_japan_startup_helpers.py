#!/usr/bin/env python3
"""Bounded CPU-only execution of two Japanese resident-kernel buffer helpers.

This tests original bytes at 0x0600A58E and 0x0600A5A2 with explicit WorkRAM
buffers. It does not model MMIO, BIOS calls, natural callers, or gameplay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

try:
    from . import probe_kernel as pinned
except ImportError:  # direct script execution from the documented CLI
    import probe_kernel as pinned

BASE = 0x0600A000
KERNEL_BYTES = 786432
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
ENTRY_FILL = 0x0600A58E
ENTRY_COPY = 0x0600A5A2
END_COPY = 0x0600A5B8
CODE_START, CODE_END = ENTRY_FILL, END_COPY
DEST = 0x060DD000
SOURCE = 0x060DE000
BUFFER_BYTES = 256
LIMIT = 512
LENGTHS = (-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 17, 30, 31, 32, 63, 64, 65, 126, 127, 128, 129)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word_count(length: int) -> int:
    """Observed loop count candidate: signed positive lengths round up by 2."""
    return (length + 1) // 2 if length > 0 else 0


def japan_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_BYTES)
    if len(data) != KERNEL_BYTES or sha(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def execute(emu, code: bytes, kind: str, length: int, mutation: tuple[int, int] | None = None) -> dict:
    entry = ENTRY_FILL if kind == "fill" else ENTRY_COPY
    if kind not in ("fill", "copy") or length not in LENGTHS:
        raise ValueError("Unsupported helper or constructed length")
    count = word_count(length)
    dest = bytearray((i * 29 + 7) & 0xFF for i in range(BUFFER_BYTES))
    source = bytearray((i * 43 + 0x91) & 0xFF for i in range(BUFFER_BYTES))
    initial_dest, initial_source = bytes(dest), bytes(source)

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.writes = []
            self.reads = []

        def read(self, address, size):
            address &= 0xFFFFFFFF
            if not (CODE_START <= address and address + size <= CODE_END or
                    kind == "copy" and SOURCE <= address and address + size <= SOURCE + BUFFER_BYTES):
                raise ValueError(f"Unexpected read outside original code/source: 0x{address:08x}/{size}")
            self.reads.append((address, size))
            return super().read(address, size)

        def write(self, address, size, value):
            address &= 0xFFFFFFFF
            if not (DEST <= address and address + size <= DEST + BUFFER_BYTES):
                raise ValueError(f"Unexpected write outside explicit destination: 0x{address:08x}/{size}")
            self.writes.append((address, size, value & ((1 << (8 * size)) - 1)))
            return super().write(address, size, value)

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.trace = []

        def fetch(self, pc):
            if not CODE_START <= pc < CODE_END:
                raise ValueError(f"Original instruction escaped inspected helpers at 0x{pc:08x}")
            ins = super().fetch(pc)
            self.trace.append((pc, ins.word, ins.op))
            return ins

    memory = Memory()
    original_code = bytearray(code)
    if mutation:
        pc, opcode = mutation
        if not CODE_START <= pc < CODE_END:
            raise ValueError("Mutation PC outside inspected original helper ranges")
        offset = pc - CODE_START
        original_code[offset:offset + 2] = opcode.to_bytes(2, "big")
    memory.add(CODE_START, CODE_END - CODE_START, original_code)
    dest_view = memory.add(DEST, BUFFER_BYTES, dest)
    source_view = memory.add(SOURCE, BUFFER_BYTES, source)
    memory.log = []
    cpu = CPU(memory)
    cpu.r = [0xA5A50000 + i for i in range(16)]
    cpu.r[15] = 0x060FFFF0
    cpu.r[4], cpu.r[5], cpu.r[6] = DEST, (0x13579BDF if kind == "fill" else SOURCE), length & 0xFFFFFFFF
    before_registers = cpu.r.copy()
    result = cpu.call(entry, max_steps=LIMIT)
    out_dest, out_source = bytes(dest_view), bytes(source_view)
    expected = bytearray(initial_dest)
    if kind == "fill":
        for i in range(count):
            expected[2 * i:2 * i + 2] = (0x9BDF).to_bytes(2, "big")
    else:
        for i in range(count):
            expected[2 * i:2 * i + 2] = initial_source[2 * i:2 * i + 2]
    if out_dest != bytes(expected):
        raise ValueError("Destination bytes differ from bounded word-loop contract")
    if out_source != initial_source:
        raise ValueError("Copy helper changed its read-only source buffer")
    expected_r5 = 0x13579BDF if kind == "fill" else SOURCE + 2 * count
    expected_r3 = before_registers[3]
    expected_r7 = 2 * count if length > 0 else 0
    if kind == "copy" and count:
        expected_r3 = int.from_bytes(initial_source[2 * (count - 1):2 * count], "big", signed=True) & 0xFFFFFFFF
    if (cpu.r[4] != DEST + 2 * count or cpu.r[6] != before_registers[6] or
            cpu.r[5] != expected_r5 or cpu.r[3] != expected_r3 or
            cpu.r[7] != expected_r7 or
            cpu.t != (1 if length > 0 else 0) or cpu.r[15] != before_registers[15] or
            cpu.pr != emu.RETURN_SENTINEL):
        raise ValueError(f"Register/return mismatch for {kind}/{length}: "
                         f"r3={cpu.r[3]:08x}/{expected_r3:08x} r4={cpu.r[4]:08x}/{DEST + 2 * count:08x} "
                         f"r5={cpu.r[5]:08x}/{expected_r5:08x} r6={cpu.r[6]:08x}/{before_registers[6]:08x} "
                         f"r7={cpu.r[7]:08x}/{expected_r7:08x} "
                         f"T={cpu.t}/{(1 if length > 0 else 0)} SP={cpu.r[15]:08x}/{before_registers[15]:08x} "
                         f"PR={cpu.pr:08x}/{emu.RETURN_SENTINEL:08x}")
    allowed_clobbers = {4, 7} if kind == "fill" else {3, 4, 5, 7}
    if any(cpu.r[i] != before_registers[i] for i in range(16) if i not in allowed_clobbers):
        raise ValueError("Unlisted general register was clobbered")
    expected_write_count = count
    if len(memory.writes) != expected_write_count:
        raise ValueError("Unexpected number of original destination writes")
    if any(addr != DEST + 2 * i or size != 2 for i, (addr, size, _) in enumerate(memory.writes)):
        raise ValueError("Original write address/width sequence differs")
    return {"helper": kind, "entry": f"0x{entry:08x}", "length": length,
            "words_written": count, "return_r0": f"0x{result:08x}",
            "r4_after": f"0x{cpu.r[4]:08x}", "r5_after": f"0x{cpu.r[5]:08x}",
            "steps": cpu.steps, "instruction_trace_sha256": sha(json.dumps(cpu.trace, separators=(",", ":")).encode()),
            "read_count": len(memory.reads), "write_count": len(memory.writes),
            "destination_sha256": sha(out_dest), "source_sha256_before": sha(initial_source),
            "source_sha256_after": sha(out_source), "untouched_destination_equal": out_dest == bytes(expected)}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = japan_kernel(kernel_path)
    code = kernel[CODE_START - BASE:CODE_END - BASE]
    if len(code) != CODE_END - CODE_START:
        raise ValueError("Inspected source range is incomplete")
    emu = pinned.interpreter(source_root)
    results = []
    for kind in ("fill", "copy"):
        for length in LENGTHS:
            first = execute(emu, code, kind, length)
            second = execute(emu, code, kind, length)
            if first != second:
                raise ValueError("Repeated original helper execution differed")
            results.append(first)
    controls = []
    for kind, length, pc, opcode in (("fill", 7, 0x0600A594, 0x2452),
                                     ("copy", 7, 0x0600A5A8, 0x6354)):
        try:
            execute(emu, code, kind, length, (pc, opcode))
        except (ValueError, RuntimeError):
            controls.append({"helper": kind, "changed_pc": f"0x{pc:08x}",
                             "replacement_opcode": f"0x{opcode:04x}", "rejected": True})
        else:
            raise ValueError("Changed original instruction escaped semantic rejection")
    return {"schema": "neptune.japan-kernel-memory-helpers.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": sha(Path(__file__).read_bytes()),
            "kernel_base": f"0x{BASE:08x}", "source_range": [f"0x{CODE_START:08x}", f"0x{CODE_END:08x}"],
            "source_range_sha256": sha(code), "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "scope": "two isolated original-byte buffer helpers; two repeated runs per constructed length",
            "limitations": ["Constructed inputs and explicit WorkRAM buffers, not a natural caller",
                            "No MMIO, BIOS, hardware timing, overlays or gameplay validation",
                            "Not exhaustive for all lengths or aliased/overlapping buffers"],
            "lengths": list(LENGTHS), "repeated_cases": len(results), "results": results,
            "wrong_opcode_controls": controls}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--saturn-recomp", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-memory-helpers.v1", "status": "failure"}
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with args.report.open("x", encoding="utf-8") as output:
            try:
                report.update(run(args.kernel, args.saturn_recomp))
            except Exception as error:
                report["error"] = f"{type(error).__name__}: {error}"
            output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
            output.flush()
        args.report.chmod(0o600)
    except OSError as error:
        print(f"FAIL: cannot create fresh report: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "repeated_cases": report.get("repeated_cases", 0),
                      "wrong_opcode_controls": len(report.get("wrong_opcode_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
