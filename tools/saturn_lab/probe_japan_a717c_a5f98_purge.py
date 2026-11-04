#!/usr/bin/env python3
"""Execute the A717C A5F98 call and record original cache-purge requests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

CALLER_ENTRY, STOP = 0x060A723C, 0x060A7244
ENTRY, CODE_END = 0x060A5F98, 0x060A5FB4
LITERAL_START, LITERAL_END = 0x060A5FBC, 0x060A5FC4
STACK = 0x06007FA4
BASES = (0x06009000, 0x06009004)
SIZE = 4
CALLER_PCS = (0x060A723C, 0x060A723E, 0x060A7240, 0x060A7242)
HELPER_PCS = tuple(range(ENTRY, 0x060A5FB4, 2))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cases():
    return [(base, SIZE) for base in BASES]


def purge_line(base: int) -> int:
    return (((base & 0x1FFFFFFF) | 0x40000000) & 0xFFFFFFF0)


def execute(ram: bytes, emu, base: int, size: int):
    if (base, size) not in cases():
        raise ValueError("A5F98 caller inputs outside declared domain")
    reads, writes, pcs = [], [], []
    allowed = set(CALLER_PCS + HELPER_PCS)
    target = purge_line(base)
    end = ((base & 0x1FFFFFFF) | 0x40000000) + size

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in allowed:
                    raise ValueError(f"A5F98 PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address == 0x060A7360 and width == 4:
                value = super().read(address, width)
                if value != ENTRY:
                    raise ValueError(f"A717C A5F98 pointer differs: {value:08x}")
                reads.append(["caller-literal", address, width, value])
                return value
            if address in (0x060A5FBC, 0x060A5FC0) and width == 4:
                value = super().read(address, width)
                expected = 0x1FFFFFFF if address == 0x060A5FBC else 0x40000000
                if value != expected:
                    raise ValueError(f"A5F98 literal differs at {address:08x}: {value:08x}")
                reads.append(["helper-literal", address, width, value])
                return value
            raise ValueError(f"unexpected A5F98 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if not (0x40000000 <= address < 0x48000000 and width == 4 and value == 0):
                raise ValueError(f"unexpected non-purge A5F98 write {address:08x}/{width}/{value:08x}")
            if address & 0xF:
                raise ValueError(f"A5F98 purge request is not line-aligned: {address:08x}")
            writes.append(["CACHE_PURGE_REQUEST", address, width, value])
            # The interpreter's Memory is not the SH7604 cache. Log the CPU request;
            # intentionally do not treat the associative-purge space as writable RAM.

    mem = Memory()
    mem.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, ram)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 64 or pc not in allowed:
                raise ValueError(f"A5F98 instruction budget/PC fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x28640000 + i * 0x00010203) & 0xFFFFFFFF for i in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[5] = 0xDEADBEEF, 0x06009004, SIZE
    cpu.r[10], cpu.r[12] = base, SIZE
    cpu.r[15], cpu.pr, cpu.pc = STACK, CALLER_ENTRY, CALLER_ENTRY
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 64:
            raise ValueError("A5F98 instruction budget exceeded")
    expected_pcs = CALLER_PCS + HELPER_PCS
    if tuple(pcs) != expected_pcs:
        raise ValueError(f"A5F98 original PC path differs: {pcs!r}/{expected_pcs!r}")
    if cpu.steps != len(expected_pcs) or len(writes) != 1:
        raise ValueError("A5F98 call/loop event count differs")
    expected_end = ((base & 0x1FFFFFFF) | 0x40000000) + size
    if end != expected_end or writes != [["CACHE_PURGE_REQUEST", target, 4, 0]]:
        raise ValueError("A5F98 cache-purge request does not match source address arithmetic")
    if cpu.pc != STOP or cpu.pr != STOP or cpu.r[15] != STACK:
        raise ValueError("A5F98 did not return to the original A717C post-call boundary")
    if cpu.r[4] != target + 16 or cpu.r[5] != expected_end:
        raise ValueError("A5F98 loop end registers differ")
    return {"input_base": base, "size": size, "purge_line": target,
        "end_address": expected_end, "reads": reads, "writes": writes,
        "pc_trace": [hex(pc) for pc in pcs], "steps": cpu.steps,
        "stop_pc": hex(cpu.pc), "r4_after": cpu.r[4], "r5_after": cpu.r[5]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-a5f98-purge-request.v1",
        "status": "failure", "entry": hex(CALLER_ENTRY), "helper": hex(ENTRY),
        "stop": hex(STOP), "limits": [
            "Original A717C call site through A5F98 RTS/delay slot",
            "Associative-purge stores are recorded as CPU requests only; cache invalidation is not simulated"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                meta = json.loads(args.checkpoint.read_text())
                if meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != source.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if sha(state) != source.STATE_SHA or meta.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, source.KERNEL_SIZE)
                if len(kernel) != source.KERNEL_SIZE or sha(kernel) != source.KERNEL_SHA:
                    raise ValueError("original Japanese kernel identity mismatch")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", source.WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                ranges = ((CALLER_ENTRY, STOP), (ENTRY, CODE_END),
                    (LITERAL_START, LITERAL_END))
                for start, finish in ranges:
                    if ram[start-source.WORKRAM_BASE:finish-source.WORKRAM_BASE] != kernel[start-source.BASE:finish-source.BASE]:
                        raise ValueError(f"captured/original source bytes differ at {start:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for base, size in cases():
                    first = execute(ram, emu, base, size)
                    second = execute(ram, emu, base, size)
                    if first != second:
                        raise ValueError(f"paired A5F98 executions differ: {base:08x}/{size}")
                    rows.append(first)
                result = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(result), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    caller_source_sha256=sha(kernel[CALLER_ENTRY-source.BASE:STOP-source.BASE]),
                    helper_source_sha256=sha(kernel[ENTRY-source.BASE:CODE_END-source.BASE]),
                    helper_literal_sha256=sha(kernel[LITERAL_START-source.BASE:LITERAL_END-source.BASE]),
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="Original A717C passes R10 as purge target and R12=4 as size. Original A5F98 emits a longword zero store in associative-purge space at the aligned 16-byte line and returns to 0x060A7244. This report records the CPU request; actual cache invalidation is unmodeled.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: fresh report path required: {error}")
        return 1
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
