#!/usr/bin/env python3
"""Execute the bounded A717C zero-shift route before unresolved helper calls."""
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
ENTRY, END = 0x060A717C, 0x060A727E
GLOBAL_LITERAL, GLOBAL_BASE = 0x060A7364, 0x060FCD30
CALL_LITERAL, CALL_TARGET = 0x060A7214, 0x060A6112
STACK, LIMIT, STATE_MAX = 0x06008000, 64, 16 * 1024 * 1024
STACK_R12_VALUES = (0, 1, 2, 3)
MODES, BASES = (0, 1), (0x06009000, 0x06009004)
R7_VALUES = (0x11223344, 0x55667788)
STACK_TOP_VALUES = (0x01020304, 0xF1234567)
PRIORITIES, SEEDS = tuple(range(16)), (0, 1)
PREFIX_PCS = tuple(range(ENTRY, 0x060A71A4, 2))
TAIL_PCS = tuple(range(0x060A7244, END, 2))
EXPECTED_PCS = PREFIX_PCS + TAIL_PCS
CONTROL_PCS = (0x060A71A4, 0x060A71A6, 0x060A71A8)
STACK_READS = {STACK + 4, STACK, STACK - 92, *range(STACK - 32, STACK, 4)}
STACK_WRITES = {*range(STACK - 32, STACK, 4), STACK - 92, STACK - 88}
GLOBAL_WRITES = {GLOBAL_BASE, GLOBAL_BASE + 4, GLOBAL_BASE + 8}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(arg, mode, base, r7, stack_top, priority, seed)
        for arg in STACK_R12_VALUES for mode in MODES for base in BASES for r7 in R7_VALUES
        for stack_top in STACK_TOP_VALUES for priority in PRIORITIES for seed in SEEDS]


class PCFence(ValueError):
    pass


