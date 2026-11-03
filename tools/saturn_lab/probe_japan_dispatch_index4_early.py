#!/usr/bin/env python3
"""Compose original A6C94 index 4 through A72D8/A727E/A6142 early return."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
DISPATCH,DISPATCH_END=0x060A6C94,0x060A6CB2
TARGET,TARGET_END=0x060A72D8,0x060A72DC
BRANCH,BRANCH_END=0x060A727E,0x060A7296
HELPER,HELPER_END=0x060A6142,0x060A6150
HELPER_LITERAL=0x060A7368
TABLE_LITERAL=0x060A6CF8; TABLE=0x060B2168; TABLE_BYTES=96; INDEX=4
ENTRY=TABLE+INDEX*16; EXPECTED=TARGET
ZERO_WORD=0xFFFFFF8C
CONTEXT=0x06004000; CONTEXT_SIZE=44; SP=0x06002000; STACK_SIZE=40; STACK_BASE=SP-STACK_SIZE
LIMIT=64; MASK=0xffffffff
VALUES=(0,1,0x7fffffff,0x80000000,0xffffffff,0x12345678,0x55555555,0xaaaaaaaa)

def sha(data): return hashlib.sha256(data).hexdigest()
def corpus(): return [(r5,seed) for r5 in VALUES for seed in (0,1)]

def execute(data,emu,r5,seed,mutation=None):
    if not 0<=r5<=MASK or seed not in (0,1): raise ValueError('index-4 input outside declared domain')
    dispatch=bytearray(data[DISPATCH-BASE:DISPATCH_END-BASE])
    target=bytearray(data[TARGET-BASE:TARGET_END-BASE])
    branch=bytearray(data[BRANCH-BASE:BRANCH_END-BASE])
    helper=bytearray(data[HELPER-BASE:HELPER_END-BASE])
    table=bytearray(data[TABLE-BASE:TABLE-BASE+TABLE_BYTES])
    if int.from_bytes(data[TABLE_LITERAL-BASE:TABLE_LITERAL-BASE+4],'big')!=TABLE:
        raise ValueError('original dispatcher table literal differs')
    if int.from_bytes(table[INDEX*16:INDEX*16+4],'big')!=EXPECTED:
        raise ValueError('original index-4 table target differs')
    if mutation:
        address,value=mutation
        if address!=ENTRY or not 0<=value<=MASK: raise ValueError('unsupported index-4 mutation')
        table[INDEX*16:INDEX*16+4]=value.to_bytes(4,'big')
    context=bytearray((0x51+seed*31+i*13)&255 for i in range(CONTEXT_SIZE))
    context[40:44]=INDEX.to_bytes(4,'big'); original_context=bytes(context)
    stack=bytearray((0x83+seed*23+i*11)&255 for i in range(STACK_SIZE)); initial_stack=bytes(stack)
    reads=[]; writes=[]
    allowed=lambda pc: DISPATCH<=pc<DISPATCH_END or TARGET<=pc<TARGET_END or BRANCH<=pc<BRANCH_END or HELPER<=pc<HELPER_END
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not allowed(address): raise ValueError(f'fetch outside index-4 early-return fence: {address:08x}/{n}')
            elif address==TABLE_LITERAL and n==4:
                reads.append(['table-literal',address,n,TABLE]); return TABLE
            elif address==CONTEXT+40 and n==4:
                v=super().read(address,n); reads.append(['context-index',address,n,v]); return v
            elif address==ENTRY and n==4:
                v=super().read(address,n); reads.append(['dispatch-target',address,n,v]); return v
            elif address==ZERO_WORD and n==4:
                v=super().read(address,n); reads.append(['early-return-word',address,n,v]); return v
            elif address==HELPER_LITERAL and n==4:
                reads.append(['helper-literal',address,n,HELPER]); return HELPER
            elif STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                v=super().read(address,n); reads.append(['stack',address-STACK_BASE,n,v]); return v
            else: raise ValueError(f'unexpected index-4 read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]); return super().write(address,n,value)
            raise ValueError(f'unexpected index-4 write {address:08x}/{n}')
    memory=Memory()
    for address,blob in ((DISPATCH,dispatch),(TARGET,target),(BRANCH,branch),(HELPER,helper)):
        memory.add(address,len(blob),blob)
    memory.add(TABLE_LITERAL,4,data[TABLE_LITERAL-BASE:TABLE_LITERAL-BASE+4])
    memory.add(HELPER_LITERAL,4,data[HELPER_LITERAL-BASE:HELPER_LITERAL-BASE+4])
    table_mem=memory.add(TABLE,TABLE_BYTES,table)
    context_mem=memory.add(CONTEXT,CONTEXT_SIZE,context)
    stack_mem=memory.add(STACK_BASE,STACK_SIZE,stack)
    memory.add(ZERO_WORD,4,(0).to_bytes(4,'big'))
    class CPU(emu.CPU):
        def __init__(self,mem): super().__init__(mem); self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try: return super().fetch(pc)
            finally: memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed(pc): raise ValueError(f'PC/budget escaped index-4 path at {pc:08x}')
            self.executed.append(pc); return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory); cpu.r=[(0xB1000000+i*0x01020305+r5+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF; cpu.r[4]=CONTEXT; cpu.r[5]=r5; cpu.r[15]=SP; cpu.sr=0x3f0
    before=cpu.r.copy(); result=cpu.call(DISPATCH,max_steps=LIMIT)
    if mutation is None:
        if result!=1 or cpu.r[0]!=1: raise ValueError(f'early handler result differs: {result}/{cpu.r[0]}')
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=0x3f1: raise ValueError(f'index-4 return state differs: sp={cpu.r[15]:08x} pr={cpu.pr:08x} sr={cpu.sr:08x} sentinel={emu.RETURN_SENTINEL:08x}')
        if bytes(table_mem)!=bytes(table) or bytes(context_mem)!=original_context: raise ValueError('table/context changed')
        expected_reads=[['table-literal',TABLE_LITERAL,4,TABLE],['context-index',CONTEXT+40,4,INDEX],
            ['dispatch-target',ENTRY,4,EXPECTED],['stack',STACK_SIZE-4,4,before[14]],
            ['helper-literal',HELPER_LITERAL,4,HELPER],['early-return-word',ZERO_WORD,4,0],
            ['stack',STACK_SIZE-4,4,emu.RETURN_SENTINEL]]
        expected_writes=[['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,INDEX],
            ['stack',STACK_SIZE-4,4,emu.RETURN_SENTINEL],['stack',STACK_SIZE-8,4,0]]
        if reads!=expected_reads: raise ValueError(f'exact index-4 reads differ: {reads!r}')
        if writes!=expected_writes: raise ValueError(f'exact index-4 writes differ: {writes!r}')
        expected_stack=bytearray(initial_stack)
        expected_stack[STACK_SIZE-8:STACK_SIZE-4]=(0).to_bytes(4,'big')
        expected_stack[STACK_SIZE-4:STACK_SIZE]=emu.RETURN_SENTINEL.to_bytes(4,'big')
        if bytes(stack_mem)!=bytes(expected_stack): raise ValueError('index-4 stack image differs')
        if cpu.steps!=36: raise ValueError(f'index-4 instruction count differs: {cpu.steps}')
        for reg in (6,7,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]: raise ValueError(f'preserved GPR r{reg} changed')
    return {'r5':r5,'seed':seed,'index':INDEX,'target':EXPECTED,'result':result,'reads':reads,'writes':writes,
        'steps':cpu.steps,'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed)),
        'table_sha256':sha(bytes(table_mem)),'context_sha256':sha(bytes(context_mem)),'stack_sha256':sha(bytes(stack_mem))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--kernel',type=Path,required=True); p.add_argument('--saturn-recomp',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-dispatch-index4-early.v1','status':'failure','kernel_sha256':KERNEL,
        'ranges':[[hex(DISPATCH),hex(DISPATCH_END)],[hex(TARGET),hex(TARGET_END)],[hex(BRANCH),hex(BRANCH_END)],[hex(HELPER),hex(HELPER_END)]],
        'limits':['Constructed index-4 context and zero word at 0xffffff8c; A727E null/early return only','No globals, callbacks, natural caller, or gameplay']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL: raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp); rows=[]
                for r5,seed in corpus():
                    x=execute(data,emu,r5,seed); y=execute(data,emu,r5,seed)
                    if x!=y: raise ValueError('repeated index-4 dispatch differs')
                    rows.append(x)
                try: execute(data,emu,0,0,(ENTRY,0x060A72DC))
                except ValueError as e:
                    if 'fetch outside index-4 early-return fence: 060a72dc/2' not in str(e).lower(): raise
                else: raise ValueError('wrong target crossed index-4 fence')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),probe_sha256=sha(Path(__file__).read_bytes()),
                    source_code_sha256=sha(b''.join(data[x-BASE:y-BASE] for x,y in ((DISPATCH,DISPATCH_END),(TARGET,TARGET_END),(BRANCH,BRANCH_END),(HELPER,HELPER_END)))),
                    table_sha256=sha(data[TABLE-BASE:TABLE-BASE+TABLE_BYTES]),mutation_control={'entry':hex(ENTRY),'replacement':'0x060A72DC','rejected':True},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
            except Exception as e: report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e: print(f'FAIL: fresh report path required: {e}'); return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
