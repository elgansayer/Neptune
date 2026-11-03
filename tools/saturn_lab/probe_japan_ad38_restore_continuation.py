#!/usr/bin/env python3
"""Execute Japan AD38's conditional A186 restore and ready-word epilogue."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
CALL,BOUND=0x0600AD38,0x0600AD60;RESTORE,RESTORE_END=0x0600A186,0x0600A1AA
FRAME=0x060BDD7C;CONTEXT_BYTES=48;SP=0x06002000;READY_ALIAS=0x2600A028;READY_BASE=0x0600A028
LIT_FRAME,LIT_RESTORE,LIT_READY=0x0600AD88,0x0600ADA8,0x0600ADAC
LIMIT=48;MASK=0xffffffff

def sha(b):return hashlib.sha256(b).hexdigest()

def execute(data,emu,seed,r0,mutation=None):
    caller=bytearray(data[CALL-BASE:BOUND-BASE]);restore=bytearray(data[RESTORE-BASE:RESTORE_END-BASE])
    if mutation:
        pc,word=mutation
        if CALL<=pc<BOUND:caller[pc-CALL:pc-CALL+2]=word.to_bytes(2,'big')
        elif RESTORE<=pc<RESTORE_END:restore[pc-RESTORE:pc-RESTORE+2]=word.to_bytes(2,'big')
        else:raise ValueError('Mutation outside AD38/A186 original code')
    context_words=[((0xB1000000+i*0x01030507+seed*0x11111111)&MASK) for i in range(12)]
    context_words[7]=1;context_words[8]=SP;context_words[9]=0x0600AD46
    raw=b''.join(x.to_bytes(4,'big') for x in context_words)
    stack_words=[0xAABBCCDD,0xFFFFFFF0,0x0600AD00,1]
    stack_raw=b''.join(x.to_bytes(4,'big') for x in stack_words)
    ready=bytearray().join(x.to_bytes(4,'big') for x in (0x12345678,0x87654321))
    reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not ((CALL<=a and a+2<=BOUND) or (RESTORE<=a and a+2<=RESTORE_END)):raise ValueError('Fetch escaped original AD38/A186 ranges')
            elif (a==LIT_FRAME and n==4) or (a==LIT_RESTORE and n==4) or (a==LIT_READY and n==4):
                reads.append([a,n,super().read(a,n)]);return reads[-1][2]
            elif SP<=a and a+n<=SP+len(stack_raw) and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            elif FRAME<=a and a+n<=FRAME+CONTEXT_BYTES and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            else:raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            if n==4 and READY_ALIAS<=a and a+n<=READY_ALIAS+8 and a==READY_ALIAS+4:
                writes.append([a,n,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'Unexpected write 0x{a:08x}/{n}')
    m=Memory();m.add(CALL,len(caller),caller);m.add(RESTORE,len(restore),restore)
    for at in (LIT_FRAME,LIT_RESTORE,LIT_READY):
        val={LIT_FRAME:FRAME,LIT_RESTORE:RESTORE,LIT_READY:READY_ALIAS}[at]
        m.add(at,4,val.to_bytes(4,'big'))
    frame=m.add(FRAME,CONTEXT_BYTES,raw);stack=m.add(SP,len(stack_raw),stack_raw);ready_mem=m.add(READY_BASE,8,ready)
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.fetching=False;self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ((CALL<=pc<BOUND) or (RESTORE<=pc<RESTORE_END)):raise ValueError(f'AD38/A186 PC or instruction budget violation at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[((0xD3000000+i*0x0305070B+seed*0x1010101)&MASK) for i in range(16)]
    c.r[0]=r0&MASK;c.r[5]=(0xCAFEBABE^seed)&MASK;c.r[13]=0x0600D130;c.r[14]=1;c.r[15]=SP;c.vbr=0x06000400;c.sr=0x3f0;c.pr=0xBAD0BAD0
    before=c.r.copy();expected_stack=stack_raw
    result=c.call(CALL,max_steps=LIMIT)
    expected_reads=[]
    if r0 == 0:
        expected_reads += [[SP,4,stack_words[0]],[LIT_FRAME,4,FRAME],[LIT_RESTORE,4,RESTORE]]
        expected_reads += [[FRAME+i*4,4,context_words[i]] for i in (1,2,3,4,5,6,7,8,11,10,9,0)]
    expected_reads += [[LIT_READY,4,READY_ALIAS],[SP+4,4,stack_words[1]],[SP+8,4,stack_words[2]],[SP+12,4,stack_words[3]]]
    ready_after=bytearray(ready);ready_after[4:8]=(0).to_bytes(4,'big')
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'Original read sequence mismatch: actual={reads} expected={expected_reads}')
        if writes!=[[READY_ALIAS+4,4,0]]:raise ValueError(f'Ready-word clear mismatch: {writes}')
        if bytes(ready_mem)!=bytes(ready_after):raise ValueError('Only VBR-selected ready word should clear')
        if bytes(frame)!=raw or bytes(stack)!=expected_stack:raise ValueError('Restore context or epilogue stack changed')
        if c.r[15]!=SP+16 or c.r[14]!=1 or c.r[13]!=stack_words[2] or c.pr!=stack_words[1]:raise ValueError('Original stack/PR/R13/R14 epilogue differs')
        if r0 == 0:
            if c.r[4]!=context_words[0] or c.r[8]!=context_words[1] or c.pr!=stack_words[1]:raise ValueError(f'A186 restore path differs r0={c.r[0]:08x} expected_r5={c.r[5]:08x} r4={c.r[4]:08x}/{context_words[0]:08x} r8={c.r[8]:08x}/{context_words[1]:08x} pr={c.pr:08x} r15={c.r[15]:08x} r14={c.r[14]:08x}')
            if c.steps!=38:raise ValueError(f'Expected 38 instructions on restore path, got {c.steps}')
        else:
            if c.r[0]!=READY_ALIAS or c.r[4]!=before[4] or c.r[8]!=before[8]:raise ValueError('Zero-result skip-restore path differs')
            if c.steps!=15:raise ValueError(f'Expected 15 instructions on skip path, got {c.steps}')
        expected_sr=0x3f1 if r0==0 else 0x3f0
        if result!=READY_ALIAS or c.sr!=expected_sr:raise ValueError(f'Return result or test-bit state differs: r0={result:08x}, sr={c.sr:03x}, expected_sr={expected_sr:03x}')
    return {'seed':seed,'incoming_r0':r0,'result_r0':result,'final_r4':c.r[4],'final_r8':c.r[8],'reads':reads,'writes':writes,'steps':c.steps,'pcs':[f'0x{x:08x}' for x in c.executed],'ready_sha256':sha(bytes(ready_mem)),'context_sha256':sha(bytes(frame))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-ad38-restore-continuation.v1','status':'failure','kernel_sha256':KERNEL,'caller_range':[hex(CALL),hex(BOUND)],'restore_range':[hex(RESTORE),hex(RESTORE_END)],'frame':hex(FRAME),'ready_word':hex(READY_ALIAS+4),'limits':['Constructed incoming R0, stack, context and ready words; both branches execute original AD38/A186 bytes','R0=0 matches A164 return value; nonzero branch is separately constructed and does not prove A164 can produce it','No natural scheduler/task lifetime, device timing, BIOS or gameplay proof']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            literals={LIT_FRAME:FRAME,LIT_RESTORE:RESTORE,LIT_READY:READY_ALIAS}
            for at,val in literals.items():
                if data[at-BASE:at-BASE+4]!=val.to_bytes(4,'big'):raise ValueError(f'Original literal mismatch at {at:08x}')
            emu=pinned.interpreter(a.saturn_recomp);rows=[]
            for r0 in (0,1):
                for seed in range(16):
                    x=execute(data,emu,seed,r0);y=execute(data,emu,seed,r0)
                    if x!=y:raise ValueError('Repeated original continuation differs')
                    rows.append(x)
            controls=[]
            for name,mut,seed,r0 in [('force_skip_restore_on_zero',(CALL+2,0x8904),3,0),('force_restore_on_nonzero',(CALL+2,0x8904),4,1)]:
                base=execute(data,emu,seed,r0)
                try:altered=execute(data,emu,seed,r0,mut)
                except Exception as e:reason=f'{type(e).__name__}: {e}'
                else:
                    if (altered.get('final_r4'),altered.get('final_r8'))==(base.get('final_r4'),base.get('final_r8')):raise ValueError('Mutation survived: '+name)
                    reason='changed restored register state through branch selection'
                controls.append({'name':name,'pc':hex(mut[0]),'replacement':hex(mut[1]),'rejected':True,'reason':reason})
            report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,caller_sha256=sha(data[CALL-BASE:BOUND-BASE]),restore_sha256=sha(data[RESTORE-BASE:RESTORE_END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
