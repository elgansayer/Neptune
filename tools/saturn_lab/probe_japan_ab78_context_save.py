#!/usr/bin/env python3
"""Compose the original Japanese AB78 context-save caller with A164."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
CALL,BOUND=0x0600AB78,0x0600AB94;SAVE,SAVE_END=0x0600A164,0x0600A186
FRAME=0x060BDD7C;LIT_FRAME,LIT_TARGET=0x0600AD88,0x0600AD8C
SP=0x06002000;STACK_BYTES=40;FRAME_BYTES=48;LIMIT=40;MASK=0xffffffff
PATTERNS=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,0x7fffffff,0x80000000,0xffffffff,0x01020304,0x55aa55aa,0xaa55aa55,0x13579bdf,0x2468ace0,0xdeadbeef,0xc001d00d,0x0f0e0d0c,0xf0e0d0c0,0x12345678,0x87654321)
def sha(b):return hashlib.sha256(b).hexdigest()

def execute(data,emu,seed,mutation=None):
    caller=bytearray(data[CALL-BASE:BOUND-BASE]);callee=bytearray(data[SAVE-BASE:SAVE_END-BASE]);lit1=bytearray(data[LIT_FRAME-BASE:LIT_FRAME-BASE+4]);lit2=bytearray(data[LIT_TARGET-BASE:LIT_TARGET-BASE+4])
    if mutation:
        pc,word=mutation
        if CALL<=pc<BOUND:caller[pc-CALL:pc-CALL+2]=word.to_bytes(2,'big')
        elif SAVE<=pc<SAVE_END:callee[pc-SAVE:pc-SAVE+2]=word.to_bytes(2,'big')
        elif pc==LIT_TARGET:lit2[:]=word.to_bytes(4,'big')
        else:raise ValueError('Mutation outside original caller/callee/literal')
    frame=bytearray([0xCC]*FRAME_BYTES);stack=bytearray([0xD3]*STACK_BYTES);events=[];reads=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not ((CALL<=a and a+2<=BOUND) or (SAVE<=a and a+2<=SAVE_END)):raise ValueError('Instruction fetch escaped caller/callee')
            elif a==LIT_FRAME and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            elif a==LIT_TARGET and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            elif SP-STACK_BYTES<=a and a+n<=SP and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            else:raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if n==4 and FRAME<=a and a+4<=FRAME+FRAME_BYTES and (a-FRAME)%4:
                raise ValueError('Unaligned context store')
            if n==4 and FRAME<=a and a+4<=FRAME+FRAME_BYTES:
                events.append([2,a-FRAME,n,v&MASK]);return super().write(a,n,v)
            if n==4 and SP-STACK_BYTES<=a and a+4<=SP and a%4==0:
                events.append([2,a-SP,n,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'Write outside context/stack: 0x{a:08x}/{n}')
    m=Memory();m.add(CALL,len(caller),caller);m.add(SAVE,len(callee),callee);m.add(LIT_FRAME,4,lit1);m.add(LIT_TARGET,4,lit2);fbuf=m.add(FRAME,FRAME_BYTES,frame);sbuf=m.add(SP-STACK_BYTES,STACK_BYTES,stack)
    class CPU(emu.CPU):
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ((CALL<=pc<BOUND) or (SAVE<=pc<SAVE_END)):raise ValueError('Original AB78/A164 PC or budget violation')
            return super().exec(ins,pc,in_slot=in_slot)
        def step(self):
            if self.pc==BOUND:
                self.observed_return_pc=self.pc;self.pc=emu.RETURN_SENTINEL;return
            return super().step()
    c=CPU(m);c.r=[((0xA3000000+i*0x02030405+seed*0x11111111)&MASK) for i in range(16)]
    c.r[15]=SP;c.sr=0x3f0 if seed&1 else 0x1f0;c.pr=MASK;c.macl=(0x89abcdef^seed)&MASK;c.mach=(0x13572468^seed)&MASK
    before=c.r.copy();before_special=(c.sr,c.macl,c.mach);c.observed_return_pc=None;result=c.call(CALL,max_steps=LIMIT)
    saved={0:before[8],4:before[8],8:before[9],12:before[10],16:before[11],20:before[12],24:before[13],28:before[14],32:SP-STACK_BYTES,36:BOUND,40:before_special[2],44:before_special[1]}
    expected=bytearray([0xCC]*FRAME_BYTES)
    for off,val in saved.items():expected[off:off+4]=val.to_bytes(4,'big')
    expected_events=[]
    for off,reg in ((0,14),(4,13),(8,12),(12,11),(16,10),(20,9),(24,8)):
        expected_events.append([2,-(off+4),4,before[reg]])
    expected_events.extend(([2,-32,4,emu.RETURN_SENTINEL],[2,-36,4,before_special[1]]))
    expected_events.extend([[2,off,4,saved[off]] for off in (0,4,8,12,16,20,24,28,32,40,44,36)])
    if mutation is None:
        if bytes(fbuf)!=bytes(expected):
            off=next(i for i,(x,y) in enumerate(zip(fbuf,expected)) if x!=y)
            raise ValueError(f'Saved task frame differs at +0x{off:x}: got 0x{fbuf[off]:02x}, expected 0x{expected[off]:02x}')
        if events!=expected_events:
            j=next((i for i,(x,y) in enumerate(zip(events,expected_events)) if x!=y),min(len(events),len(expected_events)))
            raise ValueError(f'Stack/context transaction differs at event {j}: got {events[j:j+1]}, expected {expected_events[j:j+1]} (counts {len(events)}/{len(expected_events)})')
        if reads!=[[LIT_FRAME,4,FRAME],[LIT_TARGET,4,SAVE]]:raise ValueError('Exact two original caller literals differ')
        if c.observed_return_pc!=BOUND or c.r[4]!=FRAME or c.r[3]!=SAVE or c.r[0]!=0 or result!=0:raise ValueError('Original JSR/return/R0 contract differs')
        if c.r[15]!=SP-STACK_BYTES or c.pr!=BOUND or (c.sr,c.macl,c.mach)!=before_special:raise ValueError('Caller stack/special-register contract differs')
        if any(c.r[i]!=before[i] for i in range(1,16) if i not in (3,4,15)):raise ValueError('Unexpected GPR clobber')
        if c.steps!=31:raise ValueError(f'Expected 31 original instructions, got {c.steps}')
    return {'seed':seed,'frame_sha256':sha(bytes(fbuf)),'stack_sha256':sha(bytes(sbuf)),'writes':events,'literal_reads':reads,
            'steps':c.steps,'return_pc':c.observed_return_pc,'frame_pointer':c.r[4],'pr':c.pr,'result_r0':result}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    r={'schema':'neptune.original-japan-sh2-ab78-context-save.v1','status':'failure','release':'Japan T-14302G V1.000','mapping':hex(BASE),'caller_range':[hex(CALL),hex(BOUND)],'callee_range':[hex(SAVE),hex(SAVE_END)],'literal_ranges':[[hex(LIT_FRAME),hex(LIT_FRAME+4)],[hex(LIT_TARGET),hex(LIT_TARGET+4)]],'frame':hex(FRAME),'stack_top':hex(SP),'kernel_sha256':KERNEL,'original_game_bytes_executed':False,'limits':['Constructed saved registers and stack; original AB78 prologue, literal loads, JSR/delay slot and A164 callee','Stops at AB94 immediately after actual callee RTS; remaining caller device/cache-through behavior excluded','No natural boot/task-switch or live frame lifetime proof']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            if data[LIT_FRAME-BASE:LIT_FRAME-BASE+4]!=FRAME.to_bytes(4,'big') or data[LIT_TARGET-BASE:LIT_TARGET-BASE+4]!=SAVE.to_bytes(4,'big'):raise ValueError('Original caller literal targets mismatch')
            emu=pinned.interpreter(a.saturn_recomp);rows=[]
            for seed in range(len(PATTERNS)):
                x=execute(data,emu,seed);y=execute(data,emu,seed)
                if x!=y:raise ValueError('Repeated AB78 caller/callee differed')
                rows.append(x)
            controls=[]
            for name,mut,seed in [('wrong_target_frame_offset',(CALL+26,0xE401),4),('wrong_saved_r8_source',(SAVE,0x1490),9)]:
                baseline=execute(data,emu,seed)
                try:
                    altered=execute(data,emu,seed,mut)
                except Exception as fault:
                    if 'Instruction limit' in str(fault):raise
                    rejection=f'{type(fault).__name__}: {fault}'
                else:
                    if altered['frame_sha256']==baseline['frame_sha256']:raise ValueError('Mutation survived: '+name)
                    rejection='changed_frame'
                controls.append({'name':name,'pc':hex(mut[0]),'replacement':hex(mut[1]),'rejected':True,'rejection':rejection})
            r.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                     results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                     caller_sha256=sha(data[CALL-BASE:BOUND-BASE]),callee_sha256=sha(data[SAVE-BASE:SAVE_END-BASE]),
                     literals_sha256=sha(data[LIT_FRAME-BASE:LIT_TARGET-BASE+4]),probe_sha256=sha(Path(__file__).read_bytes()),
                     interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:r['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':r['status'],'cases':r.get('cases',0),'report':str(a.report)}));return 0 if r['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
