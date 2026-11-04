#!/usr/bin/env python3
"""Continue original Japan A61B0 through its captured SYS_GETSINT call."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import probe_japan_a717c_zero_divisor as source
import state_graphics as sg

BASE, KERNEL_SIZE = 0x0600A000, 786432
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
ENTRY, STOP = 0x060A61B0, 0x060A6236
GETUINT_STUB = 0x0600077C
GETSINT_STUB = 0x06000774
STUB_PCS = (0x06000774, 0x06000776, 0x06000778, 0x0600077A,
            0x0600077C, 0x0600077E, 0x06000780, 0x06000782)
GETUINT_SLOT, GETSINT_SLOT = 0x06000304, 0x06000314
GETUINT_TABLE_BASE, GETUINT_TABLE_ENTRY = 0x06000900, 0x06000A2C
VBR_ENTRY, EXPECTED_VBR = 0x0600012C, 0x06000000
EXPECTED_GETUINT, EXPECTED_GETSINT = 0x0600083C, 0x0600087C
GLOBAL = 0x060FCD14
SP, STACK_SIZE = 0x06002000, 40
STACK_BASE = SP - STACK_SIZE
WORKRAM_BASE, WORKRAM_SIZE = 0x06000000, 0x100000
LIMIT = 64
SR_VALUES, SEEDS = (0x030, 0x130, 0x230, 0x3F0), (0, 1)
RETURN_SENTINEL = 0xFFFFFE00
MASK = 0xFFFFFFFF
LITERALS = {
    0x060A61E8: (2, 0xFF0F),
    0x060A61F8: (4, 0x060A62D8),
    0x060A62B8: (4, GLOBAL),
    0x060A62BC: (4, GETUINT_SLOT),
    0x060A62C0: (4, 0x060FCD20),
    0x060A62C4: (4, GETSINT_SLOT),
}


class PathFence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(sr, seed) for sr in SR_VALUES for seed in SEEDS]


def execute(kernel: bytes, ram: bytes, emu, sr: int, seed: int, vbr: int,
            mutate_getsint: bool = False) -> dict:
    if sr not in SR_VALUES or seed not in SEEDS:
        raise ValueError("A61B0 input outside declared corpus")
    if vbr != EXPECTED_VBR:
        raise ValueError(f"captured frame-1200 VBR differs: {vbr:08x}")
    if len(kernel) != KERNEL_SIZE or len(ram) != WORKRAM_SIZE:
        raise ValueError("Complete original kernel and normalized WorkRAM-H required")
    if ram[ENTRY - WORKRAM_BASE:STOP - WORKRAM_BASE] != kernel[ENTRY - BASE:STOP - BASE]:
        raise ValueError("captured A61B0 source differs from original Japan kernel")

    captured_values = {
        GETUINT_SLOT: GETUINT_STUB,
        GETSINT_SLOT: GETSINT_STUB,
        GETUINT_TABLE_ENTRY: EXPECTED_GETUINT,
        VBR_ENTRY: EXPECTED_GETSINT,
    }
    for address, expected in captured_values.items():
        value = int.from_bytes(ram[address - WORKRAM_BASE:address - WORKRAM_BASE + 4], "big")
        if value != expected:
            raise ValueError(f"captured runtime word differs at {address:08x}: {value:08x}")
    if int.from_bytes(ram[0x060007A4 - WORKRAM_BASE:0x060007A8 - WORKRAM_BASE], "big") != GETUINT_TABLE_BASE:
        raise ValueError("captured SYS_GETUINT base literal differs")

    work = bytearray(ram)
    if mutate_getsint:
        work[GETSINT_SLOT - WORKRAM_BASE:GETSINT_SLOT - WORKRAM_BASE + 4] = (0x06000794).to_bytes(4, "big")
    stack = bytearray((0x8B + seed * 31 + i * 17) & 0xFF for i in range(STACK_SIZE))
    stack_off = STACK_BASE - WORKRAM_BASE
    work[stack_off:stack_off + STACK_SIZE] = stack
    reads, writes, pcs = [], [], []
    executable = lambda pc: ENTRY <= pc < STOP or pc in STUB_PCS

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not executable(address):
                    raise PathFence(f"A61B0/SYS_GETSINT PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = LITERALS[address][1]
                reads.append(["kernel-literal", address, width, value])
                return value
            if address in (GETUINT_SLOT, GETSINT_SLOT) and width == 4:
                value = super().read(address, width)
                reads.append(["captured-system-vector", address, width, value])
                return value
            if address == 0x060007A4 and width == 4:
                value = super().read(address, width)
                reads.append(["captured-getuint-base", address, width, value])
                return value
            if address in (GETUINT_TABLE_ENTRY, VBR_ENTRY) and width == 4:
                value = super().read(address, width)
                label = "captured-getuint-entry" if address == GETUINT_TABLE_ENTRY else "captured-vbr-entry"
                reads.append([label, address, width, value])
                return value
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                value = super().read(address, width)
                reads.append(["constructed-stack", address, width, value])
                return value
            raise ValueError(f"unexpected A61B0/SYS_GETSINT read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= MASK
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                writes.append(["constructed-stack", address, width, value])
                return super().write(address, width, value)
            if address == GLOBAL and width == 4 and value == EXPECTED_GETUINT:
                writes.append(["global-result", address, width, value])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A61B0/SYS_GETSINT write {address:08x}/{width}/{value:08x}")

    mem = Memory()
    work_mem = mem.add(WORKRAM_BASE, WORKRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not executable(pc):
                raise PathFence(f"A61B0/SYS_GETSINT instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x46000000 + i * 0x01020305 + seed * 0x10001) & MASK for i in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[15] = 0xDEADBEEF, 0, SP
    cpu.sr, cpu.vbr, cpu.pr, cpu.pc = sr, vbr, RETURN_SENTINEL, ENTRY
    before = bytes(work_mem)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A61B0/SYS_GETSINT instruction budget exceeded")

    if tuple(pcs[-6:]) != (0x060A6232, 0x060A6234, 0x06000774, 0x06000776, 0x06000778, 0x0600077A):
        raise ValueError(f"A61B0 SYS_GETSINT path suffix differs: {pcs[-6:]!r}")
    if cpu.r[0] != EXPECTED_GETSINT or cpu.r[4] != 75 * 4 or cpu.r[1] != GETSINT_STUB:
        raise ValueError(f"captured SYS_GETSINT result/register contract differs: r0={cpu.r[0]:08x} r4={cpu.r[4]:08x} r1={cpu.r[1]:08x}")
    if cpu.r[8] != 0x060FCD20 or cpu.r[12] != 0x060A62D8 or cpu.r[14] != 75:
        raise ValueError("A61B0 second BIOS-call arguments differ")
    if cpu.r[15] != SP - 28 or cpu.pr != STOP or cpu.vbr != vbr:
        raise ValueError("A61B0 stack, PR or captured VBR differs at second BIOS return")
    if cpu.sr & 0xF0 != 0xF0:
        raise ValueError("A61B0 interrupt priority differs at SYS_GETSINT return")
    stack_writes = [row for row in writes if row[0] == "constructed-stack"]
    globals_writes = [row for row in writes if row[0] == "global-result"]
    if len(stack_writes) != 7 or globals_writes != [["global-result", GLOBAL, 4, EXPECTED_GETUINT]]:
        raise ValueError("A61B0 stack/global write contract differs")
    if len(reads) != 12:
        raise ValueError(f"A61B0/SYS_GETSINT read count differs: {len(reads)}")
    final = bytes(work_mem)
    expected = bytearray(before)
    for label, address, width, value in writes:
        start = address - WORKRAM_BASE
        expected[start:start + width] = value.to_bytes(width, "big")
    if final != bytes(expected):
        first = next(i for i, (actual, want) in enumerate(zip(final, expected)) if actual != want)
        raise ValueError(f"unexpected captured WorkRAM-H mutation at {WORKRAM_BASE + first:08x}")
    return {
        "sr_input": sr, "seed": seed, "steps": cpu.steps,
        "pc_trace": [hex(pc) for pc in pcs], "reads": reads, "writes": writes,
        "r0_return": hex(cpu.r[0]), "r4_scaled_index": cpu.r[4],
        "r1_runtime_vector": hex(cpu.r[1]), "r8_second_global": hex(cpu.r[8]),
        "r12_service_table": hex(cpu.r[12]), "r14_service_number": cpu.r[14],
        "vbr": hex(cpu.vbr), "sp_after_frame": hex(cpu.r[15]),
        "pr_after_call": hex(cpu.pr),
        "workram_bytes_unchanged_outside_declared_stack_and_global": WORKRAM_SIZE - STACK_SIZE - 4,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {
        "schema": "neptune.original-japan-a61b0-getsint-runtime.v1",
        "status": "failure", "entry": hex(ENTRY), "stop": hex(STOP),
        "getsint_vector_slot": hex(GETSINT_SLOT), "getsint_stub": hex(GETSINT_STUB),
        "vbr_entry": hex(VBR_ENTRY),
        "limits": [
            "Original Japanese A61B0 bytes and captured frame-1200 SYS_GETUINT/SYS_GETSINT runtime bytes",
            "Uses captured master-SH2 VBR and WorkRAM-H vector words; stubs are not identified as BIOS-ROM copies",
            "Stops after SYS_GETSINT returns at 0x060A6236, before its result store and later services",
            "Constructed registers/stack; one original global store is allowed; no SCU side effect modeled",
        ],
    }
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                meta = json.loads(args.checkpoint.read_text())
                if meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != source.CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, source.STATE_MAX)
                if sha(state) != source.STATE_SHA or meta.get("state_sha256") != source.STATE_SHA:
                    raise ValueError("frame-1200 checkpoint state identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA:
                    raise ValueError("Japanese kernel identity differs")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != source.RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                ctrl = sg.field(parsed, "SH2-M", "CtrlRegs", 12)
                vbr = int.from_bytes(ctrl[8:12], "little")
                if vbr != EXPECTED_VBR:
                    raise ValueError("captured master-SH2 VBR differs")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for sr, seed in corpus():
                    first = execute(kernel, ram, emu, sr, seed, vbr)
                    second = execute(kernel, ram, emu, sr, seed, vbr)
                    if first != second:
                        raise ValueError("paired A61B0/SYS_GETSINT executions differ")
                    rows.append(first)
                try:
                    execute(kernel, ram, emu, SR_VALUES[-1], SEEDS[0], vbr, mutate_getsint=True)
                except PathFence as error:
                    if "pc fence" not in str(error).lower():
                        raise ValueError("SYS_GETSINT vector mutation failed unexpectedly") from error
                    mutation_rejected = True
                else:
                    raise ValueError("mutated SYS_GETSINT target crossed its source fence")
                code = kernel[ENTRY - BASE:STOP - BASE]
                stub_range = ram[GETSINT_STUB - WORKRAM_BASE:GETUINT_STUB + 8 - WORKRAM_BASE]
                report.update(
                    status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, captured_runtime_service_bytes_executed=True,
                    cases=len(rows), executions_per_case=2, results=rows,
                    results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                    kernel_sha256=KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA, captured_vbr=hex(vbr),
                    probe_sha256=sha(Path(__file__).read_bytes()), a61b0_source_sha256=sha(code),
                    runtime_stub_range_sha256=sha(stub_range),
                    getsint_slot_sha256=sha(ram[GETSINT_SLOT - WORKRAM_BASE:GETSINT_SLOT - WORKRAM_BASE + 4]),
                    vbr_entry_sha256=sha(ram[VBR_ENTRY - WORKRAM_BASE:VBR_ENTRY - WORKRAM_BASE + 4]),
                    getuint_entry_sha256=sha(ram[GETUINT_TABLE_ENTRY - WORKRAM_BASE:GETUINT_TABLE_ENTRY - WORKRAM_BASE + 4]),
                    interpreter_revision=pinned.INTERPRETER_REVISION, interpreter_sources=pinned.SOURCE_HASHES,
                    mutation_control={"slot": hex(GETSINT_SLOT), "replacement": "0x06000794",
                                      "rejected": mutation_rejected, "reason": "mutated SYS_GETSINT vector escaped captured GET runtime PC fence"},
                    contract="Original A61B0 stores captured SYS_GETUINT result 0x0600083C at 0x060FCD14, calls the captured SYS_GETSINT stub at 0x06000774 with R4=75 and captured VBR 0x06000000, then receives VBR[75]=0x0600087C from 0x0600012C and returns to PC 0x060A6236. The second result is not stored yet.")
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
