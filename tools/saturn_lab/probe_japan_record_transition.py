#!/usr/bin/env python3
"""Execute the original Japanese KRNL ADB0 record transition in bounded CPU isolation."""
from __future__ import annotations
import argparse, hashlib, itertools, json, os
from pathlib import Path
import probe_kernel as pinned
import probe_kernel_records as common

BASE=0x0600A000
ENTRY,END,LITERAL,TABLE=0x0600ADB0,0x0600ADE6,0x0600AF04,0x060BCEEC
SIZE=786432
KERNEL_SHA256='23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb'
SP=0x06002000
MAX_STEPS=64
MASK=0xFFFFFFFF

def digest(data): return hashlib.sha256(data).hexdigest()

def address(index): return (TABLE+common.signed((88*common.signed(index,16))&0xFFFFFFFF,16))&MASK

def observe(data,emu,index,flag,category):
    table=address(index); record=bytearray((i*37+index*11+17)&255 for i in range(88)); record[80]=flag; record[81]=category
    stack=bytearray([0xCD]*4)
    events=[]; trace=[]
    class Memory(emu.Memory):
        def __init__(self): super().__init__(); self.fetching=False
        def read(self,a,n):
            if self.fetching:
                if n!=2 or not (ENTRY<=a and a+2<=END): raise ValueError('Instruction fetch outside original code range')
                return super().read(a,n)
            value=super().read(a,n)
            if a==LITERAL and n==4: events.append([1,a,n,value])
            elif a==table+80 and n==1: events.append([1,a,n,value])
            elif a==SP-4 and n==4: events.append([1,a,n,value])
            else: raise ValueError(f'Unexpected data read 0x{a:08x}/{n}')
            return value
        def write(self,a,n,v):
            if (a,n) not in ((SP-4,4),(table+80,1),(table+81,1)): raise ValueError(f'Unexpected write 0x{a:08x}/{n}')
            events.append([2,a,n,v&((1<<(8*n))-1)]); return super().write(a,n,v)
    memory=Memory()
    memory.add(ENTRY,END-ENTRY,data[ENTRY-BASE:END-BASE])
    memory.add(LITERAL,4,data[LITERAL-BASE:LITERAL-BASE+4])
    stack_buffer=memory.add(SP-4,4,stack)
    record_buffer=memory.add(table,88,record)
    class CPU(emu.CPU):
        def fetch(self,pc):
            memory.fetching=True
            try: return super().fetch(pc)
            finally: memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if len(trace)>=MAX_STEPS or not ENTRY<=pc<END: raise ValueError('Instruction bound/range exceeded')
            trace.append([pc,bool(in_slot)]); return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory); cpu.r=[(0xA5A50000|i*0x101) for i in range(16)]
    cpu.r[4]=index&MASK; cpu.r[15]=SP; cpu.sr=0x3F2; cpu.macl=0x13579BDF; cpu.mach=0x2468ACE0
    cpu.pr=emu.RETURN_SENTINEL
    before=list(cpu.r); beforemacl=cpu.macl
    cpu.call(ENTRY,max_steps=MAX_STEPS)
    want_success=common.signed(index,32)<18 and flag==1
    expected=bytearray(record)
    if want_success: expected[80]=2; expected[81]=0
    if cpu.pc!=emu.RETURN_SENTINEL or cpu.r[0]!=(0 if want_success else MASK): raise ValueError('Return contract differs')
    if cpu.macl!=beforemacl or cpu.r[15]!=SP: raise ValueError('MACL/stack restoration differs')
    if any(cpu.r[i]!=before[i] for i in (5,6,7,8,9,10,11,12,13,14,15)):
        raise ValueError('Unexpected callee-saved register clobber')
    after=bytes(record_buffer)
    if after!=bytes(expected): raise ValueError('Record bytes differ')
    expected_events=[[2,SP-4,4,beforemacl]]
    if common.signed(index,32)<18:
        expected_events.extend(([1,LITERAL,4,TABLE],[1,table+80,1,flag]))
        if flag==1: expected_events.extend(([2,table+80,1,2],[2,table+81,1,0]))
    expected_events.append([1,SP-4,4,beforemacl])
    if events!=expected_events: raise ValueError('Exact original memory transaction sequence differs')
    if bytes(stack_buffer)!=beforemacl.to_bytes(4,'big'): raise ValueError('Exact MACL spill slot differs')
    return {'index':index,'flag':flag,'category':category,'return':cpu.r[0],'steps':cpu.steps,'trace':trace,
            'events':events,'record_sha256':digest(after),'macl_spill_sha256':digest(bytes(stack_buffer)),
            'macl_restored':True,'stack_restored':True}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--kernel',type=Path,required=True); p.add_argument('--saturn-recomp',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args(argv)
    report={'schema':'neptune.original-japan-sh2-record-transition.v1','status':'failure','release':'Japan T-14302G V1.000','module':'KRNL','cpu':'SH-2','load_address':hex(BASE),'entry':hex(ENTRY),'code_range':[hex(ENTRY),hex(END)],'literal_range':[hex(LITERAL),hex(LITERAL+4)],'table':hex(TABLE),'max_instructions_per_call':MAX_STEPS,'original_game_bytes_executed':False,'kernel_sha256':KERNEL_SHA256,'limitations':['Constructed table, registers and stack; pinned SH-2 interpreter only','No natural caller, device, timing, gameplay, or independent-emulator validation']}
    try: fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError: print('FAIL: fresh report path required'); return 1
    with os.fdopen(fd,'w') as f:
        try:
            data=pinned.read_bounded(a.kernel,SIZE)
            if len(data)!=SIZE or digest(data)!=KERNEL_SHA256: raise ValueError('Japan kernel identity mismatch')
            emu=pinned.interpreter(a.saturn_recomp)
            cases=list(itertools.product(range(18),(0,1,2,3,255),(0,1,127,255)))
            rows=[observe(data,emu,i,flag,cat) for i,flag,cat in cases]
            controls={}
            for name,pc,word in [('wrong_upper_bound',ENTRY+6,0x8900),('wrong_active_value',ENTRY+26,0x8800),('wrong_latched_value',ENTRY+32,0xE203)]:
                changed=bytearray(data); changed[pc-BASE:pc-BASE+2]=word.to_bytes(2,'big')
                rejects=0
                for i,flag,cat in ((0,1,7),(17,1,9),(0,2,11),(18,1,13)):
                    try: observe(bytes(changed),emu,i,flag,cat)
                    except Exception: rejects+=1
                if not rejects: raise ValueError('Mutation survived: '+name)
                controls[name]={'pc':hex(pc),'rejected_cases':rejects,'mutated_kernel_sha256':digest(changed)}
            report.update(status='success',original_game_bytes_executed=True,cases=len(rows),results=rows,
                          results_sha256=digest(json.dumps(rows,sort_keys=True).encode()),mutation_controls=controls,
                          source_kernel_sha256=digest(data),interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          probe_sha256=digest(Path(__file__).read_bytes()),
                          code_sha256=digest(data[ENTRY-BASE:END-BASE]),
                          literal_sha256=digest(data[LITERAL-BASE:LITERAL-BASE+4]))
        except Exception as e: report['error']={'type':type(e).__name__,'reason':str(e)}
        f.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'report':str(a.report)})); return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
