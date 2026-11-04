#!/usr/bin/env python3
"""Execute Japan A4C4/A638/A546 through A714, stopping before A6D6."""
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
ENTRY,STOP=0x0600A4C4,0x0600A6D6
SP=0x06002000
POLL_WORD=0x060B3D40
COUNTER=0x060B3D42
LONG_POINTER=0x060B3D44
HALF_POINTER=0x060B3D48
DESCRIPTOR,DESCRIPTOR_SIZE=0x060BCE8C,96
TIMING_WORD=0x060BCE88
VDP1=0x25C00000
LONG_DEST=0x25E80000
HALF_DEST=0x25F00800
SCU_PPAF,SCU_PPD,SCU_PDD=0x25FE0080,0x25FE0084,0x25FE008C
SCSP_CONTROL,SCSP_RAM,SCSP_DSP=0x25B00400,0x25A00000,0x25A00400
SMPC_COMREG=0x2010001F
CODE=(tuple(range(0x0600A4C4,0x0600A4D2,2))+
      tuple(range(0x0600A52C,0x0600A55A,2))+
      tuple(range(0x0600A610,0x0600A620,2))+
      tuple(range(0x0600A638,0x0600A66C,2))+
      tuple(range(0x0600A66C,0x0600A6D6,2))+
      tuple(range(0x0600A714,0x0600A73E,2))+
      tuple(range(0x0600A58E,0x0600A5E4,2)))
LITERALS={
 0x0600A528:(4,COUNTER),0x0600A624:(4,COUNTER),0x0600A62C:(4,POLL_WORD),0x0600A742:(2,0x01FE),
 0x0600A758:(4,0x0001FFFC),0x0600A75C:(4,LONG_POINTER),0x0600A760:(4,HALF_POINTER),
 0x0600A73E:(2,0x013F),0x0600A740:(2,0x8000),0x0600A74C:(4,DESCRIPTOR),
 0x0600A750:(4,TIMING_WORD),0x0600A754:(4,VDP1),
 0x0600A744:(2,0x03FC),0x0600A764:(4,SMPC_COMREG),0x0600A768:(4,SCSP_CONTROL),
 0x0600A76C:(4,SCSP_RAM),0x0600A770:(4,0x0007FFFC),0x0600A774:(4,0x4E7160FC),
 0x0600A778:(4,SCSP_DSP),0x0600A74A:(2,0x0100),0x0600A77C:(4,SCU_PPAF),
 0x0600A780:(4,SCU_PPD),0x0600A784:(4,0xF0000000),0x0600A788:(4,SCU_PDD)}
SEEDS=(0,1)
LOOP_COUNT=4
LIMIT=800000
POLL_SAMPLES=(5,5,6, 6,6,7, 7,7,8, 8,8,9)
EXPECTED_LONG_WRITES=131072
EXPECTED_HALF_WRITES=1024

class Fence(ValueError): pass
def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":" )).encode()

def digest_event(digest,counts,first_last,name,address,width,value):
    event=[name,address,width,value]
    digest.update(canonical(event))
    counts[name]=counts.get(name,0)+1
    if name not in first_last: first_last[name]=[event,None]
    first_last[name][1]=event

