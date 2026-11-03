#!/usr/bin/env python3
"""Execute Japan's original twelve-entry CDA0 caller with its CD74 helper."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import probe_kernel as pinned
import probe_japan_descriptor_update as leaf

CALLER,CALLER_END=0x0600CDA0,0x0600CDC4
STACK_SIZE=16;STACK_BASE=leaf.SP-STACK_SIZE;LIMIT=512
def sha(b):return hashlib.sha256(b).hexdigest()

def case_values():return (0,1,2,3,4,0x100,0xffff,0x80000000)

def execute(data,emu,typ,mutation=None):
    if not 0<=typ<=leaf.MASK:raise ValueError('caller type must be an unsigned word')
    leaf_code=bytearray(data[leaf.ENTRY-leaf.BASE:leaf.END-leaf.BASE])
    caller_code=bytearray(data[CALLER-leaf.BASE:CALLER_END-leaf.BASE])
    if mutation:
        pc,word=mutation
        if not leaf.ENTRY<=pc<leaf.END or pc&1:raise ValueError('mutation outside CD74 helper')
        leaf_code[pc-leaf.ENTRY:pc-leaf.ENTRY+2]=word.to_bytes(2,'big')
    type_table=bytearray();rows=[]
    for i in range(4):
        type_table.extend((leaf.ROW_BASE+i*0x100).to_bytes(4,'big'))
        rows.append(bytes((i*41+j*17+3)&255 for j in range(leaf.N*4)))
    initial_ptrs=bytearray((0xA0+j)&255 for j in range(leaf.N*4))
    initial_ptrs[:4]=leaf.ALT_ROW.to_bytes(4,'big')
    initial_types=bytes((0xC0+i*3)&255 for i in range(leaf.N*2))
    stack_init=bytearray((0xD3+i*23)&255 for i in range(STACK_SIZE))
    reads=[];writes=[]
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not ((leaf.ENTRY<=a and a+2<=leaf.END) or (CALLER<=a and a+2<=CALLER_END)):
                    raise ValueError(f'fetch outside composed caller/helper: {a:08x}/{n}')
            elif STACK_BASE<=a and a+n<=leaf.SP and n==4 and (a-leaf.SP)%4==0:
                v=super().read(a,n);reads.append(['stack',a-STACK_BASE,n,v]);return v
            elif a in leaf.LITERALS and n==4:
                v=super().read(a,n)
                if v!=leaf.LITERALS[a]:raise ValueError(f'original literal differs at {a:08x}')
                reads.append(['literal',a,n,v]);return v
            elif leaf.TYPE_TABLE<=a and a+n<=leaf.PTR_TABLE and n==4 and (a-leaf.TYPE_TABLE)%4==0:
                v=super().read(a,n);reads.append(['type-pointer',a,n,v]);return v
            elif leaf.PTR_TABLE<=a and a+n<=leaf.PTR_TABLE+leaf.N*4 and n==4 and (a-leaf.PTR_TABLE)%4==0:
                v=super().read(a,n);reads.append(['output-pointer',a,n,v]);return v
            elif any(base<=a and a+n<=base+leaf.N*4 and n==4 and (a-base)%4==0 for base in (leaf.ROW_BASE,leaf.ROW_BASE+0x100,leaf.ROW_BASE+0x200,leaf.ROW_BASE+0x300,leaf.ALT_ROW)):
                v=super().read(a,n);reads.append(['row-value',a,n,v]);return v
            else:
                cpu=getattr(self,'cpu',None)
                pc=getattr(self,'current_pc',0)
                regs=getattr(cpu,'r',[]) if cpu is not None else []
                raise ValueError(f'unexpected read {a:08x}/{n} at {pc:08x}, r4={regs[4] if regs else 0:08x}, r5={regs[5] if regs else 0:08x}, r14={regs[14] if regs else 0:08x}, tail={reads[-5:]}')
            return super().read(a,n)
        def write(self,a,n,v):
            if STACK_BASE<=a and a+n<=leaf.SP and n==4 and (a-leaf.SP)%4==0:
                writes.append(['stack',a-STACK_BASE,n,v&leaf.MASK]);return super().write(a,n,v)
            if n==4 and leaf.PTR_TABLE<=a<leaf.PTR_TABLE+leaf.N*4 and (a-leaf.PTR_TABLE)%4==0:
                idx=(a-leaf.PTR_TABLE)//4;writes.append(['output-pointer',idx,n,v&leaf.MASK]);return super().write(a,n,v)
            if n==2 and leaf.TYPE_WORDS<=a<leaf.TYPE_WORDS+leaf.N*2 and (a-leaf.TYPE_WORDS)%2==0:
                idx=(a-leaf.TYPE_WORDS)//2;writes.append(['type-word',idx,n,v&0xffff]);return super().write(a,n,v)
            raise ValueError(f'unexpected write {a:08x}/{n}')
    m=Memory();m.add(leaf.ENTRY,len(leaf_code),leaf_code);m.add(CALLER,len(caller_code),caller_code)
    for addr in leaf.LITERALS:
        raw=data[addr-leaf.BASE:addr-leaf.BASE+4]
        if len(raw)!=4 or int.from_bytes(raw,'big')!=leaf.LITERALS[addr]:raise ValueError(f'original literal identity mismatch at {addr:08x}')
        m.add(addr,4,raw)
    m.add(leaf.TYPE_TABLE,16,type_table);ptrs=m.add(leaf.PTR_TABLE,leaf.N*4,initial_ptrs);types=m.add(leaf.TYPE_WORDS,leaf.N*2,initial_types)
    row_memory=[m.add(leaf.ROW_BASE+i*0x100,len(row),row) for i,row in enumerate(rows)]
    alt=m.add(leaf.ALT_ROW,leaf.N*4,leaf.ALT_ROW.to_bytes(4,'big')*leaf.N)
    stack=m.add(STACK_BASE,STACK_SIZE,stack_init)
    class CPU(emu.CPU):
        def __init__(self,memory):super().__init__(memory);self.executed=[];m.cpu=self
        def fetch(self,pc):
            m.fetching=True
            try:return super().fetch(pc)
            finally:m.fetching=False
        def exec(self,ins,pc,in_slot=False):
            m.current_pc=pc
            if self.steps>=LIMIT or not ((leaf.ENTRY<=pc<leaf.END) or (CALLER<=pc<CALLER_END)):
                raise ValueError(f'PC/budget escaped composition at {pc:08x}')
            self.executed.append(pc);return super().exec(ins,pc,in_slot=in_slot)
    c=CPU(m);c.r=[(0x72000000+i*0x1020305+typ*0x101)&leaf.MASK for i in range(16)]
    c.r[4]=typ;c.r[15]=leaf.SP;c.sr=0x3f0
    before=c.r.copy();expected_ptrs=bytearray(initial_ptrs);expected_types=bytearray(initial_types)
    result=c.call(CALLER,max_steps=LIMIT)
    expected_reads=[];expected_writes=[
        ['stack',STACK_SIZE-4,4,before[14]],['stack',STACK_SIZE-8,4,before[13]],
        ['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL],['stack',0,4,typ]]
    if typ<4:
        for idx in range(leaf.N):
            expected_reads.append(['stack',0,4,typ])
            base=leaf.ROW_BASE+typ*0x100;value=int.from_bytes(rows[typ][idx*4:idx*4+4],'big')
            expected_reads.extend([['literal',0x0600CF08,4,leaf.PTR_TABLE],['literal',0x0600CF00,4,leaf.TYPE_TABLE],['type-pointer',leaf.TYPE_TABLE+typ*4,4,base],['literal',0x0600CF0C,4,leaf.TYPE_WORDS],['row-value',base+idx*4,4,value]])
            expected_writes.extend([['output-pointer',idx,4,value],['type-word',idx,2,typ]])
            expected_ptrs[idx*4:idx*4+4]=value.to_bytes(4,'big');expected_types[idx*2:idx*2+2]=typ.to_bytes(2,'big')
    else:
        expected_reads.extend([['stack',0,4,typ]]*leaf.N)
    expected_reads.extend([['stack',STACK_SIZE-12,4,emu.RETURN_SENTINEL],['stack',STACK_SIZE-8,4,before[13]],['stack',STACK_SIZE-4,4,before[14]]])
    if mutation is None:
        if reads!=expected_reads:raise ValueError(f'composed reads differ: got {len(reads)} expected {len(expected_reads)}')
        if writes!=expected_writes:raise ValueError(f'composed writes differ: got {len(writes)} expected {len(expected_writes)}')
        if bytes(ptrs)!=bytes(expected_ptrs) or bytes(types)!=bytes(expected_types):raise ValueError('composed output tables differ')
        stack_expected=bytearray(stack_init);stack_expected[0:4]=typ.to_bytes(4,'big')
        stack_expected[4:8]=emu.RETURN_SENTINEL.to_bytes(4,'big')
        stack_expected[8:12]=before[13].to_bytes(4,'big')
        stack_expected[12:16]=before[14].to_bytes(4,'big')
        if bytes(stack)!=bytes(stack_expected):raise ValueError(f'caller stack spill/restore differs: got {bytes(stack).hex()} expected {bytes(stack_expected).hex()}')
        for reg in (8,9,10,11,12,13,14):
            if c.r[reg]!=before[reg]:raise ValueError(f'caller preserved register r{reg} changed')
        if c.r[15]!=leaf.SP or c.pr!=emu.RETURN_SENTINEL:raise ValueError('caller SP/PR differs')
    return {'type_argument':typ,'record_iterations':leaf.N,'result_r0':result,'steps':c.steps,'reads':reads,'writes':writes,
        'pointer_table_sha256':sha(bytes(ptrs)),'type_words_sha256':sha(bytes(types)),'stack_sha256':sha(bytes(stack)),
        'pcs_sha256':sha(b''.join(pc.to_bytes(4,'big') for pc in c.executed))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--saturn-recomp',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-descriptor-caller.v1','status':'failure','kernel_sha256':leaf.KERNEL,'caller_entry':hex(CALLER),'caller_range':[hex(CALLER),hex(CALLER_END)],'helper_range':[hex(leaf.ENTRY),hex(leaf.END)],'limits':['Constructed four type tables and twelve output records plus caller stack','No BIOS/library callback semantics, natural gameplay caller, timing or device claim']}
    try:
        with a.report.open('x',encoding='utf-8') as f:
            try:
                data=pinned.read_bounded(a.kernel,leaf.SIZE)
                if len(data)!=leaf.SIZE or sha(data)!=leaf.KERNEL:raise ValueError('Japan kernel identity mismatch')
                emu=pinned.interpreter(a.saturn_recomp);rows=[]
                for typ in case_values():
                    x=execute(data,emu,typ);y=execute(data,emu,typ)
                    if x!=y:raise ValueError('repeated caller composition differs')
                    rows.append(x)
                ref=execute(data,emu,4);mut=execute(data,emu,4,(leaf.ENTRY+4,0x0009))
                if ref['pointer_table_sha256']==mut['pointer_table_sha256'] and ref['type_words_sha256']==mut['type_words_sha256']:
                    raise ValueError('invalid-type branch mutation survived composed caller')
                report.update(status='success',original_game_bytes_executed=True,cases=len(rows),executions_per_case=2,results=rows,
                    results_sha256=sha(json.dumps(rows,sort_keys=True).encode()),mutation_control={'pc':'0x0600CD78','replacement':'0x0009','rejected':True},
                    caller_source_sha256=sha(data[CALLER-leaf.BASE:CALLER_END-leaf.BASE]),helper_source_sha256=sha(data[leaf.ENTRY-leaf.BASE:leaf.END-leaf.BASE]),
                    literal_source_sha256=sha(b''.join(data[addr-leaf.BASE:addr-leaf.BASE+4] for addr in sorted(leaf.LITERALS))),
                    probe_sha256=sha(Path(__file__).read_bytes()),interpreter_revision=pinned.INTERPRETER_REVISION,interpreter_sources=pinned.SOURCE_HASHES,
                    contract='Original CDA0 loop calls original CD74 twelve times with caller-saved R4 as the repeated R5 type argument and indices 0..11 in R4. Accepted types 0..3 fill all twelve pointer/type outputs. Types >=4 perform no table data accesses or writes. The constructed caller stack is spilled and restored; services and natural caller inputs are outside this probe.')
            except Exception as e:report['error']={'type':type(e).__name__,'reason':str(e)}
            f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    except OSError as e:print(f'FAIL: fresh report path required: {e}');return 1
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)}));return 0 if report['status']=='success' else 1
if __name__=='__main__':raise SystemExit(main())
