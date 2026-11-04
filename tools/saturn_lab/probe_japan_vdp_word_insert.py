#!/usr/bin/env python3
"""Execute Japan's original bounded 06095C24 SH-2 word-bitfield helper."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x06095C24,0x06095C8C;TARGET=0x06003000;SP=0x06002000;STACK_BYTES=20;STACK_BASE=SP-STACK_BYTES;LIMIT=256;MASK=0xffffffff
SELECTORS=(0x0101,0x0201,0x0301,0x0401,0x0501)
VALUES=(0,1,2,3,0x1f,0x20,0xff,0x100,0x7fff,0x8000,0xffff,0x12345678,0x55555555,0xaaaaaaaa,0x80000000,0xffffffff)
OLD_WORDS=(0,1,0xffffffff,0xaaaaaaaa,0x55555555,0x12345678,0x87654321,0xdeadbeef)

def sha(b):return hashlib.sha256(b).hexdigest()

def contract(old,value,selector):
    width=selector&0xff;gap=(selector>>8)&0xff
    if width!=1 or not 1<=gap<=5:raise ValueError('selector outside five observed caller values')
    shift=32-width-gap
    fieldmask=((1<<width)-1)<<shift
    return ((old&(~fieldmask&MASK))|((value&((1<<width)-1))<<shift))&MASK, value&((1<<width)-1)

def execute(data,emu,case,mutation=None):
    selector,value,old=case
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside original helper code')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    stack_init=bytearray((0xCC ^ ((i*13)&0xff))&0xff for i in range(STACK_BYTES));stack_before=bytes(stack_init)
    target_init=old.to_bytes(4,'big');reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=a and a+2<=END):raise ValueError(f'Fetch outside original helper: {a:08x}/{n}')
            elif a==TARGET and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            elif STACK_BASE<=a and a+n<=SP and n==4 and (a-SP)%4==0:
                v=super().read(a,n);reads.append([a,n,v]);return v
            else:raise ValueError(f'Unexpected read {a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if n==4 and STACK_BASE<=a and a+n<=SP and (a-SP)%4==0:
                writes.append(['stack',a-STACK_BASE,n,v&MASK]);return super().write(a,n,v)
            if a==TARGET and n==4:
                writes.append(['target',0,n,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'Unexpected write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);stack=m.add(STACK_BASE,STACK_BYTES,stack_init);target=m.add(TARGET,4,target_init)
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped original helper at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xA1000000+i*0x01020305+selector*0x101+value*0x1111)&MASK for i in range(16)]
    c.r[0]=value;c.r[1]=selector;c.r[2]=TARGET;c.r[15]=SP;c.sr=0x3f0;c.macl=0x13579bdf;c.mach=0x2468ace0
    before=c.r.copy();saved=(c.macl,c.mach,c.sr)
    result=c.call(ENTRY,max_steps=LIMIT)
    expected,masked=contract(old,value,selector)
    if mutation is None:
        if int.from_bytes(target,'big')!=expected:raise ValueError(f'Independent bitfield result mismatch: got {int.from_bytes(target,"big"):08x}, expected {expected:08x}')
        if writes.count(['target',0,4,expected])!=1 or [w[0] for w in writes].count('target')!=1:raise ValueError(f'Target write count/value differs: {writes}')
        expected_pushes=[['stack',off,4,before[reg]] for off,reg in ((16,1),(12,3),(8,4),(4,5),(0,6))]
        expected_pops=[[STACK_BASE+off,4,before[reg]] for off,reg in ((0,6),(4,5),(8,4),(12,3),(16,1))]
        if [w for w in writes if w[0]=='stack']!=expected_pushes or [r for r in reads if r[0]!=TARGET]!=expected_pops:raise ValueError('Exact stack spill/restore transaction differs')
        if c.r[0]!=masked or result!=masked:raise ValueError(f'Return value mismatch {c.r[0]:08x}/{masked:08x}')
        for reg in range(1,16):
            if reg!=15 and c.r[reg]!=before[reg]:raise ValueError(f'Unexpected GPR clobber r{reg}: {c.r[reg]:08x}')
        if c.r[15]!=SP or (c.macl,c.mach)!=(saved[0],saved[1]) or c.pr!=emu.RETURN_SENTINEL:raise ValueError('Stack/MAC/PR preservation differs')
        if c.steps>LIMIT:raise ValueError('Instruction bound exceeded')
    return {'selector':selector,'value':value,'old_word':old,'new_word':int.from_bytes(target,'big'),'result_r0':result,'steps':c.steps,'reads':reads,'writes':writes,'stack_pointer_restored':c.r[15]==SP,'stack_after_sha256':sha(bytes(stack)),'pcs_sha256':sha(b''.join(x.to_bytes(4,'big') for x in c.executed))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-vdp-word-insert.v1','status':'failure','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'target':hex(TARGET),'stack':[hex(STACK_BASE),hex(SP)],'limits':['Original helper bytes execute with constructed selectors observed in Japanese VDP callers, values, old target word and bounded stack','Only one controlled data word is writable outside the spill stack; VDP/MMIO behavior is not modeled','No natural caller/data lifetime, hardware VDP behavior, timing or independent emulator claim']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            emu=pinned.interpreter(a.saturn_recomp)
            corpus=[(sel,val,old) for sel in SELECTORS for val in VALUES for old in OLD_WORDS]
            rows=[]
            for case in corpus:
                one=execute(data,emu,case);two=execute(data,emu,case)
                if one!=two:raise ValueError('Repeated original bitfield helper differs')
                rows.append(one)
            controls=[]
            c0=(0x0101,2,0xAAAAAAAA);base=execute(data,emu,c0)
            for name,mut,case in [('replace_input_mask',(0x06095C52,0x6053),c0),('remove_target_store',(0x06095C7E,0x0009),(0x0501,1,0))]:
                reference=execute(data,emu,case);altered=execute(data,emu,case,mut)
                if altered['new_word']==reference['new_word']:raise ValueError('Mutation survived: '+name)
                controls.append({'name':name,'pc':hex(mut[0]),'replacement':hex(mut[1]),'rejected':True,'reference_word':hex(reference['new_word']),'mutated_word':hex(altered['new_word'])})
            report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,selector_values=[hex(x) for x in SELECTORS],results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,contract='Use low byte of R1 as field width and high byte as gap; preserve bits outside width at shift 32-width-gap, insert low width bits of R0, return the masked R0. For tested observed selectors 0x0101..0x0501, writes exactly one controlled longword and restores R1,R3-R6, R2, R7-R14, SP, MACH, MACL, PR; SR test bit is not claimed preserved.')
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
