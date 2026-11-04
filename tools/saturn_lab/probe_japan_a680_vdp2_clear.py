#!/usr/bin/env python3
"""Execute original Japan A680's captured-pointer halfword clear."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

KERNEL_SHA="23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA="c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
CORE_SHA="c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
RAM_SHA="3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
BASE,KERNEL_SIZE=0x0600A000,786432
WRAM,WRAM_SIZE=0x06000000,0x100000
ENTRY,RETURN=0x0600A680,0xFFFFFE00
SP=0x06002000
POINTER_WORD,POINTER_VALUE=0x060B3D48,0x25F00800
VDP2_START,SIZE=0x25F00800,0x200
CODE=tuple(range(ENTRY,0x0600A694,2))+tuple(range(0x0600A5B8,0x0600A5CE,2))
LITERALS={0x0600A760:(4,POINTER_WORD),0x0600A742:(2,0x01FE)}
SEEDS=(0,1)
LIMIT=2048

class Fence(ValueError):pass
def sha(data):return hashlib.sha256(data).hexdigest()

def execute(kernel,ram,emu,seed,mutate_pointer=False,mutate_size=False):
    if seed not in SEEDS:raise ValueError("A680 seed outside declared corpus")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start,end in ((ENTRY,0x0600A694),(0x0600A5B8,0x0600A5CE)):
        if ram[start-WRAM:end-WRAM]!=kernel[start-BASE:end-BASE]:raise ValueError(f"captured A680/helper code differs at {start:08x}")
    for address,(width,value) in LITERALS.items():
        if int.from_bytes(kernel[address-BASE:address-BASE+width],"big")!=value:raise ValueError(f"original A680 literal differs at {address:08x}")
    if int.from_bytes(ram[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4],"big")!=POINTER_VALUE:raise ValueError("frame-1200 A680 destination pointer differs")
    work=bytearray(ram)
    if mutate_pointer:work[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4]=(POINTER_VALUE+2).to_bytes(4,"big")
    if mutate_size:work[0x0600A742-WRAM:0x0600A744-WRAM]=(0x01FC).to_bytes(2,"big")
    reads,writes,pcs=[],[],[]
    saved_pr=RETURN
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,width):
            if self.fetching:
                if width!=2 or address not in CODE:raise Fence(f"A680 PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address in LITERALS and LITERALS[address][0]==width:
                value=super().read(address,width);reads.append(["original-literal",address,width,value]);return value
            if address==POINTER_WORD and width==4:
                value=super().read(address,width);reads.append(["captured-destination-pointer",address,width,value]);return value
            if address==SP-4 and width==4:
                value=super().read(address,width);reads.append(["stack-restore",address,width,value]);return value
            raise ValueError(f"unexpected A680 read {address:08x}/{width}")
        def write(self,address,width,value):
            value &= 0xFFFFFFFF
            if address==SP-4 and width==4 and value==saved_pr:
                writes.append(["stack-save",address,width,value]);return super().write(address,width,value)
            if VDP2_START<=address<VDP2_START+SIZE and width==2 and value==0:
                index=len([event for event in writes if event[0]=="vdp2-memory-intent"])
                expected=VDP2_START+2*index
                if address!=expected:raise ValueError(f"unexpected VDP2 memory write intent {address:08x}; expected {expected:08x}")
                writes.append(["vdp2-memory-intent",address,width,value]);return
            if address==POINTER_WORD and width==4:
                writes.append(["destination-pointer-update",address,width,value]);return super().write(address,width,value)
            raise ValueError(f"unexpected A680 write {address:08x}/{width}/{value:08x}")
    mem=Memory();work_mem=mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or pc not in CODE:raise Fence(f"A680 instruction fence {pc:08x}")
            pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.r=[(0x44000000+n*0x01020307+seed*0x101)&0xffffffff for n in range(16)]
    cpu.r[15]=SP;cpu.r[14]=0x6F000014+seed;cpu.sr=0xF0;cpu.vbr=0x06000000;cpu.pr=RETURN;cpu.pc=ENTRY
    before=bytes(work_mem)
    while cpu.pc!=RETURN:
        cpu.step()
        if cpu.steps>LIMIT:raise ValueError("A680 instruction budget exceeded")
    device=[event for event in writes if event[0]=="vdp2-memory-intent"]
    if len(device)!=SIZE//2:raise ValueError(f"A680 emitted {len(device)} stores, expected {SIZE//2}")
    if cpu.pc!=RETURN or cpu.pr!=RETURN or cpu.r[15]!=SP or cpu.r[4]!=VDP2_START+SIZE or cpu.r[0]!=VDP2_START+SIZE:
        raise ValueError("A680 return register/linkage contract differs")
    expected_work=bytearray(before)
    expected_work[SP-4-WRAM:SP-WRAM]=saved_pr.to_bytes(4,"big")
    expected_work[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4]=(VDP2_START+SIZE).to_bytes(4,"big")
    if bytes(work_mem)!=bytes(expected_work):raise ValueError("A680 changed WorkRAM-H outside stack and pointer")
    return {"seed":seed,"steps":cpu.steps,"pc_trace":[hex(pc) for pc in pcs],"reads":reads,"writes":writes,
            "return_pc":hex(cpu.pc),"return_pr":hex(cpu.pr),"sp_after":hex(cpu.r[15]),
            "destination":hex(VDP2_START),"bytes_requested":SIZE,"vdp2_store_count":len(device),
            "pointer_after":hex(VDP2_START+SIZE),"workram_unchanged_outside_stack_and_pointer":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"):ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a680-vdp2-clear.v1","status":"failure","entry":hex(ENTRY),"return":hex(RETURN),
            "limits":["Direct constructed A680 entry with captured frame-1200 B3D48 pointer; stores to 25F00800 are strict memory write intents, not VDP2 hardware effects",
                      "No A546 caller reachability, VDP2 display/color semantics, hardware timing, or natural startup path is included"]}
    try:
        with args.report.open("x",encoding="utf-8") as out:
            try:
                meta=json.loads(args.checkpoint.read_text());state=pinned.read_bounded(args.state,16*1024*1024)
                if meta.get("frame")!=1200 or meta.get("identity",{}).get("core_sha256")!=CORE_SHA or sha(state)!=STATE_SHA or meta.get("state_sha256")!=STATE_SHA:raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel=pinned.read_bounded(args.kernel,KERNEL_SIZE)
                if sha(kernel)!=KERNEL_SHA:raise ValueError("original Japan kernel identity differs")
                ram=sg.cpu_words(sg.field(sg.parse(state),"MAIN","WorkRAMH",WRAM_SIZE),"little")
                if sha(ram)!=RAM_SHA:raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for seed in SEEDS:
                    a=execute(kernel,ram,emu,seed);b=execute(kernel,ram,emu,seed)
                    if a!=b:raise ValueError("paired A680 executions differ")
                    rows.append(a)
                try:execute(kernel,ram,emu,0,mutate_pointer=True)
                except ValueError as e:
                    if "unexpected vdp2 memory write intent 25f00802" not in str(e).lower():raise
                    pointer_control={"rejected":True,"replacement":"0x25F00802","reason":str(e)}
                else:raise ValueError("mutated captured destination pointer escaped intent sink")
                try:execute(kernel,ram,emu,0,mutate_size=True)
                except ValueError as e:
                    if "emitted 255 stores, expected 256" not in str(e).lower():raise
                    size_control={"rejected":True,"literal":"0x0600A742","replacement":"0x01FC","reason":str(e)}
                else:raise ValueError("mutated A680 size literal escaped count contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[[hex(ENTRY),"0x0600A694"],["0x0600A5B8","0x0600A5CE"]],
                    cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"destination_pointer":pointer_control,"clear_size":size_control},
                    contract="A680 loads the frame-1200 B3D48 destination 25F00800 and size 1FEh, calls A5B8 to emit 256 zero halfword write intents through 25F009FE, then stores the returned end address 25F00A00 back to B3D48.")
            except Exception as e:report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError:print(json.dumps({"status":"failure","reason":"report exists; immutable"}));return 2
if __name__=="__main__":raise SystemExit(main())
