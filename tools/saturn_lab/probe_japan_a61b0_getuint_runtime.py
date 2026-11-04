#!/usr/bin/env python3
"""Continue Japan A61B0 through the captured SYS_GETUINT runtime stub."""
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
ENTRY, STOP = 0x060A61B0, 0x060A6224
STUB = 0x0600077C
STUB_PCS = (0x0600077C, 0x0600077E, 0x06000780, 0x06000782)
BIOS_SLOT, STUB_LITERAL, TABLE_BASE = 0x06000304, 0x060007A4, 0x06000900
SERVICE_INDEX = 75
TABLE_WORD = TABLE_BASE + 4 * SERVICE_INDEX
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
    0x060A62BC: (4, BIOS_SLOT),
}


class PathFence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(sr, seed) for sr in SR_VALUES for seed in SEEDS]


def execute(kernel: bytes, ram: bytes, emu, sr: int, seed: int,
            mutate_vector: bool = False) -> dict:
    if sr not in SR_VALUES or seed not in SEEDS:
        raise ValueError("A61B0 input outside declared corpus")
    if len(kernel) != KERNEL_SIZE or len(ram) != WORKRAM_SIZE:
        raise ValueError("Complete original kernel and normalized WorkRAM-H required")
    if ram[ENTRY - WORKRAM_BASE:STOP - WORKRAM_BASE] != kernel[ENTRY - BASE:STOP - BASE]:
        raise ValueError("captured A61B0 source differs from original Japan kernel")
    if int.from_bytes(ram[BIOS_SLOT - WORKRAM_BASE:BIOS_SLOT - WORKRAM_BASE + 4], "big") != STUB:
        raise ValueError("frame-1200 SYS_GETUINT vector differs")
    if int.from_bytes(ram[STUB_LITERAL - WORKRAM_BASE:STUB_LITERAL - WORKRAM_BASE + 4], "big") != TABLE_BASE:
        raise ValueError("captured SYS_GETUINT table literal differs")
    if int.from_bytes(ram[TABLE_WORD - WORKRAM_BASE:TABLE_WORD - WORKRAM_BASE + 4], "big") != 0x0600083C:
        raise ValueError("frame-1200 SYS_GETUINT entry 75 differs")

    work = bytearray(ram)
    if mutate_vector:
        # Private-copy control only. This points at a different captured stub,
        # which the execution PC fence must reject.
        work[BIOS_SLOT - WORKRAM_BASE:BIOS_SLOT - WORKRAM_BASE + 4] = (0x06000774).to_bytes(4, "big")
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
                    raise PathFence(f"A61B0/SYS_GETUINT PC fence at {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = LITERALS[address][1]
                reads.append(["kernel-literal", address, width, value])
                return value
            if address == BIOS_SLOT and width == 4:
                value = int.from_bytes(work[address - WORKRAM_BASE:address - WORKRAM_BASE + width], "big")
                reads.append(["captured-system-vector", address, width, value])
                return value
            if address == STUB_LITERAL and width == 4:
                value = super().read(address, width)
                reads.append(["captured-stub-literal", address, width, value])
                return value
            if address == TABLE_WORD and width == 4:
                value = super().read(address, width)
                reads.append(["captured-SYS_GETUINT-entry", address, width, value])
                return value
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                value = super().read(address, width)
                reads.append(["constructed-stack", address, width, value])
                return value
            raise ValueError(f"unexpected A61B0/SYS_GETUINT read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= MASK
            if STACK_BASE <= address and address + width <= SP and width == 4 and (address - STACK_BASE) % 4 == 0:
                writes.append(["constructed-stack", address, width, value])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A61B0/SYS_GETUINT write {address:08x}/{width}")

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
                raise PathFence(f"A61B0/SYS_GETUINT instruction fence at {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x46000000 + i * 0x01020305 + seed * 0x10001) & MASK for i in range(16)]
    cpu.r[0], cpu.r[4], cpu.r[15] = 0xDEADBEEF, 0, SP
    cpu.sr, cpu.pr, cpu.pc = sr, RETURN_SENTINEL, ENTRY
    before = bytes(work_mem)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A61B0/SYS_GETUINT instruction budget exceeded")

    if tuple(pcs[-6:]) != (0x060A6220, 0x060A6222, *STUB_PCS):
        raise ValueError(f"A61B0 call/return suffix differs: {pcs[-6:]!r}")
    if cpu.r[0] != 0x0600083C or cpu.r[4] != SERVICE_INDEX * 4 or cpu.r[1] != STUB:
        raise ValueError(
            "captured SYS_GETUINT result/register contract differs: "
            f"r0={cpu.r[0]:08x} r4={cpu.r[4]:08x} r1={cpu.r[1]:08x}"
        )
    if cpu.r[8] != GLOBAL or cpu.r[12] != 0x060A62D8 or cpu.r[14] != SERVICE_INDEX:
        raise ValueError("A61B0 first BIOS-call arguments differ")
    if cpu.pc != STOP or cpu.pr != STOP or cpu.r[15] != SP - 28:
        raise ValueError("A61B0 did not return from captured SYS_GETUINT to 0x060A6224")
    if cpu.sr & 0xF0 != 0xF0:
        raise ValueError("A61B0 interrupt priority differs at BIOS return")
    if any(row[0] != "constructed-stack" for row in writes):
        raise ValueError("unexpected non-stack write")
    if len(writes) != 7:
        raise ValueError(f"A61B0 stack write count differs: {len(writes)}")
    if len(reads) != 7:
        raise ValueError(f"A61B0/BIOs read count differs: {len(reads)}")
    final = bytes(work_mem)
    expected = bytearray(before)
    for _, address, width, value in writes:
        start = address - WORKRAM_BASE
        expected[start:start + width] = value.to_bytes(width, "big")
    if final != bytes(expected):
        first = next(i for i, (actual, want) in enumerate(zip(final, expected)) if actual != want)
        raise ValueError(f"unexpected captured WorkRAM-H mutation at {WORKRAM_BASE + first:08x}")
    return {
        "sr_input": sr, "seed": seed, "steps": cpu.steps,
        "pc_trace": [hex(pc) for pc in pcs], "reads": reads, "writes": writes,
        "r0_return": hex(cpu.r[0]), "r4_scaled_index": cpu.r[4],
        "r1_runtime_vector": hex(cpu.r[1]), "r8_result_global": hex(cpu.r[8]),
        "r12_service_table": hex(cpu.r[12]), "r14_service_number": cpu.r[14],
        "sp_after_frame": hex(cpu.r[15]), "pr_after_call": hex(cpu.pr),
        "workram_bytes_unchanged_outside_stack": WORKRAM_SIZE - STACK_SIZE,
        "stack_sha256": sha(bytes(work_mem[stack_off:stack_off + STACK_SIZE])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {
        "schema": "neptune.original-japan-a61b0-getuint-runtime.v1",
        "status": "failure", "entry": hex(ENTRY), "stop": hex(STOP),
        "runtime_vector_slot": hex(BIOS_SLOT), "runtime_stub": hex(STUB),
        "runtime_table_entry": hex(TABLE_WORD),
        "limits": [
            "Original Japanese A61B0 bytes plus captured frame-1200 SYS_GETUINT stub/table only",
            "The captured runtime stub is not identified as bytes copied directly from the BIOS ROM",
            "Stops at A61B0 PC 0x060A6224 before the result is stored or the next BIOS call",
            "Constructed stack and register seeds; no BIOS hardware/device effect or natural caller claim",
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
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for sr, seed in corpus():
                    first = execute(kernel, ram, emu, sr, seed)
                    second = execute(kernel, ram, emu, sr, seed)
                    if first != second:
                        raise ValueError("paired A61B0/SYS_GETUINT executions differ")
                    rows.append(first)
                try:
                    execute(kernel, ram, emu, SR_VALUES[-1], SEEDS[0], mutate_vector=True)
                except PathFence as error:
                    if "pc fence" not in str(error).lower():
                        raise ValueError("runtime-vector mutation failed for an unexpected reason") from error
                    mutation_rejected = True
                else:
                    raise ValueError("mutated runtime-vector target crossed its source fence")
                report.update(
                    status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, runtime_service_bytes_from_snapshot=True,
                    cases=len(rows), executions_per_case=2, results=rows,
                    results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                    kernel_sha256=KERNEL_SHA, state_sha256=source.STATE_SHA,
                    normalized_workram_sha256=source.RAM_SHA, probe_sha256=sha(Path(__file__).read_bytes()),
                    a61b0_source_sha256=sha(kernel[ENTRY - BASE:STOP - BASE]),
                    captured_stub_sha256=sha(ram[STUB - WORKRAM_BASE:STUB - WORKRAM_BASE + 8]),
                    captured_stub_literal_sha256=sha(ram[STUB_LITERAL - WORKRAM_BASE:STUB_LITERAL - WORKRAM_BASE + 4]),
                    captured_vector_sha256=sha(ram[BIOS_SLOT - WORKRAM_BASE:BIOS_SLOT - WORKRAM_BASE + 4]),
                    captured_table_entry_sha256=sha(ram[TABLE_WORD - WORKRAM_BASE:TABLE_WORD - WORKRAM_BASE + 4]),
                    interpreter_revision=pinned.INTERPRETER_REVISION, interpreter_sources=pinned.SOURCE_HASHES,
                    mutation_control={"runtime_vector_slot": hex(BIOS_SLOT), "replacement": "0x06000774",
                                      "rejected": mutation_rejected, "reason": "mutated call target escaped the captured SYS_GETUINT PC fence"},
                    contract="Original A61B0 calls the captured frame-1200 vector at 0x06000304 (0x0600077C), which scales service number 75 to 300, indexes the captured 0x06000900 table and returns 0x0600083C to A61B0 PC 0x060A6224. The result store and subsequent services are outside this probe.")
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
