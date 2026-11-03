#!/usr/bin/env python3
"""Execute original Japan kernel A750A scaled-difference arithmetic leaf."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A750A,0x060A7518
TARGET=0x06004000; RECORD_SIZE=48; SP=0x06002000; LIMIT=8; MASK=0xffffffff
VALUES=(0,1,2,3,0x7fffffff,0x80000000,0xffffffff,0x12345678)

def sha(data): return hashlib.sha256(data).hexdigest()

def corpus(): return [(scale,delta,offset) for scale in VALUES for delta in VALUES for offset in VALUES]

def execute(data,emu,scale,delta,offset,mutation=None):
    if any(not 0<=v<=MASK for v in (scale,delta,offset)):
        raise ValueError('arguments must be unsigned 32-bit values')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY: raise ValueError('original leaf range is incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1 or not 0<=word<=0xffff:
            raise ValueError('mutation outside the original leaf')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    record=bytearray((0x5B+i*37)&255 for i in range(RECORD_SIZE))
    for at,value in ((4,scale),(8,delta),(44,offset)):
        record[at:at+4]=value.to_bytes(4,'big')
    before=bytes(record);reads=[];writes=[]

    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,address,n):
            if self.fetching:
                if n!=2 or not ENTRY<=address or address+2>END:
                    raise ValueError(f'fetch outside A750A: {address:08x}/{n}')
            elif n==4 and address in (TARGET+4,TARGET+8,TARGET+44):
                value=super().read(address,n); reads.append([address-TARGET,n,value]); return value
            else: raise ValueError(f'unexpected read {address:08x}/{n}')
            return super().read(address,n)
        def write(self,address,n,value):
            writes.append([address,n,value&MASK]); raise ValueError(f'unexpected write {address:08x}/{n}')

    memory=Memory();memory.add(ENTRY,len(code),code); record_mem=memory.add(TARGET,RECORD_SIZE,record)
    class CPU(emu.CPU):
        def __init__(self,mem): super().__init__(mem);self.executed=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END: raise ValueError(f'PC/budget escaped A750A at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)

    cpu=CPU(memory);cpu.r=[(0xA5000000+i*0x01020305+scale+delta+offset)&MASK for i in range(16)]
    cpu.r[0]=0xDEADBEEF;cpu.r[4]=TARGET;cpu.r[15]=SP;cpu.sr=0x3f0
    cpu.macl=0x2468ace0;cpu.mach=0x13579bdf
    before_regs=cpu.r.copy();before_mach=cpu.mach;before_sr=cpu.sr
    result=cpu.call(ENTRY,max_steps=LIMIT)
    product=(scale*offset)&MASK;expected=(product-delta)&MASK
    expected_sr=before_sr
    if mutation is None:
        if reads!=[[44,4,offset],[4,4,scale],[8,4,delta]]:
            raise ValueError(f'exact reads differ: {reads!r}')
        if writes:raise ValueError(f'leaf wrote memory: {writes!r}')
        if result!=expected or cpu.r[0]!=expected:raise ValueError(f'R0 differs: {result:08x}/{expected:08x}')
        if cpu.macl!=product:raise ValueError('MACL low product differs')
        if cpu.mach!=before_mach:raise ValueError('MACH changed')
        for reg,value in ((1,delta),(2,scale),(3,offset)):
            if cpu.r[reg]!=value:raise ValueError(f'loaded argument r{reg} differs')
        for reg in range(5,15):
            if cpu.r[reg]!=before_regs[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if cpu.r[15]!=SP or cpu.pr!=emu.RETURN_SENTINEL or cpu.sr!=expected_sr:
            raise ValueError(f'SP/PR/SR differs: {cpu.r[15]:08x}/{cpu.pr:08x}/{cpu.sr:08x}/{expected_sr:08x}')
        if bytes(record_mem)!=before:raise ValueError('input record was modified')
    return {'scale':scale,'delta':delta,'offset':offset,'product_low32':product,
        'result':result,'sr':cpu.sr,'macl':cpu.macl,'steps':cpu.steps,'reads':reads,'writes':writes,
        'record_sha256':sha(bytes(record_mem)),
        'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in cpu.executed))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-japan-scaled-difference.v1','status':'failure',
        'kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],
        'record':[hex(TARGET),hex(TARGET+RECORD_SIZE)],
        'limits':['Only original five-instruction leaf including RTS delay slot','One constructed read-only 48-byte record; no caller/service/timing/gameplay validation']}
    try:
        with args.report.open('x',encoding='utf-8') as output:
            try:
                data=pinned.read_bounded(args.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(args.saturn_recomp);rows=[]
                for scale,delta,offset in corpus():
                    one=execute(data,emu,scale,delta,offset);two=execute(data,emu,scale,delta,offset)
                    if one!=two:raise ValueError('repeated original leaf execution differs')
                    rows.append(one)
                ref=execute(data,emu,7,11,5);mut=execute(data,emu,7,11,5,(0x060A7516,0x0009))
                if ref['result']==mut['result']:raise ValueError('RTS-delay subtraction mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,
                    results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),
                    mutation_control={'pc':'0x060A7516','replacement':'0x0009','rejected':True},
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Returns ((unsigned32 field+4 * unsigned32 field+44) mod 2^32) - field+8 mod 2^32; MACL receives the low product and SR is unchanged by this instruction sequence. Reads exactly offsets +44,+4,+8, writes nothing, and leaves input bytes unchanged. This arithmetic contract is isolated from caller units and service behavior.')
            except Exception as error:report['error']={'type':type(error).__name__,'reason':str(error)}
            output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as error:
        print(f'FAIL: fresh report path required: {error}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(args.report)}))
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
