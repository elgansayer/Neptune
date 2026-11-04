#!/usr/bin/env python3
"""Execute the original Japanese kernel's bounded SH-2 context restore leaf."""
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
ENTRY = 0x0600A186
CODE_END = 0x0600A1AA
CONTEXT = 0x060D1000
CONTEXT_BYTES = 48
RETURN_SENTINEL = 0xFFFFFFF0
MAX_STEPS = 24
SAVED_GPR_OFFSETS = {8: 4, 9: 8, 10: 12, 11: 16, 12: 20, 13: 24, 14: 28, 15: 32}
SPECIAL_OFFSETS = {"pr": 36, "mach": 40, "macl": 44}
PATTERNS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF,
    0x01020304, 0x10203040, 0x55AA55AA, 0xAA55AA55, 0x13579BDF,
    0x2468ACE0, 0xDEADBEEF, 0xC001D00D, 0x0F0E0D0C, 0xF0E0D0C0,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_kernel(path: Path) -> bytes:
    data = pinned.read_bounded(path, KERNEL_BYTES)
    if len(data) != KERNEL_BYTES or digest(data) != KERNEL_SHA256:
        raise ValueError("Japanese T-14302G V1.000 kernel identity mismatch")
    return data


def context_words(seed: int) -> list[int]:
    values = []
    for i in range(12):
        value = (PATTERNS[(seed + i * 7) % len(PATTERNS)] ^ (seed * 0x01010101) ^ (i * 0x11111111)) & 0xFFFFFFFF
        values.append(value)
    values[9] = RETURN_SENTINEL
    return values


