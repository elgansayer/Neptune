#!/usr/bin/env python3
"""Execute the original Japanese kernel's six-halfword state clear helper."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600B256,0x0600B272;TABLE=0x060BDDB4;LIMIT=64;MASK=0xffffffff
LITERALS=((0x0600B2B4,0x060BDDB8),(0x0600B2B0,0x060BDDB6),(0x0600B2AC,0x060BDDB4),(0x0600B2BC,0x060BDDBE),(0x0600B2A8,0x060BDDBC),(0x0600B2C4,0x060BDDBA))
WRITE_OFFSETS=(4,2,0,10,8,6)

def sha(b):return hashlib.sha256(b).hexdigest()
def pattern(seed):return b''.join(((seed*73+i*0x1357+0xA55A)&0xffff).to_bytes(2,'big') for i in range(6))
def execute(data,emu,initial,mutation=None):
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('B256 instruction range incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside B256')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    reads=[];writes=[]
    class Memory(emu.Memory):
        def read(self,a,n):
            if ENTRY<=a and a+n<=END:return super().read(a,n)
            if any(a==src and n==4 for src,_target in LITERALS):reads.append(a);return super().read(a,n)
            raise ValueError(f'Unexpected B256 read {a:08x}/{n}')
        def write(self,a,n,v):
            if TABLE<=a and a+n<=TABLE+12 and n==2:
                writes.append([a-TABLE,v&0xffff]);return super().write(a,n,v)
            raise ValueError(f'Unexpected B256 write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);words=m.add(TABLE,12,initial)
    for src,_target in LITERALS:m.add(src,4,data[src-BASE:src-BASE+4])
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.pcs=[]
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped B256 at {pc:08x}')
            self.pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xD7000000+i*0x0103070B)&MASK for i in range(16)];c.r[15]=0x060FFFF0;c.sr=0x3f0
    before=c.r.copy();before_sr=c.sr;c.call(ENTRY,max_steps=LIMIT)
    if mutation is None and bytes(words)!=bytes(12):raise ValueError('B256 did not clear all six halfwords')
    if mutation is None and writes!=[[off,0] for off in WRITE_OFFSETS]:raise ValueError(f'Unexpected B256 write order: {writes}')
    if reads!=[src for src,_ in LITERALS]:raise ValueError(f'Unexpected B256 literal read order: {reads}')
    if c.r[4]!=0 or c.r[15]!=before[15] or c.pr!=emu.RETURN_SENTINEL or c.sr!=before_sr:raise ValueError('B256 R4/SP/PR/SR result differs')
    for reg in (0,5,6,7,8,9,10,11,12,13,14):
        if c.r[reg]!=before[reg]:raise ValueError(f'B256 preserved register R{reg} changed')
    return {'initial_sha256':sha(initial),'final_sha256':sha(bytes(words)),'literal_reads':[hex(x) for x in reads],'writes':writes,'pcs':[hex(x) for x in c.pcs]}

def run(kernel_path,source_root):
    data=pinned.read_bounded(kernel_path,SIZE)
    if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
    emu=pinned.interpreter(source_root);inputs=[pattern(i) for i in range(64)];rows=[]
    for initial in inputs:
        a=execute(data,emu,initial);b=execute(data,emu,initial)
        if a!=b:raise ValueError('Repeated B256 case differs')
        rows.append(a)
    control_case=inputs[17];reference=execute(data,emu,control_case)
    altered=execute(data,emu,control_case,(0x0600B262,0x0009))
    if reference['final_sha256']==altered['final_sha256']:raise ValueError('B256 removed-store mutation survived')
    return {'schema':'neptune.original-japan-state-halfword-clear.v1','status':'success','game':'Japan T-14302G V1.000','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'table':[hex(TABLE),hex(TABLE+12)],'cases':len(rows),'executions_per_case':2,'mutation_controls':[{'name':'remove_fourth_halfword_store','pc':'0x0600b262','replacement':'0x0009','rejected':True,'reference_sha256':reference['final_sha256'],'mutated_sha256':altered['final_sha256']}],'results':rows,'results_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'code_sha256':sha(data[ENTRY-BASE:END-BASE]),'probe_sha256':sha(Path(__file__).read_bytes()),'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'contract':'Clear six 16-bit words at offsets 4,2,0,10,8,6 of the 12-byte table through six original literal pointers; set R4=0; preserve sampled R0,R5-R14,SP,SR,PR. Bounded helper only; caller state names and natural lifecycle unresolved.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    report={'schema':'neptune.original-japan-state-halfword-clear.v1','status':'failure'}
    with os.fdopen(fd,'w') as out:
        try:report.update(run(a.kernel,a.saturn_recomp))
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