def execute(kernel,ram,emu,seed,mutate_long_pointer=False):
    if seed not in SEEDS: raise ValueError("A546 seed outside declared corpus")
    if len(kernel)!=KERNEL_SIZE or sha(kernel)!=KERNEL_SHA or len(ram)!=WRAM_SIZE:
        raise ValueError("complete original Japan kernel and captured WorkRAM-H are required")
    for start,end in ((0x0600A4C4,0x0600A4D2),(0x0600A52C,0x0600A55A),
                      (0x0600A610,0x0600A620),(0x0600A638,0x0600A66C),
                      (0x0600A66C,0x0600A6D6),(0x0600A714,0x0600A73E),
                      (0x0600A58E,0x0600A5E4)):
        if ram[start-WRAM:end-WRAM]!=kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured original code differs at {start:08x}")
    for address,(width,expected) in LITERALS.items():
        actual=int.from_bytes(kernel[address-BASE:address-BASE+width],"big")
        if actual!=expected: raise ValueError(f"original A546-family literal differs at {address:08x}: {actual:08x}")
    expected_initial={POLL_WORD:5,COUNTER:4,LONG_POINTER:LONG_DEST,HALF_POINTER:HALF_DEST}
    for address,value in expected_initial.items():
        width=4 if address>=LONG_POINTER else 2
        if int.from_bytes(ram[address-WRAM:address-WRAM+width],"big")!=value:
            raise ValueError(f"captured A546 word differs at {address:08x}")
    work=bytearray(ram)
    if mutate_long_pointer: work[LONG_POINTER-WRAM:LONG_POINTER-WRAM+4]=(LONG_DEST+4).to_bytes(4,"big")

    saved_r14=0x6C000014+seed
    stack_allowed={SP-4:{saved_r14,0x0600A534,0x0600A538,0x0600A53E},SP-8:{0x0600A4C8}}
    stack_seen=[]
    poll_index=[0]
    poll_reads=[]
    work_reads={"captured-pointer":0,"counter":0,"timing":0,"descriptor":0,"stack":0}
    read_counts={}; read_digest=hashlib.sha256(); read_first_last={}
    write_counts={}; write_digest=hashlib.sha256(); write_first_last={}
    pc_digest=hashlib.sha256(); pc_count=0; pc_first_last=[None,None]; pc_counts={}
    descriptor_fill_count=0; descriptor_setup={0:9,20:0x013F,22:int.from_bytes(ram[TIMING_WORD-WRAM:TIMING_WORD-WRAM+2],"big"),32:10,64:0xFFFF8000}
    vdp1_count=0; long_count=0; half_count=0; scsp_count=0; scsp_fill_count=0; smpc_commands=[]; scu_index=0
    counter_values=[0,1,2,3,4]
    long_pointer_updates=[LONG_DEST+0x20000*n for n in range(1,LOOP_COUNT+1)]
    half_pointer_updates=[HALF_DEST+0x200*n for n in range(1,LOOP_COUNT+1)]
    scu_expected=[["scu-mmio-intent",SCU_PPAF,4,0]]
    scu_expected += [["scu-mmio-intent",SCU_PPD,4,0xF0000000] for _ in range(256)]
    for n in range(256):
        scu_expected.extend([["scu-mmio-intent",SCU_PDD-4,4,n],["scu-mmio-intent",SCU_PDD,4,0]])
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,width):
            nonlocal descriptor_fill_count
            if self.fetching:
                if width!=2 or address not in CODE: raise Fence(f"A546 PC fence {address:08x}/{width}")
                return super().read(address,width)
            if address in LITERALS and LITERALS[address][0]==width:
                value=super().read(address,width); digest_event(read_digest,read_counts,read_first_last,"original-literal",address,width,value); return value
            if address==POLL_WORD and width==2:
                if poll_index[0]>=len(POLL_SAMPLES): raise ValueError("A546 exhausted declared A610 input samples")
                value=POLL_SAMPLES[poll_index[0]];poll_index[0]+=1
                poll_reads.append(value); digest_event(read_digest,read_counts,read_first_last,"external-A610-sample",address,width,value); return value
            if address==TIMING_WORD and width==2:
                value=super().read(address,width);work_reads["timing"]+=1;digest_event(read_digest,read_counts,read_first_last,"captured-timing-word",address,width,value);return value
            if DESCRIPTOR<=address<DESCRIPTOR+DESCRIPTOR_SIZE and width==2:
                value=super().read(address,width);work_reads["descriptor"]+=1;digest_event(read_digest,read_counts,read_first_last,"descriptor-source",address,width,value);return value
            if address in (LONG_POINTER,HALF_POINTER) and width==4:
                value=super().read(address,width);work_reads["captured-pointer"]+=1;digest_event(read_digest,read_counts,read_first_last,"workram-pointer",address,width,value);return value
            if address==COUNTER and width==2:
                value=super().read(address,width);work_reads["counter"]+=1;digest_event(read_digest,read_counts,read_first_last,"workram-counter",address,width,value);return value
            if address in stack_allowed and width==4:
                value=super().read(address,width);work_reads["stack"]+=1;digest_event(read_digest,read_counts,read_first_last,"stack-restore",address,width,value);return value
            raise ValueError(f"unexpected A546 read {address:08x}/{width}")
        def write(self,address,width,value):
            nonlocal descriptor_fill_count,vdp1_count,long_count,half_count,scsp_count,scsp_fill_count,scu_index
            value &= 0xFFFFFFFF
            if address in stack_allowed and width==4 and value in stack_allowed[address]:
                stack_seen.append([address,width,value]);digest_event(write_digest,write_counts,write_first_last,"stack-save",address,width,value);return super().write(address,width,value)
            if DESCRIPTOR<=address<DESCRIPTOR+DESCRIPTOR_SIZE and width==2:
                offset=address-DESCRIPTOR
                if descriptor_fill_count<DESCRIPTOR_SIZE//2:
                    expected=0
                    if offset!=descriptor_fill_count*2: raise ValueError(f"A638 descriptor fill order differs at {address:08x}")
                    descriptor_fill_count+=1
                elif offset in descriptor_setup: expected=descriptor_setup[offset]
                else: raise ValueError(f"unexpected A638 descriptor setup at {address:08x}")
                if value!=expected: raise ValueError(f"unexpected A638 descriptor write {address:08x}/{width}/{value:08x}; expected {expected:04x}")
                digest_event(write_digest,write_counts,write_first_last,"descriptor-write",address,width,value);return super().write(address,width,value)
            if address==COUNTER and width==2:
                if not counter_values or value!=counter_values.pop(0): raise ValueError(f"unexpected A546 counter store {address:08x}/{width}/{value:08x}")
                digest_event(write_digest,write_counts,write_first_last,"counter-store",address,width,value);return super().write(address,width,value)
            if address==LONG_POINTER and width==4:
                if not long_pointer_updates or value!=long_pointer_updates.pop(0): raise ValueError(f"unexpected A66C pointer update {address:08x}/{width}/{value:08x}")
                digest_event(write_digest,write_counts,write_first_last,"long-pointer-update",address,width,value);return super().write(address,width,value)
            if address==HALF_POINTER and width==4:
                if not half_pointer_updates or value!=half_pointer_updates.pop(0): raise ValueError(f"unexpected A680 pointer update {address:08x}/{width}/{value:08x}")
                digest_event(write_digest,write_counts,write_first_last,"half-pointer-update",address,width,value);return super().write(address,width,value)
            if VDP1<=address<VDP1+DESCRIPTOR_SIZE and width==2:
                expected=VDP1+2*vdp1_count
                if address!=expected or vdp1_count>=DESCRIPTOR_SIZE//2: raise ValueError(f"unexpected VDP1 write intent {address:08x}; expected {expected:08x}")
                vdp1_count+=1;digest_event(write_digest,write_counts,write_first_last,"vdp1-write-intent",address,width,value);return
            if LONG_DEST<=address<LONG_DEST+0x80000 and width==4 and value==0:
                expected=LONG_DEST+4*long_count
                if address!=expected or long_count>=EXPECTED_LONG_WRITES: raise ValueError(f"unexpected A66C clear intent {address:08x}; expected {expected:08x}")
                long_count+=1;digest_event(write_digest,write_counts,write_first_last,"a66c-memory-write-intent",address,width,value);return
            if HALF_DEST<=address<HALF_DEST+0x800 and width==2 and value==0:
                expected=HALF_DEST+2*half_count
                if address!=expected or half_count>=EXPECTED_HALF_WRITES: raise ValueError(f"unexpected A680 clear intent {address:08x}; expected {expected:08x}")
                half_count+=1;digest_event(write_digest,write_counts,write_first_last,"a680-memory-write-intent",address,width,value);return
            if address==SMPC_COMREG and width==1:
                if value not in (7,6): raise ValueError(f"unexpected SMPC command intent {value:08x}")
                smpc_commands.append(value);digest_event(write_digest,write_counts,write_first_last,"smpc-write-intent",address,width,value);return
            if SCSP_CONTROL<=address<SCSP_CONTROL+1 and width==1:
                if value!=2: raise ValueError(f"unexpected SCSP control intent {value:08x}")
                scsp_count+=1;digest_event(write_digest,write_counts,write_first_last,"scsp-write-intent",address,width,value);return
            if SCSP_RAM<=address<SCSP_RAM+0x400 and width==4:
                if address==SCSP_RAM and value==0x7FFFC and scsp_fill_count==256:
                    scsp_count+=1
                elif address==SCSP_RAM+4*scsp_fill_count and value==0x400 and scsp_fill_count<256:
                    scsp_count+=1;scsp_fill_count+=1
                else: raise ValueError(f"unexpected SCSP RAM intent {address:08x}/{width}/{value:08x}")
                digest_event(write_digest,write_counts,write_first_last,"scsp-write-intent",address,width,value);return
            if address==SCSP_DSP and width==4 and value==0x4E7160FC and scsp_count==258:
                scsp_count+=1;digest_event(write_digest,write_counts,write_first_last,"scsp-write-intent",address,width,value);return
            if address in (SCU_PPAF,SCU_PPD,SCU_PDD,SCU_PDD-4) and width==4:
                if scu_index>=len(scu_expected): raise ValueError("A714 exceeded declared SCU event sequence")
                expected=scu_expected[scu_index]
                actual=["scu-mmio-intent",address,width,value]
                if actual!=expected: raise ValueError(f"unexpected SCU intent {actual!r}; expected {expected!r}")
                scu_index+=1;digest_event(write_digest,write_counts,write_first_last,*actual);return
            raise ValueError(f"unexpected A546 write {address:08x}/{width}/{value:08x}")

    mem=Memory(); work_mem=mem.add(WRAM,WRAM_SIZE,work)
    class CPU(emu.CPU):
        def fetch(self,pc):
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            nonlocal pc_count
            if self.steps>=LIMIT or pc not in CODE: raise Fence(f"A546 instruction fence {pc:08x}")
            pc_digest.update(pc.to_bytes(4,"big"));pc_count+=1
            if pc_first_last[0] is None: pc_first_last[0]=pc
            pc_first_last[1]=pc;pc_counts[hex(pc)]=pc_counts.get(hex(pc),0)+1
            return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.r=[(0x47000000+n*0x01020307+seed*0x101)&0xFFFFFFFF for n in range(16)]
    cpu.r[14]=saved_r14;cpu.r[15]=SP;cpu.r[13]=0x6D00000D+seed
    cpu.sr=0xF0;cpu.vbr=0x06000000;cpu.pr=0xFFFFFE00;cpu.pc=ENTRY
    before=bytes(work_mem)
    while cpu.pc!=STOP:
        cpu.step()
        if cpu.steps>LIMIT: raise ValueError("A546 instruction budget exceeded")
    if poll_index[0]!=len(POLL_SAMPLES) or len(poll_reads)!=len(POLL_SAMPLES): raise ValueError("A610 did not consume exactly the declared sample stream")
    if descriptor_fill_count!=DESCRIPTOR_SIZE//2: raise ValueError("A638 descriptor zero-fill count differs")
    if vdp1_count!=DESCRIPTOR_SIZE//2: raise ValueError(f"A638 emitted {vdp1_count} VDP1 intents, expected 48")
    if long_count!=EXPECTED_LONG_WRITES: raise ValueError(f"A546 emitted {long_count} A66C intents, expected {EXPECTED_LONG_WRITES}")
    if half_count!=EXPECTED_HALF_WRITES: raise ValueError(f"A546 emitted {half_count} A680 intents, expected {EXPECTED_HALF_WRITES}")
    if scu_index!=len(scu_expected): raise ValueError(f"A714 emitted {scu_index} SCU intents, expected {len(scu_expected)}")
    if counter_values or long_pointer_updates or half_pointer_updates: raise ValueError("A546 did not complete all four pointer/counter updates")
    if scsp_count!=259 or smpc_commands!=[7,6]: raise ValueError(f"A694 mode intents differ: SCSP={scsp_count}, SMPC={smpc_commands}")
    if cpu.pc!=STOP or cpu.r[15]!=SP or cpu.r[13]!=LOOP_COUNT or cpu.pr!=0x0600A556:
        raise ValueError("A546 stop boundary/linkage differs")
    expected=bytearray(before)
    desc=bytearray(DESCRIPTOR_SIZE)
    for offset,value in descriptor_setup.items():desc[offset:offset+2]=(value&0xFFFF).to_bytes(2,"big")
    expected[DESCRIPTOR-WRAM:DESCRIPTOR-WRAM+DESCRIPTOR_SIZE]=desc
    expected[COUNTER-WRAM:COUNTER-WRAM+2]=(LOOP_COUNT).to_bytes(2,"big")
    expected[LONG_POINTER-WRAM:LONG_POINTER-WRAM+4]=(LONG_DEST+0x80000).to_bytes(4,"big")
    expected[HALF_POINTER-WRAM:HALF_POINTER-WRAM+4]=(HALF_DEST+0x800).to_bytes(4,"big")
    expected[SP-4-WRAM:SP-WRAM]=(0x0600A53E).to_bytes(4,"big")
    expected[SP-8-WRAM:SP-4-WRAM]=(0x0600A4C8).to_bytes(4,"big")
    if bytes(work_mem)!=bytes(expected): raise ValueError("A546 changed WorkRAM-H outside descriptor/counter/pointers/stack")
    return {"seed":seed,"steps":cpu.steps,"executed_pc_count":pc_count,
            "pc_trace_sha256":pc_digest.hexdigest(),"pc_counts":pc_counts,"pc_first_last":[hex(pc_first_last[0]),hex(pc_first_last[1])],
            "reads":{"counts":read_counts,"sha256":read_digest.hexdigest(),"first_last":read_first_last,
                     "workram_read_classes":work_reads,"a610_samples":[hex(v) for v in poll_reads]},
            "writes":{"counts":write_counts,"sha256":write_digest.hexdigest(),"first_last":write_first_last},
            "loop_iterations":LOOP_COUNT,"counter_after":hex(int.from_bytes(work_mem[COUNTER-WRAM:COUNTER-WRAM+2],"big")),
            "a66c":{"longword_intents":long_count,"bytes":long_count*4,"first":"0x25E80000","last":"0x25EFFFFC","pointer_after":"0x25F00000"},
            "a680":{"halfword_intents":half_count,"bytes":half_count*2,"first":"0x25F00800","last":"0x25F00FFE","pointer_after":"0x25F01000"},
            "a638":{"descriptor":"0x060BCE8C","descriptor_bytes":DESCRIPTOR_SIZE,"vdp1_intents":vdp1_count},
            "a694":{"selected_modes":[0,1,2,3],"smpc_commands":[7,6],"scsp_intents":scsp_count},
            "a714":{"scu_intents":scu_index},"stop_pc":hex(cpu.pc),"return_pr":hex(cpu.pr),"sp_after":hex(cpu.r[15]),
            "workram_unchanged_outside_declared_state":True}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("kernel","state","checkpoint","saturn-recomp","report"):ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args(argv)
    report={"schema":"neptune.original-japan-a546-loop-prefix.v1","status":"failure","entry":hex(ENTRY),"stop":hex(STOP),
            "limits":["Starts at A4C4 with constructed registers and captured frame-1200 WorkRAM-H; A472 caller and natural A546 reachability are not established",
                      "A610 uses explicit constructed changing samples; all VDP1/VRAM/SMPC/SCSP/SCU writes are strict intents, not device effects",
                      "Stops before A6D6 because its SH-2 on-chip register behavior is unresolved; A78C and BIOS epilogue are not included"]}
    try:
        with args.report.open("x",encoding="utf-8") as out:
            try:
                meta=json.loads(args.checkpoint.read_text());state=pinned.read_bounded(args.state,16*1024*1024)
                if meta.get("frame")!=1200 or meta.get("identity",{}).get("core_sha256")!=CORE_SHA or sha(state)!=STATE_SHA or meta.get("state_sha256")!=STATE_SHA:
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel=pinned.read_bounded(args.kernel,KERNEL_SIZE)
                if sha(kernel)!=KERNEL_SHA:raise ValueError("original Japan kernel identity differs")
                ram=sg.cpu_words(sg.field(sg.parse(state),"MAIN","WorkRAMH",WRAM_SIZE),"little")
                if sha(ram)!=RAM_SHA:raise ValueError("normalized frame-1200 WorkRAM-H identity differs")
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for seed in SEEDS:
                    first=execute(kernel,ram,emu,seed);second=execute(kernel,ram,emu,seed)
                    if first!=second:raise ValueError("paired A546 loop executions differ")
                    rows.append(first)
                try:execute(kernel,ram,emu,0,mutate_long_pointer=True)
                except ValueError as e:
                    if "unexpected a66c clear intent 25e80004" not in str(e).lower():raise
                    pointer_control={"rejected":True,"replacement":"0x25E80004","reason":str(e)}
                else:raise ValueError("mutated A66C start pointer escaped strict sink")
                report.update(status="success",original_game_bytes_executed=True,captured_snapshot_data_used=True,
                    release="Japan T-14302G V1.000",source_file="0KRNL.BIN",cpu="master SH-2",
                    code_ranges=[["0x0600A4C4","0x0600A4D2"],["0x0600A52C","0x0600A55A"],
                                 ["0x0600A610","0x0600A620"],["0x0600A638","0x0600A66C"],
                                 ["0x0600A66C","0x0600A6D6"],["0x0600A714","0x0600A73E"],
                                 ["0x0600A58E","0x0600A5E4"]],cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(canonical(rows)),kernel_sha256=KERNEL_SHA,state_sha256=STATE_SHA,
                    normalized_workram_sha256=RAM_SHA,probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    mutation_controls={"a66c_destination":pointer_control},
                    contract="From constructed A4C4 entry, original A638 initializes the descriptor and emits 48 VDP1 intents; A546 performs four iterations calling original A610/A680/A66C/A694 with modes 0..3, increments B3D42 to four, then original A714 emits 769 SCU intents: one PPAF clear, 256 PPD writes, and 256 paired PDD/PDD-4 writes. Execution stops at A6D6 before on-chip register effects.")
            except Exception as e:report["error"]={"type":type(e).__name__,"reason":str(e)}
            out.write(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
        print(json.dumps({"status":report["status"],"cases":report.get("cases",0),"report":str(args.report)}))
        return 0 if report["status"]=="success" else 1
    except FileExistsError:print(json.dumps({"status":"failure","reason":"report exists; immutable"}));return 2

if __name__=="__main__":raise SystemExit(main())
