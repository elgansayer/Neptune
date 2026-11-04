#!/usr/bin/env python3
"""Execute original Japan A472 through captured SETUINT and CHGSCUIM stubs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
BASE, KERNEL_SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
CALLER, CALLER_END = 0x0600A324, 0x0600A32C
ENTRY, STOP = 0x0600A472, 0x0600A4C4
CALLER_SP, SENTINEL = 0x06002000, 0xFFFFFE00
STACK_ENTRY = CALLER_SP - 4
PR_FROM_CALLER = 0x0600A32C
TVSTAT, TIMING_A, TIMING_B = 0x25F80004, 0x060BCE88, 0x060BCE8A
WORD_NTSC, WORD_PAL, LINE_DELTA = 0x00DF, 0x00FF, 0x5000
SET_SLOT, CHG_SLOT, MASK_SLOT = 0x06000300, 0x06000344, 0x06000348
SET_STUB, CHG_STUB = 0x06000794, 0x060007C0
TABLE_BASE, SERVICE64, SERVICE65 = 0x06000900, 0x06000A00, 0x06000A04
MASK_BEFORE, MASK_AFTER = 0xFFFFD77C, 0xFFFFD77C
SET_PCS = tuple(range(SET_STUB, 0x060007A2, 2))
CHG_PCS = tuple(range(CHG_STUB, 0x060007E6, 2))
LIMIT = 96
STATUS_SAMPLES = (0x0000, 0x0001, 0x020A, 0x020B)
SR_SAMPLES = (0x000000F0, 0x00000301)
LITERALS = {
    0x0600A50C: (4, TIMING_A), 0x0600A510: (4, TVSTAT),
    0x0600A4DA: (2, WORD_PAL), 0x0600A4DC: (2, WORD_NTSC),
    0x0600A4DE: (2, LINE_DELTA), 0x0600A514: (4, TIMING_B),
    0x0600A4D2: (2, 0xFF0F), 0x0600A518: (4, SET_SLOT),
    0x0600A51C: (4, 0x0600A5E4), 0x0600A520: (4, 0x0600A5EE),
    0x0600A524: (4, CHG_SLOT), 0x060007A4: (4, TABLE_BASE),
    0x060007AC: (4, 0x0600083C), 0x060007EC: (4, MASK_SLOT),
    0x060007E8: (4, 0x25FE00A0), 0x06000828: (2, 0x00F0),
}


class Fence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(tvstat, sr, seed) for tvstat in STATUS_SAMPLES for sr in SR_SAMPLES for seed in range(2)]


def execute(kernel, ram, emu, tvstat, initial_sr, seed, mutate_vector=False,
            mutate_scu_address=False):
    if tvstat not in STATUS_SAMPLES or initial_sr not in SR_SAMPLES or seed not in (0, 1):
        raise ValueError("A472 service input outside declared corpus")
    if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start, end in ((CALLER, CALLER_END), (ENTRY, STOP)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured original code differs at {start:08x}")
    for address, (width, expected) in LITERALS.items():
        actual = int.from_bytes(kernel[address-BASE:address-BASE+width], "big") if address >= BASE else int.from_bytes(ram[address-WRAM:address-WRAM+width], "big")
        if actual != expected:
            raise ValueError(f"original literal differs at {address:08x}: {actual:08x}")
    if int.from_bytes(ram[SET_SLOT-WRAM:SET_SLOT-WRAM+4], "big") != SET_STUB:
        raise ValueError("captured SYS_SETUINT vector differs")
    if int.from_bytes(ram[CHG_SLOT-WRAM:CHG_SLOT-WRAM+4], "big") != CHG_STUB:
        raise ValueError("captured SYS_CHGSCUIM vector differs")
    if int.from_bytes(ram[MASK_SLOT-WRAM:MASK_SLOT-WRAM+4], "big") != MASK_BEFORE:
        raise ValueError("captured SCU interrupt mask differs")
    work = bytearray(ram)
    if mutate_vector:
        work[SET_SLOT-WRAM:SET_SLOT-WRAM+4] = (0x06000702).to_bytes(4, "big")
    if mutate_scu_address:
        work[0x060007E8-WRAM:0x060007EC-WRAM] = (0x25FE0080).to_bytes(4, "big")
    reads, writes, pcs = [], [], []
    stack_values = {STACK_ENTRY: SENTINEL, STACK_ENTRY-4: 0x6D000014+seed,
                    STACK_ENTRY-8: 0x6D000013+seed, STACK_ENTRY-12: PR_FROM_CALLER}
    executable = (tuple(range(CALLER, CALLER_END, 2)) + tuple(range(ENTRY, STOP, 2)) +
                  SET_PCS + CHG_PCS)

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__(); self.fetching = False
        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in executable:
                    raise Fence(f"A472 service PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["original-literal", address, width, value]); return value
            if address == TVSTAT and width == 2:
                reads.append(["mmio-input", address, width, tvstat]); return tvstat
            if address == TIMING_A and width == 2:
                value = super().read(address, width)
                reads.append(["workram-timing-word", address, width, value]); return value
            if address in (SET_SLOT, CHG_SLOT) and width == 4:
                value = super().read(address, width); reads.append(["captured-vector", address, width, value]); return value
            if address == MASK_SLOT and width == 4:
                value = super().read(address, width); reads.append(["captured-scu-mask", address, width, value]); return value
            if address in stack_values and width == 4:
                value = super().read(address, width); reads.append(["stack", address, width, value]); return value
            raise ValueError(f"unexpected A472 service read {address:08x}/{width}")
        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if address in stack_values and width == 4 and value == stack_values[address]:
                writes.append(["entry-stack-save", address, width, value]); return super().write(address, width, value)
            if address in (TIMING_A, TIMING_B) and width == 2:
                pal = bool(tvstat & 1); selected = WORD_PAL if pal else WORD_NTSC
                expected = selected if address == TIMING_A else selected + LINE_DELTA
                if value != expected: raise ValueError(f"A472 timing output differs at {address:08x}: {value:08x}")
                writes.append(["startup-timing", address, width, value]); return super().write(address, width, value)
            if address in (SERVICE64, SERVICE65) and width == 4:
                expected = 0x0600A5E4 if address == SERVICE64 else 0x0600A5EE
                if value != expected: raise ValueError(f"unexpected SYS_SETUINT table write {address:08x}/{width}/{value:08x}")
                writes.append(["sys-setuint", address, width, value]); return super().write(address, width, value)
            if address == MASK_SLOT and width == 4:
                if value != MASK_AFTER: raise ValueError(f"unexpected SCU mask store {value:08x}")
                writes.append(["scu-mask", address, width, value]); return super().write(address, width, value)
            if 0x25FE0000 <= address < 0x25FE0100:
                if address not in (0x25FE00A0, 0x25FE00A4, 0x25FE00A8):
                    raise ValueError(f"unexpected SCU MMIO write {address:08x}/{width}/{value:08x}")
                expected = {0x25FE00A0: MASK_AFTER, 0x25FE00A4: 0xFFFFFFFC, 0x25FE00A8: 1}[address]
                # With R4=-4, cmp/pz branches around the +8 write; it must never occur.
                if address == 0x25FE00A8 or width != 4 or value != expected:
                    raise ValueError(f"unexpected SCU MMIO write {address:08x}/{width}/{value:08x}")
                writes.append(["scu-mmio-intent", address, width, value]); return
            raise ValueError(f"unexpected A472 service write {address:08x}/{width}/{value:08x}")

    mem = Memory(); work_mem = mem.add(WRAM, WRAM_SIZE, work)
    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try: return super().fetch(pc)
            finally: mem.fetching = False
        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in executable:
                raise Fence(f"A472 service instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins, pc, in_slot=in_slot)
    cpu = CPU(mem)
    cpu.r = [(0x4D000000+n*0x01020307+seed*0x101)&0xFFFFFFFF for n in range(16)]
    cpu.r[0], cpu.r[13], cpu.r[14], cpu.r[15] = initial_sr, 0x6D000013+seed, 0x6D000014+seed, CALLER_SP
    cpu.sr, cpu.vbr, cpu.pr, cpu.pc = 0xF0, 0x06000000, SENTINEL, CALLER
    before = bytes(work_mem)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > LIMIT: raise ValueError("A472 service instruction budget exceeded")
    pal = bool(tvstat & 1); selected = WORD_PAL if pal else WORD_NTSC
    expected_writes = [
        ["entry-stack-save", STACK_ENTRY, 4, SENTINEL],
        ["entry-stack-save", STACK_ENTRY-4, 4, 0x6D000014+seed],
        ["entry-stack-save", STACK_ENTRY-8, 4, 0x6D000013+seed],
        ["entry-stack-save", STACK_ENTRY-12, 4, PR_FROM_CALLER],
        ["startup-timing", TIMING_A, 2, selected],
        ["startup-timing", TIMING_B, 2, selected+LINE_DELTA],
        ["sys-setuint", SERVICE64, 4, 0x0600A5E4],
        ["sys-setuint", SERVICE65, 4, 0x0600A5EE],
        ["scu-mask", MASK_SLOT, 4, MASK_AFTER],
        ["scu-mmio-intent", 0x25FE00A0, 4, MASK_AFTER],
        ["scu-mmio-intent", 0x25FE00A4, 4, 0xFFFFFFFC],
    ]
    if writes != expected_writes: raise ValueError(f"A472 service write order differs: {writes!r}")
    expected = bytearray(before)
    for label, address, width, value in writes:
        if label == "scu-mmio-intent": continue
        off = address-WRAM; expected[off:off+width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected): raise ValueError("unlisted A472 WorkRAM-H mutation")
    # SETUINT's final nonzero-pointer TST clears T; A4C0/A4C2 then clears IMASK.
    expected_sr = ((initial_sr & 0x3F3) & 0xFFFFFF0E) & 0xFFFFFF0F
    if cpu.pc != STOP or cpu.pr != 0x0600A4BC or cpu.r[15] != STACK_ENTRY-12 or cpu.sr != expected_sr:
        raise ValueError(f"A472 service stop differs: pc={cpu.pc:08x} pr={cpu.pr:08x} sp={cpu.r[15]:08x} sr={cpu.sr:08x}")
    return {"tvstat_sample": hex(tvstat), "initial_sr": hex(initial_sr), "seed": seed,
            "steps": cpu.steps, "pc_trace": [hex(pc) for pc in pcs], "reads": reads,
            "writes": writes, "stop_pc": hex(cpu.pc), "sr_after": hex(cpu.sr),
            "service64": hex(0x0600A5E4), "service65": hex(0x0600A5EE),
            "scu_mask_after": hex(MASK_AFTER), "workram_unchanged_outside_declared_writes": True}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--"+name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a472-services.v1", "status": "failure",
              "entry": hex(CALLER), "stop": hex(STOP),
              "limits": ["Constructed A324 registers and TVSTAT inputs; executes original A472 timing code, captured frame-1200 SYS_SETUINT/SYS_CHGSCUIM stub bytes and returns to the instruction before BSR A638",
                         "Captured runtime stub bytes and frame-1200 vectors/table are not established as BIOS-ROM provenance or lifetime; SCU writes are intents, not hardware behavior",
                         "No natural caller, device timing or later A638 dependency is included"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, 16*1024*1024)
                if meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA or meta.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if sha(kernel) != KERNEL_SHA: raise ValueError("original Japan kernel identity differs")
                ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
                if sha(ram) != RAM_SHA: raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for status, sr, seed in corpus():
                    a = execute(kernel, ram, emu, status, sr, seed); b = execute(kernel, ram, emu, status, sr, seed)
                    if a != b: raise ValueError("paired A472 service executions differ")
                    rows.append(a)
                try: execute(kernel, ram, emu, 1, SR_SAMPLES[0], 0, mutate_vector=True)
                except Fence as e:
                    if "pc fence" not in str(e).lower(): raise
                    vector_control = {"rejected": True, "replacement": "0x06000702", "reason": str(e)}
                else: raise ValueError("mutated SYS_SETUINT vector escaped PC fence")
                try: execute(kernel, ram, emu, 1, SR_SAMPLES[0], 0, mutate_scu_address=True)
                except ValueError as e:
                    if "unexpected scu mmio write 25fe0080" not in str(e).lower(): raise
                    scu_control = {"rejected": True, "replacement": "0x25FE0080", "reason": str(e)}
                else: raise ValueError("mutated SCU MMIO address was accepted")
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, constructed_tvstat_samples=True,
                    release="Japan T-14302G V1.000", source_file="0KRNL.BIN", cpu="master SH-2",
                    source_ranges=[[hex(CALLER), hex(CALLER_END)], [hex(ENTRY), hex(STOP)],
                                   [hex(SET_STUB), hex(0x060007A2)], [hex(CHG_STUB), hex(0x060007E6)]],
                    cases=len(rows), executions_per_case=2, results=rows,
                    results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                    kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()), interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    mutations={"setuint_vector": vector_control, "scu_mmio_address": scu_control},
                    contract="Original A472 calls captured SYS_SETUINT for services 64/65, writes their function pointers into table slots A00/A04, calls captured SYS_CHGSCUIM(-4), then restores the startup SR mask and stops at A4C4. SCU stores are intent events only.")
            except Exception as e: report["error"] = {"type": type(e).__name__, "reason": str(e)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":"))+"\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"})); return 2


if __name__ == "__main__": raise SystemExit(main())
