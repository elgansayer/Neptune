#!/usr/bin/env python3
"""Execute A8154's original occupied-queue-slot return path only."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY=0x060A8154;BUSY_END=0x060A8178;CLEANUP=0x060A820C;END=0x060A8218
GLOBAL_LITERAL=0x060A8260;OFFSET_LITERAL=0x060A825C;GLOBAL=0x060FB580
TABLE_BASE=0x06006000;TABLE_SIZE=0x450;SLOT_OFFSET=0x438
SP=0x06002000;STACK_SIZE=44;STACK_BASE=SP-STACK_SIZE;LIMIT=80;MASK=0xffffffff
BUSY_VALUES=(1,0x80000000,0xffffffff)
R4_VALUES=(0x06004000,0x06004100,0x12345678,0xffffffff)
R5_VALUES=(0,1,0xABCDEF01,0xffffffff)

def sha(data):return hashlib.sha256(data).hexdigest()

def corpus():
    return [(busy,r4,r5) for busy in BUSY_VALUES for r4 in R4_VALUES for r5 in R5_VALUES]

def execute(data,emu,occupied,r4,r5,mutation=None):
    if occupied not in BUSY_VALUES or any(not 0<=v<=MASK for v in (r4,r5)):
        raise ValueError('busy-path input is outside the declared domain')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('bounded busy-path source window is incomplete')
    if mutation:
        pc,word=mutation
        if pc!=0x060A8170 or not 0<=word<=0xffff:
            raise ValueError('only the declared busy-condition mutation is supported')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    global_literal=int.from_bytes(data[GLOBAL_LITERAL-BASE:GLOBAL_LITERAL-BASE+4],'big')
    offset_literal=int.from_bytes(data[OFFSET_LITERAL-BASE:OFFSET_LITERAL-BASE+2],'big')
    if global_literal!=GLOBAL or offset_literal!=SLOT_OFFSET:
        raise ValueError('original busy-path literals differ')
    table=bytearray((0x47+i*31)&255 for i in range(TABLE_SIZE))
    slot=TABLE_BASE+SLOT_OFFSET
    table[SLOT_OFFSET+16:SLOT_OFFSET+20]=occupied.to_bytes(4,'big')
    initial_table=bytes(table)
    stack=bytearray((0x6B+i*13)&255 for i in range(STACK_SIZE));initial_stack=bytes(stack)
    reads=[];writes=[]
    allowed_pc=lambda pc: ENTRY<=pc<BUSY_END or CLEANUP<=pc<END

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not allowed_pc(address) or not allowed_pc(address+2-2):
                    raise ValueError(f'fetch outside A8154 busy path: {address:08x}/{n}')
            elif address==GLOBAL_LITERAL and n==4:
                reads.append(['literal-global',address,n,GLOBAL]);return GLOBAL
            elif address==OFFSET_LITERAL and n==2:
                reads.append(['literal-slot-offset',address,n,SLOT_OFFSET]);return SLOT_OFFSET
            elif address==GLOBAL and n==4:
                value=super().read(address,n);reads.append(['global-pointer',address,n,value]);return value
            elif address==slot+16 and n==4:
                value=super().read(address,n);reads.append(['slot-occupied',address,n,value]);return value
            elif STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                value=super().read(address,n);reads.append(['stack',address-STACK_BASE,n,value]);return value
            else:raise ValueError(f'unexpected busy-path read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected busy-path write {address:08x}/{n}')

    memory=Memory();memory.add(ENTRY,len(code),code)
    memory.add(GLOBAL_LITERAL,4,data[GLOBAL_LITERAL-BASE:GLOBAL_LITERAL-BASE+4])
    memory.add(OFFSET_LITERAL,2,data[OFFSET_LITERAL-BASE:OFFSET_LITERAL-BASE+2])
    memory.add(GLOBAL,4,TABLE_BASE.to_bytes(4,'big'));table_memory=memory.add(TABLE_BASE,TABLE_SIZE,table)
    stack_memory=memory.add(STACK_BASE,STACK_SIZE,stack)
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed_pc(pc):
                raise ValueError(f'PC/budget escaped A8154 busy path at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0xD1000000+i*0x01020305+occupied+r4+r5)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=r4;cpu.r[5]=r5;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy();result=cpu.call(ENTRY,max_steps=LIMIT)
    expected_reads=[['literal-global',GLOBAL_LITERAL,4,GLOBAL],['literal-slot-offset',OFFSET_LITERAL,2,SLOT_OFFSET],
        ['stack',STACK_SIZE-24,4,r4],['global-pointer',GLOBAL,4,TABLE_BASE],['slot-occupied',slot+16,4,occupied],
        ['stack',STACK_SIZE-16,4,emu.RETURN_SENTINEL],['stack',STACK_SIZE-12,4,before[12]],
        ['stack',STACK_SIZE-8,4,before[13]],['stack',STACK_SIZE-4,4,before[14]]]
    expected_writes=[['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,before[13]],
        ['stack',STACK_SIZE-12,4,before[12]],['stack',STACK_SIZE-16,4,emu.RETURN_SENTINEL],
        ['stack',STACK_SIZE-24,4,r4],['stack',STACK_SIZE-20,4,r5]]
    expected_stack=bytearray(initial_stack)
    expected_stack[STACK_SIZE-24:STACK_SIZE-20]=r4.to_bytes(4,'big')
    expected_stack[STACK_SIZE-20:STACK_SIZE-16]=r5.to_bytes(4,'big')
    expected_stack[STACK_SIZE-16:STACK_SIZE-12]=emu.RETURN_SENTINEL.to_bytes(4,'big')
    expected_stack[STACK_SIZE-12:STACK_SIZE-8]=before[12].to_bytes(4,'big')
    expected_stack[STACK_SIZE-8:STACK_SIZE-4]=before[13].to_bytes(4,'big')
    expected_stack[STACK_SIZE-4:STACK_SIZE]=before[14].to_bytes(4,'big')
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'busy path reads differ: {reads!r}')
        if writes!=expected_writes:raise ValueError(f'busy path stack writes differ: {writes!r}')
        if bytes(table_memory)!=initial_table:raise ValueError('busy path modified the queue table')
        if bytes(stack_memory)!=bytes(expected_stack):raise ValueError('busy path stack image differs')
        if result!=0 or cpu.r[0]!=0 or cpu.r[4]!=r4 or cpu.r[5]!=r5:
            raise ValueError('busy path return/caller arguments differ')
        if cpu.r[3]!=GLOBAL or cpu.r[2]!=SLOT_OFFSET or cpu.r[6]!=before[6]:
            raise ValueError('busy path selected table/slot registers differ')
        for reg in (1,7,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=0x3f0:
            raise ValueError('busy path SP/PR/SR differs')
    return {'occupied':occupied,'r4':r4,'r5':r5,'result':result,'reads':reads,'writes':writes,
        'table_sha256':sha(bytes(table_memory)),'stack_sha256':sha(bytes(stack_memory)),
        'steps':cpu.steps,'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-dispatch-busy-return.v1','status':'failure',
        'kernel_sha256':KERNEL,'entry':hex(ENTRY),'executed_pc_ranges':[[hex(ENTRY),hex(BUSY_END)],[hex(CLEANUP),hex(END)]],
        'static_dispatch_target':'0x060A8154','global_pointer':hex(GLOBAL),'slot_offset':hex(SLOT_OFFSET),
        'limits':['Only the occupied-slot branch and original epilogue are executable','Callback success path and allocator/service behavior are outside this probe']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for occupied,r4,r5 in corpus():
                    one=execute(data,emu,occupied,r4,r5);two=execute(data,emu,occupied,r4,r5)
                    if one!=two:raise ValueError('repeated occupied-slot return differs')
                    rows.append(one)
                try:
                    execute(data,emu,1,R4_VALUES[0],R5_VALUES[0],(0x060A8170,0x8F02))
                except ValueError as error:
                    if 'fetch outside a8154 busy path: 060a8178/2' not in str(error).lower():
                        raise ValueError(f'mutation escaped for an unexpected reason: {error}')
                    rejected=True
                else:raise ValueError('busy-branch inversion reached past the path fence')
                source= b''.join(data[a-BASE:b-BASE] for a,b in ((ENTRY,BUSY_END),(CLEANUP,END)))
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(source),probe_sha256=sha(Path(__file__).read_bytes()),
                    source_literals_sha256=sha(data[OFFSET_LITERAL-BASE:OFFSET_LITERAL-BASE+2]+data[GLOBAL_LITERAL-BASE:GLOBAL_LITERAL-BASE+4]),
                    mutation_control={'pc':'0x060A8170','replacement':'0x8F02','rejected':rejected,'reason':'busy branch inversion attempted success-path fetch at 0x060A8178 and hit the PC fence'},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='For occupied slot+16 nonzero, A8154 follows the early busy return: it returns R0=0, does not modify the table, saves/restores its declared registers and stack, and does not execute success-path callbacks. This does not establish when the global slot is occupied in natural runtime.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
