#!/usr/bin/env python3
"""Resume original A717C boundary state through A600C/A6100 to A5F98."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a717c_zero_divisor as source
import probe_japan_a717c_a600c_caller as caller
import probe_japan_a600c_dmac as a600c
import probe_japan_a717c_a5fc4_composed as boundary_probe

ENTRY, STOP = 0x060A71C0, 0x060A723C
LOCAL_SP = 0x06007FA4
STACK_TOP = 0x06008000
CALL_A600C = 0x060A7232
CALL_A6100 = 0x060A6100
POST_CALL_PCS = (0x060A7236, 0x060A7238, 0x060A723A)
A6100_PCS = tuple(range(CALL_A6100, 0x060A6112, 2))
FLAGS = caller.FLAGS
R6_VALUES = boundary_probe.R6_VALUES
CHCR_VALUES = (0, 3)
DMAOR_VALUES = (0, 3, 15)
PRIORITIES = (0, 15)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_inputs():
    return [(mode, chcr, dmaor, base, r7, top, priority, seed, r6)
        for mode in boundary_probe.MODES for chcr in CHCR_VALUES for dmaor in DMAOR_VALUES
        for base in boundary_probe.BASES for r7 in boundary_probe.R7_VALUES
        for top in boundary_probe.STACK_TOPS for priority in PRIORITIES
        for seed in boundary_probe.SEEDS for r6 in R6_VALUES]


def input_key(row):
    i = row["inputs"]
    return (i["mode"], i["chcr_before"], i["dmaor_before"], i["base"],
        i["r7"], i["stack_top"], i["priority"], i["seed"], i["r6"])


def execute_tail(kernel: bytes, ram: bytes, emu, boundary, mutation=None):
    inputs = boundary["inputs"]
    if boundary["return_pc"] != hex(ENTRY) or boundary["return_pr"] != hex(ENTRY):
        raise ValueError("A5FC4 boundary PC/PR identity differs")
    if boundary["steps"] != len(boundary_probe.expected_pcs()):
        raise ValueError("A5FC4 boundary instruction count differs")
    mode = inputs["mode"]
    r8 = boundary["boundary_registers"]["r8"]
    top = inputs["stack_top"]
    channel = mode
    chcr_address = a600c.BASES[channel] + 12
    chcr_value = boundary["chcr_after"]
    if boundary["boundary_registers"]["r11"] != mode:
        raise ValueError("A717C channel register differs at the continuation boundary")

    work = bytearray(ram)
    work[STACK_TOP - source.WORKRAM_BASE:STACK_TOP - source.WORKRAM_BASE + 4] = top.to_bytes(4, "big")
    work[STACK_TOP + 4 - source.WORKRAM_BASE:STACK_TOP + 8 - source.WORKRAM_BASE] = (4).to_bytes(4, "big")
    for row in boundary["writes"]:
        if row[0] == "stack":
            _, address, size, value = row
            if size != 4 or not source.WORKRAM_BASE <= address <= source.WORKRAM_BASE + source.WORKRAM_SIZE - 4:
                raise ValueError("boundary stack write is outside captured WorkRAM-H")
            work[address - source.WORKRAM_BASE:address - source.WORKRAM_BASE + 4] = value.to_bytes(4, "big")
    if mutation is not None:
        address, word = mutation
        if address != CALL_A600C or word not in (0x0009, 0x430B):
            raise ValueError("unsupported A717C tail mutation")
        work[address - source.WORKRAM_BASE:address - source.WORKRAM_BASE + 2] = word.to_bytes(2, "big")

    descriptor = LOCAL_SP + 8
    reads, writes, pcs = [], [], []
    tail_pcs = caller.caller_pcs(r8, top)
    expected = tail_pcs + a600c.expected_pcs(FLAGS) + POST_CALL_PCS + A6100_PCS
    allowed = set(expected)
    registers = {chcr_address: chcr_value}
    dmac_addresses = {a600c.BASES[channel], a600c.BASES[channel] + 4, a600c.BASES[channel] + 8}
    drcr_address = 0xFFFFFE71 + channel
    work_literals = {0x060A7350, 0x060A7352, 0x060A7354,
        0x060A7358, 0x060A735C}
    descriptor_reads = {descriptor + off for off in range(0, 40, 4)}
    stack_reads = {STACK_TOP, LOCAL_SP, LOCAL_SP + 4, LOCAL_SP - 4}
    stack_writes = {LOCAL_SP - 4, *range(LOCAL_SP + 4, LOCAL_SP + 48, 4)}

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, size):
            if self.fetching:
                if size != 2 or address not in allowed:
                    raise ValueError(f"A717C tail PC fence at {address:08x}/{size}")
                return super().read(address, size)
            if address == chcr_address and size == 4:
                value = registers[chcr_address]
                reads.append(["CHCR", address, size, value])
                return value
            if address in descriptor_reads and size == 4:
                value = super().read(address, size)
                reads.append(["descriptor", address - descriptor, size, value])
                return value
            if address in stack_reads and size == 4:
                value = super().read(address, size)
                reads.append(["stack", address, size, value])
                return value
            if address in work_literals and size in (2, 4):
                value = super().read(address, size)
                reads.append(["literal", address, size, value])
                if address == 0x060A7358 and value != a600c.ENTRY:
                    raise ValueError("original A600C tail-call literal differs")
                if address == 0x060A735C and value != CALL_A6100:
                    raise ValueError("original A6100 tail-call literal differs")
                return value
            if address in a600c.LITERALS and size in (2, 4):
                value = super().read(address, size)
                reads.append(["literal", address, size, value])
                return value
            raise ValueError(f"unexpected A717C tail read: {address:08x}/{size}")

        def write(self, address, size, value):
            nonlocal chcr_value
            value &= 0xFFFFFFFF
            if address == chcr_address and size == 4:
                if value & 0xFFFF0000:
                    raise ValueError("CHCR upper bits were written")
                old = chcr_value
                chcr_value = (value & ~a600c.CHCR_TE) | (old & value & a600c.CHCR_TE)
                registers[chcr_address] = chcr_value
                writes.append(["CHCR", address, size, value, chcr_value])
                return
            if address in dmac_addresses and size == 4:
                writes.append(["DMAC", address, size, value])
                return
            if address == drcr_address and size == 1:
                writes.append(["DRCR", address, size, value & 0xFF])
                return
            if address in stack_writes and size == 4:
                writes.append(["stack", address, size, value])
                return super().write(address, size, value)
            raise ValueError(f"unexpected A717C tail write: {address:08x}/{size}")

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
            if self.steps >= 192 or pc not in allowed:
                raise ValueError(f"A717C tail instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [boundary["boundary_registers"][f"r{i}"] for i in range(16)]
    cpu.sr = boundary["boundary_sr"]
    cpu.pc, cpu.pr = ENTRY, ENTRY
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > 192:
            raise ValueError("A717C tail instruction budget exceeded")
    if tuple(pcs) != expected:
        raise ValueError(f"A717C tail path differs ({len(pcs)}/{len(expected)} PCs)")
    if cpu.r[15] != LOCAL_SP or cpu.pr != STOP:
        raise ValueError("A6100 return does not restore the A717C A5F98 call boundary")
    descriptor_inputs = tuple(int.from_bytes(work_mem[descriptor + off - source.WORKRAM_BASE:
        descriptor + off - source.WORKRAM_BASE + 4], "big") for off in range(0, 36, 4))
    flags = int.from_bytes(work_mem[descriptor + 36 - source.WORKRAM_BASE:
        descriptor + 40 - source.WORKRAM_BASE], "big")
    if flags != FLAGS:
        raise ValueError(f"A717C produced unexpected A600C flags {flags:#x}")
    _, expected_chcr, expected_regs = a600c.scalar(flags, descriptor_inputs, channel, boundary["chcr_after"])
    expected_mmio = []
    for address, size, value in expected_regs:
        kind = "CHCR" if address == chcr_address else "DRCR" if address == drcr_address else "DMAC"
        expected_mmio.append([kind, address, size, value])
    expected_mmio.append(["CHCR", chcr_address, 4, expected_chcr | 1])
    actual_mmio = [row[:4] for row in writes if row[0] != "stack"]
    if actual_mmio != expected_mmio:
        raise ValueError(f"A600C/A6100 MMIO sequence differs: {actual_mmio!r}/{expected_mmio!r}")
    expected_after = ((expected_chcr | 1) & ~a600c.CHCR_TE) | (expected_chcr & (expected_chcr | 1) & a600c.CHCR_TE)
    if chcr_value != expected_after:
        raise ValueError("final CHCR differs after A600C/A6100")
    return {"inputs": inputs, "boundary_r6": r8, "descriptor_words": list(descriptor_inputs),
        "descriptor_flags": flags, "reads": reads, "writes": writes,
        "steps": cpu.steps, "tail_instruction_count": len(pcs),
        "pc_path_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
        "mmio_writes": actual_mmio, "chcr_after_a600c_a6100": chcr_value,
        "stop_pc": hex(cpu.pc), "stop_pr": hex(cpu.pr), "sp": hex(cpu.r[15]),
        "selected_workram_sha256": sha(bytes(work_mem[LOCAL_SP + 4 - source.WORKRAM_BASE:
            LOCAL_SP + 48 - source.WORKRAM_BASE]))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "boundary-report", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a717c-a600c-a6100-tail.v1",
        "status": "failure", "entry": hex(ENTRY), "stop": hex(STOP),
        "limits": ["Continues exact serialized A5FC4 return state through original A600C/A6100 to the A5F98 call boundary",
            "Caller state and CHCR/DMAC/DRCR fixtures are constructed; active DMA, purge, natural caller and timing remain unproved"]}
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
                    raise ValueError("original Japanese kernel identity differs")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", source.WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                ranges = ((ENTRY, STOP), (a600c.ENTRY, a600c.END),
                    (CALL_A6100, 0x060A6112), (a600c.SHIFT_LEAF, a600c.SHIFT_END))
                for start, end in ranges:
                    if ram[start-source.WORKRAM_BASE:end-source.WORKRAM_BASE] != kernel[start-source.BASE:end-source.BASE]:
                        raise ValueError(f"captured/original tail source differs at {start:08x}")
                boundary_bytes = pinned.read_bounded(args.boundary_report, 64 * 1024 * 1024)
                boundary = json.loads(boundary_bytes)
                if boundary.get("status") != "success" or boundary.get("probe_sha256") != sha(Path(boundary_probe.__file__).read_bytes()):
                    raise ValueError("A5FC4 boundary report does not match the current source")
                if boundary.get("kernel_sha256") != source.KERNEL_SHA or boundary.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("A5FC4 boundary report input identities differ")
                lookup = {input_key(row): row for row in boundary["results"]}
                inputs = selected_inputs()
                rows, pairs = [], []
                emu = pinned.interpreter(args.saturn_recomp)
                for values in inputs:
                    start = lookup.get(values)
                    if start is None:
                        raise ValueError(f"missing A5FC4 boundary state for {values!r}")
                    first = execute_tail(kernel, ram, emu, start)
                    second = execute_tail(kernel, ram, emu, start)
                    if first != second:
                        raise ValueError(f"paired A717C tail continuation differs: {values!r}")
                    rows.append(first)
                    pairs.append(start)
                control_start = lookup[inputs[0]]
                try:
                    execute_tail(kernel, ram, emu, control_start, mutation=(CALL_A600C, 0x0009))
                except ValueError as error:
                    mutation_reason = str(error)
                    if "tail path differs" not in mutation_reason:
                        raise
                else:
                    raise ValueError("A717C tail A600C JSR-to-NOP mutation was not detected")
                result_bytes = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, boundary_report_sha256=sha(boundary_bytes),
                    boundary_probe_sha256=boundary.get("probe_sha256"), cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(result_bytes), probe_sha256=sha(Path(__file__).read_bytes()),
                    kernel_sha256=source.KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA,
                    source_range_sha256={"A717C_tail":sha(kernel[ENTRY-source.BASE:STOP-source.BASE]),
                        "A600C":sha(kernel[a600c.ENTRY-source.BASE:a600c.END-source.BASE]),
                        "A6100":sha(kernel[CALL_A6100-source.BASE:0x060A6112-source.BASE]),
                        "A595B6":sha(kernel[a600c.SHIFT_LEAF-source.BASE:a600c.SHIFT_END-source.BASE])},
                    mutation_control={"address":hex(CALL_A600C),"original":"0x430B","replacement":"0x0009",
                        "rejected":True,"reason":mutation_reason},
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    contract="The exact serialized A717C state returned from A5FC4 continues through A600C and A6100 to PC 060A723C, immediately before A717C calls A5F98. Original A600C descriptor reads and DMAC/DRCR/CHCR writes, followed by A6100's CHCR.DE write, match the bounded register fixture.")
            except Exception as error:
                report["error"] = {"type":type(error).__name__,"reason":str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
    except OSError as error:
        print(f"FAIL: fresh report path required: {error}")
        return 1
    print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
