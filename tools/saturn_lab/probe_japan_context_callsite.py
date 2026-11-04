#!/usr/bin/env python3
"""Compose the original Japanese A7D0 context callsite with its A164 callee."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432; KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
CALL,BOUND,LITERAL=0x0600A7D0,0x0600A7D6,0x0600A8D4
SAVE,SAVE_END=0x0600A164,0x0600A186
FRAME=0x060BDD24; BYTES=80; LIMIT=32; MASK=0xffffffff
PATTERNS=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,0x7fffffff,0x80000000,0xffffffff,0x01020304,0x55aa55aa,0xaa55aa55,0x13579bdf,0x2468ace0,0xdeadbeef,0xc001d00d,0x0f0e0d0c,0xf0e0d0c0,0x12345678,0x87654321)
def sha(b):return hashlib.sha256(b).hexdigest()

def execute(data,emu,seed,mutation=None):
    call_code=bytearray(data[CALL-BASE:BOUND-BASE]);save_code=bytearray(data[SAVE-BASE:SAVE_END-BASE]);literal=data[LITERAL-BASE:LITERAL-BASE+4]
    if mutation:
        pc,word=mutation
        if CALL<=pc<BOUND:call_code[pc-CALL:pc-CALL+2]=word.to_bytes(2,'big')
        elif SAVE<=pc<SAVE_END:save_code[pc-SAVE:pc-SAVE+2]=word.to_bytes(2,'big')
        else:raise ValueError('Mutation outside inspected caller/callee')
    frame=bytearray([0xCD]*BYTES);reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not ((CALL<=a and a+2<=BOUND) or (SAVE<=a and a+2<=SAVE_END)):raise ValueError('Fetch escaped original caller/callee')
            elif a==LITERAL and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            else:raise ValueError(f'Unexpected data read 0x{a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if n!=4 or not FRAME<=a or a+4>FRAME+BYTES or (a-FRAME)%4:raise ValueError(f'Write outside controlled frame 0x{a:08x}/{n}')
            writes.append([a-FRAME,n,v&MASK]);return super().write(a,n,v)
    m=Memory();m.add(CALL,len(call_code),call_code);m.add(SAVE,len(save_code),save_code);m.add(LITERAL,4,literal);buf=m.add(FRAME,BYTES,frame)
    class CPU(emu.CPU):
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT:raise RuntimeError('Original caller/callee instruction limit exceeded')
            if not ((CALL<=pc<BOUND) or (SAVE<=pc<SAVE_END)):raise ValueError(f'PC escaped inspected caller/callee at {pc:08x}')
            return super().exec(ins,pc,in_slot=in_slot)
        def step(self):
            if self.pc==BOUND:
                self.observed_return_pc=self.pc;self.pc=emu.RETURN_SENTINEL;return
            return super().step()
    c=CPU(m);c.r=[((0x91000000+i*0x01020305+seed*0x11111111)&MASK) for i in range(16)]
    c.r[4]=FRAME;c.r[15]=0x06002000;c.sr=0x3f0 if seed&1 else 0x1f0;c.pr=0xffffffff;c.macl=(0x13579bdf^seed)&MASK;c.mach=(0x2468ace0^seed)&MASK
    before=c.r.copy();saved=(c.sr,c.macl,c.mach);c.observed_return_pc=None
    result=c.call(CALL,max_steps=LIMIT)
    expected=bytearray([0xCD]*BYTES);values={0:before[8],4:before[8],8:before[9],12:before[10],16:before[11],20:before[12],24:before[13],28:before[14],32:before[15],36:BOUND,40:saved[2],44:saved[1]}
    for off,val in values.items():expected[32+off:36+off]=val.to_bytes(4,'big')
    expected_writes=[[32+off,4,values[off]] for off in (0,4,8,12,16,20,24,28,32,40,44,36)]
    if mutation is None:
        if bytes(buf)!=bytes(expected) or writes!=expected_writes:raise ValueError('Original callsite frame bytes/write order differ')
        if reads!=[[LITERAL,4,SAVE]]:raise ValueError('Original target literal read differs')
        if c.observed_return_pc!=BOUND or c.r[4]!=FRAME+32 or c.r[0]!=0 or result!=0:raise ValueError('JSR/delay-slot/callee/return path differs')
        if c.pr!=BOUND or c.r[15]!=before[15] or (c.sr,c.macl,c.mach)!=saved:raise ValueError('Callsite ABI/special state differs')
        if any(c.r[i]!=before[i] for i in range(1,16) if i not in (3,4)):raise ValueError('Unexpected register clobber')
        if c.steps!=20:raise ValueError(f'Expected 20 original instructions, got {c.steps}')
    return {'seed':seed,'frame_sha256':sha(bytes(buf)),'writes':writes,'literal_reads':reads,'steps':c.steps,
            'return_pc':c.observed_return_pc,'result_r0':result,'frame_pointer':c.r[4],'pr':c.pr}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    r={'schema':'neptune.original-japan-sh2-context-callsite.v1','status':'failure','release':'Japan T-14302G V1.000','mapping':hex(BASE),'caller_range':[hex(CALL),hex(BOUND)],'callee_range':[hex(SAVE),hex(SAVE_END)],'literal':hex(LITERAL),'frame':hex(FRAME),'frame_bytes':BYTES,'kernel_sha256':KERNEL,'original_game_bytes_executed':False,'limits':['Constructed VBR-selected caller frame and registers; exact A7D0 JSR plus A164 original bytes','Execution stops at A7D6 immediately after actual callee RTS return, before next caller instruction','No natural boot/task-switch proof or live cache-through table/lifetime validation']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            if data[LITERAL-BASE:LITERAL-BASE+4]!=SAVE.to_bytes(4,'big'):raise ValueError('A7D0 target literal differs from original A164 address')
            emu=pinned.interpreter(a.saturn_recomp);rows=[]
            for seed in range(len(PATTERNS)):
                one=execute(data,emu,seed);two=execute(data,emu,seed)
                if one!=two:raise ValueError('Repeated original context callsite differs')
                rows.append(one)
            controls=[]
            for name,mut,seed in [('missing_context_advance',(CALL+4,0x7400),3),('wrong_r8_source',(SAVE,0x1490),8)]:
                altered=execute(data,emu,seed,mut);baseline=execute(data,emu,seed)
                if altered['frame_sha256']==baseline['frame_sha256']:raise ValueError('Mutation survived: '+name)
                controls.append({'name':name,'pc':hex(mut[0]),'replacement':hex(mut[1]),'rejected':True})
            r.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                     results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                     caller_sha256=sha(data[CALL-BASE:BOUND-BASE]),callee_sha256=sha(data[SAVE-BASE:SAVE_END-BASE]),
                     literal_sha256=sha(data[LITERAL-BASE:LITERAL-BASE+4]),probe_sha256=sha(Path(__file__).read_bytes()),
                     interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:r['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':r['status'],'cases':r.get('cases',0),'report':str(a.report)}));return 0 if r['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
