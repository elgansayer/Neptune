#!/usr/bin/env python3
"""Execute the original A72B0 -> A717C zero-shift caller path."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as body

CALLER, CALLEE, END = 0x060A72B0, body.ENTRY, 0x060A72D8
STACK = body.STACK
CALLER_PCS = tuple(range(CALLER, END, 2))
EXPECTED_PCS = CALLER_PCS[:16] + body.EXPECTED_PCS + CALLER_PCS[16:]
CALLER_R4_VALUES = (0x06009000, 0x06009004)
SEEDS = (0, 1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(argument, initial_r4, r5, r6, r7, stack6, priority, seed)
        for argument in body.STACK_R12_VALUES for initial_r4 in CALLER_R4_VALUES
        for r5 in body.R7_VALUES for r6 in body.R7_VALUES
        for r7 in body.STACK_TOP_VALUES for stack6 in body.STACK_TOP_VALUES
        for priority in body.PRIORITIES for seed in SEEDS]


class PCFence(ValueError):
    pass


def execute(kernel, ram, emu, values):
    argument, initial_r4, r5, r6, r7, stack6, priority, seed = values
    if argument not in body.STACK_R12_VALUES or initial_r4 not in CALLER_R4_VALUES:
        raise ValueError("A72B0 caller input outside declared domain")
    work = bytearray(ram)
    work[STACK - body.WORKRAM_BASE:STACK - body.WORKRAM_BASE + 4] = argument.to_bytes(4, "big")
    work[STACK + 4 - body.WORKRAM_BASE:STACK + 8 - body.WORKRAM_BASE] = stack6.to_bytes(4, "big")
    reads, writes, pcs = [], [], []
    inner_entry_sp = STACK - 28
    stack_read_range = set(range(inner_entry_sp - 32, STACK + 8, 4)) | {STACK - 120, STACK - 116}
    stack_write_range = set(range(STACK - 120, STACK - 3, 4))

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or address not in EXPECTED_PCS:
                    raise PCFence(f"A72B0 caller PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address == body.GLOBAL_LITERAL and size == 4:
                value = super().read(address, size)
                reads.append(["global-base", address, size, value])
                return value
            if size == 4 and address in stack_read_range:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            raise ValueError(f"unexpected composed caller read: {address:08x}/{size}")

        def write(self, address, size, value):
            if size == 4 and address in stack_write_range:
                kind = "stack"
            elif size == 4 and address in body.GLOBAL_WRITES:
                kind = "global"
            else:
                raise ValueError(f"unexpected composed caller write: {address:08x}/{size}")
            writes.append([kind, address, size, value & 0xffffffff])
            return super().write(address, size, value)

    mem = Memory()
    work_mem = mem.add(body.WORKRAM_BASE, body.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 160 or pc not in EXPECTED_PCS:
                raise PCFence(f"A72B0 caller PC/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x12340000 + reg * 0x00010203 + seed * 0x00010001) & 0xffffffff for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[4], cpu.r[5], cpu.r[6], cpu.r[7] = initial_r4, r5, r6, r7
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    result = cpu.call(CALLER, max_steps=160)
    words = tuple(int.from_bytes(work_mem[body.GLOBAL_BASE - body.WORKRAM_BASE + offset:
        body.GLOBAL_BASE - body.WORKRAM_BASE + offset + 4], "big") for offset in (0, 4, 8))
    if words != (argument & 3, r6, 0):
        raise ValueError(f"A72B0/A717C output words differ: {words!r}")
    if result != 92 or cpu.r[0] != 92 or cpu.r[15] != STACK or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A72B0/A717C return, SP or PR differs")
    if tuple(pcs) != EXPECTED_PCS:
        raise ValueError("A72B0/A717C executed PC sequence differs")
    if len(writes) != 20 or len(reads) != 18:
        raise ValueError(f"A72B0/A717C memory event counts differ: {len(reads)}/{len(writes)}")
    if cpu.steps != len(EXPECTED_PCS):
        raise ValueError("A72B0/A717C instruction count differs")
    return {"stack_argument": argument, "caller_initial_r4": initial_r4, "caller_r5": r5,
        "caller_r6_to_callee_r7": r6, "caller_r7": r7, "stack_argument6": stack6,
        "priority": priority, "seed": seed, "result": result, "global_words": list(words),
        "reads": reads, "writes": writes, "steps": cpu.steps,
        "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs))}


def paired(kernel, ram, emu, values):
    first, second = execute(kernel, ram, emu, values), execute(kernel, ram, emu, values)
    if first != second:
        raise ValueError(f"paired A72B0/A717C executions differ: {values!r}")
    return first


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-caller-zero-divisor.v1",
        "status": "failure", "caller": hex(CALLER), "callee": hex(CALLEE),
        "limits": ["Original A72B0 call and A717C zero-shift path only", "A6112 and other A717C helpers remain unresolved"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                identity = metadata.get("identity", {})
                if metadata.get("frame") != 1200 or identity.get("core_sha256") != body.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, body.STATE_MAX)
                if sha(state) != body.STATE_SHA or metadata.get("state_sha256") != body.STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, body.KERNEL_SIZE)
                if len(kernel) != body.KERNEL_SIZE or sha(kernel) != body.KERNEL_SHA:
                    raise ValueError("original Japan kernel identity mismatch")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", body.WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != body.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu = body.pinned.interpreter(args.saturn_recomp)
                rows = [paired(kernel, ram, emu, values) for values in corpus()]
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(data), probe_sha256=sha(Path(__file__).read_bytes()),
                    source_code_sha256=sha(kernel[CALLER - body.BASE:END - body.BASE]),
                    state_sha256=body.STATE_SHA, normalized_workram_sha256=body.RAM_SHA,
                    interpreter_revision=body.pinned.INTERPRETER_REVISION,
                    contract="Original A72B0 enters A717C via BSR at 060A72CC; the fifth caller stack argument 0..3 drives the zero-shift branch. A72B0 sets R4 to zero before saving and passes caller R6 as callee R7. The composed path returns 0x5C and stores the argument, caller R6, and zero to 060FCD30..38. A6112 and all later helpers remain fenced/unexecuted.")
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
