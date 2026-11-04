#!/usr/bin/env python3
"""Execute the original Japanese A7178 constant-return thunk."""
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
ENTRY, END = 0x060A7178, 0x060A717C
RETURN_IMMEDIATE = 0x060A717A
STACK, LIMIT, STATE_MAX = 0x06008000, 4, 16 * 1024 * 1024
PRIORITIES, SEEDS = tuple(range(16)), (0, 1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(priority, seed) for priority in PRIORITIES for seed in SEEDS]


def execute(kernel, ram, emu, priority, seed, mutation=None):
    if priority not in PRIORITIES or seed not in SEEDS:
        raise ValueError("A7178 priority/seed outside declared domain")
    original = ram[ENTRY - WORKRAM_BASE:END - WORKRAM_BASE]
    if original != kernel[ENTRY - BASE:END - BASE]:
        raise ValueError("captured A7178 bytes differ from original Japan kernel")
    work = bytearray(ram)
    if mutation is not None:
        address, replacement = mutation
        if address != RETURN_IMMEDIATE or replacement not in (0xE000, 0xE001):
            raise ValueError("unsupported A7178 instruction mutation")
        work[address - WORKRAM_BASE:address - WORKRAM_BASE + 2] = replacement.to_bytes(2, "big")
    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if not self.fetching or size != 2 or not ENTRY <= address < END:
                raise ValueError(f"unexpected A7178 data read: {address:08x}/{size}")
            reads.append([address, size])
            return super().read(address, size)

        def write(self, address, size, value):
            writes.append([address, size, value & 0xFFFFFFFF])
            raise ValueError(f"unexpected A7178 write: {address:08x}/{size}")

    mem = Memory()
    mem.add(WORKRAM_BASE, WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < END:
                raise ValueError(f"A7178 PC/budget escaped: {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x51930017 + reg * 0x01020305 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    initial = cpu.r.copy()
    initial_sr = cpu.sr
    result = cpu.call(ENTRY, max_steps=LIMIT)
    expected = 0 if mutation and mutation[1] == 0xE000 else 1
    if result != expected or cpu.r[0] != expected:
        raise ValueError(f"A7178 return differs: {result}/{expected}")
    if cpu.steps != 2 or reads != [[ENTRY, 2], [RETURN_IMMEDIATE, 2]]:
        raise ValueError(f"A7178 instruction/read sequence differs: {cpu.steps}/{reads!r}")
    if writes:
        raise ValueError("A7178 unexpectedly wrote memory")
    for reg in range(1, 16):
        if cpu.r[reg] != initial[reg]:
            raise ValueError(f"A7178 preserved GPR r{reg} changed")
    if cpu.r[15] != STACK or cpu.pr != emu.RETURN_SENTINEL or cpu.sr != initial_sr:
        raise ValueError("A7178 SP/PR/SR return contract differs")
    return {"priority": priority, "seed": seed, "result": result, "steps": cpu.steps,
        "reads": reads, "writes": writes, "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs))}


def run_pair(kernel, ram, emu, values, mutation=None):
    first = execute(kernel, ram, emu, *values, mutation=mutation)
    second = execute(kernel, ram, emu, *values, mutation=mutation)
    if first != second:
        raise ValueError(f"repeated A7178 execution differs: {values!r}")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a7178-return-thunk.v1", "status": "failure",
        "entry": hex(ENTRY), "range": [hex(ENTRY), hex(END)],
        "limits": ["Original two-instruction A7178 thunk from frame-1200 WorkRAM", "No caller/runtime-PC or gameplay claim"]}
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
                control = run_pair(kernel, ram, emu, (0, 0), mutation=(RETURN_IMMEDIATE, 0xE000))
                if control["result"] != 0:
                    raise ValueError("mutated A7178 return immediate was not observed")
                data = {"results": rows, "mutation_control": control}
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_code_bytes_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()),
                    mutation_control={"address": hex(RETURN_IMMEDIATE), "source_word": "0xE001",
                        "replacement_word": "0xE000", "observed_mutated_return": control["result"], "executions": 2},
                    source_code_sha256=sha(kernel[ENTRY - BASE:END - BASE]),
                    state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()), interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    contract="The original A7178 RTS delay slot loads constant 1 into R0. Across all 16 interrupt-priority values and two register seeds, the thunk returns 1 in two SH-2 instructions without other memory accesses. Replacing the original delay-slot immediate with zero changes the return to zero.")
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
