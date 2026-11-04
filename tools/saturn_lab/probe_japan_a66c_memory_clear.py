#!/usr/bin/env python3
"""Execute original Japan A66C and A5CE with a captured destination pointer."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

KERNEL_SHA="23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA="c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
CORE_SHA="c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
RAM_SHA="3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
BASE,KERNEL_SIZE=0x0600A000,786432
WRAM,WRAM_SIZE=0x06000000,0x100000
ENTRY,RETURN=0x0600A66C,0xFFFFFE00
SP=0x06002000
POINTER_WORD,POINTER_VALUE=0x060B3D44,0x25E80000
DESTINATION,SIZE=0x25E80000,0x1FFFC
CODE=tuple(range(ENTRY,0x0600A680,2))+tuple(range(0x0600A5CE,0x0600A5E4,2))
LITERALS={0x0600A75C:(4,POINTER_WORD),0x0600A758:(4,SIZE)}
SEEDS=(0,1)
LIMIT=200000

class Fence(ValueError): pass
def sha(data): return hashlib.sha256(data).hexdigest()

def execute(kernel,ram,emu,seed,mutate_pointer=False,mutate_size=False):
    if seed not in SEEDS: raise ValueError("A66C seed outside declared corpus")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start,end in ((ENTRY,0x0600A680),(0x0600A5CE,0x0600A5E4)):
        if ram[start-WRAM:end-WRAM]!=kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured A66C/helper bytes differ at {start:08x}")
    for address,(width,value) in LITERALS.items():
        if int.from_bytes(kernel[address-BASE:address-BASE+width],"big")!=value:
            raise ValueError(f"original A66C literal differs at {address:08x}")
    if int.from_bytes(ram[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4],"big")!=POINTER_VALUE:
        raise ValueError("frame-1200 A66C destination pointer differs")
    work=bytearray(ram)
    if mutate_pointer: work[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4]=(POINTER_VALUE+4).to_bytes(4,"big")
    if mutate_size: work[0x0600A758-WRAM:0x0600A75C-WRAM]=(SIZE-4).to_bytes(4,"big")
    reads,writes,pcs=[],[],[]
    intent_count=[0]
    saved_pr=RETURN
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,width):
            if self.fetching:
                if width!=2 or address not in CODE: raise Fence(f"A66C PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address in LITERALS and LITERALS[address][0]==width:
                value=super().read(address,width); reads.append(["original-literal",address,width,value]); return value
            if address==POINTER_WORD and width==4:
                value=super().read(address,width); reads.append(["captured-destination-pointer",address,width,value]); return value
            if address==SP-4 and width==4:
                value=super().read(address,width); reads.append(["stack-restore",address,width,value]); return value
            raise ValueError(f"unexpected A66C read {address:08x}/{width}")
        def write(self,address,width,value):
            value &= 0xFFFFFFFF
            if address==SP-4 and width==4 and value==saved_pr:
                writes.append(["stack-save",address,width,value]); return super().write(address,width,value)
            if DESTINATION<=address<DESTINATION+SIZE+4 and width==4 and value==0:
                index=intent_count[0]
                expected=DESTINATION+4*index
                if address!=expected: raise ValueError(f"unexpected A66C memory write intent {address:08x}; expected {expected:08x}")
                writes.append(["memory-write-intent",address,width,value]); intent_count[0]+=1; return
            if address==POINTER_WORD and width==4:
                writes.append(["destination-pointer-update",address,width,value]); return super().write(address,width,value)
            raise ValueError(f"unexpected A66C write {address:08x}/{width}/{value:08x}")
    mem=Memory(); work_mem=mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try: return super().fetch(pc)
            finally: mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or pc not in CODE: raise Fence(f"A66C instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem); cpu.r=[(0x4A000000+n*0x01020307+seed*0x101)&0xFFFFFFFF for n in range(16)]
    cpu.r[15]=SP; cpu.r[14]=0x6A000014+seed; cpu.sr=0xF0; cpu.vbr=0x06000000; cpu.pr=RETURN; cpu.pc=ENTRY
    before=bytes(work_mem)
    while cpu.pc!=RETURN:
        cpu.step()
        if cpu.steps>LIMIT: raise ValueError("A66C instruction budget exceeded")
    device=[event for event in writes if event[0]=="memory-write-intent"]
    end=DESTINATION+SIZE+4
    expected_count=SIZE//4+1
    if len(device)!=expected_count: raise ValueError(f"A66C emitted {len(device)} stores, expected {expected_count}")
    if cpu.pc!=RETURN or cpu.pr!=RETURN or cpu.r[15]!=SP or cpu.r[4]!=end or cpu.r[0]!=end:
        raise ValueError("A66C return register/linkage contract differs")
    expected_work=bytearray(before); expected_work[SP-4-WRAM:SP-WRAM]=saved_pr.to_bytes(4,"big")
    expected_work[POINTER_WORD-WRAM:POINTER_WORD-WRAM+4]=end.to_bytes(4,"big")
    if bytes(work_mem)!=bytes(expected_work): raise ValueError("A66C changed WorkRAM-H outside stack and pointer")
    return {"seed":seed,"steps":cpu.steps,"pc_trace":[hex(pc) for pc in pcs],"reads":reads,
            "writes":writes,"return_pc":hex(cpu.pc),"return_pr":hex(cpu.pr),"sp_after":hex(cpu.r[15]),
            "destination":hex(DESTINATION),"size_threshold":SIZE,"longword_store_count":len(device),
            "bytes_written":expected_count*4,"last_address":hex(DESTINATION+SIZE),"pointer_after":hex(end),
            "workram_unchanged_outside_stack_and_pointer":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"): ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a66c-memory-clear.v1","status":"failure","entry":hex(ENTRY),"return":hex(RETURN),
            "limits":["Direct constructed A66C entry with captured frame-1200 B3D44 pointer; stores are strict memory-write intents",
                      "No A546 reachability, mapped hardware semantics, memory-device effects, timing, or natural startup path is established"]}
    try:
        with args.report.open("x",encoding="utf-8") as out:
            try:
                meta=json.loads(args.checkpoint.read_text()); state=pinned.read_bounded(args.state,16*1024*1024)
                if meta.get("frame")!=1200 or meta.get("identity",{}).get("core_sha256")!=CORE_SHA or sha(state)!=STATE_SHA or meta.get("state_sha256")!=STATE_SHA:
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel=pinned.read_bounded(args.kernel,KERNEL_SIZE)
                if sha(kernel)!=KERNEL_SHA: raise ValueError("original Japan kernel identity differs")
                ram=sg.cpu_words(sg.field(sg.parse(state),"MAIN","WorkRAMH",WRAM_SIZE),"little")
                if sha(ram)!=RAM_SHA: raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu=pinned.interpreter(args.saturn_recomp); rows=[]
                for seed in SEEDS:
                    a=execute(kernel,ram,emu,seed); b=execute(kernel,ram,emu,seed)
                    if a!=b: raise ValueError("paired A66C executions differ")
                    rows.append(a)
                try: execute(kernel,ram,emu,0,mutate_pointer=True)
                except ValueError as e:
                    if "unexpected a66c memory write intent 25e80004" not in str(e).lower(): raise
                    pointer_control={"rejected":True,"replacement":"0x25E80004","reason":str(e)}
                else: raise ValueError("mutated A66C destination escaped strict intent sink")
                try: execute(kernel,ram,emu,0,mutate_size=True)
                except ValueError as e:
                    if f"emitted {SIZE//4} stores, expected {SIZE//4+1}" not in str(e).lower(): raise
                    size_control={"rejected":True,"literal":"0x0600A758","replacement":hex(SIZE-4),"reason":str(e)}
                else: raise ValueError("mutated A66C byte count escaped store-count contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[[hex(ENTRY),"0x0600A680"],["0x0600A5CE","0x0600A5E4"]],cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"destination_pointer":pointer_control,"clear_size":size_control},
                    contract="Original A66C loads captured B3D44=25E80000 and threshold 1FFFC, calls A5CE, whose initial CMP/GT plus post-store delay-slot increment produces 32768 zero longword write intents from 25E80000 through 25E9FFFC (131072 bytes), then stores 25EA0000 back to B3D44.")
            except Exception as e: report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError: print(json.dumps({"status":"failure","reason":"report exists; immutable"})); return 2

if __name__=="__main__": raise SystemExit(main())
