#!/usr/bin/env python3
"""Execute original Japanese SH-2 helper AB1B4 bounded to an eight-byte record."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x060AB1B4,0x060AB31A;LITERAL=0x060AB266;TARGET=0x06003000;SP=0x06002000;STACK_BYTES=4;LIMIT=256;MASK=0xffffffff
EXEC_RANGES=((ENTRY,LITERAL),(LITERAL+2,END))
FIELD_MASKS=(((0x00004,0x00002),1),((0x00008,0x00080),0),((0x00010,),3),((0x00020,),2),((0x00001,),5),((0x00100,),4),((0x10000,),7),((0x20000,),6))
FLAG_BITS=tuple(bit for choices,_off in FIELD_MASKS for bit in choices)
ALL_FLAGS=sum(FLAG_BITS)
ALTERNATING_FLAGS=sum(bit for i,bit in enumerate(FLAG_BITS) if i%2==0)
DATA_VALUES=(0x55,0xff)
STACK_MASKS=(0x55,0xff)
INITIALS=(bytes(8),bytes((0x13+i*0x17)&0xff for i in range(8)))

def sha(b):return hashlib.sha256(b).hexdigest()
def corpus():
    for flags in range(1 << len(FLAG_BITS)):
        r5=sum(bit for i,bit in enumerate(FLAG_BITS) if flags & (1 << i))
        for r4 in (0,ALL_FLAGS,ALTERNATING_FLAGS):
            for r7 in DATA_VALUES:
                for stack_mask in STACK_MASKS:
                    for initial in INITIALS:yield r5,r4,r7,stack_mask,initial

def expected_bytes(initial,r5,r4,r7,stack_mask):
    result=bytearray(initial);events=[]
    for choices,offset in FIELD_MASKS:
        gate=0
        for bit in choices:gate|=bit
        if r5&gate:
            if r4&gate:result[offset]|=r7
            else:result[offset]&=stack_mask
            events.append((offset,result[offset]))
    return bytes(result),events

def execute(data,emu,case,mutation=None):
    r5,r4,r7,stack_mask,initial=case
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('Original AB1B4 source range is incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside original AB1B4 range')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    reads=[];writes=[];stack_data=bytearray((0xA5,0x5A,0xC3,stack_mask));stack_before=bytes(stack_data)
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not any(lo<=a and a+2<=hi for lo,hi in EXEC_RANGES):raise ValueError(f'Fetch escaped executable AB1B4 bytes at {a:08x}/{n}')
                return super().read(a,n)
            if (a,n) in ((LITERAL,2),(0x060AB31A,2),(0x060AB31C,4),(0x060AB320,4)):
                v=super().read(a,n);reads.append(['literal',a,n,v]);return v
            if a==SP+3 and n==1:
                v=super().read(a,n);reads.append(['stack',a-SP,n,v]);return v
            if TARGET<=a and a+n<=TARGET+8 and n==1:
                v=super().read(a,n);reads.append(['record',a-TARGET,n,v]);return v
            raise ValueError(f'Unexpected read 0x{a:08x}/{n}')
        def write(self,a,n,v):
            if n==1 and TARGET<=a and a+n<=TARGET+8:
                writes.append([a-TARGET,n,v&0xff]);return super().write(a,n,v)
            raise ValueError(f'Unexpected write 0x{a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);frame=m.add(TARGET,8,initial);m.add(SP,STACK_BYTES,stack_data)
    m.add(LITERAL,2,data[LITERAL-BASE:LITERAL-BASE+2])
    m.add(0x060AB31A,2,data[0x060AB31A-BASE:0x060AB31C-BASE])
    m.add(0x060AB31C,4,data[0x060AB31C-BASE:0x060AB320-BASE])
    m.add(0x060AB320,4,data[0x060AB320-BASE:0x060AB324-BASE])
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.pcs=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not any(lo<=pc<hi for lo,hi in EXEC_RANGES):raise ValueError(f'PC or budget escaped AB1B4 at 0x{pc:08x}')
            self.pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0xB7000000+i*0x0103070B+r5*0x0101+r4*0x11+r7)&MASK for i in range(16)]
    c.r[4]=r4;c.r[5]=r5;c.r[6]=TARGET;c.r[7]=r7;c.r[15]=SP;c.sr=0x3f0;c.mach=0x13579bdf;c.macl=0x2468ace0
    before=c.r.copy();special=(c.pr,c.mach,c.macl)
    c.call(ENTRY,max_steps=LIMIT)
    expected,ordered=expected_bytes(initial,r5,r4,r7,stack_mask)
    if mutation is None:
        if bytes(frame)!=expected:raise ValueError(f'Independent record byte result differs for flags {r5:05x}')
        expected_writes=[[off,1,val] for off,val in ordered]
        if writes!=expected_writes:raise ValueError(f'Record write order/count differs: {writes} != {expected_writes}')
        expected_reads=[off for choices,off in FIELD_MASKS if r5 & sum(choices)]
        if [x[1] for x in reads if x[0]=='record']!=expected_reads:raise ValueError('Record read order/coverage differs')
        literal_addresses=[x[1] for x in reads if x[0]=='literal']
        if any(a not in (0x060AB266,0x060AB31A,0x060AB31C,0x060AB320) for a in literal_addresses):raise ValueError(f'Unexpected literal address {literal_addresses}')
        if reads.count(['stack',3,1,stack_mask])!=1:raise ValueError('Expected caller mask byte read once')
        if bytes(stack_data)!=stack_before:raise ValueError('Caller stack input changed')
        if c.r[6]!=before[6] or c.r[15]!=SP:raise ValueError('Record base or stack pointer changed')
        for reg in range(8,15):
            if c.r[reg]!=before[reg]:raise ValueError(f'Unexpected preserved-register change r{reg}')
        if c.pr!=emu.RETURN_SENTINEL or (c.mach,c.macl)!=(special[1],special[2]):raise ValueError('PR/MACH/MACL changed')
    return {'flags_r5':r5,'operation_flags_r4':r4,'value_r7':r7,'clear_mask':stack_mask,'initial_sha256':sha(initial),'final_sha256':sha(bytes(frame)),'record_reads':[x for x in reads if x[0]=='record'],'writes':writes,'steps':c.steps,'pc_trace_sha256':sha(b''.join(x.to_bytes(4,'big') for x in c.pcs))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-record-flag-bytes.v1','status':'failure','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'literal':hex(LITERAL),'record':[hex(TARGET),hex(TARGET+8)],'stack':[hex(SP),hex(SP+STACK_BYTES)],'limits':['Constructed flag words, caller mask byte, R7 value and eight-byte record; original AB1B4 instruction/literal bytes execute','Only the exact record and one stack input byte are accessible; no device/MMIO state is mapped','No natural caller record semantics/lifetime or gameplay claim']}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    with os.fdopen(fd,'w') as out:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
            emu=pinned.interpreter(a.saturn_recomp);cases=list(corpus());rows=[]
            for case in cases:
                first=execute(data,emu,case);second=execute(data,emu,case)
                if first!=second:raise ValueError('Repeated AB1B4 case differs')
                rows.append(first)
            controls=[]
            for name,mutation,case in [('invert_first_flag_branch',(0x060AB1BE,0x8903),(4,0,0x55,0x00,bytes([0xff]*8))),('remove_first_field_store',(0x060AB1EE,0x0009),(4,0,0x55,0x00,bytes([0xff]*8)))]:
                reference=execute(data,emu,case);altered=execute(data,emu,case,mutation)
                if altered['final_sha256']==reference['final_sha256']:raise ValueError('Mutation survived: '+name)
                controls.append({'name':name,'pc':hex(mutation[0]),'replacement':hex(mutation[1]),'rejected':True,'reference_sha256':reference['final_sha256'],'mutated_sha256':altered['final_sha256']})
            report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,flag_words=len(FLAG_BITS),flag_masks=[[hex(y) for y in x[0]] for x in FIELD_MASKS],r4_modes=3,value_samples=len(DATA_VALUES),mask_samples=len(STACK_MASKS),initial_records=len(INITIALS),results=rows,results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,code_sha256=sha(data[ENTRY-BASE:END-BASE]),probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,contract='For each active R5 gate group, if corresponding R4 group is set, OR low R7 into the selected R6 byte; if R4 group is clear, AND the byte with caller mask at SP+3. Eight observed mask constants address byte offsets 0..7. One-byte writes occur in original instruction order. Tested unaffected R6,R8-R14,SP,PR,MACH,MACL are preserved; no complete ABI claim.')
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
