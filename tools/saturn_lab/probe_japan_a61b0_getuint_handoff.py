#!/usr/bin/env python3
"""Execute A61B0 to its first BIOS SYS_GETUINT call boundary."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,HANDOFF=0x060A61B0,0x060A6220
LITERAL_VALUES={0x060A61E8:(2,0xFF0F),0x060A61F8:(4,0x060A62D8),
    0x060A62B8:(4,0x060FCD14),0x060A62BC:(4,0x06000304)}
BIOS_SLOT=0x06000304;GETUINT_PTR=0x06005000;GLOBAL=0x060FCD14
SP=0x06002000;STACK_BASE=SP-40;STACK_SIZE=40;GLOBAL_SIZE=16
LIMIT=64;SR_VALUES=(0x030,0x130,0x230,0x3F0);SEEDS=(0,1);MASK=0xffffffff

class Handoff(Exception):pass
def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return [(sr,seed) for sr in SR_VALUES for seed in SEEDS]

def execute(data,emu,sr,seed,mutation=None):
    if sr not in SR_VALUES or seed not in SEEDS:raise ValueError('A61B0 state outside declared domain')
    code=bytearray(data[ENTRY-BASE:HANDOFF-BASE])
    literals={a:v for a,(n,v) in LITERAL_VALUES.items()}
    for a,(n,v) in LITERAL_VALUES.items():
        if int.from_bytes(data[a-BASE:a-BASE+n],'big')!=v:raise ValueError(f'A61B0 source literal differs at {a:08x}')
    if mutation is not None:
        a,v=mutation
        if a!=0x060A62BC or v!=0x06000308:raise ValueError('only BIOS function-pointer slot mutation is supported')
        literals[0x060A62BC]=v
    events=[]
    stack=bytearray((0x8B+seed*31+i*17)&255 for i in range(STACK_SIZE)); initial_stack=bytes(stack)
    global_data=bytearray((0x49+seed*13+i*19)&255 for i in range(GLOBAL_SIZE))
    system_data=bytearray(GETUINT_PTR.to_bytes(4,'big')+b'\x06\x00\x50\x04')
    def in_stack(a,n):return STACK_BASE<=a and a+n<=SP and n==4 and (a-STACK_BASE)%4==0
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=address<HANDOFF) or 0x060A61E8<=address<0x060A6204:
                    raise ValueError(f'fetch outside A61B0 pre-BIOS fence: {address:08x}/{n}')
            elif address in literals and LITERAL_VALUES[address][0]==n:
                value=literals[address];events.append(['literal',address,n,value]);return value
            elif BIOS_SLOT<=address and address+n<=BIOS_SLOT+len(system_data) and n==4:
                value=super().read(address,n);events.append(['bios-system-slot',address,n,value]);return value
            elif in_stack(address,n):
                value=super().read(address,n);events.append(['stack-read',address-STACK_BASE,n,value]);return value
            elif GLOBAL<=address and address+n<=GLOBAL+GLOBAL_SIZE and n==4 and (address-GLOBAL)%4==0:
                value=super().read(address,n);events.append(['global-read',address,n,value]);return value
            else:raise ValueError(f'unexpected A61B0 read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if in_stack(address,n):
                events.append(['stack-write',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            if GLOBAL<=address and address+n<=GLOBAL+GLOBAL_SIZE and n==4 and (address-GLOBAL)%4==0:
                events.append(['global-write',address,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected A61B0 write {address:08x}/{n}')
    mem=Memory();mem.add(ENTRY,len(code),code)
    stack_mem=mem.add(STACK_BASE,STACK_SIZE,stack);global_mem=mem.add(GLOBAL,GLOBAL_SIZE,global_data)
    mem.add(BIOS_SLOT,len(system_data),system_data)
    class CPU(emu.CPU):
        def __init__(self,m):super().__init__(m);self.executed=[]
        def fetch(self,pc):
            if pc==HANDOFF:raise Handoff('A61B0 is at its first BIOS SYS_GETUINT call')
            mem.fetching=True
            try:return super().fetch(pc)
            finally:mem.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<HANDOFF or 0x060A61E8<=pc<0x060A6204:
                raise ValueError(f'A61B0 PC/budget escaped at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(mem);cpu.r=[(0x46000000+i*0x01020305+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=0;cpu.r[15]=SP;cpu.sr=sr
    before=cpu.r.copy()
    try:cpu.call(ENTRY,max_steps=LIMIT)
    except Handoff:pass
    else:raise ValueError('A61B0 did not stop at the first BIOS call boundary')
    if cpu.pc!=HANDOFF:raise ValueError(f'wrong A61B0 handoff PC {cpu.pc:08x}')
    if cpu.r[1]!=GETUINT_PTR:raise ValueError(f'constructed BIOS SYS_GETUINT pointer differs: {cpu.r[1]:08x}')
    if cpu.r[4]!=0 or cpu.r[8]!=GLOBAL or cpu.r[12]!=0x060A62D8 or cpu.r[14]!=75:
        raise ValueError(f'A61B0 first BIOS call arguments/state differ: r4={cpu.r[4]:08x} r8={cpu.r[8]:08x} r12={cpu.r[12]:08x} r14={cpu.r[14]:08x}')
    if cpu.r[15]!=STACK_BASE+12 or cpu.pr!=emu.RETURN_SENTINEL:raise ValueError('A61B0 frame or PR differs at call boundary')
    if cpu.sr&0xF0!=0xF0:raise ValueError(f'A61B0 interrupt priority not masked at handoff: {cpu.sr:08x}')
    expected_saved={SP-4:before[14],SP-8:before[13],SP-12:before[12],SP-16:before[8],SP-20:emu.RETURN_SENTINEL}
    for address,value in expected_saved.items():
        actual=int.from_bytes(stack_mem[address-STACK_BASE:address-STACK_BASE+4],'big')
        if actual!=value:raise ValueError(f'A61B0 saved frame differs at {address:08x}')
    if len(global_mem)!=GLOBAL_SIZE:raise ValueError('constructed BIOS global map changed shape')
    return {'sr_input':sr,'seed':seed,'handoff_pc':cpu.pc,'steps':cpu.steps,
        'bios_slot_value':cpu.r[1],'bios_argument_r4':cpu.r[4],'global_base_r8':cpu.r[8],
        'service_table_r12':cpu.r[12],'selected_service_r14':cpu.r[14],
        'events':events,'event_sha256':sha(json.dumps(events,separators=(',',':')).encode()),
        'stack_sha256':sha(bytes(stack_mem)),'global_sha256':sha(bytes(global_mem)),
        'pc_sha256':sha(b''.join(x.to_bytes(4,'big') for x in cpu.executed))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-a61b0-getuint-handoff.v1','status':'failure','kernel_sha256':KERNEL,
        'range':[hex(ENTRY),hex(HANDOFF)],'bios_slot':hex(BIOS_SLOT),'constructed_sys_getuint_pointer':hex(GETUINT_PTR),
        'limits':['Constructed BIOS system pointer table/global and A61B0 entry ABI','Stops before BIOS execution; no BIOS behavior or later SCU effects']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for sr,seed in corpus():
                    x=execute(data,emu,sr,seed);y=execute(data,emu,sr,seed)
                    if x!=y:raise ValueError('repeated A61B0 prefix differs')
                    rows.append(x)
                try:execute(data,emu,0x3F0,0,(0x060A62BC,0x06000308))
                except ValueError as e:
                    if 'constructed bios sys_getuint pointer differs' not in str(e).lower():raise
                    rejected=True
                else:raise ValueError('mutated BIOS system slot escaped ABI check')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(data[ENTRY-BASE:HANDOFF-BASE]),
                    source_literals_sha256=sha(b''.join(data[a-BASE:a-BASE+n] for a,(n,_) in LITERAL_VALUES.items())),
                    probe_sha256=sha(Path(__file__).read_bytes()),mutation_control={'slot_literal':'0x060A62BC','replacement':'0x06000308','rejected':rejected},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='A61B0 masks interrupt priority, selects service 75 from constructed R4=0, loads a constructed SYS_GETUINT pointer from 06000304, and stops at the original JSR before BIOS code executes.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
