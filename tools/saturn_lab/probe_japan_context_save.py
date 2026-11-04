#!/usr/bin/env python3
"""Execute the original Japanese kernel's bounded SH-2 context-save leaf."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000; SIZE=786432
KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600A164,0x0600A186
CONTEXT=0x060D1000; CONTEXT_BYTES=48; LIMIT=24
PATTERNS=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,0x7fffffff,0x80000000,0xfffffffe,0xffffffff,0x01020304,0x10203040,0x55aa55aa,0xaa55aa55,0x13579bdf,0x2468ace0,0xdeadbeef,0xc001d00d,0x0f0e0d0c,0xf0e0d0c0)
MASK=0xffffffff

def sha(b): return hashlib.sha256(b).hexdigest()

def execute(data,emu,seed,mutation=None):
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1: raise ValueError('Mutation outside inspected save routine')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    initial=bytearray([0xCD]*CONTEXT_BYTES); writes=[]
    class Memory(emu.Memory):
        def read(self,a,n):
            if ENTRY<=a and a+n<=END: return super().read(a,n)
            raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
        def write(self,a,n,v):
            if n!=4 or not CONTEXT<=a or a+4>CONTEXT+CONTEXT_BYTES or (a-CONTEXT)%4:
                raise ValueError(f'Write outside exact 48-byte context: 0x{a:08x}/{n}')
            writes.append([a-CONTEXT,n,v&MASK]); return super().write(a,n,v)
    m=Memory();m.add(ENTRY,len(code),code);context=m.add(CONTEXT,CONTEXT_BYTES,initial)
    c=emu.CPU(m);c.r=[((0x91000000+i*0x01020305+seed*0x11111111)&MASK) for i in range(16)]
    c.r[4]=CONTEXT;c.r[15]=0x06002000;c.sr=0x3F2 if seed&1 else 0x1F0
    c.pr=0xfffffff0;c.macl=(0x13579bdf^seed)&MASK;c.mach=(0x2468ace0^seed)&MASK
    before=c.r.copy();special=(c.sr,c.pr,c.macl,c.mach)
    result=c.call(ENTRY,max_steps=LIMIT)
    values={0:before[8],4:before[8],8:before[9],12:before[10],16:before[11],20:before[12],24:before[13],28:before[14],32:before[15],36:special[1],40:special[3],44:special[2]}
    expected=bytearray(CONTEXT_BYTES)
    for off,val in values.items():expected[off:off+4]=val.to_bytes(4,'big')
    expected_writes=[[off,4,values[off]] for off in (0,4,8,12,16,20,24,28,32,40,44,36)]
    if mutation is None:
        if bytes(context)!=bytes(expected) or writes!=expected_writes:raise ValueError('Saved context bytes/order differ')
        if c.pc!=emu.RETURN_SENTINEL or result!=0 or c.r[0]!=0:raise ValueError('Return or RTS delay-slot R0 differs')
        if any(c.r[i]!=before[i] for i in range(1,16)):raise ValueError('Unexpected GPR clobber')
        if (c.sr,c.pr,c.macl,c.mach)!=special:raise ValueError('Unexpected special-register change')
        if c.steps!=17:raise ValueError(f'Expected 17 original instructions; got {c.steps}')
    return {'seed':seed,'input_registers':[f'0x{x:08x}' for x in before],
            'context_sha256':sha(bytes(context)),'write_offsets':[x[0] for x in writes],
            'writes':writes,'result_r0':result,'instructions':c.steps,
            'return_sentinel_reached':c.pc==emu.RETURN_SENTINEL}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    r={'schema':'neptune.original-japan-sh2-context-save.v1','status':'failure','release':'Japan T-14302G V1.000','mapping':hex(BASE),'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'context_base':hex(CONTEXT),'context_bytes':CONTEXT_BYTES,'kernel_sha256':KERNEL,'max_instructions_per_call':LIMIT,'original_game_bytes_executed':False,'limits':['Constructed source registers, PR, and writable 48-byte context; pinned SH-2 interpreter','R8 is copied to both context offsets 0 and 4 in original bytes','No natural caller/task lifetime, MMIO, timing/gameplay, or independent emulator validation']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            emu=pinned.interpreter(a.saturn_recomp); rows=[]
            for seed in range(len(PATTERNS)):
                first=execute(data,emu,seed);second=execute(data,emu,seed)
                if first!=second:raise ValueError(f'Repeated original save differed at seed {seed}')
                rows.append(first)
            controls=[]
            for name,mutation,seed in [('wrong_r8_source',(ENTRY,0x1490),4),('removed_return_delay_move',(ENTRY+32,0x0009),7)]:
                changed=execute(data,emu,seed,mutation);base=execute(data,emu,seed)
                if changed['context_sha256']==base['context_sha256'] and changed['result_r0']==base['result_r0']:
                    raise ValueError('Original instruction mutation survived: '+name)
                controls.append({'name':name,'pc':hex(mutation[0]),'replacement_opcode':hex(mutation[1]),'rejected':True})
            r.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                     results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                     code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),
                     interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES)
        except Exception as e:r['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':r['status'],'cases':r.get('cases',0),'report':str(a.report)}));return 0 if r['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
