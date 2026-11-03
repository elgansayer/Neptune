#!/usr/bin/env python3
"""Execute the original Japanese kernel's bounded 16-bit counter helper."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END,LITERAL,WORD=0x0600A5E4,0x0600A5EE,0x0600A62C,0x060B3D40
MAX_STEPS=8; MASK=0xFFFFFFFF

def sha(data): return hashlib.sha256(data).hexdigest()

def execute(data,emu,value,variant=0,mutation=None):
    if not 0<=value<=0xFFFF: raise ValueError('Word input outside 16-bit domain')
    code=bytearray(data[ENTRY-BASE:END-BASE]); literal=bytearray(data[LITERAL-BASE:LITERAL-BASE+4])
    if mutation:
        kind,arg=mutation
        if kind=='code':
            pc,opcode=arg; code[pc-ENTRY:pc-ENTRY+2]=opcode.to_bytes(2,'big')
        elif kind=='literal': literal[:]=arg.to_bytes(4,'big')
        else: raise ValueError('Unknown mutation')
    word=bytearray(value.to_bytes(2,'big')); events=[]; fetching=False
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not(ENTRY<=a and a+2<=END): raise ValueError('Fetch outside original helper')
            elif not ((a==LITERAL and n==4) or (a==WORD and n==2)):
                raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
            v=super().read(a,n)
            if not self.fetching: events.append([1,a,n,v])
            return v
        def write(self,a,n,v):
            if a!=WORD or n!=2: raise ValueError(f'Unexpected write 0x{a:08x}/{n}')
            events.append([2,a,n,v&0xffff]); return super().write(a,n,v)
    m=Memory(); m.add(ENTRY,len(code),code); m.add(LITERAL,4,literal); mapped_word=m.add(WORD,2,word)
    class CPU(emu.CPU):
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=MAX_STEPS or not ENTRY<=pc<END: raise ValueError('Instruction budget/range exceeded')
            return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m); c.r=[((0xA5000000 if variant==0 else 0x5A000000)|i*0x101)&MASK for i in range(16)]
    c.r[15]=0x06002000; c.sr=0x3F2 if variant==0 else 0; c.pr=emu.RETURN_SENTINEL
    c.macl=0x13579BDF^variant; c.mach=0x2468ACE0^variant; before=c.r.copy(); special=(c.sr,c.pr,c.macl,c.mach)
    c.call(ENTRY,max_steps=MAX_STEPS)
    result={'return_pc':c.pc,'word':int.from_bytes(mapped_word,'big'),'events':events,'trace':getattr(c,'trace',None)}
    if mutation is None:
        if c.pc!=emu.RETURN_SENTINEL or result['word']!=((value+1)&0xffff): raise ValueError('Original 16-bit increment differs')
        if any(c.r[i]!=before[i] for i in range(16) if i not in (2,3)): raise ValueError('Unexpected GPR clobber')
        if (c.sr,c.pr,c.macl,c.mach)!=special or events!=[[1,LITERAL,4,WORD],[1,WORD,2,value],[2,WORD,2,(value+1)&0xffff]]: raise ValueError('Register, return, or exact memory contract differs')
    return {'input':value,'variant':variant,'output':result['word'],'events':events,'steps':c.steps,
            'gprs_preserved_except_r2_r3':True,'special_registers_preserved':True,'return_sentinel_reached':c.pc==emu.RETURN_SENTINEL}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--kernel',type=Path,required=True); p.add_argument('--saturn-recomp',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args(argv)
    r={'schema':'neptune.original-japan-sh2-word-counter.v1','status':'failure','release':'Japan T-14302G V1.000','mapping':hex(BASE),'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'literal':hex(LITERAL),'word':hex(WORD),'original_game_bytes_executed':False,'kernel_sha256':KERNEL,'max_instructions_per_call':MAX_STEPS,'limits':['Constructed 16-bit global and CPU state; pinned SH-2 interpreter','No natural caller/device/timing/gameplay or independent-emulator validation']}
    try: fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError: print('FAIL: fresh report path required'); return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL: raise ValueError('Japan kernel identity mismatch')
            emu=pinned.interpreter(a.saturn_recomp)
            values=sorted(set(range(256))|{0x7fff,0x8000,0xfffe,0xffff})
            rows=[execute(data,emu,v,k) for v in values for k in (0,1)]
            controls=[]
            for name,mut in [('wrong_increment',('code',(ENTRY+4,0x7202))),('missing_delay_store',('code',(ENTRY+8,0x0009))),('wrong_literal',('literal',WORD+2))]:
                rejected=0
                for v in (0,0x7fff,0xffff):
                    try:
                        actual=execute(data,emu,v,0,mut)
                        if actual['output']!=((v+1)&0xffff): rejected+=1
                    except Exception: rejected+=1
                if not rejected: raise ValueError('Mutation survived: '+name)
                controls.append({'name':name,'rejected_cases':rejected})
            r.update(status='success',original_game_bytes_executed=True,cases=len(rows),results=rows,
                     results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                     source_sha256=sha(data),code_sha256=sha(data[ENTRY-BASE:END-BASE]),literal_sha256=sha(data[LITERAL-BASE:LITERAL-BASE+4]),
                     probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:r['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':r['status'],'cases':r.get('cases',0),'report':str(a.report)})); return 0 if r['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
