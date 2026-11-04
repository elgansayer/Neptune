#!/usr/bin/env python3
"""Execute A717C's original descriptor-building tail into original A600C."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source
import probe_japan_a600c_dmac as a600c

ENTRY, STOP = 0x060A71C0, 0x060A723C
LOCAL_SP = 0x06007FA4
STACK_TOP = 0x06008000
CALLER_PCS = tuple(range(0x060A71C0, 0x060A7200, 2)) + tuple(range(0x060A721C, 0x060A7236, 2))
R8_VALUES = (0xFFFFFFFF, 0, 1)
STACK_TOP_VALUES = (0xFFFFFFFF, 0, 1)
R7_VALUES = (0x11223344, 0xA55A5AA5)
CHANNELS = (0, 1)
BASES = (0x06009000, 0x06009004)
CHCR_VALUES = (0, 2, 3)
FLAGS = 0x2FF


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def caller_pcs(r8: int, stack_top: int) -> tuple[int, ...]:
    pcs = [0x060A71C0, 0x060A71C2, 0x060A71C4, 0x060A71C6,
        0x060A71C8, 0x060A71CA, 0x060A71CC, 0x060A71CE]
    r8s = r8 if r8 < 0x80000000 else r8 - 0x100000000
    if r8s > 0:
        pcs.extend((0x060A71D0, 0x060A71D2, 0x060A71D4))
    else:
        pcs.extend((0x060A71D6, 0x060A71D8))
        if r8s == 0:
            pcs.append(0x060A71E0)
        else:
            pcs.extend((0x060A71DA, 0x060A71DC, 0x060A71DE))
    pcs.extend((0x060A71E2, 0x060A71E4, 0x060A71E6, 0x060A71E8))
    stack_s = stack_top if stack_top < 0x80000000 else stack_top - 0x100000000
    if stack_s > 0:
        pcs.extend((0x060A71EA, 0x060A71EC, 0x060A71EE))
    else:
        pcs.extend((0x060A71F0, 0x060A71F2, 0x060A71F4, 0x060A71F6))
        if stack_s == 0:
            pcs.append(0x060A721C)
        else:
            pcs.extend((0x060A71F8, 0x060A71FA, 0x060A71FC))
    pcs.extend((0x060A721E, 0x060A7220, 0x060A7222, 0x060A7224,
        0x060A7226, 0x060A7228, 0x060A722A, 0x060A722C, 0x060A722E,
        0x060A7230, 0x060A7232, 0x060A7234))
    return tuple(pcs)


def cases():
    return [(r8, top, r7, channel, base, chcr)
        for r8 in R8_VALUES for top in STACK_TOP_VALUES for r7 in R7_VALUES
        for channel in CHANNELS for base in BASES for chcr in CHCR_VALUES]


def execute(kernel: bytes, ram: bytes, emu, values):
    r8, stack_top, r7, channel, base, chcr_initial = values
    if values not in cases():
        raise ValueError("caller input outside declared domain")
    work = bytearray(ram)
    work[STACK_TOP - source.WORKRAM_BASE:STACK_TOP - source.WORKRAM_BASE + 4] = stack_top.to_bytes(4, "big")
    work[LOCAL_SP - source.WORKRAM_BASE:LOCAL_SP - source.WORKRAM_BASE + 4] = r7.to_bytes(4, "big")
    work[LOCAL_SP + 4 - source.WORKRAM_BASE:LOCAL_SP + 8 - source.WORKRAM_BASE] = (1).to_bytes(4, "big")
    descriptor = LOCAL_SP + 8
    # A717C leaves descriptor word +32 untouched. Preserve the captured frame value.
    stale_drc = int.from_bytes(work[descriptor + 32 - source.WORKRAM_BASE:descriptor + 36 - source.WORKRAM_BASE], "big")
    chcr_addr = a600c.BASES[channel] + 12
    reg_values = {chcr_addr: chcr_initial}
    reads, writes, pcs = [], [], []
    post_a600c_pcs = (0x060A7236, 0x060A7238, 0x060A723A)
    a6100_pcs = tuple(range(0x060A6100, 0x060A6112, 2))
    allowed = (set(CALLER_PCS) | set(a600c.expected_pcs(FLAGS)) |
        set(post_a600c_pcs) | set(a6100_pcs) | {a600c.SHIFT_LEAF})

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or address not in allowed:
                    raise ValueError(f"caller/A600C PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address == chcr_addr and size == 4:
                reads.append(["CHCR", address, size, reg_values[chcr_addr]])
                return reg_values[chcr_addr]
            return super().read(address, size)

        def write(self, address, size, value):
            value &= 0xFFFFFFFF
            if address == chcr_addr and size == 4:
                old = reg_values[chcr_addr]
                if value & 0xFFFF0000:
                    raise ValueError("CHCR upper bits must remain zero")
                reg_values[chcr_addr] = (value & ~a600c.CHCR_TE) | (old & value & a600c.CHCR_TE)
                writes.append(["CHCR", address, size, value, reg_values[chcr_addr]])
                return
            if address in (a600c.BASES[channel], a600c.BASES[channel] + 4,
                    a600c.BASES[channel] + 8) and size == 4:
                writes.append(["DMAC", address, size, value])
                return
            if address == 0xFFFFFE71 + channel and size == 1:
                writes.append(["DRCR", address, size, value & 0xFF])
                return
            return super().write(address, size, value)

    mem = Memory()
    work_mem = mem.add(source.WORKRAM_BASE, source.WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= 160 or pc not in allowed:
                raise ValueError(f"caller/A600C PC budget fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x13570000 + i * 0x10203) & 0xFFFFFFFF for i in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[5] = 0xDEADBEEF, 0x06009000, 0x06009004
    cpu.r[7], cpu.r[8], cpu.r[9], cpu.r[10] = r7, r8, 1, base
    cpu.r[11], cpu.r[12], cpu.r[13], cpu.r[14] = channel, 4, 1, 0
    cpu.r[15], cpu.pr, cpu.pc = LOCAL_SP, ENTRY, ENTRY
    caller_trace = caller_pcs(r8, stack_top)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 160:
            raise ValueError("caller/A600C instruction budget exceeded")
    if tuple(pcs[:len(caller_trace)]) != caller_trace:
        raise ValueError(f"A717C tail control flow differs: {pcs[:len(caller_trace)]!r}/{caller_trace!r}")
    callee_start = len(caller_trace)
    callee_end = callee_start + len(a600c.expected_pcs(FLAGS))
    if tuple(pcs[callee_start:callee_end]) != a600c.expected_pcs(FLAGS):
        raise ValueError("A600C/leaf exact PC sequence differs")
    if tuple(pcs[callee_end:]) != post_a600c_pcs + a6100_pcs:
        raise ValueError("A717C A6100 call and original A6100 delay-slot path differs")

    d12 = 1 if r8 < 0x80000000 and r8 != 0 else (0 if r8 == 0 else 2)
    top_s = stack_top if stack_top < 0x80000000 else stack_top - 0x100000000
    d16 = 1 if top_s > 0 else (0 if top_s == 0 else 2)
    fields = (r7, base, 1, d12, d16, 0x800, 0x200, 0, stale_drc & 0xFF)
    _, expected_chcr, expected_regs = a600c.scalar(FLAGS, fields, channel, chcr_initial)
    mmio = [(row[0], row[1], row[2], row[3]) for row in writes]
    expected_mmio = []
    for addr, size, value in expected_regs:
        kind = ("CHCR" if addr == chcr_addr else
            "DRCR" if addr == 0xFFFFFE71 + channel else "DMAC")
        expected_mmio.append((kind, addr, size, value))
    expected_mmio.append(("CHCR", chcr_addr, 4, expected_chcr | 1))
    if mmio != expected_mmio:
        raise ValueError(f"caller-derived A600C writes differ: {mmio!r}/{expected_mmio!r}")
    expected_chcr_after_setter = ((expected_chcr | 1) & ~a600c.CHCR_TE) | (
        expected_chcr & (expected_chcr | 1) & a600c.CHCR_TE)
    if reg_values[chcr_addr] != expected_chcr_after_setter:
        raise ValueError("A6100 did not set CHCR.DE after the A600C write")
    after_stale = int.from_bytes(work_mem[descriptor + 32 - source.WORKRAM_BASE:
        descriptor + 36 - source.WORKRAM_BASE], "big")
    if after_stale != stale_drc:
        raise ValueError("A717C/A600C unexpectedly modified inherited descriptor word +32")
    if cpu.r[15] != LOCAL_SP or cpu.pc != STOP or cpu.pr != STOP:
        raise ValueError("A6100 did not return to original A717C A5F98 call boundary")
    return {"inputs": {"r8": r8, "stack_top": stack_top, "r7": r7,
            "channel": channel, "base": base, "chcr_before": chcr_initial},
        "caller_derived_descriptor": {"base": descriptor, "flags": FLAGS,
            "words_0_to_8": [r7, base, 1, d12, d16, 0x800, 0x200, 0, stale_drc]},
        "drc_word_32_preserved_from_snapshot": stale_drc,
        "chcr_after": reg_values[chcr_addr], "reads": reads, "writes": writes,
        "pc_trace": [hex(pc) for pc in pcs], "steps": cpu.steps,
        "boundary_registers": {f"r{i}": cpu.r[i] for i in (4, 5, 8, 9, 10, 11, 12, 13, 14, 15)},
        "stop_pc": hex(cpu.pc), "stop_contract": "A6100 returned to 0x060A723C immediately before the A717C call of A5F98"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-a600c-caller.v1", "status": "failure",
        "entry": hex(ENTRY), "stop": hex(STOP),
        "limits": ["Original A717C tail from the A5FC4 return boundary through A600C and A6100",
            "Preceding A717C/A6112/A5FC4 context and active DMA timing remain separately modeled/unproved"]}
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
                ranges = ((ENTRY, STOP), (a600c.ENTRY, a600c.END),
                    (0x060A6100, 0x060A6112),
                    (a600c.SHIFT_LEAF, a600c.SHIFT_END))
                for start, end in ranges:
                    if ram[start-source.WORKRAM_BASE:end-source.WORKRAM_BASE] != kernel[start-source.BASE:end-source.BASE]:
                        raise ValueError(f"captured/original source bytes differ at {start:08x}")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for values in cases():
                    first = execute(kernel, ram, emu, values)
                    second = execute(kernel, ram, emu, values)
                    if first != second:
                        raise ValueError(f"paired caller/A600C execution differs: {values!r}")
                    rows.append(first)
                mutated = bytearray(ram)
                mutation_address = LOCAL_SP + 8 + 32
                mutated[mutation_address-source.WORKRAM_BASE:
                    mutation_address-source.WORKRAM_BASE + 4] = (0x123456AB).to_bytes(4, "big")
                mutation_case = (0, 0, R7_VALUES[0], 0, BASES[0], 0)
                mutation_result = execute(kernel, mutated, emu, mutation_case)
                baseline_result = rows[cases().index(mutation_case)]
                if (any(row[0] == "DRCR" for row in mutation_result["writes"])
                        or mutation_result["writes"] != baseline_result["writes"]
                        or mutation_result["chcr_after"] != baseline_result["chcr_after"]):
                    raise ValueError("unused descriptor +32 mutation changed the A600C caller route")
                results = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(results), probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={"address": hex(mutation_address), "word": "0x123456AB",
                        "observed_DRCR_write": False,
                        "writes_unchanged": mutation_result["writes"] == baseline_result["writes"],
                        "chcr_unchanged": mutation_result["chcr_after"] == baseline_result["chcr_after"],
                        "result_sha256": sha(json.dumps(mutation_result, sort_keys=True,
                            separators=(",", ":")).encode())},
                    a717c_source_sha256=sha(kernel[ENTRY-source.BASE:STOP-source.BASE]),
                    a600c_source_sha256=sha(kernel[a600c.ENTRY-source.BASE:a600c.END-source.BASE]),
                    a595b6_source_sha256=sha(kernel[a600c.SHIFT_LEAF-source.BASE:a600c.SHIFT_END-source.BASE]),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="Original A717C tail constructs a 0x2FF descriptor and calls original A600C; A6100 then sets CHCR.DE for the selected channel and returns to the A5F98 call boundary. Descriptor word +32 is inherited from the captured frame but flag 0x100 is clear, so it is not consumed on this route.")
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
