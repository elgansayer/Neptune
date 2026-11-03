#!/usr/bin/env python3
"""Compose the original A714E status branch with its A6280 byte helper."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE, KERNEL_SIZE = 0x0600A000, 786432
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
WORKRAM_BASE, WORKRAM_SIZE = 0x06000000, 0x100000
A6280, A6280_END = 0x060A6280, 0x060A62B4
A714E, A714E_END = 0x060A714E, 0x060A7178
FUNCTION_LITERAL, GLOBAL_LITERAL = 0x060A7210, 0x060A7200
FLAG_BASE, FLAG_LITERAL, SR_MASK_LITERAL = 0x060FCD2C, 0x060A62C8, 0x060A62B6
GLOBAL_WORD = 0x060FB588
STACK = 0x06008000
LIMIT, STATE_MAX = 64, 16 * 1024 * 1024
FLAGS, PRIORITIES, SEEDS = (0, 1, 2, 255), tuple(range(16)), (0, 1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(flag, priority, seed) for flag in FLAGS for priority in PRIORITIES for seed in SEEDS]


def allowed_pc(pc):
    return A6280 <= pc < A6280_END or A714E <= pc < A714E_END


def execute(kernel, ram, emu, flag, priority, seed):
    if flag not in FLAGS or priority not in PRIORITIES or seed not in SEEDS:
        raise ValueError("A714E flag/priority/seed outside declared domain")
    for entry, end in ((A6280, A6280_END), (A714E, A714E_END)):
        if ram[entry - WORKRAM_BASE:end - WORKRAM_BASE] != kernel[entry - BASE:end - BASE]:
            raise ValueError(f"captured source range differs from original kernel at {entry:08x}")
    if int.from_bytes(ram[FUNCTION_LITERAL - WORKRAM_BASE:FUNCTION_LITERAL - WORKRAM_BASE + 4], "big") != A6280:
        raise ValueError("captured A714E helper pointer differs")
    if int.from_bytes(ram[GLOBAL_LITERAL - WORKRAM_BASE:GLOBAL_LITERAL - WORKRAM_BASE + 4], "big") != GLOBAL_WORD:
        raise ValueError("captured A714E global pointer differs")

    work = bytearray(ram)
    work[FLAG_BASE - WORKRAM_BASE] = flag
    before_global = int.from_bytes(work[GLOBAL_WORD - WORKRAM_BASE:GLOBAL_WORD - WORKRAM_BASE + 4], "big")
    reads, writes, executed = [], [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or not allowed_pc(address):
                    raise ValueError(f"fetch outside A714E/A6280 composition: {address:08x}/{size}")
            elif address == FUNCTION_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["helper-pointer", address, size, value])
                return value
            elif address == GLOBAL_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["global-pointer", address, size, value])
                return value
            elif address == SR_MASK_LITERAL and size == 2:
                value = super().read(address, size)
                reads.append(["sr-mask", address, size, value])
                return value
            elif address == FLAG_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["flag-base", address, size, value])
                return value
            elif address == FLAG_BASE and size == 1:
                value = super().read(address, size)
                reads.append(["flag-byte", address, size, value])
                return value
            elif address == STACK - 8 and size == 4:
                value = super().read(address, size)
                reads.append(["status-slot", address, size, value])
                return value
            elif address == STACK - 4 and size == 4:
                value = super().read(address, size)
                reads.append(["saved-pr", address, size, value])
                return value
            else:
                raise ValueError(f"unexpected A714E/A6280 read: {address:08x}/{size}")
            return super().read(address, size)

        def write(self, address, size, value):
            if address in (STACK - 8, STACK - 4) and size == 4:
                writes.append(["stack", address, size, value & 0xFFFFFFFF])
                return super().write(address, size, value)
            if address == GLOBAL_WORD and size == 4:
                writes.append(["global", address, size, value & 0xFFFFFFFF])
                return super().write(address, size, value)
            raise ValueError(f"unexpected A714E/A6280 write: {address:08x}/{size}")

    mem = Memory()
    work_mem = mem.add(WORKRAM_BASE, WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not allowed_pc(pc):
                raise ValueError(f"A714E/A6280 PC/budget escaped: {pc:08x}")
            executed.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x41720031 + reg * 0x01020305 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    initial_sr = cpu.sr
    initial_registers = cpu.r.copy()
    result = cpu.call(A714E, max_steps=LIMIT)

    expected_reads = [["helper-pointer", FUNCTION_LITERAL, 4, A6280], ["sr-mask", SR_MASK_LITERAL, 2, 0xFF0F],
        ["flag-base", FLAG_LITERAL, 4, FLAG_BASE], ["flag-byte", FLAG_BASE, 1, flag],
        ["sr-mask", SR_MASK_LITERAL, 2, 0xFF0F], ["status-slot", STACK - 8, 4, flag]]
    if flag != 1:
        expected_reads.append(["global-pointer", GLOBAL_LITERAL, 4, GLOBAL_WORD])
    expected_reads.append(["saved-pr", STACK - 4, 4, emu.RETURN_SENTINEL])
    if reads != expected_reads:
        raise ValueError(f"A714E/A6280 read order differs: {reads!r}")

    expected_result = 1 if flag == 1 else 0
    expected_global = before_global if flag == 1 else 0
    actual_global = int.from_bytes(work_mem[GLOBAL_WORD - WORKRAM_BASE:GLOBAL_WORD - WORKRAM_BASE + 4], "big")
    expected_writes = [["stack", STACK - 4, 4, emu.RETURN_SENTINEL], ["stack", STACK - 8, 4, flag]]
    if flag != 1:
        expected_writes.append(["global", GLOBAL_WORD, 4, 0])
    if writes != expected_writes:
        raise ValueError(f"A714E/A6280 write set differs: {writes!r}")
    if result != expected_result or cpu.r[0] != expected_result:
        raise ValueError(f"A714E status result differs: {result}/{expected_result}")
    if actual_global != expected_global:
        raise ValueError(f"A714E global clear branch differs: {actual_global:08x}/{expected_global:08x}")
    if cpu.r[15] != STACK or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A714E SP/PR return contract differs")
    if (cpu.sr & ~1) != (initial_sr & ~1):
        raise ValueError("A714E/A6280 non-T SR fields differ")
    for reg in (1, 7, 8, 9, 10, 11, 12, 13, 14):
        if cpu.r[reg] != initial_registers[reg]:
            raise ValueError(f"A714E/A6280 preserved register r{reg} differs")

    return {"flag": flag, "priority": priority, "seed": seed, "result": result,
        "global_before": before_global, "global_after": actual_global, "reads": reads, "writes": writes,
        "steps": cpu.steps, "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in executed))}


def run_pair(kernel, ram, emu, values):
    a = execute(kernel, ram, emu, *values)
    b = execute(kernel, ram, emu, *values)
    if a != b:
        raise ValueError(f"repeated A714E/A6280 execution differs: {values!r}")
    return a


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a714e-status-dispatch.v1", "status": "failure",
        "ranges": [[hex(A714E), hex(A714E_END)], [hex(A6280), hex(A6280_END)]],
        "limits": ["Original A714E and A6280 bytes plus frame-1200 WorkRAM state", "Constructed status-byte values; no natural caller/runtime-PC proof"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                identity = metadata.get("identity", {})
                if metadata.get("frame") != 1200 or identity.get("core_sha256") != CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
                if sha(state) != STATE_SHA or metadata.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA:
                    raise ValueError("original Japan kernel identity mismatch")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = [run_pair(kernel, ram, emu, values) for values in corpus()]
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2, results=rows,
                    results_sha256=sha(data), source_a714e_sha256=sha(kernel[A714E - BASE:A714E_END - BASE]),
                    source_a6280_sha256=sha(kernel[A6280 - BASE:A6280_END - BASE]),
                    state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()), interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    contract="Original A714E calls original A6280 through its captured function-table pointer. The composed route returns 1 only when the selected status byte equals 1; other tested byte values clear 060FB588 and return 0. Values 0,1,2,255 are constructed inputs.")
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