def execute(kernel, ram, emu, arg, mode, base, r7, stack_top, priority, seed):
    if (arg not in (0, 1, 2, 3, 4) or mode not in MODES or base not in BASES or r7 not in R7_VALUES
            or stack_top not in STACK_TOP_VALUES or priority not in PRIORITIES or seed not in SEEDS):
        raise ValueError("A717C zero-shift input outside declared domain")
    if ram[ENTRY - WORKRAM_BASE:END - WORKRAM_BASE] != kernel[ENTRY - BASE:END - BASE]:
        raise ValueError("captured A717C source bytes differ from original Japan kernel")
    if int.from_bytes(ram[GLOBAL_LITERAL - WORKRAM_BASE:GLOBAL_LITERAL - WORKRAM_BASE + 4], "big") != GLOBAL_BASE:
        raise ValueError("captured A717C global-base literal differs")

    work = bytearray(ram)
    work[STACK - WORKRAM_BASE:STACK - WORKRAM_BASE + 4] = stack_top.to_bytes(4, "big")
    work[STACK + 4 - WORKRAM_BASE:STACK + 8 - WORKRAM_BASE] = arg.to_bytes(4, "big")
    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                allowed = EXPECTED_PCS + (CONTROL_PCS if arg == 4 else ())
                if size != 2 or address not in allowed:
                    raise PCFence(f"A717C PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address == GLOBAL_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["global-base", address, size, value])
                return value
            if arg == 4 and address == CALL_LITERAL and size == 4:
                value = super().read(address, size)
                if value != CALL_TARGET:
                    raise ValueError("captured A717C unresolved-call pointer differs")
                reads.append(["unresolved-call-pointer", address, size, value])
                return value
            if address in STACK_READS and size == 4:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            raise ValueError(f"unexpected A717C read: {address:08x}/{size}")

        def write(self, address, size, value):
            if size == 4 and address in STACK_WRITES:
                kind = "stack"
            elif size == 4 and address in GLOBAL_WRITES:
                kind = "global"
            else:
                raise ValueError(f"unexpected A717C write: {address:08x}/{size}")
            writes.append([kind, address, size, value & 0xFFFFFFFF])
            return super().write(address, size, value)

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
            allowed = EXPECTED_PCS + (CONTROL_PCS if arg == 4 else ())
            if self.steps >= LIMIT or pc not in allowed:
                raise PCFence(f"A717C PC/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x12340000 + reg * 0x00010203 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[1] = 0x2468ACE0 + seed
    cpu.r[4] = mode
    cpu.r[5] = base
    cpu.r[6] = 0x10102020 + seed
    cpu.r[7] = r7
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    initial = cpu.r.copy()
    initial_sr = cpu.sr
    initial_global = bytes(work_mem[GLOBAL_BASE - WORKRAM_BASE:GLOBAL_BASE - WORKRAM_BASE + 12])
    result = cpu.call(ENTRY, max_steps=LIMIT)

    expected_global_words = (arg & 3, r7, base)
    actual_global_words = tuple(int.from_bytes(work_mem[GLOBAL_BASE - WORKRAM_BASE + offset:
        GLOBAL_BASE - WORKRAM_BASE + offset + 4], "big") for offset in (0, 4, 8))
    if actual_global_words != expected_global_words:
        raise ValueError(f"A717C zero-shift global stores differ: {actual_global_words!r}/{expected_global_words!r}")
    if result != 92 or cpu.r[0] != 92:
        raise ValueError(f"A717C zero-shift return differs: {result}/{cpu.r[0]}")
    if tuple(pcs) != EXPECTED_PCS:
        mismatch = next((i for i, pair in enumerate(zip(pcs, EXPECTED_PCS)) if pair[0] != pair[1]), None)
        raise ValueError(f"A717C zero-shift executed PC sequence differs at {mismatch}: {pcs!r}")
    if len(writes) != 13 or cpu.steps != len(EXPECTED_PCS):
        raise ValueError(f"A717C exact write count differs: {len(writes)}")
    stack_expected = [["stack", address, 4, value] for address, value in zip(
        (STACK - 4, STACK - 8, STACK - 12, STACK - 16, STACK - 20, STACK - 24, STACK - 28, STACK - 32),
        (initial[14], initial[13], initial[12], initial[11], initial[10], initial[9], initial[8], emu.RETURN_SENTINEL))]
    stack_expected.append(["stack", STACK - 92, 4, initial[7]])
    stack_expected.append(["stack", STACK - 88, 4, arg >> 2])
    global_expected = [["global", GLOBAL_BASE, 4, arg & 3], ["global", GLOBAL_BASE + 8, 4, base],
        ["global", GLOBAL_BASE + 4, 4, r7]]
    if writes != stack_expected + global_expected:
        raise ValueError(f"A717C stack/global write order differs: {writes!r}")
    if cpu.r[15] != STACK or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A717C zero-shift SP/PR contract differs")
    for reg in (8, 9, 10, 11, 12, 13, 14):
        if cpu.r[reg] != initial[reg]:
            raise ValueError(f"A717C preserved register r{reg} differs")
    if cpu.r[4] != mode or cpu.r[5] != base or cpu.r[6] != initial[6] or cpu.r[7] != r7:
        raise ValueError("A717C caller register contract differs")
    if (cpu.sr & ~1) != (initial_sr & ~1) or cpu.sr & 1:
        raise ValueError(f"A717C SR contract differs: {cpu.sr:08x}/{initial_sr:08x}")
    expected_read_count = 12
    if len(reads) != expected_read_count:
        raise ValueError(f"A717C data-read count differs: {len(reads)}")

    return {"stack_r12": arg, "mode_r4": mode, "base_r5": base, "r7_value": r7,
        "stack_top": stack_top, "priority": priority, "seed": seed,
        "result": result, "global_words": list(actual_global_words), "reads": reads,
        "writes": writes, "steps": cpu.steps,
        "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
        "global_before_sha256": sha(initial_global)}


def run_pair(kernel, ram, emu, values):
    first = execute(kernel, ram, emu, *values)
    second = execute(kernel, ram, emu, *values)
    if first != second:
        raise ValueError(f"repeated A717C zero-shift execution differs: {values!r}")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-zero-divisor.v1", "status": "failure",
        "entry": hex(ENTRY), "code_range": [hex(ENTRY), hex(END)],
        "limits": ["Original A717C zero-shift route with exact stack/global accesses", "R12>>2 == 0 skips unresolved calls; no full A717C claim"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                identity = metadata.get("identity", {})
                if metadata.get("frame") != 1200 or identity.get("core_sha256") != CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, STATE_MAX)
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
                try:
                    execute(kernel, ram, emu, 4, MODES[0], BASES[0], R7_VALUES[0], STACK_TOP_VALUES[0], 0, 0)
                except PCFence as error:
                    if "060a6112" not in str(error).lower():
                        raise
                    call_escape_rejected = True
                else:
                    raise ValueError("A717C R12=4 did not leave zero-shift route at unresolved call")
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(data),
                    call_escape_control={"stack_r12":4,"call_site":"0x060A71A6","delay_slot":"0x060A71A8","unresolved_target":"0x060A6112","rejected_by_pc_fence":call_escape_rejected},
                    source_code_sha256=sha(kernel[ENTRY - BASE:END - BASE]),
                    state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()), interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    contract="For constructed stack R12 values 0..3, A717C computes R12>>2 == 0, skips unresolved calls, stores low two bits at 060FCD30, saved R7 at +4 and R5 at +8, then returns 0x5C. R12=4 reaches JSR at 060A71A6, whose captured pointer targets 060A6112; target execution is rejected by the PC fence.")
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
