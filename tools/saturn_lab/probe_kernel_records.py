#!/usr/bin/env python3
"""Original kernel record markers/clears and their full18/16-record callers."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
from probe_position_bounds import SP
from probe_split_add import map_inputs

MASK=0xFFFFFFFF
MARK,MARK_ALL,CLEAR,CLEAR_ALL=0x06006B38,0x06006B56,0x0600940A,0x0600942E
RECORDS,SLOTS,COUNT=0x060BC190,0x060CE060,0x060BF4A0
RANGES={MARK:((MARK,0x06006B56),),MARK_ALL:((MARK,0x06006B96),),
        CLEAR:((CLEAR,0x0600942E),),CLEAR_ALL:((CLEAR,0x0600944A),)}
LITERALS={0x06006B98:RECORDS,0x0600945C:SLOTS,0x06009468:COUNT}
NAMES=tuple([f'r{i}' for i in range(16)]+['sr','pr','macl','mach','gbr','vbr','pc'])
MAX_STEPS=1024


def signed(value,bits):
    return (value&((1<<bits)-1))-(1<<bits) if value&(1<<(bits-1)) else value&((1<<bits)-1)


def initial(entry,argument,variant):
    regs={f'r{i}':((0xA5A50000 if variant==0 else 0x5A5A0000)|i*0x101) for i in range(16)}
    regs.update(r4=argument,r15=SP,sr=0x3F3 if variant==0 else 0,
                macl=0x13579BDF if variant==0 else 0x89ABCDEF,
                mach=0x2468ACE0 if variant==0 else 0xFEDCBA98,
                pr=0xFFFFFFF0,gbr=0x00205200+variant*0x100,vbr=0x06005000+variant*0x100,pc=entry)
    return regs


class Model:
    """Expected byte/register effects; no opcode decoder or substituted CPU calls."""
    def __init__(self,before,regions):
        self.before=dict(before);self.reg=dict(before);self.regions=regions
        self.buffers=[bytearray(data) for _,data in regions]
        self.events=[];self.trace=[]

    def step(self,pc,delay=False):self.trace.append([pc,delay])

    def read(self,address,size):
        if address in LITERALS and size==4:value=LITERALS[address]
        else:
            value=None
            for (lo,_),buf in zip(self.regions,self.buffers):
                if lo<=address and address+size<=lo+len(buf):
                    value=int.from_bytes(buf[address-lo:address-lo+size],'big');break
            if value is None:raise ValueError('Expected read outside declared inputs')
        self.events.append([1,address,size,value]);return value

    def write(self,address,size,value):
        value &= (1<<(size*8))-1
        for (lo,_),buf in zip(self.regions,self.buffers):
            if lo<=address and address+size<=lo+len(buf):
                buf[address-lo:address-lo+size]=value.to_bytes(size,'big')
                self.events.append([2,address,size,value]);return
        raise ValueError('Expected write outside declared inputs')

    def push(self,value):
        self.reg['r15']-=4;self.write(self.reg['r15'],4,value)

    def pop(self):
        value=self.read(self.reg['r15'],4);self.reg['r15']+=4;return value

    def t(self,value):self.reg['sr']=(self.reg['sr']&~1)|int(value)

    def marker(self):
        r=self.reg
        self.step(MARK);self.push(r['macl'])
        self.step(MARK+2);r['r3']=88
        self.step(MARK+4);r['r2']=self.read(0x06006B98,4)
        self.step(MARK+6);r['r0']=80
        self.step(MARK+8);r['macl']=(88*signed(r['r4'],16))&MASK
        self.step(MARK+10);r['r4']=r['macl']
        self.step(MARK+12);r['r4']=signed(r['r4'],16)&MASK
        self.step(MARK+14);r['r4']=(r['r4']+RECORDS)&MASK
        self.step(MARK+16);r['r3']=signed(self.read(r['r4']+80,1),8)&MASK
        self.step(MARK+18);self.t(r['r3']==0)
        self.step(MARK+20)
        if r['r3']:
            self.step(MARK+22);r['r3']=1
            self.step(MARK+24);self.write(r['r4'],4,1)
        self.step(MARK+26)
        self.step(MARK+28,True);r['macl']=self.pop()

    def marker_all(self):
        r=self.reg
        for pc,reg in ((0x06006B56,'r14'),(0x06006B58,'r13'),(0x06006B5A,'r12'),(0x06006B5C,'r11')):
            self.step(pc);self.push(r[reg])
        self.step(0x06006B5E);r['r12']=0
        self.step(0x06006B60);r['r13']=self.read(0x06006B98,4)
        self.step(0x06006B62);r['r11']=18
        self.step(0x06006B64);self.push(r['pr'])
        self.step(0x06006B66);r['r14']=0
        self.step(0x06006B68);r['r15']-=4
        self.step(0x06006B6A);self.write(r['r15'],4,r['r4'])
        for i in range(18):
            self.step(0x06006B6C);r['r2']=self.read(r['r15'],4)
            self.step(0x06006B6E);r['r0']=81
            self.step(0x06006B70);r['r3']=signed(self.read(r['r13']+81,1),8)&MASK
            self.step(0x06006B72);r['r3'] &= 255
            self.step(0x06006B74);self.t(r['r2']==r['r3'])
            self.step(0x06006B76)
            if r['sr']&1:
                self.step(0x06006B78);r['r0']=81
                self.step(0x06006B7A);self.write(r['r13']+81,1,0)
                self.step(0x06006B7C);r['pr']=0x06006B80
                self.step(0x06006B7E,True);r['r4']=r['r14']
                self.marker()
            self.step(0x06006B80);r['r14']+=1
            self.step(0x06006B82);self.t(r['r14']>=18)
            self.step(0x06006B84)
            self.step(0x06006B86,True);r['r13']+=88
        self.step(0x06006B88);r['r15']+=4
        for pc,reg in ((0x06006B8A,'pr'),(0x06006B8C,'r11'),(0x06006B8E,'r12'),(0x06006B90,'r13')):
            self.step(pc);r[reg]=self.pop()
        self.step(0x06006B92)
        self.step(0x06006B94,True);r['r14']=self.pop()

    def clear(self):
        r=self.reg
        self.step(CLEAR);self.t(r['r4']==0)
        self.step(CLEAR+2)
        if r['r4']:
            self.step(CLEAR+4);r['r4']=(r['r4']-1)&MASK
            self.step(CLEAR+6);r['r3']=self.read(0x0600945C,4)
            self.step(CLEAR+8);r['r4']=(r['r4']<<2)&MASK
            self.step(CLEAR+10);r['r4']=(r['r4']<<2)&MASK
            self.step(CLEAR+12);r['r4']=(r['r4']+SLOTS)&MASK
            self.step(CLEAR+14);r['r0']=signed(self.read(r['r4']+11,1),8)&MASK
            self.step(CLEAR+16);self.t(r['r0']==0)
            self.step(CLEAR+18)
            if r['r0']:
                self.step(CLEAR+20);r['r0']=0
                self.step(CLEAR+22);self.write(r['r4']+11,1,0)
                self.step(CLEAR+24);r['r4']=self.read(0x06009468,4)
                self.step(CLEAR+26);r['r2']=signed(self.read(r['r4'],1),8)&MASK
                self.step(CLEAR+28);r['r2']=(r['r2']-1)&MASK
                self.step(CLEAR+30);self.write(r['r4'],1,r['r2'])
        self.step(CLEAR+32)
        self.step(CLEAR+34,True)

    def clear_all(self):
        r=self.reg
        self.step(0x0600942E);self.push(r['r14'])
        self.step(0x06009430);self.push(r['r13'])
        self.step(0x06009432);r['r14']=1
        self.step(0x06009434);self.push(r['pr'])
        self.step(0x06009436);r['r13']=16
        for i in range(1,17):
            self.step(0x06009438);r['pr']=0x0600943C
            self.step(0x0600943A,True);r['r4']=r['r14']
            self.clear()
            self.step(0x0600943C);r['r14']+=1
            self.step(0x0600943E);self.t(r['r14']>16)
            self.step(0x06009440)
        self.step(0x06009442);r['pr']=self.pop()
        self.step(0x06009444);r['r13']=self.pop()
        self.step(0x06009446)
        self.step(0x06009448,True);r['r14']=self.pop()


def contract(case):
    kind,a,b,c,variant=case
    entry={'mark':MARK,'mark-all':MARK_ALL,'clear':CLEAR,'clear-all':CLEAR_ALL}[kind]
    argument=a if kind in ('mark','mark-all','clear') else 0xDEADBEEF
    before=initial(entry,argument,variant)
    canary=lambda n:bytes((i*37+19+variant*83)&255 for i in range(n))
    regions=[(SP-32,bytes([0xCD])*32)]
    if kind=='mark':
        address=(RECORDS+signed(88*signed(a,16),16))&MASK
        record=bytearray(canary(88));record[80]=b;regions.append((address,bytes(record)))
    elif kind=='mark-all':
        table=bytearray(canary(18*88))
        for i in range(18):
            table[i*88+80]=(0x80 if variant else 1) if c>>i&1 else 0
            table[i*88+81]=((a if b>>i&1 else a+1)&255)
        regions.append((RECORDS,bytes(table)))
    elif kind=='clear':
        if a:
            address=(SLOTS+((a-1)*16))&MASK
            record=bytearray(canary(16));record[11]=b;regions.append((address,bytes(record)))
        regions.append((COUNT,bytes([c])))
    else:
        table=bytearray(canary(16*16))
        for i in range(16):table[i*16+11]=(0xFF if variant else 1) if a>>i&1 else 0
        regions.extend(((SLOTS,bytes(table)),(COUNT,bytes([b]))))
    model=Model(before,regions)
    {'mark':model.marker,'mark-all':model.marker_all,'clear':model.clear,'clear-all':model.clear_all}[kind]()
    model.reg['pc']=0xFFFFFFF0
    return entry,model


def observe(data,emu,entry,regions,before,budget=MAX_STEPS):
    ranges=RANGES[entry]
    if not 0<budget<=MAX_STEPS:raise ValueError('Invalid local instruction budget')
    for lo,buf in regions:
        if not len(buf) or lo<0 or lo+len(buf)>1<<32:raise ValueError('Invalid input region')
        if any(lo<end and start<lo+len(buf) for start,end in ranges):raise ValueError('Input overlaps executed code')
        if any(lo<lit+4 and lit<lo+len(buf) for lit in LITERALS):raise ValueError('Input overlaps original literal')
    class Memory(emu.Memory):
        def __init__(self):super().__init__();self.fetching=False;self.events=[]
        def read(self,address,size):
            if self.fetching:
                if size!=2 or address&1 or not any(lo<=address and address+2<=hi for lo,hi in ranges):
                    raise ValueError('Instruction fetch outside declared original ranges')
            elif not ((address in LITERALS and size==4) or any(lo<=address and address+size<=lo+len(buf) for lo,buf in regions)):
                raise ValueError('Read outside original literals and declared inputs')
            value=super().read(address,size)
            if not self.fetching:self.events.append([1,address,size,value])
            return value
        def write(self,address,size,value):
            if not any(lo<=address and address+size<=lo+len(buf) for lo,buf in regions):
                raise ValueError('Write outside declared controlled RAM/stack')
            super().write(address,size,value);self.events.append([2,address,size,value&((1<<(size*8))-1)])
    memory=Memory();map_inputs(memory,data,regions)
    baseline=[(lo,bytes(buf)) for lo,_,buf in memory.regions]
    class CPU(emu.CPU):
        def __init__(self,mem):super().__init__(mem);self.trace=[]
        def fetch(self,pc):
            memory.fetching=True
            try:return super().fetch(pc)
            finally:memory.fetching=False
        def exec(self,ins,pc,in_slot=False):
            if len(self.trace)>=budget:raise ValueError('Local instruction budget exceeded')
            if not any(lo<=pc<hi for lo,hi in ranges):raise ValueError('Execution outside declared original ranges')
            self.trace.append([pc,bool(in_slot)]);return super().exec(ins,pc,in_slot=in_slot)
    cpu=CPU(memory)
    cpu.r=[before[f'r{i}'] for i in range(16)]
    for name in ('sr','pr','macl','mach','gbr','vbr','pc'):setattr(cpu,name,before[name])
    error=None
    try:cpu.call(entry,max_steps=budget)
    except Exception as fault:error={'type':type(fault).__name__,'reason':str(fault)}
    after={name:(cpu.r[int(name[1:])] if name.startswith('r') and name[1:].isdigit() else getattr(cpu,name)) for name in NAMES}
    mapped={lo:bytes(buf) for lo,_,buf in memory.regions}
    controlled={lo for lo,_ in regions}
    unchanged=all(mapped[lo]==buf for lo,buf in baseline if lo not in controlled)
    return {'status':'returned' if error is None and cpu.pc==emu.RETURN_SENTINEL else 'failed',
            'error':error,'registers':after,'trace':cpu.trace,'events':memory.events,'steps':cpu.steps,
            'regions_after':[mapped[lo] for lo,_ in regions],'original_unaffected_bytes_equal':unchanged}


def run_case(data,emu,case):
    entry,expected=contract(case)
    actual=observe(data,emu,entry,expected.regions,expected.before)
    if actual['status']!='returned':raise ValueError('Original execution failed: '+str(actual['error']))
    if actual['registers']!=expected.reg:raise ValueError('Register/PC/SR/MACL/PR result differs')
    if actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):raise ValueError('Executed PC/delay path differs')
    if actual['events']!=expected.events:raise ValueError('Exact read/write transactions differ')
    if actual['regions_after']!=[bytes(v) for v in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        raise ValueError('Controlled outputs/canaries or original bytes differ')
    return {'case':list(case),'entry':entry,'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],'all_visible_registers_checked':True,
            'unaffected_bytes_equal':True,'return_sentinel_reached':True}


def owned_smoke(emu):
    """Actual pinned CPU/adapter guards using only freshly authored instructions."""
    data=bytearray(pinned.SIZE);offset=MARK-pinned.BASE
    data[offset:offset+6]=bytes.fromhex('e007 000b 0009')  # owned MOV7,R0; RTS; NOP
    before=initial(MARK,0,0);regions=[(SP-32,bytes([0xCD])*32)]
    good=observe(data,emu,MARK,regions,before)
    expected={**before,'r0':7,'pc':0xFFFFFFF0}
    if (good['status']!='returned' or good['registers']!=expected or good['events'] or
            good['trace']!=[[MARK,False],[MARK+2,False],[MARK+4,True]] or
            good['regions_after']!=[regions[0][1]] or not good['original_unaffected_bytes_equal']):
        raise ValueError('Owned CPU/adapter positive smoke failed')
    controls={}
    for name,words,target,budget,reason in (
            ('short_loop','affe 0009',0x00204000,8,'Local instruction budget exceeded'),
            ('full_loop','affe 0009',0x00204000,MAX_STEPS,'Local instruction budget exceeded'),
            ('unmapped_read','6012',0x00204000,8,'Read outside original literals and declared inputs'),
            ('unmapped_write','2102',0x00204000,8,'Write outside declared controlled RAM/stack'),
            ('code_write','2102',MARK,8,'Write outside declared controlled RAM/stack'),
            ('code_as_data','6012',MARK,8,'Read outside original literals and declared inputs'),
            ('cache_alias_read','6012',MARK|0x20000000,8,'Read outside original literals and declared inputs')):
        changed=bytearray(data);words=bytes.fromhex(words);changed[offset:offset+len(words)]=words
        actual=observe(changed,emu,MARK,regions,{**before,'r1':target},budget=budget)
        if actual['status']!='failed' or actual['error']['reason']!=reason or not actual['original_unaffected_bytes_equal']:
            raise ValueError('Owned guard failed: '+name)
        if name.endswith('loop') and len(actual['trace'])!=budget:raise ValueError('Owned instruction cap failed')
        controls[name]={'status':actual['status'],'reason':reason,'executed_instructions':len(actual['trace'])}
    literal=bytearray(data);literal[offset:offset+2]=bytes.fromhex('6012')
    literal[0x06006B98-pinned.BASE:0x06006B9C-pinned.BASE]=bytes.fromhex('11223344')
    actual=observe(literal,emu,MARK,regions,{**before,'r1':0x06006B98})
    if (actual['status']!='returned' or actual['registers']['r0']!=0x11223344 or
            actual['events']!=[[1,0x06006B98,4,0x11223344]]):raise ValueError('Owned literal read failed')
    writable=bytearray(data);writable[offset:offset+2]=bytes.fromhex('2102')
    destination=0x00204000
    actual=observe(writable,emu,MARK,regions+[(destination,bytes([0xCD])*4)],{**before,'r1':destination})
    if (actual['status']!='returned' or actual['events']!=[[2,destination,4,before['r0']]] or
            actual['regions_after'][-1]!=before['r0'].to_bytes(4,'big') or
            not actual['original_unaffected_bytes_equal']):raise ValueError('Owned controlled write failed')
    if observe(data,emu,MARK,regions,before)!=good:raise ValueError('Owned recovery after failures differs')
    return {'original_game_bytes_executed':False,'positive_instructions':3,'owned_literal_read':True,
            'owned_controlled_write':True,
            'failure_controls':controls,'fresh_after_failure':True,'native_cpu_sources_unchanged':True}


def cases():
    rows=set()
    indices=sorted(set(range(18))|{127,255,371,372,373,0x7FFF,0x8000,0xFFFF,0x10000,0xFFFFFFFF,0x80000000})
    for a,b,v in itertools.product((0,17,372,0xFFFF),range(256),range(2)):rows.add(('mark',a,b,0,v))
    for a,b,v in itertools.product(indices,(0,1,127,128,255),range(2)):rows.add(('mark',a,b,0,v))
    all18=(1<<18)-1;even18=sum(1<<i for i in range(0,18,2))
    masks18=(0,all18,even18,all18^even18,*[1<<i for i in range(18)])
    for a,b,c,v in itertools.product((0,1,127,128,255,256,0xFFFFFFFF,0x80000000),masks18,
                                    (0,all18,even18,all18^even18,1,1<<17),range(2)):
        rows.add(('mark-all',a,b,c,v))
    for a,b,c,v in itertools.product((1,16,0x10000000),range(256),(0,255),range(2)):rows.add(('clear',a,b,c,v))
    clear_indices=sorted(set(range(17))|{0x10000000,0x10000001,0x7FFFFFFF,0x80000000,0xFFFFFFFF})
    for a,b,c,v in itertools.product(clear_indices,(0,1,127,128,255),(0,1,127,128,255),range(2)):
        rows.add(('clear',a,b if a else 0,c,v))
    masks16=(0,0xFFFF,0x5555,0xAAAA,*[1<<i for i in range(16)])
    for a,b,v in itertools.product(masks16,range(256),range(2)):rows.add(('clear-all',a,b,0,v))
    return sorted(rows)


def execute(data,emu,kind=None):
    selected=[c for c in cases() if kind is None or c[0]==kind]
    rows=[run_case(data,emu,case) for case in selected]
    controls={}
    controls_selected={kind:[case for case in selected if case[0]==kind][::max(1,sum(c[0]==kind for c in selected)//64)]
                       for kind in ('mark','mark-all','clear','clear-all') if any(c[0]==kind for c in selected)}
    for name,pc,word,kind in (
            ('missing_signed_index_truncation',0x06006B44,0x0009,'mark'),
            ('missing_marker_word_store',0x06006B50,0x0009,'mark'),
            ('missing_MACL_delay_restore',0x06006B54,0x0009,'mark'),
            ('category_sign_not_zero_extended',0x06006B72,0x0009,'mark-all'),
            ('only_seventeen_records',0x06006B62,0xEB11,'mark-all'),
            ('missing_caller_index_delay',0x06006B7E,0x0009,'mark-all'),
            ('missing_slot_flag_clear',0x06009420,0x0009,'clear'),
            ('counter_increment_instead_of_decrement',0x06009426,0x7201,'clear'),
            ('only_fifteen_calls',0x06009436,0xED0F,'clear-all'),
            ('missing_outer_R14_delay_restore',0x06009448,0x0009,'clear-all')):
        if kind not in controls_selected:continue
        changed=bytearray(data);offset=pc-pinned.BASE;changed[offset:offset+2]=word.to_bytes(2,'big')
        rejected=0;reasons=set();chosen=controls_selected[kind]
        for case in chosen:
            try:run_case(changed,emu,case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived every selected control case')
        controls[name]={'pc':pc,'tested':len(chosen),'rejected':rejected,'reasons':sorted(reasons),
                        'mutated_kernel_sha256':pinned.digest(changed)}
    return {'cases':len(rows),'cases_by_kind':{kind:sum(r['case'][0]==kind for r in rows) for kind in controls_selected},
            'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(data[lo-pinned.BASE:hi-pinned.BASE])
                            for lo,hi in ((MARK,0x06006B56),(MARK_ALL,0x06006B96),(CLEAR,0x0600942E),(CLEAR_ALL,0x0600944A))}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True)
    parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--kind',choices=('mark','mark-all','clear','clear-all'))
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-sh2-kernel-records.v1','experiment':'EXP-SAT-CODE-016','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,
            'interpreter_sources':pinned.SOURCE_HASHES,'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'adapter_sha256':pinned.digest(Path(pinned.__file__).read_bytes()),
            'mapping_adapter_sha256':pinned.digest(Path(__file__).with_name('probe_split_add.py').read_bytes()),
            'position_adapter_sha256':pinned.digest(Path(__file__).with_name('probe_position_bounds.py').read_bytes()),
            'selection':args.kind or 'all','max_steps_per_call':MAX_STEPS,
            'limitations':['Constructed records/global byte/registers; no natural task/scheduler/gameplay role',
                           'Complete declared18/16-record callers, not all machine states or all kernel code',
                           'Pinned CPU-only interpreter, no hardware/device/timing/independent-engine validation',
                           'Whole-program/function/dynamic-target denominators remain unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            data=pinned.kernel_bytes(args.kernel);emu=pinned.interpreter(args.saturn_recomp)
            phase='owned_smoke';report['owned_smoke']=owned_smoke(emu)
            phase='original_execution';report.update(execute(data,emu,args.kind),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, bounded execution or contract failed'}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'cases_by_kind':report.get('cases_by_kind',{})}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
