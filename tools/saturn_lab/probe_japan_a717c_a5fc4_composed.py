#!/usr/bin/env python3
"""Compose original A717C -> A6112 -> A5FC4 through the real return edge."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as a717c
import probe_japan_a6112_chcr_contract as a6112
import probe_japan_a5fc4_dmaor as a5fc4

ENTRY = a717c.ENTRY
STOP = 0x060A71C0
CHCR_VALUES = (0, 1, 2, 3, 0xA5A4, 0xFFFF)
DMAOR_VALUES = (0, 1, 2, 3, 4, 6, 8, 9, 15)
MODES = (0, 1)
BASES = (0x06009000, 0x06009004)
R7_VALUES = (0x11223344, 0x55667788)
STACK_TOPS = (0, 0x01020304, 0xF1234567)
PRIORITIES = (0, 7, 15)
SEEDS = (0, 1)
R6_VALUES = (0, 1, 0xFFFFFFFF)
CALLER_PREFIX = tuple(range(ENTRY, 0x060A71A4, 2)) + (0x060A71A4, 0x060A71A6, 0x060A71A8)
CALLER_RESUME = tuple(range(0x060A71AA, STOP, 2))
DMAOR = a5fc4.DMAOR
LOCAL_WRITES = {0x06008000 - 92, 0x06008000 - 88, 0x06008000 - 44,
    0x06008000 - 40, 0x06008000 - 36, *range(0x06008000 - 32, 0x06008000, 4)}
STACK_READS = {0x06008000, 0x06008004, 0x06008000 - 92, 0x06008000 - 88,
    *range(0x06008000 - 32, 0x06008000, 4)}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(mode, chcr, dmaor, base, r7, top, priority, seed, r6)
        for mode in MODES for chcr in CHCR_VALUES for dmaor in DMAOR_VALUES
        for base in BASES for r7 in R7_VALUES for top in STACK_TOPS
        for priority in PRIORITIES for seed in SEEDS for r6 in R6_VALUES]


def expected_pcs():
    return CALLER_PREFIX + a6112.EXPECTED_PCS + CALLER_RESUME + a5fc4.expected_pcs(15)


def execute(kernel: bytes, ram: bytes, emu, values, mutation=None):
    mode, chcr_initial, dmaor_initial, base, r7, stack_top, priority, seed, r6 = values
    if mode not in MODES or chcr_initial not in CHCR_VALUES or dmaor_initial not in DMAOR_VALUES:
        raise ValueError("composed A717C input outside declared domain")
    if base not in BASES or r7 not in R7_VALUES or stack_top not in STACK_TOPS:
        raise ValueError("composed A717C caller state outside declared domain")
    if priority not in PRIORITIES or seed not in SEEDS:
        raise ValueError("composed A717C CPU state outside declared domain")
    if r6 not in R6_VALUES:
        raise ValueError("composed A717C R6 input outside declared domain")

    work = bytearray(ram)
    if mutation is not None:
        address, value = mutation
        if address != 0x060A71A6 or value not in (0x0009, 0x420B):
            raise ValueError("unsupported composed-call instruction mutation")
        work[address - a717c.WORKRAM_BASE:address - a717c.WORKRAM_BASE + 2] = value.to_bytes(2, "big")
    stack = a717c.STACK
    work[stack - a717c.WORKRAM_BASE:stack - a717c.WORKRAM_BASE + 4] = stack_top.to_bytes(4, "big")
    work[stack + 4 - a717c.WORKRAM_BASE:stack + 8 - a717c.WORKRAM_BASE] = (4).to_bytes(4, "big")
    reads, writes, pcs = [], [], []
    chcr_address = a6112.CHCR[mode]
    chcr_value, dmaor_value = chcr_initial, dmaor_initial
    a5fc4_pcs = a5fc4.expected_pcs(15)
    allowed = set(CALLER_PREFIX + a6112.EXPECTED_PCS + CALLER_RESUME + a5fc4_pcs)

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            nonlocal chcr_value, dmaor_value
            if self.fetching:
                if size != 2 or address not in allowed:
                    raise ValueError(f"A717C composition PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address in (a717c.CALL_LITERAL, 0x060A7218) and size == 4:
                value = super().read(address, size)
                expected = a6112.ENTRY if address == a717c.CALL_LITERAL else a5fc4.ENTRY
                if value != expected:
                    raise ValueError(f"original call literal differs at {address:08x}")
                reads.append(["literal", address, size, value])
                return value
            if address == chcr_address and size == 4:
                reads.append(["CHCR", address, size, chcr_value])
                return chcr_value
            if address == DMAOR and size == 4:
                reads.append(["DMAOR", address, size, dmaor_value])
                return dmaor_value
            if address in (stack - 44, stack - 40, stack - 36) and size == 4:
                value = super().read(address, size)
                reads.append(["descriptor", address - (stack - 44), size, value])
                return value
            if address in STACK_READS and size == 4:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            raise ValueError(f"unexpected composed A717C read: {address:08x}/{size}")

        def write(self, address, size, value):
            nonlocal chcr_value, dmaor_value
            value &= 0xFFFFFFFF
            if address == chcr_address and size == 4:
                if value & 0xFFFF0000:
                    raise ValueError("CHCR upper sixteen bits were written")
                old = chcr_value
                chcr_value = (value & ~a6112.CHCR_TE) | (old & value & a6112.CHCR_TE)
                writes.append(["CHCR", address, size, value, chcr_value])
                return
            if address == DMAOR and size == 4:
                if value & 0xFFFFFFF0:
                    raise ValueError("DMAOR reserved upper bits were written")
                old = dmaor_value
                dmaor_value = (value & a5fc4.DMAOR_RW) | (old & value & a5fc4.DMAOR_W0C)
                writes.append(["DMAOR", address, size, value, dmaor_value])
                return
            if address in LOCAL_WRITES and size == 4:
                writes.append(["stack", address, size, value])
                return super().write(address, size, value)
            raise ValueError(f"unexpected composed A717C write: {address:08x}/{size}")

    mem = Memory()
    work_mem = mem.add(a717c.WORKRAM_BASE, a717c.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 128 or pc not in allowed:
                raise ValueError(f"A717C composition instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x12340000 + reg * 0x00010203 + seed * 0x00010001) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0], cpu.r[1] = 0xDEADBEEF, 0x2468ACE0 + seed
    cpu.r[4], cpu.r[5], cpu.r[6], cpu.r[7] = mode, base, r6, r7
    cpu.r[15], cpu.sr, cpu.pc, cpu.pr = stack, 0x30 | (priority << 4), ENTRY, emu.RETURN_SENTINEL

    path = expected_pcs()
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 128:
            raise ValueError("A717C composition instruction budget exceeded")
    if tuple(pcs) != path:
        raise ValueError(f"composed original call/return path differs ({len(pcs)}/{len(path)} PCs)")
    if cpu.pr != STOP or cpu.steps != len(path):
        raise ValueError("A5FC4 did not return to A717C immediately after its JSR delay slot")
    if chcr_value != (chcr_initial & ~a6112.CHCR_DE):
        raise ValueError("original A6112 did not clear CHCR.DE under the SH7604 fixture")
    dmaor_write = writes[-1] if writes else None
    expected_dmaor_write, expected_dmaor = a5fc4.scalar(15, 0, 1, dmaor_initial)
    if dmaor_value != expected_dmaor or dmaor_write != ["DMAOR", DMAOR, 4, expected_dmaor_write, expected_dmaor]:
        raise ValueError("original A5FC4 DMAOR write differs from the W0C register fixture")
    descriptor = tuple(int.from_bytes(work_mem[address - a717c.WORKRAM_BASE:address - a717c.WORKRAM_BASE + 4], "big")
        for address in (stack - 44, stack - 40, stack - 36))
    if descriptor != (0, 1, 15):
        raise ValueError(f"A717C constructed descriptor differs at A5FC4 entry: {descriptor!r}")
    if cpu.r[15] != stack - 92 or cpu.pc != STOP:
        raise ValueError("composed A717C/A5FC4 stack or return boundary differs")
    return {"inputs": {"mode": mode, "chcr_before": chcr_initial,
            "dmaor_before": dmaor_initial, "base": base, "r7": r7,
            "stack_top": stack_top, "priority": priority, "seed": seed, "r6": r6},
        "chcr_after": chcr_value, "descriptor_at_a5fc4": list(descriptor),
        "dmaor_after": dmaor_value, "reads": reads, "writes": writes,
        "steps": cpu.steps, "pc_path_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
        "return_pc": hex(cpu.pc), "return_pr": hex(cpu.pr), "sp": hex(cpu.r[15]),
        "boundary_registers": {f"r{index}": cpu.r[index] for index in range(16)},
        "boundary_sr": cpu.sr}


def paired(kernel, ram, emu, values):
    first = execute(kernel, ram, emu, values)
    second = execute(kernel, ram, emu, values)
    if first != second:
        raise ValueError(f"paired A717C composition differs: {values!r}")
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-a6112-a5fc4-composed.v1",
        "status": "failure", "entry": hex(ENTRY), "stop": hex(STOP),
        "limits": ["Original A717C -> A6112 -> A5FC4 call/return composition",
            "Constructed CHCR/DMAOR values under documented SH7604 access rules; active DMA, cache purge, natural caller and timing remain unproved"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                meta = json.loads(args.checkpoint.read_text())
                if meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != a717c.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, a717c.STATE_MAX)
                if sha(state) != a717c.STATE_SHA or meta.get("state_sha256") != a717c.STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, a717c.KERNEL_SIZE)
                if len(kernel) != a717c.KERNEL_SIZE or sha(kernel) != a717c.KERNEL_SHA:
                    raise ValueError("original Japanese kernel identity differs")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", a717c.WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != a717c.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                for start, end in ((ENTRY, a717c.END), (a6112.ENTRY, a6112.END), (a5fc4.ENTRY, a5fc4.END)):
                    if ram[start - a717c.WORKRAM_BASE:end - a717c.WORKRAM_BASE] != kernel[start - a717c.BASE:end - a717c.BASE]:
                        raise ValueError(f"captured/original source bytes differ at {start:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = [paired(kernel, ram, emu, values) for values in corpus()]
                mutation_ram = bytearray(ram)
                mutation_ram[0x060A71A6-a717c.WORKRAM_BASE:0x060A71A8-a717c.WORKRAM_BASE] = (0x0009).to_bytes(2, "big")
                try:
                    execute(kernel, bytes(mutation_ram), emu, corpus()[0])
                except ValueError as error:
                    mutation_reason = str(error)
                    if "call/return path differs" not in mutation_reason:
                        raise
                else:
                    raise ValueError("mutating the original A717C JSR to NOP was not detected")
                result_bytes = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(result_bytes), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=a717c.KERNEL_SHA, state_sha256=a717c.STATE_SHA,
                    normalized_workram_sha256=a717c.RAM_SHA,
                    source_ranges={"A717C": [hex(ENTRY), hex(a717c.END)],
                        "A6112": [hex(a6112.ENTRY), hex(a6112.END)],
                        "A5FC4": [hex(a5fc4.ENTRY), hex(a5fc4.END)]},
                    source_range_sha256={"A717C": sha(kernel[ENTRY-a717c.BASE:a717c.END-a717c.BASE]),
                        "A6112": sha(kernel[a6112.ENTRY-a717c.BASE:a6112.END-a717c.BASE]),
                        "A5FC4": sha(kernel[a5fc4.ENTRY-a717c.BASE:a5fc4.END-a717c.BASE])},
                    mutation_control={"address": "0x060A71A6", "original": "0x420B",
                        "replacement": "0x0009", "rejected": True, "reason": mutation_reason},
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="From original A717C entry with stack argument 4, the original code calls A6112, which reads/clears CHCR.DE under the documented CHCR fixture; A717C builds descriptor words (0,1,15), calls A5FC4, applies descriptor flags to DMAOR under documented W0C semantics, and returns to A717C PC 060A71C0 with the expected call/return PC sequence.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: report path must be fresh: {error}")
        return 1
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
