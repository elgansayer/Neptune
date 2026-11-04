#!/usr/bin/env python3
"""Execute original A6C94 indirect dispatch through static table index 5."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
DISPATCH,DISPATCH_END=0x060A6C94,0x060A6CB2
TARGET,TARGET_END=0x060A730A,0x060A730E
TABLE_LITERAL=0x060A6CF8;TABLE=0x060B2168;TABLE_BYTES=96;INDEX=5
TABLE_ENTRY=TABLE+INDEX*16;EXPECTED_TARGET=TARGET
CONTEXT=0x06004000;CONTEXT_SIZE=44;SP=0x06002000;STACK_SIZE=8;STACK_BASE=SP-STACK_SIZE;LIMIT=20;MASK=0xffffffff
VALUES=(0,1,2,3,0x7fffffff,0x80000000,0xffffffff,0x12345678)

def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return [(r5,seed) for r5 in VALUES for seed in (0,1)]

def execute(data,emu,r5,seed,mutation=None):
    if not 0<=r5<=MASK or seed not in (0,1):raise ValueError('dispatch arguments outside declared domain')
    dispatcher=bytearray(data[DISPATCH-BASE:DISPATCH_END-BASE])
    target=bytearray(data[TARGET-BASE:TARGET_END-BASE])
    table=bytearray(data[TABLE-BASE:TABLE-BASE+TABLE_BYTES])
    if len(dispatcher)!=DISPATCH_END-DISPATCH or len(target)!=TARGET_END-TARGET:
        raise ValueError('original dispatcher or target bytes are incomplete')
    literal=int.from_bytes(data[TABLE_LITERAL-BASE:TABLE_LITERAL-BASE+4],'big')
    if literal!=TABLE:raise ValueError('dispatcher table literal identity differs')
    entry_value=int.from_bytes(table[INDEX*16:INDEX*16+4],'big')
    if entry_value!=EXPECTED_TARGET:raise ValueError(f'original index-5 target differs: {entry_value:08x}')
    if mutation:
        address,value=mutation
        if address!=TABLE_ENTRY or not 0<=value<=MASK:
            raise ValueError('only the declared index-5 table-target mutation is supported')
        table[INDEX*16:INDEX*16+4]=value.to_bytes(4,'big')
    context=bytearray((seed*43+i*17+0xD1)&255 for i in range(CONTEXT_SIZE))
    context[40:44]=INDEX.to_bytes(4,'big')
    original_context=bytes(context)
    reads=[];writes=[]
    allowed=lambda pc: DISPATCH<=pc<DISPATCH_END or TARGET<=pc<TARGET_END

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not allowed(address):raise ValueError(f'fetch outside A6C94/index-5 composition: {address:08x}/{n}')
            elif address==TABLE_LITERAL and n==4:
                reads.append(['table-literal',address,n,TABLE]);return TABLE
            elif address==CONTEXT+40 and n==4:
                value=super().read(address,n);reads.append(['context-index',40,n,value]);return value
            elif address==TABLE_ENTRY and n==4:
                value=super().read(address,n);reads.append(['dispatch-target',address,n,value]);return value
            elif address==SP-4 and n==4:
                value=super().read(address,n);reads.append(['stack',4,n,value]);return value
            else:raise ValueError(f'unexpected dispatch read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if address in (SP-4,SP-8) and n==4:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected dispatch write {address:08x}/{n}')

    memory=Memory();memory.add(DISPATCH,len(dispatcher),dispatcher);memory.add(TARGET,len(target),target)
    memory.add(TABLE_LITERAL,4,data[TABLE_LITERAL-BASE:TABLE_LITERAL-BASE+4])
    table_memory=memory.add(TABLE,TABLE_BYTES,table);context_memory=memory.add(CONTEXT,CONTEXT_SIZE,context)
    stack_memory=memory.add(STACK_BASE,STACK_SIZE,bytearray((0x79+i*31+seed*13)&255 for i in range(STACK_SIZE)))
    initial_stack=bytes(stack_memory)
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed(pc):raise ValueError(f'PC/budget escaped A6C94/index-5 path at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0xC7000000+i*0x01020305+r5+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=CONTEXT;cpu.r[5]=r5;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy();result=cpu.call(DISPATCH,max_steps=LIMIT)
    expected_reads=[['table-literal',TABLE_LITERAL,4,TABLE],['context-index',40,4,INDEX],
        ['dispatch-target',TABLE_ENTRY,4,EXPECTED_TARGET],['stack',4,4,before[14]]]
    expected_writes=[['stack',4,4,before[14]],['stack',0,4,INDEX]]
    expected_stack=bytearray(initial_stack)
    expected_stack[0:4]=INDEX.to_bytes(4,'big')
    expected_stack[4:8]=before[14].to_bytes(4,'big')
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'exact dispatcher reads differ: {reads!r}')
        if writes!=expected_writes:raise ValueError(f'exact dispatcher stack writes differ: {writes!r}')
        if bytes(table_memory)!=bytes(table):raise ValueError('dispatch table was modified')
        if bytes(context_memory)!=original_context:raise ValueError('context was modified')
        if bytes(stack_memory)!=bytes(expected_stack):raise ValueError('dispatch stack image differs')
        if result!=1 or cpu.r[0]!=1:raise ValueError('index-5 handler must return 1 in R0')
        if cpu.r[1]!=TABLE or cpu.r[3]!=INDEX:raise ValueError('dispatcher base/index registers differ')
        if cpu.r[4]!=CONTEXT+12 or cpu.r[5]!=r5:raise ValueError('dispatcher input registers differ')
        for reg in (2,6,7,8,9,10,11,12,13):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if cpu.r[14]!=before[14] or cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=0x3f0:
            raise ValueError('dispatch SP/PR/SR/callee-save differs')
    return {'r5':r5,'seed':seed,'context_index':INDEX,'target':entry_value,'result':result,
        'reads':reads,'writes':writes,'table_sha256':sha(bytes(table_memory)),
        'context_sha256':sha(bytes(context_memory)),'stack_sha256':sha(bytes(stack_memory)),
        'steps':cpu.steps,'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-dispatch-index5.v1','status':'failure',
        'kernel_sha256':KERNEL,'dispatcher_range':[hex(DISPATCH),hex(DISPATCH_END)],
        'target_range':[hex(TARGET),hex(TARGET_END)],'table_range':[hex(TABLE),hex(TABLE+TABLE_BYTES)],
        'table_entry':hex(TABLE_ENTRY),'context':[hex(CONTEXT),hex(CONTEXT+CONTEXT_SIZE)],
        'limits':['Original A6C94 dispatcher, static index-5 word, and A730A RTS leaf only','Constructed context/table mapping; no natural dispatch caller or gameplay proof']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for r5,seed in corpus():
                    one=execute(data,emu,r5,seed);two=execute(data,emu,r5,seed)
                    if one!=two:raise ValueError('repeated index-5 dispatch differs')
                    rows.append(one)
                try:execute(data,emu,0,0,(TABLE_ENTRY,TARGET+2))
                except ValueError as error:
                    if 'fetch outside a6c94/index-5 composition: 060a730e/2' not in str(error).lower():
                        raise ValueError(f'target mutation escaped for unexpected reason: {error}')
                    rejected=True
                else:raise ValueError('wrong target mutation crossed function fence')
                source=data[DISPATCH-BASE:DISPATCH_END-BASE]+data[TARGET-BASE:TARGET_END-BASE]
                table=data[TABLE-BASE:TABLE-BASE+TABLE_BYTES]
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(source),source_table_sha256=sha(table),
                    probe_sha256=sha(Path(__file__).read_bytes()),
                    source_literal_sha256=sha(data[TABLE_LITERAL-BASE:TABLE_LITERAL-BASE+4]),
                    mutation_control={'table_entry':'0x060B21B8','replacement':'0x060A730C','rejected':rejected,'reason':'wrong target fell through helper delay instruction and attempted fetch at 0x060A730E'},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Original A6C94 computes index*16 from context+40, loads the original index-5 target from 060B21B8, tail-dispatches through its jmp delay slot, and executes A730A RTS with its delay instruction; the handler returns 1 in R0. Direct constructed index-5 context and static original table bytes only.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
