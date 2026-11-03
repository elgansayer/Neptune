#!/usr/bin/env python3
"""Execute the original Japanese kernel's one-word interrupt flag setter."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600B3BC,0x0600B3C4;LITERAL=0x0600B3F4;TARGET=0x2600A03C;PHYSICAL=0x0600A03C;LIMIT=8;MASK=0xffffffff

def sha(b):return hashlib.sha256(b).hexdigest()
def execute(data,emu,initial,mutation=None):
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('B3BC instruction range incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside B3BC')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    reads=[];writes=[]
    class Memory(emu.Memory):
        def read(self,a,n):
            if ENTRY<=a and a+n<=END:return super().read(a,n)
            if a==LITERAL and n==4:reads.append([a,n]);return super().read(a,n)
            raise ValueError(f'Unexpected B3BC read {a:08x}/{n}')
        def write(self,a,n,v):
            if a==TARGET and n==4:writes.append([a,n,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'Unexpected B3BC write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);target=m.add(PHYSICAL,4,initial.to_bytes(4,'big'));m.add(LITERAL,4,data[LITERAL-BASE:LITERAL-BASE+4])
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.pcs=[]
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped B3BC at {pc:08x}')
            self.pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xA3000000+i*0x01020307)&MASK for i in range(16)];c.r[15]=0x060FFFF0;c.sr=0x3f0
    before=c.r.copy();sr=c.sr;c.call(ENTRY,max_steps=LIMIT)
    if mutation is None and bytes(target)!=(1).to_bytes(4,'big'):raise ValueError('B3BC did not publish flag value one')
    if reads!=[[LITERAL,4]]:raise ValueError(f'Unexpected B3BC literal read trace: {reads}')
    expected_writes=[[TARGET,4,1]]
    if mutation is None and writes!=expected_writes:raise ValueError(f'Unexpected B3BC writes: {writes}')
    if mutation is not None and writes:raise ValueError('Removed-store mutation still wrote')
    for reg in (0,2,4,5,6,7,8,9,10,11,12,13,14,15):
        if c.r[reg]!=before[reg]:raise ValueError(f'B3BC preserved R{reg} changed')
    if c.r[1]!=TARGET or c.r[3]!=1 or c.sr!=sr or c.pr!=emu.RETURN_SENTINEL:raise ValueError('B3BC caller-visible register/SR/PR contract differs')
    return {'initial':initial,'final':int.from_bytes(target,'big'),'reads':reads,'writes':writes,'steps':c.steps,'pcs':[hex(x) for x in c.pcs]}

def run(kernel_path,source_root):
    data=pinned.read_bounded(kernel_path,SIZE)
    if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
    emu=pinned.interpreter(source_root);inputs=[(i*0x9e3779b1+0xA5A55A5A)&MASK for i in range(64)];rows=[]
    for initial in inputs:
        a=execute(data,emu,initial);b=execute(data,emu,initial)
        if a!=b:raise ValueError('Repeated B3BC execution differs')
        rows.append(a)
    ref=execute(data,emu,inputs[17]);mut=execute(data,emu,inputs[17],(0x0600B3C2,0x0009))
    if ref['final']==mut['final']:raise ValueError('B3BC removed-store mutation survived')
    return {'schema':'neptune.original-japan-interrupt-flag-setter.v1','status':'success','game':'Japan T-14302G V1.000','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'literal':[hex(LITERAL),hex(LITERAL+4)],'target':hex(TARGET),'cases':len(rows),'executions_per_case':2,'mutation_controls':[{'name':'remove_rts_delay_slot_store','pc':'0x0600b3c2','replacement':'0x0009','rejected':True,'reference_value':ref['final'],'mutated_value':mut['final']}],'results':rows,'results_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'code_sha256':sha(data[ENTRY-BASE:END-BASE]),'probe_sha256':sha(Path(__file__).read_bytes()),'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'contract':'Load original literal pointer 0x2600A03C, set R3=1, return, and write one longword value 1 through the RTS delay slot. Preserve sampled R0,R2,R4-R15,SR; R1=pointer, R3=1; no stack or other memory access. Constructed initial word only; callback scheduling/lifetime unresolved.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    report={'schema':'neptune.original-japan-interrupt-flag-setter.v1','status':'failure'}
    with os.fdopen(fd,'w') as out:
        try:report.update(run(a.kernel,a.saturn_recomp))
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
