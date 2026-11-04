#!/usr/bin/env python3
"""Compose original A717C through A6112, then fence at the A5FC4 call."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as body
import probe_japan_a6112_chcr_contract as chcr

ENTRY, END = body.ENTRY, 0x060A71C0
CALLER_HELPER, NEXT_HELPER = 0x060A6112, 0x060A5FC4
CALLER_PCS = tuple(range(ENTRY, 0x060A71A4, 2)) + body.CONTROL_PCS
AFTER_CALL_PCS = tuple(range(0x060A71AA, END, 2))
EXPECTED_PCS = CALLER_PCS + chcr.EXPECTED_PCS + AFTER_CALL_PCS
STACK, BASES = body.STACK, body.BASES
CHCR_VALUES = (0, 1, 2, 3, 0xA5A4, 0xA5A5, 0xFFFE, 0xFFFF)
R7_VALUES = (0x11223344, 0x55667788)
STACK_TOPS = (0x01020304, 0xF1234567)
R6_VALUES = (0, 0x80000000)
PRIORITIES, SEEDS = body.PRIORITIES, body.SEEDS
LOCAL_WRITES = {STACK - 92, STACK - 88, STACK - 44, STACK - 40, STACK - 36,
    *range(STACK - 32, STACK, 4)}
STACK_READS = {STACK + 4, STACK, STACK - 92, STACK - 88, *range(STACK - 32, STACK, 4)}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(mode, chcr_value, r7, stack_top, r6, base, priority, seed)
        for mode in (0, 1) for chcr_value in CHCR_VALUES for r7 in R7_VALUES
        for stack_top in STACK_TOPS for r6 in R6_VALUES for base in BASES
        for priority in PRIORITIES for seed in SEEDS]


class PCFence(ValueError):
    pass


def execute(kernel, ram, emu, values):
    mode, chcr_value, r7, stack_top, r6, base, priority, seed = values
    if mode not in (0, 1) or chcr_value not in CHCR_VALUES or r7 not in R7_VALUES or stack_top not in STACK_TOPS or r6 not in R6_VALUES or base not in BASES or priority not in PRIORITIES or seed not in SEEDS:
        raise ValueError("A717C/A6112 input outside declared domain")
    work = bytearray(ram)
    work[STACK - body.WORKRAM_BASE:STACK - body.WORKRAM_BASE + 4] = stack_top.to_bytes(4, "big")
    work[STACK + 4 - body.WORKRAM_BASE:STACK + 8 - body.WORKRAM_BASE] = (4).to_bytes(4, "big")
    reads, writes, pcs = [], [], []
    register_address = chcr.CHCR[mode]
    register_value = chcr_value

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            nonlocal register_value
            if self.fetching:
                if size != 2 or address not in EXPECTED_PCS:
                    raise PCFence(f"A717C/A6112 PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address in (body.CALL_LITERAL, 0x060A7218, body.GLOBAL_LITERAL) and size == 4:
                value = super().read(address, size)
                reads.append(["literal", address, size, value])
                if address == body.CALL_LITERAL and value != CALLER_HELPER:
                    raise ValueError("A717C A6112 call pointer differs")
                if address == 0x060A7218 and value != NEXT_HELPER:
                    raise ValueError("A717C next helper pointer differs")
                if address == body.GLOBAL_LITERAL and value != body.GLOBAL_BASE:
                    raise ValueError("A717C global base pointer differs")
                return value
            if address == register_address and size == 4:
                reads.append(["CHCR", address, size, register_value])
                return register_value
            if address in STACK_READS and size == 4:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            raise ValueError(f"unexpected A717C/A6112 read: {address:08x}/{size}")

        def write(self, address, size, value):
            nonlocal register_value
            value &= 0xFFFFFFFF
            if address == register_address and size == 4:
                old = register_value
                if value & 0xFFFF0000:
                    raise ValueError("CHCR upper sixteen bits must remain zero")
                te = (old & chcr.CHCR_TE) if value & chcr.CHCR_TE else 0
                register_value = (value & ~chcr.CHCR_TE) | te
                writes.append(["CHCR", address, size, value, register_value])
                return
            if size == 4 and address in LOCAL_WRITES:
                writes.append(["stack", address, size, value])
                return super().write(address, size, value)
            raise ValueError(f"unexpected A717C/A6112 write: {address:08x}/{size}")

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
            if self.steps >= 96 or pc not in EXPECTED_PCS:
                raise PCFence(f"A717C/A6112 PC/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x12340000 + reg * 0x00010203 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[4], cpu.r[5], cpu.r[6], cpu.r[7] = mode, base, r6, r7
    cpu.r[15] = STACK
    cpu.sr = 0x30 | (priority << 4)
    try:
        cpu.call(ENTRY, max_steps=96)
    except PCFence as error:
        if "060a5fc4/2" not in str(error).lower():
            raise
    else:
        raise ValueError("A717C/A6112 did not stop at the unresolved A5FC4 target")
    if tuple(pcs) != EXPECTED_PCS:
        raise ValueError("A717C/A6112 exact PC sequence differs")
    if cpu.pc != NEXT_HELPER or cpu.steps != len(EXPECTED_PCS):
        raise ValueError(f"A717C/A6112 next call boundary differs: {cpu.pc:08x}/{cpu.steps}")
    if register_value != (chcr_value & ~chcr.CHCR_DE):
        raise ValueError("A6112 did not clear CHCR.DE")
    expected_local = {STACK - 92: r7, STACK - 88: 1,
        STACK - 44: 0, STACK - 40: 1, STACK - 36: 15}
    for address, expected in expected_local.items():
        actual = int.from_bytes(work_mem[address - body.WORKRAM_BASE:address - body.WORKRAM_BASE + 4], "big")
        if actual != expected:
            raise ValueError(f"A717C pre-A5FC4 stack contract differs at {address:08x}: {actual:08x}/{expected:08x}; SP={cpu.r[15]:08x}, R3={cpu.r[3]:08x}, writes={writes!r}")
    if len(writes) != 14 or len(reads) != 4:
        raise ValueError(f"A717C/A6112 event count differs: {len(reads)}/{len(writes)}")
    if cpu.r[15] != STACK - 92 or cpu.pr != 0x060A71C0 or cpu.r[4] != STACK - 44 or cpu.r[3] != NEXT_HELPER:
        raise ValueError("A717C/A6112 A5FC4 entry register contract differs")
    return {"mode": mode, "chcr_before": chcr_value, "chcr_after": register_value,
        "stack_argument": 4, "entry_r7": r7, "entry_r6": r6, "entry_r5": base,
        "next_helper": hex(NEXT_HELPER), "r3": cpu.r[3], "r4": cpu.r[4],
        "r15": cpu.r[15], "pr": cpu.pr, "reads": reads, "writes": writes,
        "steps": cpu.steps, "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs))}


def paired(kernel, ram, emu, values):
    first, second = execute(kernel, ram, emu, values), execute(kernel, ram, emu, values)
    if first != second:
        raise ValueError(f"paired A717C/A6112 executions differ: {values!r}")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-a6112-helper-boundary.v1", "status": "failure",
        "entry": hex(ENTRY), "next_helper": hex(NEXT_HELPER),
        "limits": ["Original A717C and A6112 through the A5FC4 call/delay-slot boundary",
            "CHCR register values are constructed; A5FC4, DMA transfer timing and natural reachability remain unresolved"]}
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
                for start, end in ((body.ENTRY, body.END), (CALLER_HELPER, chcr.END)):
                    if ram[start - body.WORKRAM_BASE:end - body.WORKRAM_BASE] != kernel[start - body.BASE:end - body.BASE]:
                        raise ValueError(f"original source bytes differ at {start:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = [paired(kernel, ram, emu, values) for values in corpus()]
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(data), probe_sha256=sha(Path(__file__).read_bytes()),
                    a717c_source_sha256=sha(kernel[body.ENTRY - body.BASE:body.END - body.BASE]),
                    a6112_source_sha256=sha(kernel[CALLER_HELPER - body.BASE:chcr.END - body.BASE]),
                    kernel_sha256=body.KERNEL_SHA, state_sha256=body.STATE_SHA,
                    normalized_workram_sha256=body.RAM_SHA,
                    interpreter_revision=pinned.INTERPRETER_REVISION,
            contract="For constructed A717C stack R12=4 and R4 mode 0/1, original A717C calls original A6112 at 060A71A6. Under the documented SH7604 CHCR contract, A6112 clears DE and returns. A717C then prepares its 16-byte helper argument block and calls A5FC4 at 060A71BC; its original 0009 delay slot is nop, and execution is fenced at 060A5FC4 after that slot.")
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