def execute(kernel: bytes, emu, seed: int,
            mutation: tuple[int, int] | None = None) -> dict:
    code = bytearray(kernel[ENTRY - BASE:CODE_END - BASE])
    if len(code) != CODE_END - ENTRY:
        raise ValueError("Original context-restore instruction range is incomplete")
    if mutation:
        address, opcode = mutation
        if not ENTRY <= address < CODE_END or address & 1:
            raise ValueError("Mutation is outside inspected context-restore instructions")
        offset = address - ENTRY
        code[offset:offset + 2] = opcode.to_bytes(2, "big")

    words = context_words(seed)
    raw = b"".join(value.to_bytes(4, "big") for value in words)
    reads = []

    class Memory(emu.Memory):
        def read(self, address, size):
            address &= 0xFFFFFFFF
            if ENTRY <= address and address + size <= CODE_END:
                return super().read(address, size)
            if CONTEXT <= address and address + size <= CONTEXT + CONTEXT_BYTES and size == 4:
                reads.append(address - CONTEXT)
                return super().read(address, size)
            raise ValueError(f"Read outside original restore code or exact 48-byte context: 0x{address:08x}/{size}")

        def write(self, address, size, value):
            raise ValueError(f"Context restore must not write memory: 0x{address & 0xffffffff:08x}/{size}")

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.executed = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.executed) >= MAX_STEPS:
                raise RuntimeError("Original context restore exceeded instruction limit")
            if not ENTRY <= pc < CODE_END or pc & 1:
                raise ValueError(f"PC escaped original restore code at 0x{pc:08x}")
            self.executed.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    memory = Memory()
    memory.add(ENTRY, len(code), code)
    context = memory.add(CONTEXT, CONTEXT_BYTES, raw)
    cpu = CPU(memory)
    cpu.r = [(0x91000000 + i * 0x01020305 + seed) & 0xFFFFFFFF for i in range(16)]
    cpu.r[4] = CONTEXT
    cpu.r[5] = (0xA5C30000 ^ seed) & 0xFFFFFFFF
    cpu.sr = 0x3F0
    before_r = cpu.r.copy()
    before_sr = cpu.sr
    result = cpu.call(ENTRY, max_steps=MAX_STEPS, r4=CONTEXT, r5=before_r[5])
    expected_reads = [4, 8, 12, 16, 20, 24, 28, 32, 44, 40, 36, 0]
    if mutation is None and reads != expected_reads:
        raise ValueError(f"Context fields were not read once in original order: {reads}")
    if mutation is None:
        expected = {
            0: before_r[5], 4: words[0],
            **{reg: words[off // 4] for reg, off in SAVED_GPR_OFFSETS.items()},
        }
        for reg, value in expected.items():
            if cpu.r[reg] != value:
                raise ValueError(f"r{reg} restore mismatch: 0x{cpu.r[reg]:08x} != 0x{value:08x}")
        for reg in (1, 2, 3, 5, 6, 7):
            if cpu.r[reg] != before_r[reg]:
                raise ValueError(f"Unexpected preserved-register change in r{reg}")
        if (cpu.pr, cpu.mach, cpu.macl) != (words[9], words[10], words[11]):
            raise ValueError("PR/MACH/MACL restore mismatch")
        if cpu.sr != before_sr or result != before_r[5] or bytes(context) != raw:
            raise ValueError("SR, return delay-slot result, or read-only context contract mismatch")
        if len(cpu.executed) != 18:
            raise ValueError(f"Expected 18 original instructions including RTS delay slot, got {len(cpu.executed)}")
    return {"seed": seed, "context_sha256": digest(raw), "result_r0": result,
            "final_gpr": [f"0x{v:08x}" for v in cpu.r], "final_pr": f"0x{cpu.pr:08x}",
            "final_mach": f"0x{cpu.mach:08x}", "final_macl": f"0x{cpu.macl:08x}",
            "context_read_offsets": reads,
            "instructions": len(cpu.executed), "executed_pcs": [f"0x{x:08x}" for x in cpu.executed],
            "context_unchanged": bytes(context) == raw}


def run(kernel_path: Path, source_root: Path) -> dict:
    kernel = load_kernel(kernel_path)
    emu = pinned.interpreter(source_root)
    results = []
    for seed in range(len(PATTERNS)):
        first = execute(kernel, emu, seed)
        second = execute(kernel, emu, seed)
        if first != second:
            raise ValueError(f"Repeated original context restore differed for seed {seed}")
        results.append(first)
    controls = []
    for name, mutation, seed in (
        ("wrong_saved_r8_offset", (ENTRY, 0x5842), 5),
        ("removed_return_delay_move", (0x0600A1A8, 0x0009), 7),
    ):
        altered = execute(kernel, emu, seed, mutation)
        reference = execute(kernel, emu, seed)
        if altered["final_gpr"] == reference["final_gpr"]:
            raise ValueError(f"Mutation control failed to detect {name}")
        controls.append({"name": name, "changed_pc": f"0x{mutation[0]:08x}",
                         "replacement_opcode": f"0x{mutation[1]:04x}", "rejected": True})
    code = kernel[ENTRY - BASE:CODE_END - BASE]
    return {"schema": "neptune.japan-kernel-context-restore.v1", "status": "success",
            "game": "Japan T-14302G V1.000", "kernel_sha256": KERNEL_SHA256,
            "probe_sha256": digest(Path(__file__).read_bytes()),
            "interpreter_revision": pinned.INTERPRETER_REVISION,
            "interpreter_sources": pinned.SOURCE_HASHES,
            "entry": f"0x{ENTRY:08x}", "code_range": [f"0x{ENTRY:08x}", f"0x{CODE_END:08x}"],
            "code_sha256": digest(code), "context_base": f"0x{CONTEXT:08x}",
            "context_bytes": CONTEXT_BYTES, "cases_per_report": len(results),
            "executions_per_case": 2, "mutation_controls": controls, "results": results,
            "contract": "Restore R8-R15, PR, MACH, MACL and R4 from the exact 48-byte context. R4 receives context word 0, then RTS delay slot replaces R0 with incoming R5. Preserve R1-R3 and R5-R7; perform no memory writes.",
            "limits": ["Constructed context words and incoming R5; PR is set to interpreter return sentinel", "Pinned SH-2 interpreter; no natural task caller, MMIO, BIOS, timing, or gameplay"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.japan-kernel-context-restore.v1", "status": "failure"}
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
                      "cases": report.get("cases_per_report", 0),
                      "mutation_controls": len(report.get("mutation_controls", []))}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
