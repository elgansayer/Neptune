#!/usr/bin/env python3
"""Execute the original Japanese A6280 status-byte helper with a fenced ABI."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE = 0x0600A000
KERNEL_SIZE = 786432
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
ENTRY, END = 0x060A6280, 0x060A62B4
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
WORKRAM_BASE, WORKRAM_SIZE = 0x06000000, 0x100000
FLAG_BASE, FLAG_LITERAL, SR_MASK_LITERAL = 0x060FCD2C, 0x060A62C8, 0x060A62B6
OUT, STACK = 0x06008000, 0x06009000
LIMIT, STATE_MAX = 32, 16 * 1024 * 1024
INDEXES, SEEDS, PRIORITIES, FLAG_VALUES = (0, 1, 2), (0, 1), tuple(range(16)), tuple(range(256))
EXPECTED_SR_MASK_WORD = 0xFF0F


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def baseline_cases():
    return [(index, priority, seed) for index in INDEXES for priority in PRIORITIES for seed in SEEDS]


def flag_cases():
    return [(index, value) for index in INDEXES for value in FLAG_VALUES]


def execute(kernel, ram, emu, index, seed, priority, flag_value=None):
    if index not in INDEXES or seed not in SEEDS or priority not in PRIORITIES:
        raise ValueError("A6280 argument outside declared domain")
    if flag_value is not None and flag_value not in FLAG_VALUES:
        raise ValueError("A6280 flag value outside byte domain")
    if ram[ENTRY - WORKRAM_BASE:END - WORKRAM_BASE] != kernel[ENTRY - BASE:END - BASE]:
        raise ValueError("captured WorkRAM A6280 bytes differ from original Japan kernel")

    work = bytearray(ram)
    if flag_value is not None:
        work[FLAG_BASE + index - WORKRAM_BASE] = flag_value
    initial_flag = work[FLAG_BASE + index - WORKRAM_BASE]
    reads, writes = [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or not ENTRY <= address < END:
                    raise ValueError(f"fetch outside A6280 source fence: {address:08x}/{size}")
            elif address == SR_MASK_LITERAL and size == 2:
                value = super().read(address, size)
                reads.append(["sr-mask", address, size, value])
                return value
            elif address == FLAG_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["flag-base", address, size, value])
                return value
            elif address == FLAG_BASE + index and size == 1:
                value = super().read(address, size)
                reads.append(["flag-byte", address, size, value])
                return value
            else:
                raise ValueError(f"unexpected A6280 read: {address:08x}/{size}")
            return super().read(address, size)

        def write(self, address, size, value):
            if address != OUT or size != 4:
                raise ValueError(f"unexpected A6280 write: {address:08x}/{size}")
            writes.append([address, size, value & 0xFFFFFFFF])
            return super().write(address, size, value)

    mem = Memory()
    work_mem = mem.add(WORKRAM_BASE, WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def __init__(self, memory):
            super().__init__(memory)
            self.executed = []

        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < END:
                raise ValueError(f"A6280 PC/budget escaped: {pc:08x}")
            self.executed.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x44881223 + reg * 0x01020305 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[4] = OUT
    cpu.r[5] = index
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    initial_sr = cpu.sr
    work_mem[OUT - WORKRAM_BASE:OUT - WORKRAM_BASE + 4] = b"\xA5" * 4
    result = cpu.call(ENTRY, max_steps=LIMIT)

    output = int.from_bytes(work_mem[OUT - WORKRAM_BASE:OUT - WORKRAM_BASE + 4], "big")
    expected_reads = [
        ["sr-mask", SR_MASK_LITERAL, 2, EXPECTED_SR_MASK_WORD],
        ["flag-base", FLAG_LITERAL, 4, FLAG_BASE],
        ["flag-byte", FLAG_BASE + index, 1, initial_flag],
        ["sr-mask", SR_MASK_LITERAL, 2, EXPECTED_SR_MASK_WORD],
    ]
    if reads != expected_reads:
        raise ValueError(f"A6280 read sequence differs: {reads!r}")
    if writes != [[OUT, 4, initial_flag]] or output != initial_flag:
        raise ValueError(f"A6280 zero-extended status write differs: {writes!r}/{output:08x}")
    if cpu.r[4] != OUT or cpu.r[5] != FLAG_BASE + index:
        raise ValueError("A6280 input/output pointer register contract differs")
    if cpu.r[15] != STACK or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A6280 SP/PR return contract differs")
    if (cpu.sr & ~1) != (initial_sr & ~1):
        raise ValueError(f"A6280 non-T SR fields differ: {cpu.sr:08x}/{initial_sr:08x}")
    if cpu.steps != 26:
        raise ValueError(f"A6280 instruction count differs: {cpu.steps}")

    return {
        "index": index,
        "seed": seed,
        "priority": priority,
        "input_flag": initial_flag,
        "output_word": output,
        "result": result,
        "final_sr": cpu.sr,
        "final_r5": cpu.r[5],
        "reads": reads,
        "writes": writes,
        "steps": cpu.steps,
        "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in cpu.executed)),
    }


def run_pair(kernel, ram, emu, args):
    first = execute(kernel, ram, emu, *args)
    second = execute(kernel, ram, emu, *args)
    if first != second:
        raise ValueError(f"repeated A6280 execution differs for {args!r}")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {
        "schema": "neptune.original-japan-a6280-status-helper.v1",
        "status": "failure",
        "entry": hex(ENTRY),
        "range": [hex(ENTRY), hex(END)],
        "limits": ["Original A6280 bytes from frame-1200 WorkRAM-H, exact status/output accesses", "Constructed status-byte matrix; no caller or device behavior"],
    }
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                checkpoint = json.loads(args.checkpoint.read_text())
                identity = checkpoint.get("identity", {})
                if checkpoint.get("frame") != 1200 or identity.get("core_sha256") != CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, STATE_MAX)
                if sha(state) != STATE_SHA or checkpoint.get("state_sha256") != STATE_SHA:
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

                baseline = []
                for index, priority, seed in baseline_cases():
                    baseline.append(run_pair(kernel, ram, emu, (index, seed, priority)))
                byte_controls = []
                for index, value in flag_cases():
                    byte_controls.append(run_pair(kernel, ram, emu, (index, 0, 0, value)))
                    if byte_controls[-1]["output_word"] != value:
                        raise ValueError("A6280 flag-byte value control was not observed")

                result_data = {"baseline": baseline, "flag_byte_controls": byte_controls}
                report.update(
                    status="success",
                    original_game_bytes_executed=True,
                    captured_snapshot_data_used=True,
                    constructed_flag_byte_controls=True,
                    baseline_cases=len(baseline),
                    flag_byte_controls=len(byte_controls),
                    executions_per_case=2,
                    results=result_data,
                    results_sha256=sha(json.dumps(result_data, sort_keys=True, separators=(",", ":")).encode()),
                    baseline_output_values=sorted({row["output_word"] for row in baseline}),
                    flag_control_output_values=sorted({row["output_word"] for row in byte_controls}),
                    source_code_sha256=sha(kernel[ENTRY - BASE:END - BASE]),
                    probe_sha256=sha(Path(__file__).read_bytes()),
                    state_sha256=STATE_SHA,
                    normalized_workram_sha256=RAM_SHA,
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    contract="Original A6280 reads the selected frame-1200 status byte at 060FCD2C+index, zero-extends it to the caller output, and restores non-T SR fields. Baseline snapshot flags and a separate exhaustive constructed byte-value matrix are reported separately.",
                )
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: fresh report path required: {error}")
        return 1
    print(json.dumps({"status": report["status"], "baseline_cases": report.get("baseline_cases", 0), "flag_byte_controls": report.get("flag_byte_controls", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
