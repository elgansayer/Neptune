#!/usr/bin/env python3
"""Execute Japan's original overlap-safe byte-copy helper at 06095AFC."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432; KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x06095AFC,0x06095B3E; SP=0x06002000; ARENA=0x06003000; N=256; LIMIT=1024; MASK=0xffffffff
def sha(b): return hashlib.sha256(b).hexdigest()

def execute(data,emu,case,mutation=None):
    dst,src,count,seed=case
    if not (0<=dst<=N and 0<=src<=N and 0<=count<=N and dst+count<=N and src+count<=N):
        raise ValueError('case escapes constructed 256-byte arena')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1: raise ValueError('mutation outside original helper')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    initial=bytes((seed+i*37+(i>>2)*11)&255 for i in range(N)); expected=bytearray(initial)
    expected[dst:dst+count]=initial[src:src+count]
    reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=a and a+2<=END): raise ValueError(f'fetch outside original helper: {a:08x}/{n}')
            elif ARENA<=a and a+n<=ARENA+N:
                v=super().read(a,n); reads.append([a-ARENA,n,v]); return v
            else: raise ValueError(f'unexpected read {a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if ARENA<=a and a+n<=ARENA+N and n==1:
                writes.append([a-ARENA,n,v&255]); return super().write(a,n,v)
            raise ValueError(f'unexpected write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);arena=m.add(ARENA,N,initial)
    class CPU(emu.CPU):
        def __init__(self,memory): super().__init__(memory);self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END: raise ValueError(f'PC/budget escaped helper at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0x91827364+i*0x1020304)&MASK for i in range(16)]
    c.r[4]=ARENA+dst;c.r[5]=ARENA+src;c.r[6]=count;c.r[15]=SP;c.sr=0x3f0
    before=c.r.copy();sr=c.sr;result=c.call(ENTRY,max_steps=LIMIT)
    actual=bytes(arena)
    if mutation is None:
        if actual!=bytes(expected): raise ValueError('original copy differs from independent slice-copy result')
        changed=[i for i,(a,b) in enumerate(zip(initial,actual)) if a!=b]
        if changed and (min(changed)<dst or max(changed)>=dst+count): raise ValueError('write escaped destination window')
        offsets=(range(count-1,-1,-1) if dst>src else range(count))
        expected_reads=[[src+i,1,initial[src+i]] for i in offsets] if dst!=src else []
        offsets=(range(count-1,-1,-1) if dst>src else range(count))
        expected_writes=[[dst+i,1,expected[dst+i]] for i in offsets] if dst!=src else []
        if reads!=expected_reads or writes!=expected_writes: raise ValueError('byte transaction sequence differs')
        if result!=ARENA+dst or c.r[0]!=ARENA+dst: raise ValueError('destination return mismatch')
        if c.r[15]!=SP or c.pr!=emu.RETURN_SENTINEL: raise ValueError('stack/return state differs')
        for reg in (2,4,6,8,9,10,11,12,13,14):
            if c.r[reg]!=before[reg]: raise ValueError(f'unexpected preserved GPR change r{reg}')
    return {'destination_offset':dst,'source_offset':src,'count':count,'result_r0':result,'steps':c.steps,
            'reads':reads,'writes':writes,'arena_sha256':sha(actual),
            'pcs_sha256':sha(b''.join(x.to_bytes(4,'big') for x in c.executed))}

def corpus():
    cases=[]
    for count in (0,1,2,3,7,16,31,64):
        for delta in (-65,-17,-1,0,1,17,65):
            src=80;dst=src+delta
            if dst>=0 and dst+count<=N and src+count<=N: cases.append((dst,src,count,(len(cases)*19+7)&255))
    for i in range(64):
        count=(i*29)%97;src=(i*31)%(N-count+1);dst=(i*47+13)%(N-count+1)
        cases.append((dst,src,count,(i*53+9)&255))
    return cases

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-memmove.v1','status':'failure','kernel_sha256':KERNEL,'entry':hex(ENTRY),
            'code_range':[hex(ENTRY),hex(END)],'arena':[hex(ARENA),hex(ARENA+N)],'limits':['Constructed 256-byte CPU memory arena; one original copy helper only','No caller, natural data lifetime, VDP/device behavior, timing, gameplay or independent-emulator claim']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL: raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp); rows=[]
                for case in corpus():
                    x=execute(data,emu,case);y=execute(data,emu,case)
                    if x!=y: raise ValueError('repeated original execution differs')
                    rows.append(x)
                case=(90,80,32,11);ref=execute(data,emu,case);mut=execute(data,emu,case,(0x06095B2E,0x7001))
                if ref['arena_sha256']==mut['arena_sha256']: raise ValueError('overlap direction mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_control={'pc':'0x06095B2E','replacement':'0x7001','rejected':True},
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Unsigned byte memmove over constructed in-range arena: equal/zero-length no-op, forward when destination below source, backward when destination above source; returns destination in R0. Preserves R2, R4, R6, R8-R14 and SP in tested cases; R1/R3/R5/R7 and SR condition state may change.')
            except Exception as e: report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e: print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}))
    return 0 if report['status']=='success' else 1
if __name__=='__main__': raise SystemExit(main())
