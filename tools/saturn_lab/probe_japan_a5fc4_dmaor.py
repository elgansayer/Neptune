#!/usr/bin/env python3
"""Execute original A5FC4 with a bounded SH7604 DMAOR access contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

ENTRY, END = 0x060A5FC4, 0x060A600C
DMAOR = 0xFFFFFFB0
DESCRIPTOR = 0x06007F00
DMAOR_RW = 0x9
DMAOR_W0C = 0x6
FLAGS = tuple(range(16))
VALUES = (0, 1, 2, 4, 8, 3, 12, 15)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_pcs(flags: int) -> tuple[int, ...]:
    pcs = [0x060A5FC4, 0x060A5FC6, 0x060A5FC8, 0x060A5FCA,
        0x060A5FCC, 0x060A5FCE, 0x060A5FD0]
    if flags & 1:
        pcs.extend((0x060A5FD2, 0x060A5FD4, 0x060A5FD6, 0x060A5FD8))
    pcs.extend((0x060A5FDA, 0x060A5FDC, 0x060A5FDE, 0x060A5FE0, 0x060A5FE2))
    if flags & 8:
        pcs.extend((0x060A5FE4, 0x060A5FE6, 0x060A5FE8, 0x060A5FEA))
    pcs.extend((0x060A5FEC, 0x060A5FEE, 0x060A5FF0, 0x060A5FF2, 0x060A5FF4))
    if flags & 2:
        pcs.extend((0x060A5FF6, 0x060A5FF8))
    pcs.extend((0x060A5FFA, 0x060A5FFC, 0x060A5FFE, 0x060A6000, 0x060A6002))
    if flags & 4:
        pcs.extend((0x060A6004, 0x060A6006))
    pcs.extend((0x060A6008, 0x060A600A))
    return tuple(pcs)


def scalar(flags: int, value0: int, value1: int, old: int) -> tuple[int, int]:
    value = old & 0xF
    if flags & 1:
        value = (value & 0xFFFFFFF7) | value0
    if flags & 8:
        value = (value & 0xFFFFFFFE) | value1
    if flags & 2:
        value &= 0xFFFFFFFB
    if flags & 4:
        value &= 0xFFFFFFFD
    written = value & 0xF
    result = (written & DMAOR_RW) | (old & written & DMAOR_W0C)
    return written, result


def execute(kernel: bytes, ram: bytes, emu, flags: int, value0: int, value1: int, dmaor: int):
    if flags not in FLAGS or value0 not in VALUES or value1 not in VALUES or dmaor not in FLAGS:
        raise ValueError("A5FC4 input outside declared domain")
    work = bytearray(ram)
    work[DESCRIPTOR - source.WORKRAM_BASE:DESCRIPTOR - source.WORKRAM_BASE + 12] = b"".join(
        word.to_bytes(4, "big") for word in (value0, value1, flags))
    reads, writes, pcs = [], [], []
    dmaor_value = dmaor
    allowed_pcs = expected_pcs(flags)

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            nonlocal dmaor_value
            if self.fetching:
                if size != 2 or address not in allowed_pcs:
                    raise ValueError(f"A5FC4 PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address == DMAOR and size == 4:
                reads.append(["DMAOR", address, size, dmaor_value])
                return dmaor_value
            if address in (DESCRIPTOR, DESCRIPTOR + 4, DESCRIPTOR + 8) and size == 4:
                value = super().read(address, size)
                reads.append(["descriptor", address, size, value])
                return value
            raise ValueError(f"unexpected A5FC4 read: {address:08x}/{size}")

        def write(self, address, size, value):
            nonlocal dmaor_value
            value &= 0xFFFFFFFF
            if address != DMAOR or size != 4:
                raise ValueError(f"unexpected A5FC4 write: {address:08x}/{size}")
            if value & 0xFFFFFFF0:
                raise ValueError("DMAOR reserved upper bits must be written zero")
            old = dmaor_value
            dmaor_value = (value & DMAOR_RW) | (old & value & DMAOR_W0C)
            writes.append(["DMAOR", address, size, value, dmaor_value])

    mem = Memory()
    mem.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 40 or pc not in allowed_pcs:
                raise ValueError(f"A5FC4 PC/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0xABC00000 + reg * 0x10203) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[4] = DESCRIPTOR
    cpu.r[15] = 0x06008000
    preserved = {reg: cpu.r[reg] for reg in (0, 1, 8, 9, 10, 11, 12, 13, 14, 15)}
    cpu.call(ENTRY, max_steps=40)
    expected_write, expected_dmaor = scalar(flags, value0, value1, dmaor)
    if tuple(pcs) != allowed_pcs or cpu.steps != len(allowed_pcs):
        raise ValueError("A5FC4 exact instruction path or RTS delay differs")
    if dmaor_value != expected_dmaor or writes != [["DMAOR", DMAOR, 4, expected_write, expected_dmaor]]:
        raise ValueError("A5FC4 DMAOR write/W0C result differs")
    expected_reads = 5 + bool(flags & 1) + bool(flags & 8)
    if len(reads) != expected_reads or sum(row[0] == "DMAOR" for row in reads) != 1:
        raise ValueError("A5FC4 bounded read trace differs")
    for reg, value in preserved.items():
        if cpu.r[reg] != value:
            raise ValueError(f"A5FC4 changed preserved R{reg}")
    return {"flags": flags, "value0": value0, "value1": value1,
        "dmaor_before": dmaor, "dmaor_write": expected_write,
        "dmaor_after": dmaor_value, "pcs": [hex(pc) for pc in pcs],
        "reads": reads, "writes": writes, "steps": cpu.steps}


def cases():
    return [(flags, value0, value1, dmaor) for flags in FLAGS
        for value0 in VALUES for value1 in VALUES for dmaor in FLAGS]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a5fc4-dmaor.v1", "status": "failure",
        "entry": hex(ENTRY), "dmaor": hex(DMAOR),
        "limits": ["Original A5FC4 through RTS delay slot with an explicit SH7604 DMAOR fixture",
            "Constructed descriptor/DMAOR values; no DMA transfer engine or timing"]}
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
                    raise ValueError("original Japan kernel identity mismatch")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", source.WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                if ram[ENTRY - source.WORKRAM_BASE:END - source.WORKRAM_BASE] != kernel[ENTRY - source.BASE:END - source.BASE]:
                    raise ValueError("A5FC4 source bytes differ between original and capture")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for values in cases():
                    a = execute(kernel, ram, emu, *values)
                    b = execute(kernel, ram, emu, *values)
                    if a != b:
                        raise ValueError(f"paired A5FC4 executions differ: {values!r}")
                    rows.append(a)
                result = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(result), probe_sha256=sha(Path(__file__).read_bytes()),
                    source_sha256=sha(kernel[ENTRY - source.BASE:END - source.BASE]),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="Original A5FC4 conditionally modifies DMAOR.PR/DME and clears DMAOR.AE/NMIF via the original RTS delay-slot write under the SH7604 W0C fixture.")
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
