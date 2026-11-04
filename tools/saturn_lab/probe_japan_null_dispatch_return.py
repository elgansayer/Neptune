#!/usr/bin/env python3
"""Execute A70B8's original null-context return path only."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY=0x060A70B8;NULL_END=0x060A70C6;EPILOGUE=0x060A7144;END=0x060A714E
SP=0x06002000;STACK_SIZE=52;STACK_BASE=SP-STACK_SIZE;LIMIT=24;MASK=0xffffffff
VALUES=(0,1,2,3,0x7fffffff,0x80000000,0xffffffff,0x12345678)

def sha(data):return hashlib.sha256(data).hexdigest()
def corpus():return [(r0,seed) for r0 in VALUES for seed in (0,1)]

def execute(data,emu,r0,seed,mutation=None):
    if not 0<=r0<=MASK or seed not in (0,1):raise ValueError('null-path inputs outside declared domain')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('original candidate window is incomplete')
    if mutation:
        pc,word=mutation
        if pc!=0x060A70C4 or not 0<=word<=0xffff:raise ValueError('only the declared null-branch mutation is supported')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    stack=bytearray((0xB7+seed*47+i*23)&255 for i in range(STACK_SIZE));initial_stack=bytes(stack)
    reads=[];writes=[]
    allowed=lambda pc: ENTRY<=pc<NULL_END or EPILOGUE<=pc<END

    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not allowed(address):raise ValueError(f'fetch outside A70B8 null path: {address:08x}/{n}')
            elif STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                value=super().read(address,n);reads.append(['stack',address-STACK_BASE,n,value]);return value
            else:raise ValueError(f'unexpected null-path read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]);return super().write(address,n,value)
            raise ValueError(f'unexpected null-path write {address:08x}/{n}')

    memory=Memory();memory.add(ENTRY,len(code),code);stack_mem=memory.add(STACK_BASE,STACK_SIZE,stack)
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not allowed(pc):raise ValueError(f'PC/budget escaped A70B8 null path at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory);cpu.r=[(0x51000000+i*0x01020305+r0+seed*0x10001)&MASK for i in range(16)]
    cpu.r[0]=r0;cpu.r[4]=0;cpu.r[15]=SP;cpu.sr=0x3f0
    before=cpu.r.copy();result=cpu.call(ENTRY,max_steps=LIMIT)
    expected_reads=[['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL],
        ['stack',STACK_SIZE-8,4,before[13]],['stack',STACK_SIZE-4,4,before[14]]]
    expected_writes=[['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,before[13]],
        ['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL]]
    expected_stack=bytearray(initial_stack)
    expected_stack[STACK_SIZE-4:STACK_SIZE]=before[14].to_bytes(4,'big')
    expected_stack[STACK_SIZE-8:STACK_SIZE-4]=before[13].to_bytes(4,'big')
    expected_stack[STACK_SIZE-12:STACK_SIZE-8]=emu.RETURN_SENTINEL.to_bytes(4,'big')
    if mutation is None:
        if reads!=expected_reads or writes!=expected_writes:raise ValueError('null-path stack transactions differ')
        if bytes(stack_mem)!=bytes(expected_stack):raise ValueError('null-path stack image differs')
        if result!=r0 or cpu.r[0]!=r0:raise ValueError('null-path return must preserve R0')
        if cpu.r[4]!=0:raise ValueError('null context argument changed')
        for reg in (1,2,3,5,6,7,8,9,10,11,12,13,14):
            if cpu.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=0x3f1:
            raise ValueError('null-path SP/PR/SR differs')
    return {'incoming_r0':r0,'seed':seed,'result':result,'reads':reads,'writes':writes,
        'stack_sha256':sha(bytes(stack_mem)),'steps':cpu.steps,
        'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-null-dispatch-return.v1','status':'failure',
        'kernel_sha256':KERNEL,'entry':hex(ENTRY),'executed_pc_ranges':[[hex(ENTRY),hex(NULL_END)],[hex(EPILOGUE),hex(END)]],
        'static_dispatch_target':'0x060A70B8','limits':['Only original R4=0 early return and epilogue execute','Non-null context path, callbacks, SCSP/SCU and service behavior are fenced']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for r0,seed in corpus():
                    one=execute(data,emu,r0,seed);two=execute(data,emu,r0,seed)
                    if one!=two:raise ValueError('repeated null-path execution differs')
                    rows.append(one)
                try:execute(data,emu,0,0,(0x060A70C4,0x8B3E))
                except ValueError as error:
                    if 'fetch outside a70b8 null path: 060a70c6/2' not in str(error).lower():
                        raise ValueError(f'null-condition mutation escaped for an unexpected reason: {error}')
                    rejected=True
                else:raise ValueError('null-condition mutation crossed the path fence')
                source=b''.join(data[a-BASE:b-BASE] for a,b in ((ENTRY,NULL_END),(EPILOGUE,END)))
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    source_code_sha256=sha(source),probe_sha256=sha(Path(__file__).read_bytes()),
                    mutation_control={'pc':'0x060A70C4','replacement':'0x8B3E','rejected':rejected,'reason':'inverted branch attempted non-null path fetch at 0x060A70C6 and hit PC fence'},
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='For R4=0, returns incoming R0 unchanged, restores saved R13/R14/PR and SP, makes no non-stack memory transactions, and exits with T=1 from tst. This bounded null-input path does not establish valid callback/service behavior.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
