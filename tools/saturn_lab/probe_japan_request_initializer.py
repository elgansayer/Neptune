#!/usr/bin/env python3
"""Execute Japan kernel A6D04 with its original A6D46/A6D3A helpers."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A6D04,0x060A6D4A
CALLER_END=0x060A6D3A; TARGET=0x06003000; RECORD_SIZE=60
SP=0x06002000; STACK_SIZE=16; STACK_BASE=SP-STACK_SIZE
LIMIT=64; MASK=0xffffffff
OLD_VALUES=(0,1,2,3,4,0x7fffffff,0x80000000,0xffffffff)
RECORD_SEEDS=(0,1,2,3)

def sha(data): return hashlib.sha256(data).hexdigest()

def corpus(): return [(old,seed) for old in OLD_VALUES for seed in RECORD_SEEDS]

def execute(data,emu,old,seed,mutation=None):
    if not 0<=old<=MASK or seed not in RECORD_SEEDS:
        raise ValueError('old state or record seed is outside the declared corpus')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY: raise ValueError('composed original range is incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1 or not 0<=word<=0xffff:
            raise ValueError('mutation is outside the composed original range')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    request=bytearray((seed*67+i*29+0x35)&255 for i in range(RECORD_SIZE))
    request[56:60]=old.to_bytes(4,'big')
    before_request=bytes(request)
    stack_init=bytearray((seed*31+i*19+0xA7)&255 for i in range(STACK_SIZE))
    reads=[]; writes=[]

    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not ENTRY<=address or address+2>END:
                    raise ValueError(f'fetch outside composed original range: {address:08x}/{n}')
            elif address==TARGET+56 and n==4:
                value=super().read(address,n); reads.append(['request',56,n,value]); return value
            elif STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                value=super().read(address,n); reads.append(['stack',address-STACK_BASE,n,value]); return value
            else:
                raise ValueError(f'unexpected read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            if STACK_BASE<=address and address+n<=SP and n==4 and (address-STACK_BASE)%4==0:
                writes.append(['stack',address-STACK_BASE,n,value&MASK]); return super().write(address,n,value)
            if address==TARGET+44 and n==4:
                writes.append(['request',44,n,value&MASK]); return super().write(address,n,value)
            if address==TARGET+52 and n==4:
                label='mutation-only-offset-52' if mutation and (value&MASK)==3 else 'request'
                writes.append([label,52,n,value&MASK]); return super().write(address,n,value)
            if address in (TARGET,TARGET+4,TARGET+8,TARGET+12,TARGET+16,TARGET+20,TARGET+24,TARGET+28,TARGET+32,TARGET+36,TARGET+40,TARGET+56) and n==4:
                offset=address-TARGET; writes.append(['request',offset,n,value&MASK]); return super().write(address,n,value)
            raise ValueError(f'unexpected write {address:08x}/{n}')

    m=Memory(); m.add(ENTRY,len(code),code); request_mem=m.add(TARGET,RECORD_SIZE,request)
    stack=m.add(STACK_BASE,STACK_SIZE,stack_init)
    class CPU(emu.CPU):
        def __init__(self,memory): super().__init__(memory); self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try: return super().fetch(pc)
            finally: m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:
                raise ValueError(f'PC/budget escaped composed initializer at {pc:08x}')
            self.executed.append(pc); return super().exec(ins,pc,in_slot=in_slot)

    c=CPU(m); c.r=[(0x61000000+i*0x01020305+old+seed*0x10001)&MASK for i in range(16)]
    c.r[0]=0xDEADBEEF; c.r[4]=TARGET; c.r[5]=0xCAFEBABE; c.r[15]=SP; c.sr=0x3f0
    before=c.r.copy(); before_sr=c.sr
    result=c.call(ENTRY,max_steps=LIMIT)

    expected=bytearray(before_request)
    for offset,value in ((0,0),(4,0),(8,0),(12,0),(16,0),(20,1),(24,0),(28,0),(32,0),(36,0),(40,0),(44,1),(52,0),(56,3)):
        expected[offset:offset+4]=value.to_bytes(4,'big')
    expected_writes=[['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,before[13]],
        ['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL]]
    expected_writes += [['request',offset,4,value] for offset,value in
        ((0,0),(4,0),(8,0),(12,0),(16,0),(20,1),(24,0),(28,0),(32,0),(44,1),(52,0),(56,3),(36,0),(40,0))]
    expected_reads=[['request',56,4,old],['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL],
        ['stack',STACK_SIZE-8,4,before[13]],['stack',STACK_SIZE-4,4,before[14]]]
    if mutation is None:
        if reads!=expected_reads: raise ValueError(f'exact read trace differs: {reads!r}')
        if writes!=expected_writes: raise ValueError(f'exact write trace differs: {writes!r}')
        if bytes(request_mem)!=bytes(expected): raise ValueError('request record image differs')
        stack_expected=bytearray(stack_init)
        stack_expected[STACK_SIZE-4:STACK_SIZE]=before[14].to_bytes(4,'big')
        stack_expected[STACK_SIZE-8:STACK_SIZE-4]=before[13].to_bytes(4,'big')
        stack_expected[STACK_SIZE-12:STACK_SIZE-8]=emu.RETURN_SENTINEL.to_bytes(4,'big')
        if bytes(stack)!=bytes(stack_expected): raise ValueError('caller stack image differs')
        if result!=TARGET or c.r[0]!=TARGET or c.r[4]!=TARGET or c.r[5]!=0:
            raise ValueError('initializer return/request pointer/R5 differs')
        if c.r[3]!=1: raise ValueError('caller-created request flag in R3 differs')
        for reg in (1,2,6,7,8,9,10,11,12):
            if c.r[reg]!=before[reg]: raise ValueError(f'preserved GPR r{reg} changed')
        if c.r[13]!=before[13] or c.r[14]!=before[14] or c.r[15]!=SP:
            raise ValueError('callee-saved GPR or stack pointer differs')
        if c.pr!=emu.RETURN_SENTINEL or c.sr!=before_sr: raise ValueError('PR/SR differs')
    return {'old_request_state':old,'record_seed':seed,'result_r0':result,'steps':c.steps,
        'reads':reads,'writes':writes,'request_sha256':sha(bytes(request_mem)),
        'stack_sha256':sha(bytes(stack)),
        'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in c.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-request-initializer.v1','status':'failure',
        'kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],
        'caller_range':[hex(ENTRY,),'0x060A6D3A'],'record':[hex(TARGET),hex(TARGET+RECORD_SIZE)],
        'limits':['Original A6D04 caller and A6D46/A6D3A helpers only','One constructed 60-byte request; no natural service, BIOS, device, timing or gameplay validation']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL: raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp); rows=[]
                for old,seed in corpus():
                    first=execute(data,emu,old,seed); second=execute(data,emu,old,seed)
                    if first!=second: raise ValueError('repeated original initializer differs')
                    rows.append(first)
                reference=execute(data,emu,0x11223344,0)
                mutation=execute(data,emu,0x11223344,0,(0x060A6D3C,0x145D))
                if reference['request_sha256']==mutation['request_sha256'] or not any(w[0]=='mutation-only-offset-52' for w in mutation['writes']):
                    raise ValueError('request-state store mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    mutation_control={'pc':'0x060A6D3C','replacement':'0x145D','rejected':True},
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='A6D04 initializes request offsets 0..32, writes 1 at +20 and +44, clears +52, calls A6D3A with state 3 which returns prior +56 in R0, stores 3 at +56 and clears +36/+40, then returns request pointer. One constructed record; request service behavior remains outside this composed call.')
            except Exception as error: report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}'); return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
