#!/usr/bin/env python3
"""Compose Japan's VBR-selected AD34 context save call with original A164."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
CALL,BOUND=0x0600AD26,0x0600AD38;SAVE,SAVE_END=0x0600A164,0x0600A186
TARGET_LITERAL=0x0600AD8C;TABLE_ALIAS=0x2600A020;TABLE_BASE=0x0600A020
FRAMES=(0x060BDD24,0x060BDD7C);SP=0x06002000;LIMIT=32;MASK=0xffffffff
PATTERNS=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,0x7fffffff,0x80000000,0xffffffff,0x01020304,0x55aa55aa,0xaa55aa55,0x13579bdf,0x2468ace0,0xdeadbeef,0xc001d00d,0x0f0e0d0c,0xf0e0d0c0,0x12345678,0x87654321)
def sha(b):return hashlib.sha256(b).hexdigest()

def execute(data,emu,seed,vbr,mutation=None):
    caller=bytearray(data[CALL-BASE:BOUND-BASE]);callee=bytearray(data[SAVE-BASE:SAVE_END-BASE]);target=data[TARGET_LITERAL-BASE:TARGET_LITERAL-BASE+4]
    if mutation:
        pc,word=mutation
        if CALL<=pc<BOUND:caller[pc-CALL:pc-CALL+2]=word.to_bytes(2,'big')
        elif SAVE<=pc<SAVE_END:callee[pc-SAVE:pc-SAVE+2]=word.to_bytes(2,'big')
        else:raise ValueError('Mutation outside original AD34/A164 code')
    table=bytearray().join(x.to_bytes(4,'big') for x in FRAMES)
    events=[];reads=[];index=((vbr>>10)&1)
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not ((CALL<=a and a+2<=BOUND) or (SAVE<=a and a+2<=SAVE_END)):raise ValueError('Fetch escaped original AD34/A164')
            elif a==TARGET_LITERAL and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            elif a==TABLE_ALIAS+index*4 and n==4:
                v=super().read(a,n);reads.append([a,n,v]);return v
            else:raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            slot=next((i for i,base in enumerate(FRAMES) if base+32<=a and a+n<=base+80),None)
            if n!=4 or slot is None or (a-(FRAMES[slot]+32))%4:raise ValueError(f'Write outside selected frame: 0x{a:08x}/{n}')
            events.append([slot,a-(FRAMES[slot]+32),n,v&MASK]);return super().write(a,n,v)
    m=Memory();m.add(CALL,len(caller),caller);m.add(SAVE,len(callee),callee);m.add(TARGET_LITERAL,4,target)
    m.add(TABLE_BASE,len(table),table)
    frames=[m.add(base+32,48,bytearray([0xA7]*48)) for base in FRAMES]
    class CPU(emu.CPU):
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ((CALL<=pc<BOUND) or (SAVE<=pc<SAVE_END)):raise ValueError('Original AD34/A164 PC or budget violation')
            return super().exec(ins,pc,in_slot=in_slot)
        def step(self):
            if self.pc==BOUND:self.observed_return_pc=self.pc;self.pc=emu.RETURN_SENTINEL;return
            return super().step()
    c=CPU(m);c.r=[((0xC7000000+i*0x03040507+seed*0x11111111)&MASK) for i in range(16)]
    c.r[13]=TABLE_ALIAS;c.r[14]=1;c.r[15]=SP;c.sr=0x3f0 if seed&1 else 0x1f0;c.pr=MASK;c.macl=(0x2468ace0^seed)&MASK;c.mach=(0x13579bdf^seed)&MASK
    before=c.r.copy();special=(c.sr,c.macl,c.mach);c.vbr=vbr;c.observed_return_pc=None
    result=c.call(CALL,max_steps=LIMIT);actual_index=next((i for i,b in enumerate(FRAMES) if b+32==c.r[4]),None)
    values={0:before[8],4:before[8],8:before[9],12:before[10],16:before[11],20:before[12],24:before[13],28:before[14],32:before[15],36:BOUND,40:special[2],44:special[1]}
    expected=bytearray([0xA7]*48)
    for off,val in values.items():expected[off:off+4]=val.to_bytes(4,'big')
    expected_events=[[index,off,4,values[off]] for off in (0,4,8,12,16,20,24,28,32,40,44,36)]
    if mutation is None:
        if actual_index!=index or bytes(frames[index])!=bytes(expected):raise ValueError('VBR-selected original frame differs')
        if events!=expected_events:raise ValueError('Selected frame store order differs')
        if reads!=[[TARGET_LITERAL,4,SAVE],[TABLE_ALIAS+index*4,4,FRAMES[index]]]:raise ValueError('Literal/VBR table read sequence differs')
        if c.observed_return_pc!=BOUND or c.r[3]!=SAVE or c.r[0]!=0 or result!=0 or c.pr!=BOUND:raise ValueError('JSR/delay/return state differs')
        if any(c.r[i]!=before[i] for i in range(1,16) if i not in (3,4)):raise ValueError('Unexpected caller/callee GPR clobber')
        if (c.sr,c.macl,c.mach,c.r[15])!=(*special,SP):raise ValueError('Unexpected special register or stack change')
        if c.steps!=26:raise ValueError(f'Expected 26 original instructions, got {c.steps}')
    return {'seed':seed,'vbr':vbr,'selected_index':actual_index,'frame_sha256':sha(bytes(frames[index])),
            'reads':reads,'writes':events,'steps':c.steps,'return_pc':c.observed_return_pc,'frame_pointer':c.r[4],'result_r0':result}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    r={'schema':'neptune.original-japan-sh2-vbr-context-save.v1','status':'failure','release':'Japan T-14302G V1.000','mapping':hex(BASE),'caller_range':[hex(CALL),hex(BOUND)],'callee_range':[hex(SAVE),hex(SAVE_END)],'target_literal':hex(TARGET_LITERAL),'table_alias':hex(TABLE_ALIAS),'frames':[hex(x) for x in FRAMES],'kernel_sha256':KERNEL,'original_game_bytes_executed':False,'limits':['Constructed VBR values and a two-entry cache-through backing table; original caller and A164 bytes execute','Cache-through slot contents and task identity are constructed, not naturally observed','No natural VBR/task-switch or context lifetime proof']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            if data[TARGET_LITERAL-BASE:TARGET_LITERAL-BASE+4]!=SAVE.to_bytes(4,'big'):raise ValueError('AD34 target literal differs')
            emu=pinned.interpreter(a.saturn_recomp);rows=[]
            for i,vbr in enumerate((0x06000000,0x06000400)):
                for seed in range(len(PATTERNS)):
                    one=execute(data,emu,seed,vbr);two=execute(data,emu,seed,vbr)
                    if one!=two:raise ValueError('Repeated VBR-selected context save differs')
                    rows.append(one)
            controls=[]
            for name,mut,seed,vbr in [('force_vbr_slot0',(CALL+8,0xC900),3,0x06000400),('wrong_context_increment',(CALL+16,0x7400),7,0x06000400)]:
                baseline=execute(data,emu,seed,vbr)
                try:altered=execute(data,emu,seed,vbr,mut)
                except Exception as e:rejection=f'{type(e).__name__}: {e}'
                else:
                    if altered['frame_sha256']==baseline['frame_sha256']:raise ValueError('Mutation survived: '+name)
                    rejection='changed_frame_or_selected_slot'
                controls.append({'name':name,'pc':hex(mut[0]),'replacement':hex(mut[1]),'rejected':True,'reason':rejection})
            r.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                     results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                     caller_sha256=sha(data[CALL-BASE:BOUND-BASE]),callee_sha256=sha(data[SAVE-BASE:SAVE_END-BASE]),
                     literal_sha256=sha(data[TARGET_LITERAL-BASE:TARGET_LITERAL-BASE+4]),probe_sha256=sha(Path(__file__).read_bytes()),
                     interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:r['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':r['status'],'cases':r.get('cases',0),'report':str(a.report)}));return 0 if r['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
