#!/usr/bin/env python3
"""Execute the original Japan kernel A753C queue-record slot allocator."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A753C,0x060A7564
TABLE_PTR_LITERAL=0x060A75A4;SLOT_SIZE_LITERAL=0x060A75A0
GLOBAL=0x060FB580;TABLE_BASE=0x06006000;TABLE_SIZE=0x460;SLOT_OFFSET=0x44C
TARGET=0x06004000;CONTEXT_SIZE=12;SP=0x06002000;LIMIT=20;MASK=0xffffffff
VALUES=(0,1,2,3,0x7fffffff,0x80000000,0xffffffff,0x12345678)

def sha(data):return hashlib.sha256(data).hexdigest()

def corpus():
    return [(left,right,VALUES[(i*3+j*5)%len(VALUES)],busy)
        for i,left in enumerate(VALUES) for j,right in enumerate(VALUES) for busy in (False,True)]

def execute(data,emu,left,right,message,busy,mutation=None):
    if any(not 0<=v<=MASK for v in (left,right,message)) or type(busy) is not bool:
        raise ValueError('allocator inputs are outside the declared unsigned/bool domain')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('original allocator range is incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1 or not 0<=word<=0xffff:
            raise ValueError('mutation outside original allocator')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    context=bytearray((0xB3+i*23)&255 for i in range(CONTEXT_SIZE))
    context[0:4]=left.to_bytes(4,'big');context[8:12]=right.to_bytes(4,'big')
    original_context=bytes(context)
    initial_table=bytearray((0x6D+i*17)&255 for i in range(TABLE_SIZE))
    slot=TABLE_BASE+SLOT_OFFSET
    initial_slot=bytearray((0x91+i*29)&255 for i in range(20))
    initial_slot[16:20]=(0xABCDEF01 if busy else 0).to_bytes(4,'big')
    initial_table[SLOT_OFFSET:SLOT_OFFSET+20]=initial_slot
    original_table=bytes(initial_table)
    reads=[];writes=[]
    table_pointer=TABLE_BASE.to_bytes(4,'big')
    offset_word=SLOT_OFFSET.to_bytes(2,'big')

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not ENTRY<=address or address+2>END:
                    raise ValueError(f'fetch outside A753C: {address:08x}/{n}')
            elif address==TABLE_PTR_LITERAL and n==4:
                value=int.from_bytes(data[address-BASE:address-BASE+4],'big')
                if value!=GLOBAL:raise ValueError('global-pointer literal identity differs')
                reads.append(['literal-global',address,n,value]);return value
            elif address==SLOT_SIZE_LITERAL and n==2:
                value=int.from_bytes(data[address-BASE:address-BASE+2],'big')
                if value!=SLOT_OFFSET:raise ValueError('slot-offset literal identity differs')
                reads.append(['literal-slot-offset',address,n,value]);return value
            elif address==GLOBAL and n==4:
                value=super().read(address,n);reads.append(['global-pointer',address,n,value]);return value
            elif address==slot+16 and n==4:
                value=super().read(address,n);reads.append(['slot-occupied',address,n,value]);return value
            elif not busy and address==TARGET+8 and n==4:
                value=super().read(address,n);reads.append(['context',8,n,value]);return value
            elif not busy and address==TARGET and n==4:
                value=super().read(address,n);reads.append(['context',0,n,value]);return value
            else:raise ValueError(f'unexpected read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if slot<=address and address+n<=slot+20 and n==4 and (address-slot)%4==0:
                writes.append(['slot',address-slot,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected write {address:08x}/{n}')

    memory=Memory();memory.add(ENTRY,len(code),code)
    memory.add(TABLE_PTR_LITERAL,4,data[TABLE_PTR_LITERAL-BASE:TABLE_PTR_LITERAL-BASE+4])
    memory.add(SLOT_SIZE_LITERAL,2,data[SLOT_SIZE_LITERAL-BASE:SLOT_SIZE_LITERAL-BASE+2])
    memory.add(GLOBAL,4,table_pointer);table_memory=memory.add(TABLE_BASE,TABLE_SIZE,initial_table)
    context_memory=memory.add(TARGET,CONTEXT_SIZE,context)
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:
                raise ValueError(f'PC/budget escaped A753C at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0x9A000000+i*0x01020305+left+right+message)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=TARGET;cpu.r[5]=message;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy();result=cpu.call(ENTRY,max_steps=LIMIT)
    expected_table=bytearray(original_table)
    expected_reads=[['literal-global',TABLE_PTR_LITERAL,4,GLOBAL],['global-pointer',GLOBAL,4,TABLE_BASE],
        ['literal-slot-offset',SLOT_SIZE_LITERAL,2,SLOT_OFFSET],['slot-occupied',slot+16,4,0xABCDEF01 if busy else 0]]
    expected_writes=[]
    expected_result=0
    if not busy:
        value=(left+right)&MASK
        expected_reads.extend([['context',8,4,right],['context',0,4,left]])
        expected_writes=[['slot',0,4,value],['slot',4,4,1],['slot',8,4,message],['slot',16,4,1]]
        for offset,word in ((0,value),(4,1),(8,message),(16,1)):
            expected_table[SLOT_OFFSET+offset:SLOT_OFFSET+offset+4]=word.to_bytes(4,'big')
        expected_result=slot
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'exact allocator reads differ: {reads!r}')
        if writes!=expected_writes:raise ValueError(f'exact allocator writes differ: {writes!r}')
        if bytes(table_memory)!=bytes(expected_table):raise ValueError('slot table image differs')
        if bytes(context_memory)!=original_context:raise ValueError('context was modified')
        if result!=expected_result or cpu.r[0]!=expected_result:raise ValueError('allocator R0 result differs')
        if cpu.r[4]!=(TARGET if busy else 1) or cpu.r[5]!=message:
            raise ValueError('allocator R4/R5 results differ')
        expected_r2,expected_r3=(SLOT_OFFSET,GLOBAL) if busy else ((left+right)&MASK,right)
        if cpu.r[2]!=expected_r2 or cpu.r[3]!=expected_r3 or cpu.r[6]!=slot:
            raise ValueError('allocator loaded global/context/slot registers differ')
        for reg in (1,7,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        expected_sr=0x3f0 | (0 if busy else 1)
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=expected_sr:
            raise ValueError('SP/PR/SR differs')
    return {'left':left,'right':right,'message':message,'busy':busy,'result':result,
        'reads':reads,'writes':writes,'slot_sha256':sha(bytes(table_memory[SLOT_OFFSET:SLOT_OFFSET+20])),
        'table_sha256':sha(bytes(table_memory)),'context_sha256':sha(bytes(context_memory)),
        'steps':cpu.steps,'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-queue-record-allocator.v1','status':'failure',
        'kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],
        'global_pointer':hex(GLOBAL),'table_base':hex(TABLE_BASE),'slot_offset':hex(SLOT_OFFSET),
        'limits':['One constructed shared table slot and context record; exact original literal words checked','CPU-only allocator; natural queue provenance, callers, timing and device behavior not claimed']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                if int.from_bytes(data[TABLE_PTR_LITERAL-BASE:TABLE_PTR_LITERAL-BASE+4],'big')!=GLOBAL:
                    raise ValueError('original global pointer literal changed')
                if int.from_bytes(data[SLOT_SIZE_LITERAL-BASE:SLOT_SIZE_LITERAL-BASE+2],'big')!=SLOT_OFFSET:
                    raise ValueError('original slot offset literal changed')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for left,right,message,busy in corpus():
                    one=execute(data,emu,left,right,message,busy);two=execute(data,emu,left,right,message,busy)
                    if one!=two:raise ValueError('repeated allocator execution differs')
                    rows.append(one)
                ref=execute(data,emu,2,3,4,False)
                mut=execute(data,emu,2,3,4,False,(0x060A755E,0x0009))
                if ref['slot_sha256']==mut['slot_sha256'] or ref['writes']==mut['writes']:
                    raise ValueError('occupied-marker mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),
                    source_literals_sha256=sha(data[SLOT_SIZE_LITERAL-BASE:SLOT_SIZE_LITERAL-BASE+2]+data[TABLE_PTR_LITERAL-BASE:TABLE_PTR_LITERAL-BASE+4]),
                    probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={'pc':'0x060A755E','replacement':'0x0009','rejected':True},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Reads the shared-table base through original literal 060A75A4 and slot offset 0x44C through 060A75A0, then checks slot+16. Busy returns 0 without context reads/writes. Free reads context+8 and +0, stores their wrapping sum at slot+0, 1 at +4, incoming R5 at +8, and 1 at +16, then returns slot pointer. Constructed global/table/context only.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
