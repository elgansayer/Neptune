#!/usr/bin/env python3
"""Compose A70B8 request setup through A6150 and stop at the A61B0 handoff."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
MAIN,MAIN_END=0x060A70B8,0x060A7150
WRITER,WRITER_END=0x060A6150,0x060A61B0
HANDOFF=0x060A7136
LITERALS={
    0x060A7100:(2,0x0100), 0x060A710C:(4,0x0FFFFFFF),
    0x060A7110:(4,0x05A00000), 0x060A7114:(4,0x05FE0000),
    0x060A7200:(4,0x060FB588), 0x060A7204:(4,WRITER),
    0x060A7208:(4,0x060A61B0), 0x060A720C:(4,0x060A5F98),
    0x060A61EC:(4,0x25FE0000), 0x060A61F0:(4,0x25FE0004),
    0x060A61F4:(4,0x25FE0008),
}
GLOBAL=0x060FB588; SCU_D0R=0x25FE0000; SCU_D0W=0x25FE0004; SCU_D0C=0x25FE0008
SP=0x06002000; STACK_BASE=SP-64; STACK_SIZE=68; GLOBAL_SIZE=4
LIMIT=160; MASK=0xffffffff
POINTERS=(0x059FFFFF,0x05A00000,0x05FDFFFF,0x05FE0000,0xA5A00000)
R5_VALUES=(0,1); R7_VALUES=(0,1); SEEDS=(0,1)

class Handoff(Exception):
    pass

def sha(data): return hashlib.sha256(data).hexdigest()
def corpus(): return [(ptr,r5,r7,seed) for ptr in POINTERS for r5 in R5_VALUES for r7 in R7_VALUES for seed in SEEDS]

def execute(data,emu,ptr,r5,r7,seed,mutation=None):
    if ptr not in POINTERS or r5 not in R5_VALUES or r7 not in R7_VALUES or seed not in SEEDS:
        raise ValueError('A70B8 arguments outside declared domain')
    main=bytearray(data[MAIN-BASE:MAIN_END-BASE]); writer=bytearray(data[WRITER-BASE:WRITER_END-BASE])
    if len(main)!=MAIN_END-MAIN or len(writer)!=WRITER_END-WRITER: raise ValueError('original A70B8/A6150 range incomplete')
    literals={a:v for a,(n,v) in LITERALS.items()}
    for address,(size,value) in LITERALS.items():
        if int.from_bytes(data[address-BASE:address-BASE+size],'big')!=value:
            raise ValueError(f'original literal identity differs at {address:08x}')
    if mutation is not None:
        address,value=mutation
        if address!=0x060A61EC or not 0<=value<=MASK:
            raise ValueError('only the composed A6150 D0R literal mutation is supported')
        literals[address]=value
    stack=bytearray((0x73+seed*29+i*13)&255 for i in range(STACK_SIZE))
    caller_word=(0xA7102301+seed*0x01020304)&MASK
    stack[SP-STACK_BASE:SP-STACK_BASE+4]=caller_word.to_bytes(4,'big')
    original_stack=bytes(stack);events=[]
    global_word=bytearray(b'\x5a\xa5\x3c\xc3');original_global=bytes(global_word)
    desc_address=SP-52
    def in_stack(a,n): return STACK_BASE<=a and a+n<=STACK_BASE+STACK_SIZE
    def in_scu(a,n): return n==4 and SCU_D0R<=a<SCU_D0R+0x100
    class Memory(emu.Memory):
        def __init__(self): super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not (MAIN<=address<MAIN_END or WRITER<=address<WRITER_END):
                    raise ValueError(f'fetch outside A70B8/A6150 to A61B0 handoff: {address:08x}/{n}')
            elif address in literals and LITERALS[address][0]==n:
                value=literals[address];events.append(['literal',address,n,value]);return value
            elif address==GLOBAL and n==4:
                value=super().read(address,n);events.append(['global-read',address,n,value]);return value
            elif in_stack(address,n) and n in (2,4):
                value=super().read(address,n);events.append(['stack-read',address-STACK_BASE,n,value]);return value
            else: raise ValueError(f'unexpected composed A70B8 read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if in_stack(address,n) and n in (2,4):
                events.append(['stack-write',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            if address==GLOBAL and n==4:
                events.append(['global-write',address,n,value&MASK]);return super().write(address,n,value)
            if in_scu(address,n):
                events.append(['scu-write-intent',address,n,value&MASK]);return
            raise ValueError(f'unexpected composed A70B8 write {address:08x}/{n}')
    memory=Memory()
    memory.add(MAIN,len(main),main);memory.add(WRITER,len(writer),writer)
    stack_mem=memory.add(STACK_BASE,STACK_SIZE,stack)
    global_mem=memory.add(GLOBAL,GLOBAL_SIZE,global_word)
    class CPU(emu.CPU):
        def __init__(self,m):super().__init__(m);self.executed=[]
        def fetch(self,pc):
            if pc==HANDOFF: raise Handoff('A70B8/A6150 returned to the fenced A61B0 call site')
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not (MAIN<=pc<MAIN_END or WRITER<=pc<WRITER_END):
                raise ValueError(f'PC/budget escaped A70B8/A6150 composition at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0x52000000+i*0x01020305+seed*0x10001+ptr+r5+r7)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=ptr;cpu.r[5]=r5;cpu.r[6]=(0x76543210+seed)&MASK;cpu.r[7]=r7;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy()
    try:cpu.call(MAIN,max_steps=LIMIT)
    except Handoff:pass
    else:raise ValueError('A70B8 path did not stop at the declared A61B0 handoff')
    if cpu.pc!=HANDOFF:raise ValueError(f'wrong handoff PC {cpu.pc:08x}')
    descriptor=bytes(stack_mem[desc_address-STACK_BASE:desc_address-STACK_BASE+40])
    words=[int.from_bytes(descriptor[i*4:i*4+4],'big') for i in range(10)]
    masked=ptr&0x0fffffff
    expected_state=0 if r5==0 else (1 if 0x05A00000<=masked<0x05FE0000 else 2)
    expected_words=[before[6],ptr,caller_word,0x0100 if r7 else 0,expected_state,0,0,0,7,3]
    if words!=expected_words:raise ValueError(f'A70B8 descriptor fields differ: {words!r} != {expected_words!r}')
    expected_scu=[
        ['scu-write-intent',SCU_D0R,4,before[6]],['scu-write-intent',SCU_D0W,4,ptr],
        ['scu-write-intent',SCU_D0C,4,caller_word],
        ['scu-write-intent',SCU_D0C+4,4,words[3]|words[4]],
        ['scu-write-intent',SCU_D0C+12,4,words[6]<<16|words[5]|words[7]<<8|words[8]],
    ]
    actual_scu=[e for e in events if e[0]=='scu-write-intent']
    if actual_scu!=expected_scu:raise ValueError(f'composed A70B8/A6150 SCU intents differ: {actual_scu!r}')
    if int.from_bytes(global_mem,'big')!=1:raise ValueError('A70B8 published unexpected global value')
    if bytes(stack_mem[SP-STACK_BASE:SP-STACK_BASE+4])!=caller_word.to_bytes(4,'big'):
        raise ValueError('caller stack argument changed')
    if cpu.r[15]!=desc_address or cpu.r[4]!=desc_address or cpu.r[5]!=0:
        raise ValueError('A6150 boundary SP/R4/R5 differs')
    if cpu.pr!=HANDOFF:raise ValueError(f'PR at A61B0 handoff differs: {cpu.pr:08x}')
    for reg in (8,9,10,11,12):
        if cpu.r[reg]!=before[reg]:raise ValueError(f'callee-saved register r{reg} changed before handoff')
    saved_r14=int.from_bytes(stack_mem[SP-4-STACK_BASE:SP-STACK_BASE],'big')
    saved_r13=int.from_bytes(stack_mem[SP-8-STACK_BASE:SP-4-STACK_BASE],'big')
    saved_pr=int.from_bytes(stack_mem[SP-12-STACK_BASE:SP-8-STACK_BASE],'big')
    if (saved_r14,saved_r13,saved_pr)!=(before[14],before[13],emu.RETURN_SENTINEL):
        raise ValueError('A70B8 saved register/PR frame differs at helper handoff')
    if mutation is None and bytes(stack_mem)==original_stack:
        raise ValueError('expected A70B8/A6150 stack frame was not written')
    return {'pointer':ptr,'masked_pointer':masked,'r5':r5,'r7':r7,'seed':seed,'descriptor_words':words,
        'descriptor_sha256':sha(descriptor),'global_word':int.from_bytes(global_mem,'big'),
        'scu_write_intents':actual_scu,'event_sha256':sha(json.dumps(events,separators=(',',':')).encode()),
        'events':events,'handoff_pc':cpu.pc,'steps':cpu.steps,
        'executed_pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed)),
        'stack_sha256':sha(bytes(stack_mem)),'global_initial_sha256':sha(original_global)}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-a70b8-scu-handoff.v1','status':'failure','kernel_sha256':KERNEL,
        'main_range':[hex(MAIN),hex(MAIN_END)],'writer_range':[hex(WRITER),hex(WRITER_END)],
        'handoff_pc':hex(HANDOFF),'limits':['Constructed A70B8 arguments/stack/global and MMIO write-intent sink',
        'Execution stops before A61B0; no SCU effects, BIOS calls, device timing, natural caller, or gameplay']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for ptr,r5,r7,seed in corpus():
                    one=execute(data,emu,ptr,r5,r7,seed);two=execute(data,emu,ptr,r5,r7,seed)
                    if one!=two:raise ValueError('repeated A70B8/A6150 handoff differs')
                    rows.append(one)
                try:execute(data,emu,0x05A00000,1,0,0,(0x060A61EC,0x25FE0080))
                except ValueError as e:
                    if 'composed a70b8/a6150 scu intents differ' not in str(e).lower():raise
                    rejected=True
                else:raise ValueError('mutated composed SCU register address was accepted')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(data[MAIN-BASE:MAIN_END-BASE]+data[WRITER-BASE:WRITER_END-BASE]),
                    source_literals_sha256=sha(b''.join(data[x-BASE:x-BASE+size] for x,(size,_) in LITERALS.items())),
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    mutation_control={'literal':'0x060A61EC','replacement':'0x25FE0080','rejected':rejected},
                    contract='A70B8 composes a constructed pointer classification and descriptor with A6150 original SCU write intents, then stops at 0x060A7136 before A61B0. The sink records write intents only.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
