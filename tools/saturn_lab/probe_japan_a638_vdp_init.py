#!/usr/bin/env python3
"""Execute original Japan A638's descriptor setup and VDP1 copy prefix."""
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
ENTRY, RETURN = 0x0600A638, 0xFFFFFE00
SP = 0x06002000
ARRAY, ARRAY_SIZE = 0x060BCE8C, 96
TIMING_WORD = 0x060BCE88
VDP1_VRAM = 0x25C00000
SETUP_PCS = tuple(range(ENTRY, 0x0600A66C, 2))
FILL_PCS = tuple(range(0x0600A58E, 0x0600A5A2, 2))
COPY_PCS = tuple(range(0x0600A5A2, 0x0600A5B8, 2))
EXECUTABLE = SETUP_PCS + FILL_PCS + COPY_PCS
LIMIT = 1024
SEEDS = (0, 1)
LITERALS = {
    0x0600A74C: (4, ARRAY), 0x0600A73E: (2, 0x013F),
    0x0600A740: (2, 0x8000), 0x0600A750: (4, TIMING_WORD),
    0x0600A754: (4, VDP1_VRAM),
}


class Fence(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, seed, mutate_vram=False, mutate_count=False):
    if seed not in SEEDS:
        raise ValueError("A638 seed outside declared corpus")
    if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start, end in ((ENTRY, 0x0600A66C), (0x0600A58E, 0x0600A5B8)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured original A638/helper bytes differ at {start:08x}")
    for address, (width, expected) in LITERALS.items():
        actual = int.from_bytes(kernel[address-BASE:address-BASE+width], "big")
        if actual != expected:
            raise ValueError(f"original A638 literal differs at {address:08x}: {actual:08x}")
    work = bytearray(ram)
    if mutate_vram:
        work[0x0600A754-WRAM:0x0600A758-WRAM] = (VDP1_VRAM+2).to_bytes(4, "big")
    if mutate_count:
        work[0x0600A73E-WRAM:0x0600A740-WRAM] = (0x0140).to_bytes(2, "big")
    reads, writes, pcs = [], [], []
    saved_r14 = 0x6D000014 + seed
    stack_values = {SP-4: saved_r14, SP-8: RETURN}
    expected_device_writes = [[VDP1_VRAM+i*2, 2] for i in range(ARRAY_SIZE//2)]

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__(); self.fetching = False
        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in EXECUTABLE:
                    raise Fence(f"A638 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["original-literal", address, width, value]); return value
            if address == TIMING_WORD and width == 2:
                value = super().read(address, width)
                reads.append(["frame1200-workram-timing", address, width, value]); return value
            if ARRAY <= address < ARRAY+ARRAY_SIZE and width == 2:
                value = super().read(address, width)
                reads.append(["descriptor-source", address, width, value]); return value
            if address in stack_values and width == 4:
                value = super().read(address, width)
                reads.append(["stack-restore", address, width, value]); return value
            raise ValueError(f"unexpected A638 read {address:08x}/{width}")
        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if address in stack_values and width == 4 and value == (saved_r14 if address == SP-4 else RETURN):
                writes.append(["stack-save", address, width, value]); return super().write(address, width, value)
            if ARRAY <= address < ARRAY+ARRAY_SIZE and width == 2:
                offset = address-ARRAY
                descriptor_writes = [event for event in writes if event[0] == "descriptor-word"]
                if len(descriptor_writes) < ARRAY_SIZE//2:
                    expected = 0
                else:
                    expected = 0
                    if offset == 0: expected = 9
                    elif offset == 20: expected = 0x013F
                    elif offset == 22: expected = int.from_bytes(ram[TIMING_WORD-WRAM:TIMING_WORD-WRAM+2], "big")
                    elif offset == 32: expected = 10
                    elif offset == 64: expected = 0xFFFF8000
                if value != expected:
                    raise ValueError(f"unexpected A638 descriptor write {address:08x}/{width}/{value:08x}; expected {expected:04x}")
                writes.append(["descriptor-word", address, width, value]); return super().write(address, width, value)
            if VDP1_VRAM <= address < VDP1_VRAM+0x80000 and width == 2:
                expected_index = len([w for w in writes if w[0] == "vdp1-vram-write-intent"])
                expected_address = VDP1_VRAM+expected_index*2
                if address != expected_address:
                    raise ValueError(f"unexpected VDP1 VRAM write intent {address:08x}/{width}; expected {expected_address:08x}")
                writes.append(["vdp1-vram-write-intent", address, width, value]); return
            raise ValueError(f"unexpected A638 write {address:08x}/{width}/{value:08x}")

    mem = Memory(); work_mem = mem.add(WRAM, WRAM_SIZE, work)
    class CPU(emu.CPU):
        def fetch(self, pc):
            mem.fetching = True
            try: return super().fetch(pc)
            finally: mem.fetching = False
        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in EXECUTABLE:
                raise Fence(f"A638 instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins, pc, in_slot=in_slot)
    cpu = CPU(mem)
    cpu.r = [(0x39000000+n*0x01020307+seed*0x101)&0xFFFFFFFF for n in range(16)]
    cpu.r[4], cpu.r[5], cpu.r[6] = 0xA4000004, 0xA5000005, 0xA6000006
    cpu.r[14], cpu.r[15] = saved_r14, SP
    cpu.sr, cpu.vbr, cpu.pr, cpu.pc = 0xF0, 0x06000000, RETURN, ENTRY
    before = bytes(work_mem)
    while cpu.pc != RETURN:
        cpu.step()
        if cpu.steps > LIMIT: raise ValueError("A638 instruction budget exceeded")
    if len([w for w in writes if w[0] == "vdp1-vram-write-intent"]) != ARRAY_SIZE//2:
        raise ValueError("A638 did not emit exactly 48 VDP1 VRAM write intents")
    expected_writes_prefix = [["stack-save", SP-4, 4, saved_r14], ["stack-save", SP-8, 4, RETURN]]
    if writes[:2] != expected_writes_prefix:
        raise ValueError(f"A638 stack-save sequence differs: {writes[:2]!r}")
    expected_ram = bytearray(before)
    expected_ram[ARRAY-WRAM:ARRAY-WRAM+ARRAY_SIZE] = bytes(ARRAY_SIZE)
    timing = int.from_bytes(ram[TIMING_WORD-WRAM:TIMING_WORD-WRAM+2], "big")
    for offset, value in ((0, 9), (20, 0x013F), (22, timing), (32, 10), (64, 0x8000)):
        expected_ram[ARRAY-WRAM+offset:ARRAY-WRAM+offset+2] = value.to_bytes(2, "big")
    # A5A2's destination is VDP1 VRAM. It does not mutate WorkRAM while copying.
    for address, width, value in ((SP-4, 4, saved_r14), (SP-8, 4, RETURN)):
        off = address-WRAM; expected_ram[off:off+width] = value.to_bytes(width, "big")
    if bytes(work_mem) != bytes(expected_ram):
        raise ValueError("A638 changed unlisted WorkRAM-H bytes")
    if cpu.pc != RETURN or cpu.pr != RETURN or cpu.r[14] != saved_r14 or cpu.r[15] != SP or cpu.r[4] != VDP1_VRAM+ARRAY_SIZE or cpu.r[5] != ARRAY+ARRAY_SIZE:
        raise ValueError(f"A638 return state differs: pc={cpu.pc:08x} pr={cpu.pr:08x} r14={cpu.r[14]:08x} sp={cpu.r[15]:08x}")
    return {"seed": seed, "steps": cpu.steps, "pc_trace": [hex(pc) for pc in pcs],
            "reads": reads, "writes": writes, "return_pc": hex(cpu.pc), "return_pr": hex(cpu.pr),
            "r14_restored": hex(cpu.r[14]), "sp_after": hex(cpu.r[15]),
            "vdp1_vram_bytes_requested": ARRAY_SIZE, "descriptor_range": [hex(ARRAY), hex(ARRAY+ARRAY_SIZE)],
            "workram_unchanged_outside_stack_and_descriptor": True}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--"+name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema":"neptune.original-japan-a638-vdp-init.v1", "status":"failure",
              "entry":hex(ENTRY), "return":hex(RETURN),
              "limits":["A638 entered directly with constructed registers and sentinel PR; executes original A638, A58E and A5A2 to RTS",
                        "Captured frame-1200 WorkRAM-H is the initial state; VDP1 VRAM stores are strict write-intent events, not hardware effects",
                        "Does not establish A472 caller reachability, VDP1 command/display semantics, startup timing, or later A638 continuation"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta=json.loads(args.checkpoint.read_text()); state=pinned.read_bounded(args.state,16*1024*1024)
                if meta.get("frame") != 1200 or meta.get("identity",{}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA or meta.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel=pinned.read_bounded(args.kernel,KERNEL_SIZE)
                if sha(kernel) != KERNEL_SHA: raise ValueError("original Japan kernel identity differs")
                ram=sg.cpu_words(sg.field(sg.parse(state),"MAIN","WorkRAMH",WRAM_SIZE),"little")
                if sha(ram) != RAM_SHA: raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu=pinned.interpreter(args.saturn_recomp); rows=[]
                for seed in SEEDS:
                    a=execute(kernel,ram,emu,seed); b=execute(kernel,ram,emu,seed)
                    if a != b: raise ValueError("paired A638 executions differ")
                    rows.append(a)
                try: execute(kernel,ram,emu,0,mutate_vram=True)
                except ValueError as e:
                    if "unexpected vdp1 vram write intent 25c00002" not in str(e).lower(): raise
                    vram_control={"rejected":True,"replacement":"0x25C00002","reason":str(e)}
                else: raise ValueError("mutated VDP1 VRAM base escaped write-intent contract")
                try: execute(kernel,ram,emu,0,mutate_count=True)
                except ValueError as e:
                    if "unexpected a638 descriptor write 060bcea0" not in str(e).lower(): raise
                    count_control={"rejected":True,"literal":"0x0600A73E","replacement":"0x0140","reason":str(e)}
                else: raise ValueError("mutated descriptor count literal escaped write contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[[hex(ENTRY),hex(0x0600A66C)],["0x0600A58E","0x0600A5B8"]],
                    cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"vdp1_vram_base":vram_control,"descriptor_count":count_control},
                    contract="Original A638 zero-fills 96 bytes at BCE8C, writes the count/control halfwords and copied timing word, places 8000 at BCECC, then original A5A2 emits 48 sequential halfword write intents to VDP1 VRAM at 25C00000–25C0005E and returns through its real loop/RTS.")
            except Exception as e: report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError:
        print(json.dumps({"status":"failure","reason":"report exists; immutable"})); return 2


if __name__ == "__main__": raise SystemExit(main())
