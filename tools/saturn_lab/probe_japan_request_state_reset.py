#!/usr/bin/env python3
"""Execute original Japanese kernel helper A6D3A that resets request state."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060A6D3A,0x060A6D46;TARGET=0x06003000;SIZE_RECORD=60;SP=0x06002000;LIMIT=16;MASK=0xffffffff
OLD_VALUES=(0,1,2,3,4,0x7fffffff,0x80000000,0xffffffff)
NEW_VALUES=(0,1,3,0x12345678)
def sha(b):return hashlib.sha256(b).hexdigest()

def execute(data,emu,old,new,mutation=None):
    if not 0<=old<=MASK or not 0<=new<=MASK:raise ValueError('request words must be unsigned 32-bit values')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('mutation outside original helper')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    record=bytearray((0x39+i*29)&255 for i in range(SIZE_RECORD))
    record[36:40]=(0x13572468).to_bytes(4,'big');record[40:44]=(0x89abcdef).to_bytes(4,'big')
    record[52:56]=(0x2468ace0).to_bytes(4,'big');record[56:60]=old.to_bytes(4,'big')
    before_record=bytes(record);reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=a and a+2<=END):raise ValueError(f'fetch outside original helper: {a:08x}/{n}')
            elif a==TARGET+56 and n==4:
                v=super().read(a,n);reads.append([56,n,v]);return v
            else:raise ValueError(f'unexpected read {a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if n==4 and a in (TARGET+56,TARGET+36,TARGET+40):
                off=a-TARGET;writes.append([off,n,v&MASK]);return super().write(a,n,v)
            if mutation and n==4 and a==TARGET+52:
                writes.append(['mutation-only-offset-52',n,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'unexpected write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);target=m.add(TARGET,SIZE_RECORD,record)
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped helper at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xB1000000+i*0x01020305+old+new)&MASK for i in range(16)]
    c.r[0]=0xdeadbeef;c.r[4]=TARGET;c.r[5]=new;c.r[15]=SP;c.sr=0x3f0
    before=c.r.copy();before_sr=c.sr
    result=c.call(ENTRY,max_steps=LIMIT)
    if mutation is None:
        expected=bytearray(before_record);expected[36:40]=b'\0'*4;expected[40:44]=b'\0'*4;expected[56:60]=new.to_bytes(4,'big')
        expected_writes=[[56,4,new],[36,4,0],[40,4,0]]
        if reads!=[[56,4,old]] or writes!=expected_writes:raise ValueError(f'exact memory transactions differ: {reads!r}/{writes!r}')
        if bytes(target)!=bytes(expected):raise ValueError('request record image differs')
        if result!=old or c.r[0]!=old:raise ValueError(f'old state return differs: {result:08x}/{old:08x}')
        if c.r[4]!=TARGET or c.r[5]!=0:raise ValueError('request pointer/R5 result differs')
        for reg in (1,2,3,6,7,8,9,10,11,12,13,14):
            if c.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if c.r[15]!=SP or c.pr!=emu.RETURN_SENTINEL or c.sr!=before_sr:raise ValueError('stack/link/SR differs')
    return {'old_state':old,'new_state':new,'result_r0':result,'steps':c.steps,'reads':reads,'writes':writes,
        'record_sha256':sha(bytes(target)),'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in c.executed))}

def corpus():return [(old,new) for old in OLD_VALUES for new in NEW_VALUES]

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-request-state-reset.v1','status':'failure','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'record':[hex(TARGET),hex(TARGET+SIZE_RECORD)],'limits':['Only the six original instructions including RTS delay slot execute','One constructed 60-byte request record; no BIOS/device/caller/gameplay validation']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for old,new in corpus():
                    one=execute(data,emu,old,new);two=execute(data,emu,old,new)
                    if one!=two:raise ValueError('repeated original helper differs')
                    rows.append(one)
                ref=execute(data,emu,0x11223344,0x55667788)
                mut=execute(data,emu,0x11223344,0x55667788,(0x060A6D3C,0x145D))
                if mut['record_sha256']==ref['record_sha256'] or not any(w[0]=='mutation-only-offset-52' for w in mut['writes']):
                    raise ValueError('store-offset mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_control={'pc':'0x060A6D3C','replacement':'0x145D','rejected':True},
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Loads and returns the prior longword at request+56, stores incoming R5 there, clears request+36 and request+40 (the latter in RTS delay slot), leaves R5=0, and preserves R4, R1-R3, R6-R14, SP, PR linkage and SR in tested cases. One constructed request record only.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
