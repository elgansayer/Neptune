#!/usr/bin/env python3
"""Execute original Japanese A600C and its A595B6 leaf with a bounded DMAC fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source

ENTRY, END = 0x060A600C, 0x060A60EA
SHIFT_LEAF, SHIFT_END = 0x060959B6, 0x060959C0
DESCRIPTOR = 0x06007F00
SP = 0x06008000
BASES = (0xFFFFFF80, 0xFFFFFF90)
CHCR_TE = 0x0002
FLAGS = tuple(range(0x400))
CHCR_INITIAL = (0x0000, 0x0003)
PATTERNS = (
    (0, 0, 0, 0, 0, 0, 0, 0, 0),
    (0x06012344, 0x25FE0000, 0x00123456, 1, 2, 0x0400, 0x0200, 1, 0xA5),
    (0xFFFFFFFF, 0xFFFFFFFF, 0x00FFFFFF, 3, 3, 0x0C00, 0x0200, 3, 0xFF),
    (0x06007F00, 0x06008000, 0x00000001, 2, 1, 0x0800, 0, 2, 0x01),
)
LITERALS = {0x060A60EA, 0x060A60EC, 0x060A60EE, 0x060A60F0,
    0x060A60F2, 0x060A60F4, 0x060A60F6, 0x060A60F8, 0x060A60FC}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_pcs(flags: int) -> tuple[int, ...]:
    pcs = [0x060A600C, 0x060A600E, 0x060A6010, 0x060A6012,
        0x060A6014, 0x060A6016]
    if flags & 0x001:
        pcs.extend((0x060A6018, 0x060A601A, 0x060A601C, 0x060A601E,
            0x060A6020, 0x060A6022))
    pcs.extend((0x060A6024, 0x060A6026, 0x060A6028, 0x060A602A, 0x060A602C))
    if flags & 0x002:
        pcs.extend((0x060A602E, 0x060A6030, 0x060A6032, 0x060A6034, 0x060A6036, 0x060A6038))
    pcs.extend((0x060A603A, 0x060A603C, 0x060A603E, 0x060A6040, 0x060A6042))
    if flags & 0x004:
        pcs.extend((0x060A6044, 0x060A6046, 0x060A6048, 0x060A604A, 0x060A604C, 0x060A604E))
    pcs.extend((0x060A6050, 0x060A6052, 0x060A6054, 0x060A6056,
        0x060A6058, 0x060A605A, 0x060A605C, 0x060A605E, 0x060A6060))
    if flags & 0x008:
        pcs.extend((0x060A6062, 0x060A6064, 0x060A6066, 0x060A6068, 0x060A606A,
            0x060959B6, 0x060959B8, 0x060959BA, 0x060959BC, 0x060959BE, 0x060A606C))
    pcs.extend((0x060A606E, 0x060A6070, 0x060A6072, 0x060A6074))
    if flags & 0x010:
        pcs.extend((0x060A6076, 0x060A6078, 0x060A607A, 0x060A607C, 0x060A607E, 0x060A6080, 0x060A6082))
    pcs.extend((0x060A6084, 0x060A6086, 0x060A6088, 0x060A608A))
    if flags & 0x020:
        pcs.extend((0x060A608C, 0x060A608E, 0x060A6090, 0x060A6092))
    pcs.extend((0x060A6094, 0x060A6096, 0x060A6098, 0x060A609A))
    if flags & 0x040:
        pcs.extend((0x060A609C, 0x060A609E, 0x060A60A0, 0x060A60A2))
    pcs.extend((0x060A60A4, 0x060A60A6, 0x060A60A8, 0x060A60AA,
        0x060A60AC, 0x060A60AE, 0x060A60B0, 0x060A60B2, 0x060A60B4))
    if flags & 0x080:
        pcs.extend((0x060A60B6, 0x060A60B8, 0x060A60BA, 0x060A60BC))
    pcs.extend((0x060A60BE, 0x060A60C0, 0x060A60C2, 0x060A60C4, 0x060A60C6, 0x060A60C8))
    if flags & 0x200:
        pcs.extend((0x060A60CA, 0x060A60CC))
    pcs.extend((0x060A60CE, 0x060A60D0, 0x060A60D2, 0x060A60D4, 0x060A60D6, 0x060A60D8))
    if flags & 0x100:
        pcs.extend((0x060A60DA, 0x060A60DC, 0x060A60DE, 0x060A60E0, 0x060A60E2))
    pcs.extend((0x060A60E4, 0x060A60E6, 0x060A60E8))
    return tuple(pcs)


def scalar(flags: int, fields: tuple[int, ...], channel: int, chcr: int):
    sar, dar, tcr, d12, d16, d20, d24, d28, drcr = fields
    value = chcr & 0xFFFFFFFF
    if flags & 0x008:
        value = (value & 0xFFFF3FFF) | ((d12 << 14) & 0xFFFFFFFF)
    if flags & 0x010:
        value = (value & 0xFFFFCFFF) | ((d16 << 12) & 0xFFFFFFFF)
    if flags & 0x020:
        value = (value & 0xFFFFF3FF) | d20
    if flags & 0x040:
        value = (value & 0xFFFFFDFF) | d24
    value &= 0xFFFFFFEF
    value &= 0xFFFFFFF7
    if flags & 0x080:
        value = (value & 0xFFFFFFFB) | d28
    if flags & 0x200:
        value &= 0xFFFFFFFD
    written = value & 0xFFFFFFFF
    after = (written & ~CHCR_TE) | (chcr & written & CHCR_TE)
    regs = []
    if flags & 1:
        regs.append((BASES[channel], 4, sar & 0xFFFFFFFF))
    if flags & 2:
        regs.append((BASES[channel] + 4, 4, dar & 0xFFFFFFFF))
    if flags & 4:
        regs.append((BASES[channel] + 8, 4, tcr & 0xFFFFFFFF))
    regs.append((BASES[channel] + 12, 4, written))
    if flags & 0x100:
        regs.append((0xFFFFFE71 + channel, 1, drcr & 0xFF))
    return written, after, regs


def cases():
    return [(flags, channel, pattern, chcr) for flags in FLAGS
        for channel in (0, 1) for pattern in range(len(PATTERNS))
        for chcr in CHCR_INITIAL]


def execute(kernel: bytes, ram: bytes, emu, flags: int, channel: int,
        pattern: int, chcr_initial: int):
    if flags not in FLAGS or channel not in (0, 1) or pattern not in range(len(PATTERNS)) or chcr_initial not in CHCR_INITIAL:
        raise ValueError("A600C input outside declared domain")
    fields = PATTERNS[pattern]
    work = bytearray(ram)
    descriptor = (b"".join((int(word) & 0xFFFFFFFF).to_bytes(4, "big") for word in fields[:8])
        + bytes((0, 0, 0, fields[8] & 0xFF)) + flags.to_bytes(4, "big"))
    work[DESCRIPTOR - source.WORKRAM_BASE:DESCRIPTOR - source.WORKRAM_BASE + 40] = descriptor
    reads, writes, pcs = [], [], []
    chcr_addr = BASES[channel] + 12
    reg_values = {chcr_addr: chcr_initial & 0xFFFFFFFF}
    allowed = expected_pcs(flags)
    expected_regs = scalar(flags, fields, channel, chcr_initial)

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or address not in allowed:
                    raise ValueError(f"A600C PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address in LITERALS and size in (2, 4):
                value = super().read(address, size)
                reads.append(["literal", address, size, value])
                return value
            if DESCRIPTOR <= address < DESCRIPTOR + 40 and size == 4 and address % 4 == 0:
                value = super().read(address, size)
                reads.append(["descriptor", address - DESCRIPTOR, size, value])
                return value
            if address == chcr_addr and size == 4:
                value = reg_values[chcr_addr]
                reads.append(["CHCR", address, size, value])
                return value
            if address == SP - 4 and size == 4:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            raise ValueError(f"unexpected A600C read: {address:08x}/{size}")

        def write(self, address, size, value):
            value &= 0xFFFFFFFF
            if address == chcr_addr and size == 4:
                old = reg_values[chcr_addr]
                if value & 0xFFFF0000:
                    raise ValueError("CHCR upper bits must remain zero")
                new = (value & ~CHCR_TE) | (old & value & CHCR_TE)
                reg_values[chcr_addr] = new
                writes.append(["CHCR", address, size, value, new])
                return
            if address in (BASES[channel], BASES[channel] + 4, BASES[channel] + 8) and size == 4:
                expected_value = next(v for a, w, v in expected_regs[2] if a == address and w == size)
                if value != expected_value:
                    raise ValueError("DMAC register write differs from descriptor contract")
                writes.append(["DMAC", address, size, value])
                return
            if address == SP - 4 and size == 4:
                writes.append(["stack", address, size, value])
                return super().write(address, size, value)
            if address == 0xFFFFFE71 + channel and size == 1 and flags & 0x100:
                if value != (fields[8] & 0xFF):
                    raise ValueError("DRCR byte differs from descriptor contract")
                writes.append(["DRCR", address, size, value])
                return
            raise ValueError(f"unexpected A600C write: {address:08x}/{size}")

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
            if self.steps >= 160 or pc not in allowed:
                raise ValueError(f"A600C PC/budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x13570000 + reg * 0x10203) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0xDEADBEEF
    cpu.r[4], cpu.r[5], cpu.r[6], cpu.r[7] = DESCRIPTOR, channel, 0x76543210, 0x76543210
    cpu.r[15] = SP
    cpu.call(ENTRY, max_steps=160)
    written, chcr_after, regs = expected_regs
    if tuple(pcs) != allowed or cpu.steps != len(allowed):
        mismatch = next((i for i, pair in enumerate(zip(pcs, allowed)) if pair[0] != pair[1]), min(len(pcs), len(allowed)))
        raise ValueError(f"A600C exact original PC path/return-delay trace differs at {mismatch}: actual={pcs[mismatch:mismatch+8]!r}, expected={allowed[mismatch:mismatch+8]!r}, lengths={len(pcs)}/{len(allowed)}, steps={cpu.steps}")
    if reg_values[chcr_addr] != chcr_after:
        raise ValueError(f"CHCR final value differs: {reg_values[chcr_addr]:08x}/{chcr_after:08x}")
    expected_mmio = [("DMAC" if addr != chcr_addr else "CHCR", addr, size, value)
        for addr, size, value in regs]
    if flags & 0x100:
        expected_mmio[-1] = ("DRCR", 0xFFFFFE71 + channel, 1, fields[8] & 0xFF)
    actual_mmio = [(row[0], row[1], row[2], row[3]) for row in writes if row[0] != "stack"]
    if actual_mmio != expected_mmio:
        raise ValueError(f"A600C MMIO writes differ: {actual_mmio!r}/{expected_mmio!r}")
    descriptor_counts = {offset: sum(row[0] == "descriptor" and row[1] == offset for row in reads)
        for offset in range(0, 40, 4)}
    expected_counts = {36: 10}
    for bit, offset in ((1, 0), (2, 4), (4, 8), (8, 12), (16, 16),
            (32, 20), (64, 24), (128, 28), (256, 32)):
        if flags & bit:
            expected_counts[offset] = 1
    expected_counts = {offset: expected_counts.get(offset, 0) for offset in range(0, 40, 4)}
    if descriptor_counts != expected_counts:
        raise ValueError(f"A600C descriptor read counts differ: {descriptor_counts!r}/{expected_counts!r}")
    literal_counts = {address: sum(row[0] == "literal" and row[1] == address for row in reads)
        for address in LITERALS}
    expected_literals = {address: int(address in (0x060A60F0, 0x060A60F2, 0x060A60F4)) for address in LITERALS}
    for bit, address in ((8, 0x060A60F8), (8, 0x060A60FC), (16, 0x060A60EA),
            (32, 0x060A60EC), (64, 0x060A60EE), (256, 0x060A60F6)):
        if flags & bit:
            expected_literals[address] += 1
    if literal_counts != expected_literals:
        raise ValueError(f"A600C literal reads differ: {literal_counts!r}/{expected_literals!r}")
    if sum(row[0] == "CHCR" for row in reads) != 1 or sum(row[0] == "stack" for row in reads) != 1 or sum(row[0] == "stack" for row in writes) != 1:
        raise ValueError("A600C CHCR or saved-PR stack event count differs")
    if cpu.r[15] != SP or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A600C did not restore stack/linkage")
    if cpu.r[4] != DESCRIPTOR or cpu.r[0] != (flags & 0x80):
        raise ValueError("A600C return register contract differs")
    expected_r5 = ((channel - 399) & 0xFFFFFFFF) if flags & 0x100 else channel
    if cpu.r[5] != expected_r5:
        raise ValueError("A600C channel/DRCR pointer return register differs")
    return {"flags": flags, "channel": channel, "pattern": pattern,
        "chcr_before": chcr_initial, "chcr_write": written,
        "chcr_after": chcr_after, "writes": writes, "reads": reads,
        "r0": cpu.r[0], "r4": cpu.r[4], "r5": cpu.r[5],
        "r15": cpu.r[15], "pr": cpu.pr, "steps": cpu.steps,
        "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a600c-dmac.v1", "status": "failure",
        "entry": hex(ENTRY), "shift_leaf": hex(SHIFT_LEAF),
        "limits": ["Original A600C and A595B6 through A600C RTS delay slot",
            "Constructed descriptor and SH-2 DMAC register fixture; no transfer engine/timing"]}
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
                for start, end in ((ENTRY, END), (SHIFT_LEAF, SHIFT_END)):
                    if ram[start - source.WORKRAM_BASE:end - source.WORKRAM_BASE] != kernel[start - source.BASE:end - source.BASE]:
                        raise ValueError(f"original source bytes differ at {start:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for case in cases():
                    first = execute(kernel, ram, emu, *case)
                    second = execute(kernel, ram, emu, *case)
                    if first != second:
                        raise ValueError(f"paired A600C executions differ: {case!r}")
                    rows.append(first)
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(data), probe_sha256=sha(Path(__file__).read_bytes()),
                    a600c_source_sha256=sha(kernel[ENTRY - source.BASE:END - source.BASE]),
                    a595b6_source_sha256=sha(kernel[SHIFT_LEAF - source.BASE:SHIFT_END - source.BASE]),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="A600C writes selected SAR/DAR/TCR/CHCR fields and optional DRCR byte; A595B6 transforms descriptor word +12 by 2^14. CHCR TE is modeled W0C; no DMA transfer semantics are claimed.")
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
