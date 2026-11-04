#!/usr/bin/env python3
"""Trace the Japan startup caller through A9E988 and SYS_SETUINT service 65."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import probe_japan_a717c_zero_divisor as source
import state_graphics as sg

KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
KERNEL_BASE, KERNEL_SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
CALLER, STOP = 0x0600A338, 0x0600A350
HELPER, HELPER_END = 0x0609E988, 0x0609E9AE
SETUINT_STUB, CHGSCUIM_STUB = 0x06000794, 0x060007C0
SLOT, CHG_SLOT, MASK_SLOT = 0x06000300, 0x06000344, 0x06000348
TABLE_ENTRY, TABLE_BASE = 0x06000A04, 0x06000900
SP, RETURN = 0x06002000, 0xFFFFFE00
LIMIT = 64
SR = 0xF0
CALLER_LITERALS = {0x0600A3B8: (4, CHG_SLOT), 0x0600A3BC: (4, HELPER),
                   0x0600A3C0: (4, SLOT),
                   0x0600A3C4: (4, 0x0600A308)}
HELPER_LITERALS = {
    0x0609E9BC: (4, 0x060BC678), 0x0609E9C0: (4, 0x060BC67C),
    0x0609E9B8: (4, 0x060BC680), 0x0609E9C4: (4, 0x060BC684),
    0x0609E9B4: (4, 0x060BC688), 0x0609E9B0: (4, 0x060BC68C),
    0x0609E9C8: (4, 0x060BC690), 0x0609E9CC: (4, 0x060FCBF8),
}
STUB_LITERALS = {0x060007A4: (4, TABLE_BASE)}
CHG_LITERALS = {0x060007E8: (4, 0x25FE00A0), 0x060007EC: (4, MASK_SLOT),
                0x06000828: (2, 0x00F0)}
STUB_PCS = (0x06000794, 0x06000796, 0x06000798, 0x0600079A,
            0x0600079C, 0x0600079E, 0x060007A0)
MASK = 0xFFFFFFFF


class Fence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def case_inputs():
    return [(seed, 0x1800 + seed * 4, 0x76000000 + seed * 0x01010101)
            for seed in range(4)]


def execute(kernel, ram, emu, seed, stack_pr, mutate_pointer=False, mutate_vector=False,
            mutate_chgscuim=False):
    if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start, end in ((CALLER, STOP), (HELPER, HELPER_END)):
        if ram[start - WRAM:end - WRAM] != kernel[start - KERNEL_BASE:end - KERNEL_BASE]:
            raise ValueError(f"captured original code differs at {start:08x}")
    if int.from_bytes(ram[SLOT - WRAM:SLOT - WRAM + 4], "big") != SETUINT_STUB:
        raise ValueError("captured SYS_SETUINT vector differs")
    if int.from_bytes(ram[CHG_SLOT - WRAM:CHG_SLOT - WRAM + 4], "big") != CHGSCUIM_STUB:
        raise ValueError("captured SYS_CHGSCUIM vector differs")
    if int.from_bytes(ram[MASK_SLOT - WRAM:MASK_SLOT - WRAM + 4], "big") != 0xFFFFD77C:
        raise ValueError("frame-1200 SCU interrupt mask differs")
    expected_initial = int.from_bytes(ram[TABLE_ENTRY - WRAM:TABLE_ENTRY - WRAM + 4], "big")
    if expected_initial != 0x0600B344:
        raise ValueError("frame-1200 service-65 table word differs")

    work = bytearray(ram)
    if mutate_pointer:
        work[0x0600A3C4 - WRAM:0x0600A3C8 - WRAM] = (0x0600A30C).to_bytes(4, "big")
    if mutate_vector:
        work[SLOT - WRAM:SLOT - WRAM + 4] = (0x06000702).to_bytes(4, "big")
    if mutate_chgscuim:
        work[0x060007E8 - WRAM:0x060007EC - WRAM] = (0x25FE0080).to_bytes(4, "big")
    reads, writes, pcs = [], [], []
    exec_ranges = ((CALLER, STOP), (HELPER, HELPER_END), (CHGSCUIM_STUB, 0x060007E6))
    executable = lambda pc: any(lo <= pc < hi for lo, hi in exec_ranges) or pc in STUB_PCS
    literals = {**CALLER_LITERALS, **HELPER_LITERALS, **STUB_LITERALS, **CHG_LITERALS}

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__(); self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not executable(address):
                    raise Fence(f"startup SETUINT PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in literals and literals[address][0] == width:
                if mutate_pointer and address == 0x0600A3C4 or mutate_chgscuim and address == 0x060007E8:
                    value = super().read(address, width)
                else:
                    value = literals[address][1]
                reads.append(["original-literal", address, width, value]); return value
            if address == SLOT and width == 4:
                value = super().read(address, width); reads.append(["captured-vector", address, width, value]); return value
            if address == CHG_SLOT and width == 4:
                value = super().read(address, width); reads.append(["captured-vector", address, width, value]); return value
            if address == MASK_SLOT and width == 4:
                value = super().read(address, width); reads.append(["captured-scu-mask", address, width, value]); return value
            if address == TABLE_ENTRY and width == 4:
                value = super().read(address, width); reads.append(["captured-service-65-entry", address, width, value]); return value
            raise ValueError(f"unexpected startup SETUINT read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= MASK
            if 0x25FE0000 <= address < 0x25FE0100:
                if address not in (0x25FE00A0, 0x25FE00A4, 0x25FE00A8):
                    raise ValueError(f"unexpected SCU MMIO write {address:08x}/{width}/{value:08x}")
                expected = {0x25FE00A0: 0xFFFFD77E, 0x25FE00A4: 0xFFFFFFFF,
                            0x25FE00A8: 0x00000000}[address]
                if width != 4 or value != expected:
                    raise ValueError(f"unexpected SCU MMIO write {address:08x}/{width}/{value:08x}")
                writes.append(["scu-mmio-intent", address, width, value]); return
            if address == MASK_SLOT and width == 4 and value == 0xFFFFD77E:
                writes.append(["scu-mask-state", address, width, value]); return super().write(address, width, value)
            if width == 2 and address == 0x060BC678 and value == 0:
                writes.append(["startup-state", address, width, value]); return super().write(address, width, value)
            if width == 4 and address in (0x060BC67C, 0x060BC680, 0x060BC684, 0x060BC688,
                                          0x060BC68C, 0x060BC690, 0x060FCBF8):
                expected = 1 if address == 0x060BC67C else 0
                if value != expected: raise ValueError(f"A9E988 state value differs at {address:08x}")
                writes.append(["startup-state", address, width, value]); return super().write(address, width, value)
            if address == TABLE_ENTRY and width == 4 and value == 0x0600A308:
                writes.append(["sys-setuint-service-65", address, width, value]); return super().write(address, width, value)
            raise ValueError(f"unexpected startup SETUINT write {address:08x}/{width}/{value:08x}")

    mem = Memory(); work_mem = mem.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try: return super().fetch(pc)
            finally: mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not executable(pc):
                raise Fence(f"startup SETUINT instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x38000000 + n * 0x01020307 + seed * 0x101) & MASK for n in range(16)]
    cpu.r[0], cpu.r[1], cpu.r[2], cpu.r[3] = 0xDEADBEEF, 0xA1000001, 0xA2000002, 0xA3000003
    cpu.r[4], cpu.r[5], cpu.r[10], cpu.r[15] = 0xFFFFFFFD, 2, 0xBAD0BAD0, SP - 4
    cpu.sr, cpu.vbr, cpu.pr, cpu.pc = SR, 0x06000000, RETURN, CALLER
    before = bytes(work_mem)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > LIMIT: raise ValueError("startup SETUINT instruction budget exceeded")
    expected_writes = [
        ["scu-mask-state", MASK_SLOT, 4, 0xFFFFD77E],
        ["scu-mmio-intent", 0x25FE00A0, 4, 0xFFFFD77E],
        ["scu-mmio-intent", 0x25FE00A4, 4, 0xFFFFFFFF],
        ["startup-state", 0x060BC678, 2, 0], ["startup-state", 0x060BC67C, 4, 1],
        ["startup-state", 0x060BC680, 4, 0], ["startup-state", 0x060BC684, 4, 0],
        ["startup-state", 0x060BC688, 4, 0], ["startup-state", 0x060BC68C, 4, 0],
        ["startup-state", 0x060BC690, 4, 0], ["startup-state", 0x060FCBF8, 4, 0],
        ["sys-setuint-service-65", TABLE_ENTRY, 4, 0x0600A308],
    ]
    if writes != expected_writes: raise ValueError(f"unexpected startup writes {writes!r}")
    expected = bytearray(before)
    for label, address, width, value in writes:
        if label in ("scu-mmio-intent",): continue
        off = address - WRAM; expected[off:off + width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected): raise ValueError("unlisted startup WorkRAM-H mutation")
    if cpu.r[15] != SP - 4 or cpu.pr != STOP or cpu.r[4] != 65 * 4 or cpu.r[5] != 0x0600A308 or cpu.r[10] != CHG_SLOT:
        raise ValueError(f"startup SETUINT return differs: sp={cpu.r[15]:08x} pr={cpu.pr:08x} r4={cpu.r[4]:08x} r5={cpu.r[5]:08x} r10={cpu.r[10]:08x}")
    if cpu.sr != SR: raise ValueError("startup SETUINT changed caller SR")
    return {"seed": seed, "stack_saved_pr": hex(stack_pr), "r10_chgscuim_slot": hex(cpu.r[10]),
            "steps": cpu.steps, "pc_trace": [hex(pc) for pc in pcs], "reads": reads, "writes": writes,
            "return_pc": hex(cpu.pc), "return_pr": hex(cpu.pr), "r4_service": cpu.r[4],
            "r5_table_value": hex(cpu.r[5]), "sr_after": hex(cpu.sr), "sp_after": hex(cpu.r[15]),
            "table_service_65_after": hex(0x0600A308),
            "workram_bytes_unchanged_outside_mask_slot_eight_helper_stores_and_one_table_store": WRAM_SIZE - 4 - 2 - 7 * 4 - 4}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-startup-setuint65.v1", "status": "failure",
              "entry": hex(CALLER), "stop": hex(STOP), "helper": hex(HELPER),
              "limits": ["Starts at constructed boundary PC 0x0600A338 after earlier startup prologue/calls; executes original SYS_CHGSCUIM callsite/runtime, A9E988 helper and SYS_SETUINT callsite to return PC 0x0600A350",
                         "Uses frame-1200 WorkRAM-H captured SYS_SETUINT vector/runtime stub; runtime stub not established as BIOS-ROM copy",
                         "SCU writes are captured intent events; no Saturn hardware timing, earlier startup calls, polling loop, later initialization or natural caller is included"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text()); state = pinned.read_bounded(args.state, source.STATE_MAX)
                if meta.get("frame") != 1200 or sha(state) != STATE_SHA or meta.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state/checkpoint identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if sha(kernel) != KERNEL_SHA: raise ValueError("original Japan kernel identity differs")
                ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for seed, pr, _ in case_inputs():
                    a = execute(kernel, ram, emu, seed, pr)
                    b = execute(kernel, ram, emu, seed, pr)
                    if a != b: raise ValueError("paired startup SETUINT executions differ")
                    rows.append(a)
                try:
                    execute(kernel, ram, emu, 0, 0x1800, mutate_pointer=True)
                except ValueError as error:
                    if "unexpected startup setuint write 06000a04/4/0600a30c" not in str(error).lower():
                        raise ValueError("service-65 pointer mutation failed outside table-write contract") from error
                    pointer_mutation = {"rejected": True, "literal": "0x0600A3C4", "replacement": "0x0600A30C", "reason": str(error)}
                else: raise ValueError("mutated service-65 table pointer was accepted")
                try:
                    execute(kernel, ram, emu, 0, 0x1800, mutate_vector=True)
                except Fence as error:
                    if "pc fence" not in str(error).lower(): raise
                    vector_mutation = {"rejected": True, "slot": hex(SLOT), "target": "0x06000702", "reason": str(error)}
                else: raise ValueError("mutated startup setter vector escaped PC fence")
                try:
                    execute(kernel, ram, emu, 0, 0x1800, mutate_chgscuim=True)
                except ValueError as error:
                    if "unexpected scu mmio write 25fe0080" not in str(error).lower():
                        raise ValueError("SCU address mutation failed outside MMIO contract") from error
                    chg_mutation = {"rejected": True, "literal": "0x060007E8", "replacement": "0x25FE0080", "reason": str(error)}
                else: raise ValueError("mutated SCU write address was accepted")
                code = kernel[CALLER - KERNEL_BASE:STOP - KERNEL_BASE]
                helper = kernel[HELPER - KERNEL_BASE:HELPER_END - KERNEL_BASE]
                report.update(status="success", cases=len(rows), executions_per_case=2, results=rows,
                              results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                              kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA, normalized_workram_sha256=sha(ram),
                              caller_sha256=sha(code), helper_sha256=sha(helper), probe_sha256=sha(Path(__file__).read_bytes()),
                              setuint_stub_sha256=sha(ram[SETUINT_STUB - WRAM:0x060007A4 - WRAM]),
                              mutations={"service65_pointer": pointer_mutation, "setuint_vector": vector_mutation,
                                         "scu_mmio_address": chg_mutation},
                              interpreter_revision="f20de940e8013fc84103a5b39c4069ed8071b1f9")
            except Exception as e: report["error"] = {"type": type(e).__name__, "reason": str(e)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"})); return 2


if __name__ == "__main__":
    raise SystemExit(main())
