#!/usr/bin/env python3
"""Execute the original Japanese kernel's bounded 18-record counter adjustment."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600AB30,0x0600AB78;RECORD_BASE=0x060BCEEC;STRIDE=88;COUNT=18;TABLE_SIZE=STRIDE*COUNT
LITERALS=((0x0600AD7C,4),(0x0600AD80,4),(0x0600AD84,4))
NEW_ADDR,OLD_ADDR=0x2600A038,0x060BDDAC;SP=0x060FFFF0;STACK=SP-4;LIMIT=512;MASK=0xffffffff
DELTAS=(0,1,2,3,17,0x7fffffff,0x80000000,0xffffffff)
RECORD_PATTERNS=(0,1,2,3,17,0x7fffffff,0x80000000,0xffffffff)

def sha(data):return hashlib.sha256(data).hexdigest()
def adjust_value(active,value,delta):
    if not active or value<=1:return None
    return (value-delta if value>delta else 1)&MASK

def corpus():
    for old in (0,1,17,0x7ffffffe,0xffffffff):
        for delta in DELTAS:
            for pattern in range(len(RECORD_PATTERNS)):
                new=(old+delta)&MASK
                records=[]
                for i in range(COUNT):
                    active=((i+pattern)%3)!=0
                    value=RECORD_PATTERNS[(i+pattern)%len(RECORD_PATTERNS)]
                    records.append((active,value))
                yield old,new,tuple(records)

def execute(data,emu,case,mutation=None):
    old,new,records=case
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if len(code)!=END-ENTRY:raise ValueError('Original AB30 instruction range incomplete')
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('Mutation outside AB30')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    initial=bytearray(TABLE_SIZE)
    for i,(active,value) in enumerate(records):
        base=i*STRIDE;initial[base:base+4]=value.to_bytes(4,'big');initial[base+80]=int(active)
        for j in range(4,STRIDE):
            if j!=80:initial[base+j]=(i*29+j*13+pattern_seed(old,new))&255
    expected=bytearray(initial);delta=(new-old)&MASK;events=[]
    if new!=old:
        for i,(active,value) in enumerate(records):
            result=adjust_value(active,value,delta)
            if result is not None:
                expected[i*STRIDE:i*STRIDE+4]=result.to_bytes(4,'big')
                if result!=value:events.append([i,result])
    reads=[];writes=[];stack_writes=[];stack_reads=[]
    class Memory(emu.Memory):
        def read(self,a,n):
            if ENTRY<=a and a+n<=END:return super().read(a,n)
            if any(a==addr and n==size for addr,size in LITERALS):reads.append(['literal',a,n]);return super().read(a,n)
            if a==NEW_ADDR and n==4:reads.append(['new',n]);return super().read(a,n)
            if a==OLD_ADDR and n==4:reads.append(['old',n]);return super().read(a,n)
            if a==STACK and n==4 and stack_writes and not stack_reads:stack_reads.append(n);return super().read(a,n)
            if RECORD_BASE<=a and a+n<=RECORD_BASE+TABLE_SIZE:
                off=a-RECORD_BASE;idx,within=divmod(off,STRIDE)
                if n==1 and within==80:reads.append(['flag',idx]);return super().read(a,n)
                if n==4 and within==0:reads.append(['value',idx]);return super().read(a,n)
            raise ValueError(f'Unexpected AB30 read {a:08x}/{n}')
        def write(self,a,n,v):
            if a==STACK and n==4 and not stack_writes:stack_writes.append(n);return super().write(a,n,v)
            if a==OLD_ADDR and n==4:writes.append(['old',v&MASK]);return super().write(a,n,v)
            if RECORD_BASE<=a and a+n<=RECORD_BASE+TABLE_SIZE and n==4 and (a-RECORD_BASE)%STRIDE==0:
                writes.append(['record',(a-RECORD_BASE)//STRIDE,v&MASK]);return super().write(a,n,v)
            raise ValueError(f'Unexpected AB30 write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code);table=m.add(RECORD_BASE,TABLE_SIZE,initial)
    for addr,size in LITERALS:m.add(addr,size,data[addr-BASE:addr-BASE+size])
    m.add(0x0600A038,4,new.to_bytes(4,'big'));oldword=m.add(OLD_ADDR,4,old.to_bytes(4,'big'));stack=m.add(STACK,4,b'\xa1\xb2\xc3\xd4')
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.pcs=[]
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped AB30 at {pc:08x}')
            self.pcs.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0x8b000000+i*0x01010101)&MASK for i in range(16)];c.r[14]=0x12345678;c.r[15]=SP;c.sr=0x3f0;c.pr=0x87654321
    before=c.r.copy();c.call(ENTRY,max_steps=LIMIT)
    if mutation is None and bytes(table)!=bytes(expected):raise ValueError(f'AB30 table oracle differs for old={old:08x}, new={new:08x}')
    if mutation is None:
        expected_writes=[]
        if new!=old:
            for i,(active,value) in enumerate(records):
                result=adjust_value(active,value,delta)
                if result is not None:expected_writes.append(['record',i,result])
            expected_writes.append(['old',new])
        if writes!=expected_writes:raise ValueError(f'AB30 write order/count differs: {writes} != {expected_writes}')
    if c.r[14]!=before[14] or c.r[15]!=before[15] or c.pr!=emu.RETURN_SENTINEL:raise ValueError('AB30 R14/SP/PR contract differs')
    if stack_writes!=[4] or stack_reads!=[4] or bytes(stack)!=before[14].to_bytes(4,'big'):raise ValueError('AB30 exact R14 stack save/restore differs')
    for reg in range(8,14):
        if c.r[reg]!=before[reg]:raise ValueError(f'AB30 preserved register R{reg} changed')
    if oldword!= (new&MASK).to_bytes(4,'big') and mutation is None:raise ValueError('AB30 old/current counter publication differs')
    return {'old':old,'new':new,'delta':delta,'record_mutations':events,'table_sha256':sha(bytes(table)),'reads':reads,'writes':writes,'steps':c.steps,'pc_trace_sha256':sha(b''.join(x.to_bytes(4,'big') for x in c.pcs))}

def pattern_seed(old,new):return (old^new)&255

def run(kernel_path,source_root):
    data=pinned.read_bounded(kernel_path,SIZE)
    if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
    emu=pinned.interpreter(source_root);rows=[]
    for case in corpus():
        a=execute(data,emu,case);b=execute(data,emu,case)
        if a!=b:raise ValueError('Repeated original AB30 case differs')
        rows.append(a)
    controls=[]
    for name,mutation,case in (
        ('remove_decrement_delay_store',(0x0600AB64,0x0009),next(c for c in corpus() if c[0]==0 and c[1]==3)),
        ('remove_floor_store',(0x0600AB66,0x0009),next(c for c in corpus() if c[0]==0 and c[1]==2))):
        base=execute(data,emu,case);changed=execute(data,emu,case,mutation)
        if base['table_sha256']==changed['table_sha256']:raise ValueError('AB30 mutation survived: '+name)
        controls.append({'name':name,'pc':hex(mutation[0]),'replacement':hex(mutation[1]),'rejected':True,'base':base['table_sha256'],'mutated':changed['table_sha256']})
    return {'schema':'neptune.original-japan-record-counter-adjust.v1','status':'success','game':'Japan T-14302G V1.000','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'table':[hex(RECORD_BASE),hex(RECORD_BASE+TABLE_SIZE)],'stride':STRIDE,'records':COUNT,'cases':len(rows),'executions_per_case':2,'mutation_controls':controls,'results':rows,'results_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'code_sha256':sha(data[ENTRY-BASE:END-BASE]),'probe_sha256':sha(Path(__file__).read_bytes()),'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,'contract':'If the cache-through current counter differs from the stored previous counter, iterate 18 records. For records with byte +80 nonzero and unsigned longword base >1, replace base with value-delta when value>delta, otherwise 1; inactive or <=1 values stay unchanged. Publish current counter at stored previous counter. Constructed table and global words; no natural producer/caller or time semantics.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: fresh report path required');return 1
    report={'schema':'neptune.original-japan-record-counter-adjust.v1','status':'failure'}
    with os.fdopen(fd,'w') as out:
        try:report.update(run(a.kernel,a.saturn_recomp))
        except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
        out.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
