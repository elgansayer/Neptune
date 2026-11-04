#!/usr/bin/env python3
"""Execute original Japan A78C's SCSP RAM clear through A58E and RTS."""
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
ENTRY,RETURN=0x0600A78C,0xFFFFFE00
SCSP_RAM,SIZE=0x25B00800,0x400
CODE=tuple((0x0600A78C,0x0600A78E,0x0600A790,0x0600A792)+tuple(range(0x0600A58E,0x0600A5A2,2)))
LITERALS={0x0600A794:(2,0x0400),0x0600A798:(4,SCSP_RAM)}
SEEDS=(0,1)
LIMIT=8192

class Fence(ValueError): pass
def sha(data): return hashlib.sha256(data).hexdigest()

def execute(kernel,ram,emu,seed,mutate_base=False,mutate_size=False):
    if seed not in SEEDS: raise ValueError("A78C seed outside declared corpus")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start,end in ((ENTRY,0x0600A794),(0x0600A58E,0x0600A5A2)):
        if ram[start-WRAM:end-WRAM]!=kernel[start-BASE:end-BASE]: raise ValueError(f"captured A78C/helper code differs at {start:08x}")
    for address,(width,value) in LITERALS.items():
        if int.from_bytes(kernel[address-BASE:address-BASE+width],"big")!=value: raise ValueError(f"original literal differs at {address:08x}")
    work=bytearray(ram)
    if mutate_base: work[0x0600A798-WRAM:0x0600A79C-WRAM]=(SCSP_RAM+2).to_bytes(4,"big")
    if mutate_size: work[0x0600A794-WRAM:0x0600A796-WRAM]=(0x03FE).to_bytes(2,"big")
    reads,writes,pcs=[],[],[]
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,width):
            if self.fetching:
                if width!=2 or address not in CODE: raise Fence(f"A78C PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address in LITERALS and LITERALS[address][0]==width:
                value=super().read(address,width); reads.append(["original-literal",address,width,value]); return value
            raise ValueError(f"unexpected A78C read {address:08x}/{width}")
        def write(self,address,width,value):
            value &= 0xFFFFFFFF
            index=len(writes)
            expected_address=SCSP_RAM+2*index
            if width!=2 or value!=0 or address!=expected_address:
                raise ValueError(f"unexpected SCSP RAM write intent {address:08x}/{width}/{value:08x}; expected {expected_address:08x}/2/00000000")
            writes.append(["scsp-ram-write-intent",address,width,value])
    mem=Memory(); mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or pc not in CODE: raise Fence(f"A78C instruction fence {pc:08x}")
            pcs.append(pc); return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem); cpu.r=[(0x42000000+n*0x01010101+seed*0x101)&0xffffffff for n in range(16)]
    cpu.r[15]=0x06002000; cpu.r[14]=0x6E000014+seed; cpu.sr=0xF0; cpu.vbr=0x06000000; cpu.pr=RETURN; cpu.pc=ENTRY
    before=bytes(work)
    while cpu.pc!=RETURN:
        cpu.step()
        if cpu.steps>LIMIT: raise ValueError("A78C instruction budget exceeded")
    if len(writes)!=SIZE//2: raise ValueError(f"A78C emitted {len(writes)} stores, expected {SIZE//2}")
    if cpu.pc!=RETURN or cpu.pr!=RETURN or cpu.r[15]!=0x06002000 or cpu.r[4]!=SCSP_RAM+SIZE or cpu.r[5]!=0 or cpu.r[6]!=SIZE:
        raise ValueError(f"A78C return state differs pc={cpu.pc:08x} pr={cpu.pr:08x} sp={cpu.r[15]:08x} r4={cpu.r[4]:08x}")
    if bytes(work)!=before: raise ValueError("A78C changed WorkRAM-H")
    return {"seed":seed,"steps":cpu.steps,"pc_trace":[hex(pc) for pc in pcs],"reads":reads,"writes":writes,
            "return_pc":hex(cpu.pc),"return_pr":hex(cpu.pr),"sp_after":hex(cpu.r[15]),
            "scsp_range":[hex(SCSP_RAM),hex(SCSP_RAM+SIZE)],"bytes_requested":SIZE,"workram_unchanged":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"):ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a78c-scsp-clear.v1","status":"failure","entry":hex(ENTRY),"return":hex(RETURN),
            "limits":["Direct constructed A78C entry; captured frame-1200 WorkRAM-H; original SCSP stores are strict write-intent events, not device effects",
                      "No A546 caller, SCSP state/timing, or natural startup path is included"]}
    try:
        with args.report.open("x",encoding="utf-8") as out:
            try:
                meta=json.loads(args.checkpoint.read_text()); state=pinned.read_bounded(args.state,16*1024*1024)
                if meta.get("frame")!=1200 or meta.get("identity",{}).get("core_sha256")!=CORE_SHA or sha(state)!=STATE_SHA or meta.get("state_sha256")!=STATE_SHA: raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel=pinned.read_bounded(args.kernel,KERNEL_SIZE)
                if sha(kernel)!=KERNEL_SHA: raise ValueError("original Japan kernel identity differs")
                ram=sg.cpu_words(sg.field(sg.parse(state),"MAIN","WorkRAMH",WRAM_SIZE),"little")
                if sha(ram)!=RAM_SHA: raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu=pinned.interpreter(args.saturn_recomp); rows=[]
                for seed in SEEDS:
                    a=execute(kernel,ram,emu,seed); b=execute(kernel,ram,emu,seed)
                    if a!=b: raise ValueError("paired A78C executions differ")
                    rows.append(a)
                try:execute(kernel,ram,emu,0,mutate_base=True)
                except ValueError as e:
                    if "unexpected scsp ram write intent 25b00802" not in str(e).lower():raise
                    base_control={"rejected":True,"replacement":"0x25B00802","reason":str(e)}
                else:raise ValueError("mutated SCSP RAM base escaped write-intent contract")
                try:execute(kernel,ram,emu,0,mutate_size=True)
                except ValueError as e:
                    if "emitted 511 stores, expected 512" not in str(e).lower():raise
                    size_control={"rejected":True,"literal":"0x0600A794","replacement":"0x03FE","reason":str(e)}
                else:raise ValueError("mutated SCSP clear size escaped store-count contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[[hex(ENTRY),"0x0600A794"],["0x0600A58E","0x0600A5A2"]],
                    cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"scsp_ram_base":base_control,"clear_size":size_control},
                    contract="Original A78C tail-calls A58E with R4=25B00800, R5=0, R6=0400; A58E emits 512 sequential zero halfword write intents through 25B00BFE and returns via the caller PR.")
            except Exception as e:report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError:print(json.dumps({"status":"failure","reason":"report exists; immutable"}));return 2

if __name__=="__main__":raise SystemExit(main())
