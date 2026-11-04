#!/usr/bin/env python3
"""Execute original Japan A694 command selection and SCSP setup branch."""
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
ENTRY,RETURN=0x0600A694,0xFFFFFE00
SP=0x06002000
SCSP_PORT,SCSP_RAM,DSP_RAM=0x25B00400,0x25A00000,0x25A00400
SMPC_COMREG=0x2010001F
CODE=tuple(range(ENTRY,0x0600A6D6,2))+tuple(range(0x0600A5CE,0x0600A5E4,2))
LITERALS={0x0600A744:(2,0x03FC),0x0600A764:(4,SMPC_COMREG),
          0x0600A768:(4,SCSP_PORT),0x0600A76C:(4,SCSP_RAM),
          0x0600A770:(4,0x0007FFFC),0x0600A774:(4,0x4E7160FC),
          0x0600A778:(4,DSP_RAM)}
MODES=(0,1,2,3)
SEEDS=(0,1)
LIMIT=4096

class Fence(ValueError):pass
def sha(data):return hashlib.sha256(data).hexdigest()
def cases():return [(mode,seed) for mode in MODES for seed in SEEDS]

def execute(kernel,ram,emu,mode,seed,mutate_smpc=False,mutate_size=False):
    if mode not in MODES or seed not in SEEDS:raise ValueError("A694 input outside declared mode/seed corpus")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start,end in ((ENTRY,0x0600A6D6),(0x0600A5CE,0x0600A5E4)):
        if ram[start-WRAM:end-WRAM]!=kernel[start-BASE:end-BASE]:raise ValueError(f"captured A694/helper code differs at {start:08x}")
    for address,(width,value) in LITERALS.items():
        if int.from_bytes(kernel[address-BASE:address-BASE+width],"big")!=value:raise ValueError(f"original A694 literal differs at {address:08x}")
    work=bytearray(ram)
    if mutate_smpc:work[0x0600A764-WRAM:0x0600A768-WRAM]=(SMPC_COMREG-1).to_bytes(4,"big")
    if mutate_size:work[0x0600A744-WRAM:0x0600A746-WRAM]=(0x03F8).to_bytes(2,"big")
    reads,writes,pcs=[],[],[]
    saved_pr=RETURN
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,width):
            if self.fetching:
                if width!=2 or address not in CODE:raise Fence(f"A694 PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address in LITERALS and LITERALS[address][0]==width:
                value=super().read(address,width);reads.append(["original-literal",address,width,value]);return value
            if address==SP-4 and width==4:
                value=super().read(address,width);reads.append(["stack-restore",address,width,value]);return value
            raise ValueError(f"unexpected A694 read {address:08x}/{width}")
        def write(self,address,width,value):
            value &= 0xFFFFFFFF
            if address==SP-4 and width==4 and value==saved_pr:
                writes.append(["stack-save",address,width,value]);return super().write(address,width,value)
            if address==SMPC_COMREG and width==1 and mode in (0,2):
                expected=7 if mode==0 else 6
                if value!=expected:raise ValueError(f"unexpected SMPC COMREG write {address:08x}/{width}/{value:08x}")
                writes.append(["smpc-command-intent",address,width,value]);return
            if address==SCSP_PORT and width==1 and mode==1 and value==2:
                writes.append(["scsp-register-intent",address,width,value]);return
            if SCSP_RAM<=address<=SCSP_RAM+0x400 and width==4 and mode==1:
                prior=[event for event in writes if event[0]=="scsp-ram-intent"]
                index=len(prior)
                if index<256:
                    expected_address=SCSP_RAM+index*4;expected_value=0x400
                elif index==256:expected_address,expected_value=SCSP_RAM,0x0007FFFC
                elif index==257:expected_address,expected_value=DSP_RAM,0x4E7160FC
                else:raise ValueError("A694 emitted too many SCSP RAM stores")
                if address!=expected_address or value!=expected_value:
                    raise ValueError(f"unexpected SCSP RAM intent {address:08x}/{width}/{value:08x}; expected {expected_address:08x}/{width}/{expected_value:08x}")
                writes.append(["scsp-ram-intent",address,width,value]);return
            raise ValueError(f"unexpected A694 write {address:08x}/{width}/{value:08x}")
    mem=Memory();work_mem=mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or pc not in CODE:raise Fence(f"A694 instruction fence {pc:08x}")
            pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.r=[(0x43000000+n*0x01020307+seed*0x101)&0xffffffff for n in range(16)]
    cpu.r[4]=mode;cpu.r[15]=SP;cpu.sr=0xF0;cpu.vbr=0x06000000;cpu.pr=RETURN;cpu.pc=ENTRY
    before=bytes(work_mem)
    while cpu.pc!=RETURN:
        cpu.step()
        if cpu.steps>LIMIT:raise ValueError("A694 instruction budget exceeded")
    expected=[]
    if mode in (0,2):expected=[["smpc-command-intent",SMPC_COMREG,1,7 if mode==0 else 6]]
    elif mode==1:
        expected=[["scsp-register-intent",SCSP_PORT,1,2]]
        expected += [["scsp-ram-intent",SCSP_RAM+4*i,4,0x400] for i in range(256)]
        expected += [["scsp-ram-intent",SCSP_RAM,4,0x0007FFFC],["scsp-ram-intent",DSP_RAM,4,0x4E7160FC]]
    actual=[event for event in writes if event[0]!="stack-save"]
    if actual!=expected:raise ValueError(f"A694 device intent sequence differs; observed {len(actual)} expected {len(expected)}")
    if cpu.pc!=RETURN or cpu.pr!=RETURN or cpu.r[15]!=SP:raise ValueError("A694 return linkage differs")
    expected_work=bytearray(before)
    expected_work[SP-4-WRAM:SP-WRAM]=saved_pr.to_bytes(4,"big")
    if bytes(work_mem)!=bytes(expected_work):raise ValueError("A694 changed WorkRAM-H outside its stack save")
    return {"mode":mode,"seed":seed,"steps":cpu.steps,"pc_trace":[hex(pc) for pc in pcs],"reads":reads,"writes":writes,
            "return_pc":hex(cpu.pc),"return_pr":hex(cpu.pr),"sp_after":hex(cpu.r[15]),
            "smpc_commands":[e[3] for e in expected if e[0]=="smpc-command-intent"],
            "scsp_ram_intents":len([e for e in actual if e[0]=="scsp-ram-intent"]),"workram_unchanged_outside_stack":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"):ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a694-smpc-scsp.v1","status":"failure","entry":hex(ENTRY),"return":hex(RETURN),
            "limits":["Direct constructed A694 modes/registers; captured frame-1200 WorkRAM-H; SMPC and SCSP stores are strict intent events, not hardware effects",
                      "Does not establish A546 caller reachability, SCSP state/timing, SMPC protocol completion, or audio output"]}
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
                for mode,seed in cases():
                    a=execute(kernel,ram,emu,mode,seed);b=execute(kernel,ram,emu,mode,seed)
                    if a!=b:raise ValueError("paired A694 executions differ")
                    rows.append(a)
                try:execute(kernel,ram,emu,0,0,mutate_smpc=True)
                except ValueError as e:
                    if "unexpected a694 write 2010001e" not in str(e).lower():raise
                    smpc_control={"rejected":True,"literal":"0x0600A764","replacement":"0x2010001E","reason":str(e)}
                else:raise ValueError("mutated SMPC address escaped intent contract")
                try:execute(kernel,ram,emu,1,0,mutate_size=True)
                except ValueError as e:
                    if "unexpected scsp ram intent 25a00000/4/000003fc" not in str(e).lower():raise
                    size_control={"rejected":True,"literal":"0x0600A744","replacement":"0x03F8","reason":str(e)}
                else:raise ValueError("mutated SCSP fill size escaped store contract")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[[hex(ENTRY),"0x0600A6D6"],["0x0600A5CE","0x0600A5E4"]],
                    cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),
                    kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,mutations={"smpc_command_address":smpc_control,"scsp_fill_size":size_control},
                    contract="A694 mode0 sends SMPC COMREG command7; mode2 sends command6; mode1 writes SCSP start byte2, fills 1024 bytes with 0x400 longwords, then writes 0x7FFFC at SCSP RAM base and 0x4E7160FC at DSP RAM; other mode returns without device stores.")
            except Exception as e:report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError:print(json.dumps({"status":"failure","reason":"report exists; immutable"}));return 2
if __name__=="__main__":raise SystemExit(main())
