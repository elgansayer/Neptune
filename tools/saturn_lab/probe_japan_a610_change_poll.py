#!/usr/bin/env python3
"""Execute original Japan A610's wait-until-word-changes poll."""
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
ENTRY,RETURN=0x0600A610,0xFFFFFE00
POLL_WORD=0x060B3D40
CODE=tuple(range(ENTRY,0x0600A620,2))
LITERAL=0x0600A62C
LIMIT=128
SAMPLES=((0x0000,(0x0001,)),(0x0000,(0x0000,0x0000,0x0001)),
         (0x7FFF,(0x7FFF,0x8000)),(0x8000,(0x8000,0x0001)))
SEEDS=(0,1)

class Fence(ValueError): pass
def sha(data): return hashlib.sha256(data).hexdigest()
def signed_word(value): return value if value < 0x8000 else value-0x10000
def cases(): return [(initial,polls,seed) for initial,polls in SAMPLES for seed in SEEDS]

def execute(kernel,ram,emu,initial,polls,seed,mutate_pointer=False):
    if (initial,tuple(polls)) not in SAMPLES or seed not in SEEDS:
        raise ValueError("A610 poll sequence outside declared finite input corpus")
    if not polls or polls[-1]==initial or any(v!=initial for v in polls[:-1]):
        raise ValueError("A610 samples must remain equal until the final changed word")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    if ram[ENTRY-WRAM:0x0600A620-WRAM]!=kernel[ENTRY-BASE:0x0600A620-BASE]:
        raise ValueError("captured original A610 bytes differ")
    if int.from_bytes(kernel[LITERAL-BASE:LITERAL-BASE+4],"big")!=POLL_WORD:
        raise ValueError("original A610 polling address literal differs")
    work=bytearray(ram)
    if mutate_pointer: work[LITERAL-WRAM:LITERAL-WRAM+4]=(POLL_WORD+2).to_bytes(4,"big")
    values=[initial,*polls]; reads=[]
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,width):
            if self.fetching:
                if width!=2 or address not in CODE: raise Fence(f"A610 PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address==LITERAL and width==4:
                value=super().read(address,width); reads.append(["original-literal",address,width,value]); return value
            if address==POLL_WORD and width==2:
                if not values: raise ValueError("A610 exhausted explicit poll samples before word changed")
                value=values.pop(0); reads.append(["external-workram-sample",address,width,value]); return value
            raise ValueError(f"unexpected A610 read {address:08x}/{width}")
        def write(self,address,width,value): raise ValueError(f"unexpected A610 write {address:08x}/{width}/{value&0xffffffff:08x}")
    mem=Memory(); mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try: return super().fetch(pc)
            finally: mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or pc not in CODE: raise Fence(f"A610 instruction fence {pc:08x}")
            return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem); cpu.r=[(0x41000000+n*0x01010101+seed*0x101)&0xffffffff for n in range(16)]
    cpu.r[15]=0x06002000; cpu.sr=0xF0; cpu.vbr=0x06000000; cpu.pr=RETURN; cpu.pc=ENTRY
    before=bytes(work)
    while cpu.pc!=RETURN:
        cpu.step()
        if cpu.steps>LIMIT: raise ValueError("A610 instruction budget exceeded")
    observed=[row[3] for row in reads if row[0]=="external-workram-sample"]
    if values or observed!=[initial,*polls]: raise ValueError(f"A610 sample read sequence differs: {observed!r}")
    if cpu.r[1]!=POLL_WORD or cpu.r[3]!=POLL_WORD or cpu.r[4]!=(signed_word(initial)&0xffffffff) or cpu.r[2]!=(signed_word(polls[-1])&0xffffffff):
        raise ValueError(f"A610 return registers differ r1={cpu.r[1]:08x} r2={cpu.r[2]:08x} r3={cpu.r[3]:08x} r4={cpu.r[4]:08x}")
    if cpu.pc!=RETURN or cpu.pr!=RETURN or cpu.r[15]!=0x06002000 or (cpu.sr&1)!=0:
        raise ValueError("A610 return linkage or final T flag differs")
    if bytes(work)!=before: raise ValueError("A610 mutated WorkRAM-H")
    return {"initial_sample":hex(initial),"poll_samples":[hex(v) for v in polls],"seed":seed,
            "steps":cpu.steps,"reads":reads,"return_pc":hex(cpu.pc),"r2_changed_word":hex(cpu.r[2]),
            "r4_initial_word":hex(cpu.r[4]),"workram_unchanged":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"): ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a610-change-poll.v1","status":"failure","entry":hex(ENTRY),"return":hex(RETURN),
            "limits":["Direct A610 entry with constructed registers and explicit changing WorkRAM sample events; not a natural caller/device timing trace",
                      "Frame-1200 state and original Japanese A610 bytes are identity-checked; no writes are permitted"]}
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
                for initial,polls,seed in cases():
                    a=execute(kernel,ram,emu,initial,polls,seed); b=execute(kernel,ram,emu,initial,polls,seed)
                    if a!=b: raise ValueError("paired A610 executions differ")
                    rows.append(a)
                try: execute(kernel,ram,emu,0,(1,),0,mutate_pointer=True)
                except ValueError as e:
                    if "unexpected a610 read 060b3d42/2" not in str(e).lower(): raise
                    control={"rejected":True,"literal":hex(LITERAL),"replacement":hex(POLL_WORD+2),"reason":str(e)}
                else: raise ValueError("mutated A610 polling pointer escaped strict read contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_range=[hex(ENTRY),"0x0600A620"],cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"poll_pointer":control},
                    contract="A610 reads B3D40 once into R4, then repeatedly reads it into R2 while CMP/EQ and BT find the same value. It returns at the first changed 16-bit sample, leaving R4 as the initial sample and R2 as the changed sample; it performs no writes.")
            except Exception as e: report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError: print(json.dumps({"status":"failure","reason":"report exists; immutable"})); return 2

if __name__=="__main__": raise SystemExit(main())
