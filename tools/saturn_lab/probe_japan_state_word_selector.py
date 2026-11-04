#!/usr/bin/env python3
"""Exhaustively execute the Japanese kernel's bounded state-word selector."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600B272,0x0600B290;DATA_BASE=0x060BDDB4;DATA_SIZE=12;LIMIT=32;MASK=0xffffffff
LITERALS=((0x0600B2BC,0x060BDDBE),(0x0600B2C4,0x060BDDBA))

def sha(b):return hashlib.sha256(b).hexdigest()
def output_word(status):return (status*40503+0x6996)&0xffff
def contract(status,value):
    if not 0<=status<=0xffff or not 0<=value<=0xffff:raise ValueError('Inputs must be halfwords')
    return value if 12<=status<=16 else 0

def execute(data,emu,status,value,mutation=None):
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('B272 instruction range incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside B272')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    accesses=[]
    class Memory(emu.Memory):
        def read(self,a,n):
            if ENTRY<=a and a+n<=END:return super().read(a,n)
            if any(a==src and n==4 for src,_target in LITERALS):accesses.append(['literal',a]);return super().read(a,n)
            if a==DATA_BASE+10 and n==2:accesses.append(['status']);return super().read(a,n)
            if a==DATA_BASE+6 and n==2:accesses.append(['value']);return super().read(a,n)
            raise ValueError(f'Unexpected B272 read {a:08x}/{n}')
        def write(self,a,n,v):raise ValueError(f'Unexpected B272 write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);region=m.add(DATA_BASE,DATA_SIZE,bytes(12))
    region[6:8]=value.to_bytes(2,'big');region[10:12]=status.to_bytes(2,'big')
    for src,_target in LITERALS:m.add(src,4,data[src-BASE:src-BASE+4])
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.pcs=[]
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped B272 at {pc:08x}')
            self.pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xA9000000+i*0x1020305)&MASK for i in range(16)];c.r[15]=0x060FFFF0;c.sr=0x3f0
    before=c.r.copy();c.call(ENTRY,max_steps=LIMIT)
    expected=contract(status,value)
    if mutation is None and c.r[0]!=(expected if expected<0x8000 else expected-0x10000)&MASK:
        raise ValueError(f'B272 result mismatch for {status:04x}/{value:04x}: {c.r[0]:08x}')
    if mutation is None:
        want_literals=[LITERALS[0][0]]+([LITERALS[1][0]] if 12<=status<=16 else [])
        if [x[1] for x in accesses if x[0]=='literal']!=want_literals:raise ValueError(f'B272 literal access mismatch {accesses}')
        want_accesses=[['literal',LITERALS[0][0]],['status']]
        if 12<=status<=16:want_accesses.extend((['literal',LITERALS[1][0]],['value']))
        if accesses!=want_accesses:raise ValueError(f'B272 data access order mismatch {accesses}')
    for reg in (1,5,6,7,8,9,10,11,12,13,14,15):
        if c.r[reg]!=before[reg]:raise ValueError(f'B272 preserved R{reg} changed')
    if c.pr!=emu.RETURN_SENTINEL:raise ValueError('B272 PR did not return through sentinel')
    return {'status':status,'value':value,'result':c.r[0],'steps':c.steps,'trace_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in c.pcs))}

def run(kernel_path,source_root):
    data=pinned.read_bounded(kernel_path,SIZE)
    if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
    emu=pinned.interpreter(source_root);rows=[]
    for status in range(65536):
        value=output_word(status);a=execute(data,emu,status,value);b=execute(data,emu,status,value)
        if a!=b:raise ValueError('Repeated B272 input differed')
        if a['result']!=((contract(status,value) if contract(status,value)<0x8000 else contract(status,value)-0x10000)&MASK):raise ValueError('B272 oracle mismatch')
        rows.append([status,value,a['result'],a['steps'],a['trace_sha256']])
    altered=execute(data,emu,12,0x3456,(0x0600B27C,0x8905))
    if altered['result']==0x3456:raise ValueError('B272 threshold-branch mutation survived')
    return {'schema':'neptune.original-japan-state-word-selector.v1','status':'success','game':'Japan T-14302G V1.000','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'status_domain':[0,65535],'cases':len(rows),'executions_per_case':2,'all_status_values_covered':True,'all_value_words_covered':len({r[1] for r in rows})==65536,'mutation_controls':[{'name':'invert_lower_bound_branch','pc':'0x0600b27c','replacement':'0x8905','rejected':True,'mutated_result':altered['result'],'expected_mutated_result':0}],'results_sha256':sha(json.dumps(rows,separators=(',',':')).encode()),'code_sha256':sha(data[ENTRY-BASE:END-BASE]),'probe_sha256':sha(Path(__file__).read_bytes()),'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'contract':'Read status halfword at 0x060BDDBE; when unsigned status is 12..16 inclusive, return signed-word load from 0x060BDDBA, otherwise return zero. No writes; preserve sampled R1,R5-R15 and PR. Exhaustive constructed inputs only; natural field/caller meaning unresolved.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    report={'schema':'neptune.original-japan-state-word-selector.v1','status':'failure'}
    with os.fdopen(fd,'w') as out:
        try:report.update(run(a.kernel,a.saturn_recomp))
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
