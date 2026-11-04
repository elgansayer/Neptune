#!/usr/bin/env python3
"""Execute original Japan A472 through its PAL-dependent timing stores."""
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
CALLER_ENTRY, CALLER_END = 0x0600A324, 0x0600A32C
ENTRY, STOP = 0x0600A472, 0x0600A4A0
CODE_RANGES = ((CALLER_ENTRY, CALLER_END), (ENTRY, STOP))
CALLER_SP = 0x06002000
STACK_ENTRY = CALLER_SP - 4  # A324 saves its incoming PR before BSR A472.
CONSTRUCTED_CALLER_PR = 0xFFFFFE00
PR_FROM_CALLER = 0x0600A32C
TVSTAT = 0x25F80004
WORD_NTSC, WORD_PAL, LINE_DELTA = 0x00DF, 0x00FF, 0x5000
TIMING_A, TIMING_B = 0x060BCE88, 0x060BCE8A
LIMIT = 32
STATUS_SAMPLES = (0x0000, 0x0001, 0x020A, 0x020B)
SR_SAMPLES = (0x000000F0, 0x00000301)
LITERALS = {
    0x0600A50C: (4, TIMING_A), 0x0600A510: (4, TVSTAT),
    0x0600A4DA: (2, WORD_PAL), 0x0600A4DC: (2, WORD_NTSC),
    0x0600A4DE: (2, LINE_DELTA), 0x0600A514: (4, TIMING_B),
    0x0600A4D2: (2, 0xFF0F),
}


class Fence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(status, sr, seed) for status in STATUS_SAMPLES
            for sr in SR_SAMPLES for seed in range(2)]


def expected_final_sr(status, initial_sr):
    # TST #1 sets T when PAL=0; the later SR read copies that T through the mask.
    t_after_tst = int((status & 1) == 0)
    return (((initial_sr & 0x3F3) & 0xFFFFFF0E) | (0xF0 | t_after_tst)) & 0x3F3


