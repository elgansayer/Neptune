#!/usr/bin/env python3
"""Execute Japan kernel CD74's bounded descriptor pointer/type update."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned

BASE=0x0600A000;SIZE=786432;KERNEL='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
ENTRY,END=0x0600CD74,0x0600CDA0;SP=0x06002000;TYPE_TABLE=0x060BEA3C;PTR_TABLE=0x060BEA4C;TYPE_WORDS=0x060BEA7C
ROW_BASE=0x06004000;ALT_ROW=0x06004800;N=12;LIMIT=64;MASK=0xffffffff
LITERALS={0x0600CF00:TYPE_TABLE,0x0600CF08:PTR_TABLE,0x0600CF0C:TYPE_WORDS}
def sha(b):return hashlib.sha256(b).hexdigest()

def case_corpus():
    out=[]
    for typ in range(4):
        for index in range(N):
            for high in (0,0xA5000000):out.append((typ,index|high))
    out.extend((typ,0x5A000000|5) for typ in (4,0x100,0xFFFF,0x10000,0x80000000))
    return out

def execute(data,emu,typ,index_value,mutation=None):
    if not 0<=typ<=MASK or not 0<=index_value<=MASK:raise ValueError('arguments must be unsigned words')
    code=bytearray(data[ENTRY-BASE:END-BASE])
    if mutation:
        pc,word=mutation
        if not ENTRY<=pc<END or pc&1:raise ValueError('mutation outside original helper')
        code[pc-ENTRY:pc-ENTRY+2]=word.to_bytes(2,'big')
    type_table=bytearray()
    rows=[]
    for i in range(4):
        ptr=ROW_BASE+i*0x100
        type_table.extend(ptr.to_bytes(4,'big'))
        row=bytes((i*41+j*17+3)&255 for j in range(N*4));rows.append(row)
    # CD74's fifth type slot aliases the first output pointer word in the
    # adjacent original layout. It is mapped only to exercise the branch mutant.
    initial_ptrs=bytearray((0xA0+j)&255 for j in range(N*4))
    initial_ptrs[:4]=ALT_ROW.to_bytes(4,'big')
    types_before=bytes((0xC0+i*3)&255 for i in range(N*2))
    reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=a and a+2<=END):raise ValueError(f'fetch outside CD74: {a:08x}/{n}')
            elif a in LITERALS and n==4:
                v=super().read(a,n)
                if v!=LITERALS[a]:raise ValueError(f'original literal differs at {a:08x}: {v:08x}')
                reads.append(['literal',a,n,v]);return v
            elif TYPE_TABLE<=a and a+n<=PTR_TABLE and n==4 and (a-TYPE_TABLE)%4==0:
                v=super().read(a,n);reads.append(['type-pointer',a,n,v]);return v
            elif PTR_TABLE<=a and a+n<=PTR_TABLE+N*4 and n==4 and (a-PTR_TABLE)%4==0:
                v=super().read(a,n);reads.append(['output-pointer',a,n,v]);return v
            elif any(base<=a and a+n<=base+N*4 and n==4 and (a-base)%4==0 for base in (ROW_BASE,ROW_BASE+0x100,ROW_BASE+0x200,ROW_BASE+0x300,ALT_ROW)):
                v=super().read(a,n);reads.append(['row-value',a,n,v]);return v
            else:raise ValueError(f'unexpected read {a:08x}/{n}')
            return super().read(a,n)
        def write(self,a,n,v):
            idx=(index_value&0xffff)
            if n==4 and a==PTR_TABLE+idx*4:
                writes.append(['output-pointer',idx,n,v&MASK]);return super().write(a,n,v)
            if n==2 and a==TYPE_WORDS+idx*2:
                writes.append(['type-word',idx,n,v&0xffff]);return super().write(a,n,v)
            raise ValueError(f'unexpected write {a:08x}/{n}')
    m=Memory();m.add(ENTRY,len(code),code)
    literal_bytes={addr:data[addr-BASE:addr-BASE+4] for addr in LITERALS}
    for addr,raw in literal_bytes.items():
        if len(raw)!=4 or int.from_bytes(raw,'big')!=LITERALS[addr]:raise ValueError(f'original literal identity mismatch at {addr:08x}')
        m.add(addr,4,raw)
    table=m.add(TYPE_TABLE,16,type_table);ptrs=m.add(PTR_TABLE,N*4,initial_ptrs);words=m.add(TYPE_WORDS,N*2,types_before)
    row_mem=[]
    for i,row in enumerate(rows):row_mem.append(m.add(ROW_BASE+i*0x100,len(row),row))
    alt_row=m.add(ALT_ROW,N*4,bytes((0x70+j*9)&255 for j in range(N*4)))
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.executed=[]
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if self.steps>=LIMIT or not ENTRY<=pc<END:raise ValueError(f'PC/budget escaped CD74 at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0x82000000+i*0x1020305+typ*0x101+index_value)&MASK for i in range(16)]
    c.r[4]=index_value;c.r[5]=typ;c.r[15]=SP;c.sr=0x3f0
    before=c.r.copy();expected_ptrs=bytearray(initial_ptrs);expected_types=bytearray(types_before)
    result=c.call(ENTRY,max_steps=LIMIT)
    idx=index_value&0xffff
    if mutation is None:
        if typ<4 and idx<N:
            base=ROW_BASE+typ*0x100;value=int.from_bytes(rows[typ][idx*4:idx*4+4],'big')
            expected_ptrs[idx*4:idx*4+4]=value.to_bytes(4,'big');expected_types[idx*2:idx*2+2]=typ.to_bytes(2,'big')
            expected_reads=[['literal',0x0600CF08,4,PTR_TABLE],['literal',0x0600CF00,4,TYPE_TABLE],['type-pointer',TYPE_TABLE+typ*4,4,base],['literal',0x0600CF0C,4,TYPE_WORDS],['row-value',base+idx*4,4,value]]
            expected_writes=[['output-pointer',idx,4,value],['type-word',idx,2,typ]]
        else:
            expected_reads=[];expected_writes=[]
        if reads!=expected_reads:raise ValueError(f'read trace differs: {reads!r}')
        if writes!=expected_writes:raise ValueError(f'write trace differs: {writes!r}')
        if bytes(ptrs)!=bytes(expected_ptrs) or bytes(words)!=bytes(expected_types):raise ValueError('descriptor/output tables differ')
        for reg in (8,9,10,11,12,13,14):
            if c.r[reg]!=before[reg]:raise ValueError(f'preserved GPR r{reg} changed')
        if c.r[15]!=SP or c.pr!=emu.RETURN_SENTINEL:raise ValueError('SP/PR differs')
    return {'type_index':typ,'record_index_input':index_value,'record_index_u16':idx,'result_r0':result,'steps':c.steps,
        'reads':reads,'writes':writes,'pointer_table_sha256':sha(bytes(ptrs)),'type_words_sha256':sha(bytes(words)),
        'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in c.executed))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-descriptor-update.v1','status':'failure','kernel_sha256':KERNEL,'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'limits':['Four selected type tables and twelve record entries are constructed in CPU memory','No BIOS/library service, natural caller, device behavior, timing or gameplay claim']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,SIZE)
                if len(data)!=SIZE or sha(data)!=KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for typ,index_value in case_corpus():
                    x=execute(data,emu,typ,index_value);y=execute(data,emu,typ,index_value)
                    if x!=y:raise ValueError('repeated descriptor update differs')
                    rows.append(x)
                ref=execute(data,emu,4,5);mut=execute(data,emu,4,5,(0x0600CD78,0x0009))
                if ref['writes']==mut['writes']:raise ValueError('invalid-type branch mutation survived')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_control={'pc':'0x0600CD78','replacement':'0x0009','rejected':True},
                    source_code_sha256=sha(data[ENTRY-BASE:END-BASE]),source_literals_sha256=sha(b''.join(data[addr-BASE:addr-BASE+4] for addr in sorted(LITERALS))),probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='For R5 in 0..3 and low16(R4) in 0..11, stores the selected type-row longword in BEA4C[low16(R4)] and R5 in BEA7C[low16(R4)]; R5>=4 returns without data reads or writes. High R4 bits are ignored by extu.w. The helper is CPU-only and its caller-created tables are constructed.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
