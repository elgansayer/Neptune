#!/usr/bin/env python3
"""Compose A6C94 index 0 with A8154's original occupied-slot return."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
DISPATCH,DISPATCH_END=0x060A6C94,0x060A6CB2
TARGET=0x060A8154;BUSY_END=0x060A8178;CLEANUP=0x060A820C;TARGET_END=0x060A8218
DISPATCH_LITERAL=0x060A6CF8;GLOBAL_LITERAL=0x060A8260;SLOT_LITERAL=0x060A825C
DISPATCH_TABLE=0x060B2168;DISPATCH_TABLE_SIZE=96;DISPATCH_ENTRY=DISPATCH_TABLE
EXPECTED_TARGET=TARGET;GLOBAL=0x060FB580;QUEUE_BASE=0x06006000;QUEUE_SIZE=0x450;QUEUE_SLOT=0x438
CONTEXT=0x06004000;CONTEXT_SIZE=44;SP=0x06002000;STACK_SIZE=44;STACK_BASE=SP-STACK_SIZE
LIMIT=96;MASK=0xffffffff
BUSY_VALUES=(1,0x80000000,0xffffffff)
R5_VALUES=(0,1,0xABCDEF01,0xffffffff)
SEEDS=(0,1,2,3)

def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return [(busy,r5,seed) for busy in BUSY_VALUES for r5 in R5_VALUES for seed in SEEDS]

def execute(data,emu,occupied,r5,seed,mutation=None):
    if occupied not in BUSY_VALUES or not 0<=r5<=MASK or seed not in SEEDS:
        raise ValueError('index-0 dispatch inputs outside declared domain')
    dispatcher=bytearray(data[DISPATCH-BASE:DISPATCH_END-BASE])
    target=bytearray(data[TARGET-BASE:TARGET_END-BASE])
    dispatch_table=bytearray(data[DISPATCH_TABLE-BASE:DISPATCH_TABLE-BASE+DISPATCH_TABLE_SIZE])
    if int.from_bytes(dispatch_table[:4],'big')!=EXPECTED_TARGET:
        raise ValueError('original index-0 target differs')
    if mutation:
        address,value=mutation
        if address!=DISPATCH_ENTRY or not 0<=value<=MASK:
            raise ValueError('only the declared index-0 target mutation is supported')
        dispatch_table[:4]=value.to_bytes(4,'big')
    literals={DISPATCH_LITERAL:int.from_bytes(data[DISPATCH_LITERAL-BASE:DISPATCH_LITERAL-BASE+4],'big'),
        GLOBAL_LITERAL:int.from_bytes(data[GLOBAL_LITERAL-BASE:GLOBAL_LITERAL-BASE+4],'big'),
        SLOT_LITERAL:int.from_bytes(data[SLOT_LITERAL-BASE:SLOT_LITERAL-BASE+2],'big')}
    if literals!={DISPATCH_LITERAL:DISPATCH_TABLE,GLOBAL_LITERAL:GLOBAL,SLOT_LITERAL:QUEUE_SLOT}:
        raise ValueError('original dispatcher/queue literal identity differs')
    context=bytearray((0x45+seed*37+i*19)&255 for i in range(CONTEXT_SIZE))
    context[40:44]=(0).to_bytes(4,'big')
    original_context=bytes(context)
    queue=bytearray((0x89+i*23+seed*7)&255 for i in range(QUEUE_SIZE))
    queue[QUEUE_SLOT+16:QUEUE_SLOT+20]=occupied.to_bytes(4,'big')
    original_queue=bytes(queue)
    stack=bytearray((0xA3+seed*29+i*17)&255 for i in range(STACK_SIZE));initial_stack=bytes(stack)
    reads=[];writes=[]
    allowed=lambda pc: (DISPATCH<=pc<DISPATCH_END or TARGET<=pc<BUSY_END or CLEANUP<=pc<TARGET_END)

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not allowed(address):raise ValueError(f'fetch outside A6C94/index-0 busy composition: {address:08x}/{n}')
            elif address==DISPATCH_LITERAL and n==4:
                reads.append(['dispatch-literal',address,n,DISPATCH_TABLE]);return DISPATCH_TABLE
            elif address==GLOBAL_LITERAL and n==4:
                reads.append(['queue-global-literal',address,n,GLOBAL]);return GLOBAL
            elif address==SLOT_LITERAL and n==2:
                reads.append(['queue-slot-literal',address,n,QUEUE_SLOT]);return QUEUE_SLOT
            elif address==CONTEXT+40 and n==4:
                value=super().read(address,n);reads.append(['context-index',40,n,value]);return value
            elif address==DISPATCH_ENTRY and n==4:
                value=super().read(address,n);reads.append(['dispatch-target',address,n,value]);return value
            elif address==GLOBAL and n==4:
                value=super().read(address,n);reads.append(['queue-global-pointer',address,n,value]);return value
            elif address==QUEUE_BASE+QUEUE_SLOT+16 and n==4:
                value=super().read(address,n);reads.append(['queue-occupied',address,n,value]);return value
            elif STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                value=super().read(address,n);reads.append(['stack',address-STACK_BASE,n,value]);return value
            else:raise ValueError(f'unexpected composed-dispatch read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected composed-dispatch write {address:08x}/{n}')

    memory=Memory();memory.add(DISPATCH,len(dispatcher),dispatcher);memory.add(TARGET,len(target),target)
    for address,size in ((DISPATCH_LITERAL,4),(GLOBAL_LITERAL,4),(SLOT_LITERAL,2)):
        memory.add(address,size,data[address-BASE:address-BASE+size])
    dispatch_table_mem=memory.add(DISPATCH_TABLE,DISPATCH_TABLE_SIZE,dispatch_table)
    queue_mem=memory.add(QUEUE_BASE,QUEUE_SIZE,queue);context_mem=memory.add(CONTEXT,CONTEXT_SIZE,context)
    stack_mem=memory.add(STACK_BASE,STACK_SIZE,stack)
    memory.add(GLOBAL,4,QUEUE_BASE.to_bytes(4,'big'))
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed(pc):raise ValueError(f'PC/budget escaped A6C94/index-0 busy path at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0x3D000000+i*0x01020305+occupied+r5+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=CONTEXT;cpu.r[5]=r5;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy();result=cpu.call(DISPATCH,max_steps=LIMIT)

    expected_reads=[['dispatch-literal',DISPATCH_LITERAL,4,DISPATCH_TABLE],['context-index',40,4,0],
        ['dispatch-target',DISPATCH_ENTRY,4,EXPECTED_TARGET],['stack',STACK_SIZE-4,4,before[14]],
        ['queue-global-literal',GLOBAL_LITERAL,4,GLOBAL],['queue-slot-literal',SLOT_LITERAL,2,QUEUE_SLOT],
        ['stack',STACK_SIZE-24,4,CONTEXT+12],['queue-global-pointer',GLOBAL,4,QUEUE_BASE],
        ['queue-occupied',QUEUE_BASE+QUEUE_SLOT+16,4,occupied],
        ['stack',STACK_SIZE-16,4,emu.RETURN_SENTINEL],['stack',STACK_SIZE-12,4,before[12]],
        ['stack',STACK_SIZE-8,4,before[13]],['stack',STACK_SIZE-4,4,before[14]]]
    expected_writes=[['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,0],
        ['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,before[13]],
        ['stack',STACK_SIZE-12,4,before[12]],['stack',STACK_SIZE-16,4,emu.RETURN_SENTINEL],
        ['stack',STACK_SIZE-24,4,CONTEXT+12],['stack',STACK_SIZE-20,4,r5]]
    expected_stack=bytearray(initial_stack)
    for offset,value in ((STACK_SIZE-4,before[14]),(STACK_SIZE-8,before[13]),
        (STACK_SIZE-12,before[12]),(STACK_SIZE-16,emu.RETURN_SENTINEL),
        (STACK_SIZE-24,CONTEXT+12),(STACK_SIZE-20,r5)):
        expected_stack[offset:offset+4]=value.to_bytes(4,'big')
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'exact dispatch/target reads differ: {reads!r}')
        if writes!=expected_writes:raise ValueError(f'exact dispatch/target stack writes differ: {writes!r}')
        if bytes(dispatch_table_mem)!=bytes(dispatch_table):raise ValueError('dispatch table changed')
        if bytes(queue_mem)!=original_queue:raise ValueError('busy target modified queue table')
        if bytes(context_mem)!=original_context:raise ValueError('context was modified')
        if bytes(stack_mem)!=bytes(expected_stack):raise ValueError('composed stack image differs')
        if result!=0 or cpu.r[0]!=0 or cpu.r[4]!=CONTEXT+12 or cpu.r[5]!=r5:
            raise ValueError('composed dispatcher/target return differs')
        if cpu.r[1]!=DISPATCH_TABLE or cpu.r[2]!=QUEUE_SLOT or cpu.r[3]!=GLOBAL:
            raise ValueError('composed table/index registers differ')
        for reg in (6,7,8,9,10,11):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if cpu.r[12]!=before[12] or cpu.r[13]!=before[13] or cpu.r[14]!=before[14]:
            raise ValueError('composed callee-saved registers differ')
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=0x3f0:
            raise ValueError('composed SP/PR/SR differs')
    return {'occupied':occupied,'r5':r5,'seed':seed,'index':0,'target':EXPECTED_TARGET,
        'result':result,'reads':reads,'writes':writes,
        'dispatch_table_sha256':sha(bytes(dispatch_table_mem)),'queue_sha256':sha(bytes(queue_mem)),
        'context_sha256':sha(bytes(context_mem)),'stack_sha256':sha(bytes(stack_mem)),
        'steps':cpu.steps,'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-dispatch-index0-busy.v1','status':'failure',
        'kernel_sha256':KERNEL,'dispatcher_range':[hex(DISPATCH),hex(DISPATCH_END)],
        'target_busy_ranges':[[hex(TARGET),hex(BUSY_END)],[hex(CLEANUP),hex(TARGET_END)]],
        'dispatch_table':hex(DISPATCH_TABLE),'queue_global':hex(GLOBAL),'queue_slot_offset':hex(QUEUE_SLOT),
        'limits':['Original A6C94 dispatcher and A8154 occupied-slot return path only','Constructed context/table/global mapping; success callbacks and natural queue lifecycle are fenced']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for occupied,r5,seed in corpus():
                    one=execute(data,emu,occupied,r5,seed);two=execute(data,emu,occupied,r5,seed)
                    if one!=two:raise ValueError('repeated index-0 busy dispatch differs')
                    rows.append(one)
                try:execute(data,emu,1,0,0,(DISPATCH_ENTRY,0x060A8178))
                except ValueError as error:
                    if 'fetch outside a6c94/index-0 busy composition: 060a8178/2' not in str(error).lower():
                        raise ValueError(f'wrong-target mutation escaped unexpectedly: {error}')
                    rejected=True
                else:raise ValueError('index-0 wrong-target mutation crossed PC fence')
                source=b''.join(data[a-BASE:b-BASE] for a,b in
                    ((DISPATCH,DISPATCH_END),(TARGET,BUSY_END),(CLEANUP,TARGET_END)))
                literals=b''.join(data[a-BASE:a-BASE+n] for a,n in
                    ((DISPATCH_LITERAL,4),(SLOT_LITERAL,2),(GLOBAL_LITERAL,4)))
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(source),source_table_sha256=sha(data[DISPATCH_TABLE-BASE:DISPATCH_TABLE-BASE+DISPATCH_TABLE_SIZE]),
                    source_literals_sha256=sha(literals),probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={'table_entry':'0x060B2168','replacement':'0x060A8178','rejected':rejected,'reason':'wrong target attempted fenced success-path fetch at 0x060A8178'},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='A6C94 loads static table index 0 from context+40 and jumps to original A8154. The target observes a constructed occupied queue slot and returns zero without queue writes. Dispatcher and target stack frames restore; no success callback executes.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