def execute(kernel, ram, emu, status, initial_sr, seed, mutate_address=False,
            mutate_pal_literal=False):
    if status not in STATUS_SAMPLES or initial_sr not in SR_SAMPLES or seed not in (0, 1):
        raise ValueError("A472 input outside declared status/SR/register corpus")
    if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start, end in ((CALLER_ENTRY, CALLER_END), (ENTRY, STOP)):
        if ram[start - WRAM:end - WRAM] != kernel[start - BASE:end - BASE]:
            raise ValueError(f"captured startup instructions differ from original kernel at {start:08x}")
    for address, (width, expected) in LITERALS.items():
        actual = int.from_bytes(kernel[address - BASE:address - BASE + width], "big")
        if actual != expected:
            raise ValueError(f"original A472 literal differs at {address:08x}: {actual:08x}")

    work = bytearray(ram)
    if mutate_address:
        work[0x0600A510 - WRAM:0x0600A514 - WRAM] = (0x25F80006).to_bytes(4, "big")
    if mutate_pal_literal:
        work[0x0600A4DA - WRAM:0x0600A4DC - WRAM] = (0x00FE).to_bytes(2, "big")
    reads, writes, pcs = [], [], []
    stack_values = {
        STACK_ENTRY - 4: 0x6D000014 + seed,
        STACK_ENTRY - 8: 0x6D000013 + seed,
        STACK_ENTRY - 12: PR_FROM_CALLER,
        STACK_ENTRY: CONSTRUCTED_CALLER_PR,
    }

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in CODE_RANGES):
                    raise Fence(f"A472 original-PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and width == LITERALS[address][0]:
                value = super().read(address, width)
                reads.append(["original-literal", address, width, value])
                return value
            if address == TVSTAT and width == 2:
                reads.append(["mmio-input", address, width, status])
                return status
            if address == TIMING_A and width == 2:
                value = super().read(address, width)
                reads.append(["workram-timing-word", address, width, value])
                return value
            raise ValueError(f"unexpected A472 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if address in stack_values and width == 4 and value == stack_values[address]:
                writes.append(["entry-stack-save", address, width, value])
                return super().write(address, width, value)
            if address in (TIMING_A, TIMING_B) and width == 2:
                pal = bool(status & 1)
                expected = (WORD_PAL if pal else WORD_NTSC) if address == TIMING_A else (WORD_PAL if pal else WORD_NTSC) + LINE_DELTA
                if value != expected:
                    raise ValueError(f"A472 global timing word differs at {address:08x}: {value:08x}, expected {expected:08x}")
                writes.append(["startup-timing", address, width, value])
                return super().write(address, width, value)
            raise ValueError(f"unexpected A472 write {address:08x}/{width}/{value:08x}")

    mem = Memory()
    work_mem = mem.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try:
                return super().fetch(pc)
            finally:
                mem.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or not any(lo <= pc < hi for lo, hi in CODE_RANGES):
                raise Fence(f"A472 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(mem)
    cpu.r = [(0x4D000000 + n * 0x01020307 + seed * 0x101) & 0xFFFFFFFF for n in range(16)]
    cpu.r[0], cpu.r[13], cpu.r[14], cpu.r[15] = initial_sr, 0x6D000013 + seed, 0x6D000014 + seed, CALLER_SP
    cpu.sr, cpu.vbr, cpu.pr, cpu.pc = 0xF0, 0x06000000, CONSTRUCTED_CALLER_PR, CALLER_ENTRY
    before = bytes(work_mem)
    while cpu.pc != STOP:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A472 instruction budget exceeded")

    pal = bool(status & 1)
    selected = WORD_PAL if pal else WORD_NTSC
    expected_writes = [
        ["entry-stack-save", STACK_ENTRY, 4, CONSTRUCTED_CALLER_PR],
        ["entry-stack-save", STACK_ENTRY - 4, 4, 0x6D000014 + seed],
        ["entry-stack-save", STACK_ENTRY - 8, 4, 0x6D000013 + seed],
        ["entry-stack-save", STACK_ENTRY - 12, 4, PR_FROM_CALLER],
        ["startup-timing", TIMING_A, 2, selected],
        ["startup-timing", TIMING_B, 2, selected + LINE_DELTA],
    ]
    if writes != expected_writes:
        raise ValueError(f"A472 write sequence differs: {writes!r}")
    expected_ram = bytearray(before)
    for _, address, width, value in writes:
        off = address - WRAM
        expected_ram[off:off + width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected_ram):
        raise ValueError("unlisted A472 WorkRAM-H mutation")
    expected_sr = expected_final_sr(status, initial_sr)
    if cpu.pc != STOP or cpu.pr != PR_FROM_CALLER or cpu.r[15] != STACK_ENTRY - 12 or cpu.sr != expected_sr:
        raise ValueError(f"A472 stop state differs: pc={cpu.pc:08x} pr={cpu.pr:08x} sp={cpu.r[15]:08x} sr={cpu.sr:08x}")
    if cpu.r[4] != TIMING_A or cpu.r[1] != TIMING_B or cpu.r[3] != 0xFFFFFF0F:
        raise ValueError("A472 timing/SR scratch registers differ")
    if reads.count(["mmio-input", TVSTAT, 2, status]) != 1:
        raise ValueError("A472 did not make exactly one TVSTAT word read")
    return {
        "tvstat_sample": hex(status), "pal_bit": int(pal), "initial_sr": hex(initial_sr),
        "sr_after": hex(cpu.sr), "t_after": cpu.sr & 1, "seed": seed, "selected_timing_word": hex(selected),
        "companion_word": hex(selected + LINE_DELTA), "steps": cpu.steps,
        "pc_trace": [hex(pc) for pc in pcs], "reads": reads, "writes": writes,
        "stop_pc": hex(cpu.pc), "sp_after": hex(cpu.r[15]),
        "workram_bytes_unchanged": WRAM_SIZE - 16 - 4,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-a472-tvstat-timing.v1", "status": "failure",
              "entry": hex(CALLER_ENTRY), "stop": hex(STOP),
              "limits": ["Starts at constructed A324 function entry with SP=0x06002000, a sentinel caller PR and R0 status seed; executes original A324 prologue/BSR/delay slot and A472 prefix",
                         "TVSTAT samples are explicit MMIO inputs; no read from flat RAM and no claim they were observed at the original call",
                         "Stops before SYS_SETUINT at A4A0; BIOS services, later A638 path and device timing are not executed"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
                if meta.get("frame") != 1200 or meta.get("identity", {}).get("core_sha256") != CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                if sha(state) != STATE_SHA or meta.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if sha(kernel) != KERNEL_SHA:
                    raise ValueError("original Japan kernel identity differs")
                raw = sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != RAM_SHA:
                    raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = []
                for status, sr, seed in corpus():
                    a = execute(kernel, ram, emu, status, sr, seed)
                    b = execute(kernel, ram, emu, status, sr, seed)
                    if a != b:
                        raise ValueError("paired A472 executions differ")
                    rows.append(a)
                try:
                    execute(kernel, ram, emu, 1, SR_SAMPLES[0], 0, mutate_address=True)
                except ValueError as error:
                    if "unexpected a472 read 25f80006/2" not in str(error).lower():
                        raise ValueError("TVSTAT address mutation escaped the MMIO read contract") from error
                    address_control = {"rejected": True, "literal": "0x0600A510", "replacement": "0x25F80006", "reason": str(error)}
                else:
                    raise ValueError("mutated TVSTAT address was accepted")
                try:
                    execute(kernel, ram, emu, 1, SR_SAMPLES[0], 0, mutate_pal_literal=True)
                except ValueError as error:
                    if "a472 global timing word differs at 060bce88" not in str(error).lower():
                        raise ValueError("PAL timing literal mutation escaped the output contract") from error
                    literal_control = {"rejected": True, "literal": "0x0600A4DA", "replacement": "0x00FE", "reason": str(error)}
                else:
                    raise ValueError("mutated PAL timing literal was accepted")
                report.update(status="success", original_game_bytes_executed=True,
                              captured_snapshot_data_used=True, constructed_tvstat_samples=True,
                              release="Japan T-14302G V1.000", source_file="0KRNL.BIN",
                              cpu="master SH-2", address_space="WorkRAM-H",
                              mapping=hex(BASE), source_ranges=[[hex(lo), hex(hi)] for lo, hi in CODE_RANGES],
                              cases=len(rows), executions_per_case=2, results=rows,
                              results_sha256=sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
                              kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                              normalized_workram_sha256=RAM_SHA,
                              code_sha256={hex(lo): sha(kernel[lo - BASE:hi - BASE]) for lo, hi in CODE_RANGES},
                              probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              mutations={"tvstat_address": address_control, "pal_timing_literal": literal_control},
                              contract="Original A324 pushes incoming PR, loads SR from R0, and calls A472; A472 then tests TVSTAT bit 0, stores 0x00DF for NTSC or 0x00FF for PAL at 0x060BCE88 and selected+0x5000 at 0x060BCE8A. The test sets SR.T to the inverse of PAL before the code sets SR bits 4-7, leaving other supported flags unchanged.",
                              external_semantics="PAL bit 0 independently cross-checked against Sega VDP2 User's Manual and Yabause 0.9.15 source; source comparison only, no Yabause execution.")
            except Exception as e:
                report["error"] = {"type": type(e).__name__, "reason": str(e)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
