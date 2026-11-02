#!/usr/bin/env python3
"""Original6BE4 full record selection, real delta polls and bounded waits."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
import probe_kernel_records as records
import probe_record_delta as delta
import probe_context_handoff as handoff
import sh2_selection_profile as profile

ENTRY,END=0x06006BE4,0x06006D36
TABLE,ROOT,PREVIOUS=records.RECORDS,handoff.ROOT,delta.PREVIOUS
INDEX,CURRENT,SAMPLE,LIVE_A,LIVE_B=0x06006018,0x06006020,delta.SAMPLE,0x06006040,0x06006044
ARRAY_A,ARRAY_B=0x060B2D2C,0x060B2D34
RAW_INDEX,RAW_CURRENT,RAW_SAMPLE,RAW_A,RAW_B=(a|0x20000000 for a in (INDEX,CURRENT,SAMPLE,LIVE_A,LIVE_B))
OUTBOUND,RETURN=handoff.OUTBOUND,handoff.RETURN
MASK=0xFFFFFFFF
LITERALS={**delta.LITERALS,0x06006E0C:ROOT,0x06006E10:handoff.SAVE,0x06006E14:ARRAY_A,
          0x06006E18:RAW_A,0x06006E1C:ARRAY_B,0x06006E20:RAW_B,0x06006E24:RAW_INDEX,
          0x06006E28:RAW_CURRENT,0x06006E2C:handoff.RESTORE}
RANGES=((handoff.SAVE,handoff.CONTEXT_END),(delta.ENTRY,END))


def fixture(case):
    family,cpu,previous_index,target,flag,word,sampled,previous,argument,variant=case
    before=records.initial(ENTRY,0xDEADBEEF,variant)
    before['vbr']=0x06005000|(cpu<<10)|(variant*0x155)
    table=bytearray((i*37+19+variant*83)&255 for i in range(18*88))
    for i in range(18):
        base=88*i
        table[base:base+4]=(0).to_bytes(4,'big');table[base+80]=0
        values={4:argument,12:OUTBOUND,16:argument,20:0x11000000+i,28:0x22000000+i,
                32:0x33000000+i,36:0x44000000+i,40:0x55000000+i,44:0x66000000+i,
                48:0x77000000+i,52:0x88000000+i,56:0x99000000+i,60:0xAA000000+i,
                64:0x060E0000+i*0x100,68:OUTBOUND,72:0xBB000000+i,76:0xCC000000+i}
        for offset,value in values.items():table[base+offset:base+offset+4]=value.to_bytes(4,'big')
    if family=='waits':
        # Four stable no-eligible layouts, with equal or changing samples.
        for i in range(18):
            table[i*88:i*88+4]=word.to_bytes(4,'big');table[i*88+80]=flag
    else:
        table[target*88:target*88+4]=word.to_bytes(4,'big');table[target*88+80]=flag
        if flag==2:table[target*88+68:target*88+72]=(0xDEAD0000).to_bytes(4,'big')
    regions=[(records.SP-64,bytes([0xCD])*64,True)]
    for slot in range(2):
        selected=slot==cpu
        regions.extend(((INDEX+4*slot,(previous_index if selected else 0xCAFE0011).to_bytes(4,'big'),selected),
                        (CURRENT+4*slot,(0xBAD00000+slot).to_bytes(4,'big'),selected),
                        (ARRAY_B+4*slot,(0xB0B00000+slot+variant*0x100).to_bytes(4,'big'),selected)))
    regions.extend(((SAMPLE,sampled.to_bytes(4,'big'),False),(PREVIOUS,previous.to_bytes(4,'big'),True),
                    (LIVE_A,bytes.fromhex('abababab'),True),(LIVE_B,bytes.fromhex('cdcdcdcd'),True),
                    (ARRAY_A,b''.join((0xA0A00000+i+variant*0x100).to_bytes(4,'big') for i in range(2)),False),
                    (ROOT,bytes([0xCE])*48,True),(TABLE,bytes(table),True)))
    return before,regions


class ModelLimit(Exception):pass


class Model(handoff.Model):
    def __init__(self,before,regions,budget):
        super().__init__(before,[(lo,buf) for lo,buf,_ in regions]);self.budget=budget;self.wait=False

    def step(self,pc,delay=False):
        # Match the CPU's fault PC if the cap lands in an actual delay slot.
        if not delay:self.reg['pc']=pc
        if len(self.trace)>=self.budget:raise ModelLimit()
        self.trace.append([pc,bool(delay)])

    def read(self,address,size):
        if address in LITERALS and size==4:value=LITERALS[address]
        else:
            physical=address&0x1FFFFFFF if address>>28==2 else address
            value=None
            for (lo,_),buf in zip(self.regions,self.buffers):
                if lo<=physical and physical+size<=lo+len(buf):
                    value=int.from_bytes(buf[physical-lo:physical-lo+size],'big');break
            if value is None:raise ValueError('Expected read outside selection inputs')
        self.events.append([1,address,size,value]);return value

    def poll(self):
        delta.Model.delta(self);self.reg['pc']=self.reg['pr']

    def selection(self):
        r=self.reg
        for pc,name in ((0x06006BE4,'r14'),(0x06006BE6,'r13'),(0x06006BE8,'r12'),(0x06006BEA,'r11'),
                        (0x06006BEC,'r10'),(0x06006BEE,'r9'),(0x06006BF0,'r8'),(0x06006BF2,'pr'),(0x06006BF4,'macl')):
            self.step(pc);self.push(r[name])
        self.step(0x06006BF6);r['r15']-=8
        self.step(0x06006BF8);r['r4']=self.read(0x06006E0C,4)
        self.step(0x06006BFA);r['r3']=self.read(0x06006E10,4)
        self.step(0x06006BFC);r['pr']=0x06006C00
        self.step(0x06006BFE,True);self.save()
        self.step(0x06006C00);r['r0']=self.read(0x06006E14,4)
        self.step(0x06006C02);r['r2']=r['vbr']
        self.step(0x06006C04);r['r1']=self.read(0x06006E18,4)
        self.step(0x06006C06);r['r11']=1
        self.step(0x06006C08);r['r4']=self.read(0x06006E24,4)
        self.step(0x06006C0A);r['r2'] >>= 8
        self.step(0x06006C0C);r['r2'] >>= 2
        self.step(0x06006C0E);r['r2'] &= r['r11']
        self.step(0x06006C10);r['r2'] <<= 2
        self.step(0x06006C12);r['r3']=self.read(r['r0']+r['r2'],4)
        self.step(0x06006C14);r['r0']=self.read(0x06006E1C,4)
        self.step(0x06006C16);r['r2']=r['vbr']
        self.step(0x06006C18);self.write(r['r1'],4,r['r3'])
        self.step(0x06006C1A);r['r2'] >>= 8
        self.step(0x06006C1C);r['r2'] >>= 2
        self.step(0x06006C1E);r['r2'] &= r['r11']
        self.step(0x06006C20);r['r2'] <<= 2
        self.step(0x06006C22);r['r1']=self.read(r['r0']+r['r2'],4)
        self.step(0x06006C24);r['r2']=self.read(0x06006E20,4)
        self.step(0x06006C26);r['r0']=r['vbr']
        self.step(0x06006C28);self.write(r['r2'],4,r['r1'])
        self.step(0x06006C2A);r['r0'] >>= 8
        self.step(0x06006C2C);self.write(r['r15']+4,4,r['r11'])
        self.step(0x06006C2E);r['r0'] >>= 2
        self.step(0x06006C30);r['r0'] &= r['r11']
        self.step(0x06006C32);r['r0'] <<= 2
        self.step(0x06006C34);r['r0']=self.read(r['r0']+r['r4'],4)
        self.step(0x06006C36);self.t(r['r0']==MASK)
        self.step(0x06006C38)
        self.step(0x06006C3A,True);r['r5']=MASK
        if r['sr']&1:
            self.step(0x06006C3C)
            self.step(0x06006C3E,True);r['r10']=r['r5']
        else:
            self.step(0x06006C40);r['r0']=r['vbr']
            self.step(0x06006C42);r['r0'] >>= 8
            self.step(0x06006C44);r['r0'] >>= 2
            self.step(0x06006C46);r['r0'] &= r['r11']
            self.step(0x06006C48);r['r0'] <<= 2
            self.step(0x06006C4A);r['r10']=self.read(r['r0']+r['r4'],4)
        self.step(0x06006C4C);r['r12']=r['r5']
        self.step(0x06006C4E);r['r13']=r['r10']
        self.step(0x06006C50);r['r13']=(r['r13']+1)&MASK
        self.step(0x06006C52);r['r0']=r['r13']
        self.step(0x06006C54);self.t(r['r0']==18)
        self.step(0x06006C56)
        self.step(0x06006C58,True);r['r9']=0
        if r['sr']&1:self.step(0x06006C5A);r['r13']=0
        self.step(0x06006C5C);r['r8']=self.read(0x06006E08,4)
        self.step(0x06006C5E);r['r2']=r['r8']
        self.step(0x06006C60);self.write(r['r15'],4,r['r2'])
        self.step(0x06006C62);self.step(0x06006C64,True)
        self.step(0x06006CCA);r['r0']=r['r12']
        self.step(0x06006CCC);self.t(r['r0']==MASK)
        self.step(0x06006CCE)
        while r['r12']==MASK:
            self.step(0x06006C66);r['r14']=88
            self.step(0x06006C68);r['macl']=(88*records.signed(r['r13'],16))&MASK
            self.step(0x06006C6A);r['r14']=r['macl']
            self.step(0x06006C6C);r['r14']=records.signed(r['r14'],16)&MASK
            self.step(0x06006C6E);r['r14']=(r['r14']+r['r8'])&MASK
            while True:
                if self.examine():break
                self.step(0x06006CAC);r['r13']=(r['r13']+1)&MASK
                self.step(0x06006CAE);r['r0']=r['r13']
                self.step(0x06006CB0);self.t(r['r0']==18)
                self.step(0x06006CB2)
                self.step(0x06006CB4,True);r['r14']=(r['r14']+88)&MASK
                if r['sr']&1:
                    self.step(0x06006CB6);r['r14']=self.read(r['r15'],4)
                    self.step(0x06006CB8);r['pr']=0x06006CBC
                    self.step(0x06006CBA,True);r['r13']=r['r9'];self.poll()
                self.step(0x06006CBC);self.t(r['r13']==r['r10'])
                self.step(0x06006CBE)
                if r['sr']&1:break
            self.step(0x06006CC0);r['r0']=r['r12']
            self.step(0x06006CC2);self.t(r['r0']==MASK)
            self.step(0x06006CC4)
            if r['sr']&1:
                self.step(0x06006CC6);r['pr']=0x06006CCA
                self.step(0x06006CC8,True);self.poll()
            self.step(0x06006CCA);r['r0']=r['r12']
            self.step(0x06006CCC);self.t(r['r0']==MASK)
            self.step(0x06006CCE)
        self.transfer()

    def examine(self):
        r=self.reg
        self.step(0x06006C70);r['r0']=self.read(r['r14'],4)
        self.step(0x06006C72);self.t(r['r0']==1)
        self.step(0x06006C74)
        eligible=False
        if r['sr']&1:
            self.step(0x06006C76);r['r0']=80
            self.step(0x06006C78);r['r0']=records.signed(self.read(r['r14']+80,1),8)&MASK
            self.step(0x06006C7A);r['r0'] &= 255
            self.step(0x06006C7C);self.t(r['r0']==1)
            self.step(0x06006C7E);eligible=bool(r['sr']&1)
            if not eligible:
                self.step(0x06006C80);r['r0']=80
                self.step(0x06006C82);r['r0']=records.signed(self.read(r['r14']+80,1),8)&MASK
                self.step(0x06006C84);r['r0'] &= 255
                self.step(0x06006C86);self.t(r['r0']==3)
                self.step(0x06006C88);eligible=bool(r['sr']&1)
        if not eligible:
            self.step(0x06006C8A);r['r0']=80
            self.step(0x06006C8C);r['r0']=records.signed(self.read(r['r14']+80,1),8)&MASK
            self.step(0x06006C8E);r['r0'] &= 255
            self.step(0x06006C90);self.t(r['r0']==2)
            self.step(0x06006C92);eligible=bool(r['sr']&1)
            if eligible:
                self.step(0x06006C94);r['r2']=self.read(r['r14']+12,4)
                self.step(0x06006C96);r['r0']=68
                self.step(0x06006C98);self.write(r['r14']+68,4,r['r2'])
                self.step(0x06006C9A);r['r0']=80
                self.step(0x06006C9C);r['r3']=self.read(r['r14']+16,4)
                self.step(0x06006C9E);self.write(r['r14']+32,4,r['r3'])
                self.step(0x06006CA0);r['r2']=self.read(r['r14']+16,4)
                self.step(0x06006CA2);r['r3']=3
                self.step(0x06006CA4);self.write(r['r15']+4,4,r['r2'])
                self.step(0x06006CA6);self.write(r['r14']+80,1,r['r3'])
        if eligible:
            self.step(0x06006CA8)
            self.step(0x06006CAA,True);r['r12']=r['r13']
        return eligible

    def transfer(self):
        r=self.reg
        self.step(0x06006CD0);r['r0']=self.read(0x06006E24,4)
        self.step(0x06006CD2);r['r2']=r['vbr']
        self.step(0x06006CD4);r['r1']=self.read(0x06006E20,4)
        self.step(0x06006CD6);r['r3']=r['vbr']
        self.step(0x06006CD8);r['r2'] >>= 8
        self.step(0x06006CDA);r['r2'] >>= 2
        self.step(0x06006CDC);r['r2'] &= r['r11']
        self.step(0x06006CDE);r['r2'] <<= 2
        self.step(0x06006CE0);self.write(r['r0']+r['r2'],4,r['r12'])
        self.step(0x06006CE2);r['r3'] >>= 8
        self.step(0x06006CE4);r['r0']=self.read(0x06006E28,4)
        self.step(0x06006CE6);r['r14']=88
        self.step(0x06006CE8);r['macl']=(88*records.signed(r['r12'],16))&MASK
        self.step(0x06006CEA);r['r3'] >>= 2
        self.step(0x06006CEC);r['r3'] &= r['r11']
        self.step(0x06006CEE);r['r3'] <<= 2
        self.step(0x06006CF0);r['r14']=r['macl']
        self.step(0x06006CF2);r['r14']=records.signed(r['r14'],16)&MASK
        self.step(0x06006CF4);r['r14']=(r['r14']+r['r8'])&MASK
        self.step(0x06006CF6);self.write(r['r0']+r['r3'],4,r['r14'])
        self.step(0x06006CF8);r['r0']=self.read(0x06006E1C,4)
        self.step(0x06006CFA);r['r3']=r['vbr']
        self.step(0x06006CFC);r['r2']=self.read(r['r1'],4)
        self.step(0x06006CFE);r['r3'] >>= 8
        self.step(0x06006D00);r['r3'] >>= 2
        self.step(0x06006D02);r['r3'] &= r['r11']
        self.step(0x06006D04);r['r3'] <<= 2
        self.step(0x06006D06);self.write(r['r0']+r['r3'],4,r['r2'])
        self.step(0x06006D08);r['r3']=self.read(r['r14']+20,4)
        self.step(0x06006D0A);r['r2']=self.read(0x06006E18,4)
        self.step(0x06006D0C);self.write(r['r2'],4,r['r3'])
        self.step(0x06006D0E);r['r1']=self.read(r['r14']+28,4)
        self.step(0x06006D10);r['r3']=self.read(0x06006E20,4)
        self.step(0x06006D12);r['r4']=r['r14']
        self.step(0x06006D14);self.write(r['r3'],4,r['r1'])
        self.step(0x06006D16);r['r4']+=32
        self.step(0x06006D18);r['r0']=self.read(r['r14']+4,4)
        self.step(0x06006D1A);self.write(r['r14'],4,r['r0'])
        self.step(0x06006D1C);r['r5']=self.read(r['r15']+4,4)
        self.step(0x06006D1E);r['r15']+=8
        self.step(0x06006D20);r['r1']=self.read(0x06006E2C,4)
        for pc,name in ((0x06006D22,'macl'),(0x06006D24,'pr'),(0x06006D26,'r8'),(0x06006D28,'r9'),
                        (0x06006D2A,'r10'),(0x06006D2C,'r11'),(0x06006D2E,'r12'),(0x06006D30,'r13')):
            self.step(pc);r[name]=self.pop()
        self.step(0x06006D32)
        self.step(0x06006D34,True);r['r14']=self.pop()
        self.restore()


def expected(case,budget=profile.MAX_STEPS):
    before,regions=fixture(case);model=Model(before,regions,budget)
    try:model.selection()
    except ModelLimit:model.wait=True
    return model,regions


def scalar(case):
    """Independent record-level search, no opcodes, PCs or register-effect model."""
    before,regions=fixture(case);table=bytearray(regions[-1][1]);previous_index=case[2]
    index=0 if previous_index==MASK else (previous_index+1)%18
    sampled,previous=case[6:8];polls=0
    def poll():
        nonlocal previous,polls
        polls+=1
        if sampled!=previous:
            difference=(sampled-previous)&MASK
            for slot in range(18):
                offset=88*slot;old=int.from_bytes(table[offset:offset+4],'big')
                if table[offset+80] and old>1:
                    table[offset:offset+4]=max(1,old-difference).to_bytes(4,'big')
            previous=sampled
    # One change can make a record eligible; after two complete scans no new
    # sample can arrive in these immutable inputs, so any further wait is stable.
    for _ in range(37):
        offset=88*index;word=int.from_bytes(table[offset:offset+4],'big');flag=table[offset+80]
        if flag==2 or word==1 and flag in (1,3):
            argument=1
            if flag==2:
                table[offset+68:offset+72]=table[offset+12:offset+16]
                table[offset+32:offset+36]=table[offset+16:offset+20]
                argument=int.from_bytes(table[offset+16:offset+20],'big');table[offset+80]=3
            table[offset:offset+4]=table[offset+4:offset+8]
            return {'selected':index,'table':bytes(table),'previous':previous,'argument':argument,'polls':polls}
        index+=1
        if index==18:index=0;poll()
        if index==previous_index:poll()
    return {'selected':None,'table':bytes(table),'previous':previous,'argument':None,'polls':polls}


def observe(data,emu,case,regions,before,budget=profile.MAX_STEPS):
    cpu=case[1]
    aliases=((RAW_INDEX+4*cpu,INDEX+4*cpu,4,True),(RAW_CURRENT+4*cpu,CURRENT+4*cpu,4,True),
             (RAW_SAMPLE,SAMPLE,4,False),(RAW_A,LIVE_A,4,True),(RAW_B,LIVE_B,4,True))
    return profile.observe(data,emu,ENTRY,regions,before,ranges=RANGES,literals=LITERALS,aliases=aliases,
                           terminals={RETURN:'returned',OUTBOUND:'handoff'},budget=budget)


class CaseFailure(ValueError):
    def __init__(self,reason,case,actual):
        super().__init__(reason)
        self.evidence={'case':list(case),'actual':{k:v for k,v in actual.items() if k!='regions_after'},
                       'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']]}


def run_case(data,emu,case,budget=profile.MAX_STEPS):
    model,regions=expected(case,budget);actual=observe(data,emu,case,regions,model.before,budget);reason=None
    if model.wait:
        if actual['status']!='failed' or actual['error']!={'type':'ValueError','reason':'Handoff instruction budget exceeded'}:
            reason='Bounded incomplete wait/short guard boundary differs'
        elif actual['steps']!=len(model.trace)+1:reason='Wait attempted/executed instruction counts differ'
    elif actual['status']!='handoff':reason='Original execution failed before task handoff: '+str(actual['error'])
    elif actual['steps']!=len(model.trace):reason='Handoff instruction count differs'
    if reason is None:
        if actual['registers']!=model.reg:reason='Register/PC/SR/PR/MAC result differs'
        elif actual['trace']!=model.trace:reason='Executed PC/delay path differs'
        elif actual['events']!=model.events:reason='Exact read/write transactions differ'
        elif actual['regions_after']!=[bytes(buf) for buf in model.buffers] or not actual['original_unaffected_bytes_equal']:
            reason='Controlled outputs/canaries or original bytes differ'
    if reason:raise CaseFailure(reason,case,actual)
    logical=scalar(case)
    if not model.wait:
        physical=dict((lo,buf) for (lo,_,_),buf in zip(regions,actual['regions_after']))
        if (logical['selected'] is None or physical[TABLE]!=logical['table']
            or int.from_bytes(physical[PREVIOUS],'big')!=logical['previous']
            or actual['registers']['r0']!=logical['argument']
            or int.from_bytes(physical[INDEX+4*case[1]],'big')!=logical['selected']):
            raise CaseFailure('Independent scalar selection/output differs',case,actual)
    root=actual['regions_after'][-2]
    outcome=('bounded_incomplete_wait' if logical['selected'] is None else 'incomplete_short_guard') if model.wait else 'selected_task_handoff'
    return {'case':list(case),'actual_status':actual['status'],'actual_error':actual['error'],
            'outcome':outcome,
            'selected_record':None if model.wait else logical['selected'],
            'instructions_executed':len(actual['trace']),'cpu_attempted_steps':actual['steps'],
            'after_registers':actual['registers'],'trace':actual['trace'],'data_events':actual['events'],
            'actual_root_context_hex':root.hex(),'actual_root_context_sha256':pinned.digest(root),
            'root_resume_PR':int.from_bytes(root[36:40],'big'),
            'poll_calls':sum(pc==delta.ENTRY for pc,_ in actual['trace']),
            'records_examined':sum(pc==0x06006C70 for pc,_ in actual['trace']),
            'all_visible_registers_checked':True,'unaffected_bytes_equal':True,
            'normal_function_return_completed':False}


def cases():
    rows=[]
    for cpu,previous,target,flag,variant in itertools.product(range(2),(MASK,*range(18)),range(18),(1,2,3),range(2)):
        rows.append((f'positions{cpu}',cpu,previous,target,flag,1,0,0,7,variant))
    for cpu,flag,word,argument,variant in itertools.product(range(2),(1,2,3),(0,1,2,MASK),delta.WORDS,range(2)):
        rows.append(('fields',cpu,MASK,0,flag,word,0,0,argument,variant))
    for cpu,flag,variant in itertools.product(range(2),range(256),range(2)):
        rows.append(('flag-bytes',cpu,16,17,flag,1,0,0,1,variant))
    for cpu,previous,target,flag,word,difference,variant in itertools.product(range(2),(MASK,0,17),(0,1,17),(1,3),
                          (2,3,0x80000000,MASK),(0,1,2,0x7FFFFFFF,0x80000000,MASK),range(2)):
        past=0 if variant==0 else MASK
        rows.append((f'polls{cpu}',cpu,previous,target,flag,word,(past+difference)&MASK,past,1,variant))
    for cpu,previous,layout,variant in itertools.product(range(2),(MASK,*range(18)),range(4),range(2)):
        flag,word,sampled,previous_sample=((0,2,1,0),(1,2,0,0),(3,0,1,0),(255,2,1,0))[layout]
        rows.append(('waits',cpu,previous,0,flag,word,sampled,previous_sample,1,variant))
    return sorted(rows)


def owned_smoke(emu):
    import sh2_handoff_profile as older
    data=bytearray(pinned.SIZE);offset=ENTRY-pinned.BASE
    data[offset:offset+10]=bytes.fromhex('2102 6322 6412 000b 0009')
    positives=[];controls={}
    for cpu in range(2):
        case=(f'positions{cpu}',cpu,MASK,0,1,1,0,0,7,0);before,regions=fixture(case)
        before.update(r0=0x11223344,r1=RAW_CURRENT+4*cpu,r2=CURRENT+4*cpu,pr=OUTBOUND)
        good=observe(data,emu,case,regions,before)
        buffers=[bytes.fromhex('11223344') if i==2+3*cpu else buf for i,(_,buf,_) in enumerate(regions)]
        if (good['status']!='handoff' or good['registers']!={**before,'r3':0x11223344,'r4':0x11223344,'pc':OUTBOUND}
            or good['events']!=[[2,RAW_CURRENT+4*cpu,4,0x11223344],[1,CURRENT+4*cpu,4,0x11223344],
                                [1,RAW_CURRENT+4*cpu,4,0x11223344]] or good['regions_after']!=buffers
            or not good['original_unaffected_bytes_equal']):raise ValueError('Owned selection alias coherence failed')
        positives.append({'slot':cpu,'instructions':good['steps'],'coherent_alias_write_reads':True})
        for name,words,address,pr,budget,reason in (
            ('sample_alias_write','2102',RAW_SAMPLE,OUTBOUND,8,'Write through readonly RAM alias'),
            ('sample_canonical_write','2102',SAMPLE,OUTBOUND,8,'Write outside writable canonical inputs'),
            ('neighbor_index_alias','2102',RAW_INDEX+4*(1-cpu),OUTBOUND,8,'Access through undeclared RAM alias'),
            ('neighbor_array_write','2102',ARRAY_B+4*(1-cpu),OUTBOUND,8,'Write outside writable canonical inputs'),
            ('readonly_array_write','2102',ARRAY_A,OUTBOUND,8,'Write outside writable canonical inputs'),
            ('code_write','2102',ENTRY,OUTBOUND,8,'Write outside writable canonical inputs'),
            ('alias_overrun','6012',RAW_CURRENT+4*cpu+2,OUTBOUND,8,'Access through undeclared RAM alias'),
            ('unknown_read','6012',0x060E0000,OUTBOUND,8,'Read outside literals and controlled inputs'),
            ('code_as_data','6012',ENTRY,OUTBOUND,8,'Read outside literals and controlled inputs'),
            ('unknown_return','000b 0009',RAW_CURRENT+4*cpu,0xDEAD0000,8,'Instruction fetch outside declared code'),
            ('short_loop','affe 0009',RAW_CURRENT+4*cpu,OUTBOUND,128,'Handoff instruction budget exceeded'),
            ('full_loop','affe 0009',RAW_CURRENT+4*cpu,OUTBOUND,profile.MAX_STEPS,'Handoff instruction budget exceeded')):
            changed=bytearray(data);blob=bytes.fromhex(words);changed[offset:offset+len(blob)]=blob
            result=observe(changed,emu,case,regions,{**before,'r1':address,'pr':pr},budget)
            if result['status']!='failed' or result['error']['reason']!=reason or not result['original_unaffected_bytes_equal']:
                raise ValueError('Owned selection guard failed: '+name)
            controls[f'{cpu}:{name}']={'status':result['status'],'reason':reason,'executed_instructions':len(result['trace'])}
        if observe(data,emu,case,regions,before)!=good:raise ValueError('Owned selection recovery differs')
    if older.MAX_STEPS!=128:raise ValueError('Older guard global changed')
    try:
        older.observe(data,emu,ENTRY,regions,before,ranges=RANGES,literals=LITERALS,aliases=(),
                      terminals={OUTBOUND:'handoff'},budget=129)
    except ValueError:controls['older_129_refused']={'rejected':True}
    else:raise ValueError('Older128 profile accepted a larger request')
    return {'original_game_bytes_executed':False,'coherent_slots':positives,'failure_controls':controls,
            'fresh_after_failure':True,'older_profile_unchanged':True,'guard_source_sha256':profile.GUARD_SHA256,
            'cap_only_derived_guard_sha256':profile.DERIVED_SHA256}


def execute(data,emu,family):
    selected=[c for c in cases() if c[0]==family];rows=[run_case(data,emu,c) for c in selected];controls={}
    for name,pc,word,selection in (
        ('wrong_next_record_increment',0x06006C50,0x7D02,'positions0'),
        ('missing_record_wrap',0x06006C5A,0x0009,'positions1'),
        ('flag_three_becomes_four',0x06006C86,0x8804,'flag-bytes'),
        ('flag_two_becomes_four',0x06006C90,0x8804,'flag-bytes'),
        ('missing_init_saved_PR_store',0x06006C98,0x0009,'positions0'),
        ('missing_init_argument_store',0x06006C9E,0x0009,'fields'),
        ('initializing_flag_four',0x06006CA2,0xE304,'positions1'),
        ('missing_scan_pointer_delay',0x06006CB4,0x0009,'positions0'),
        ('missing_wrap_index_delay',0x06006CBA,0x0009,'polls0'),
        ('missing_selection_index_store',0x06006CE0,0x0009,'positions0'),
        ('missing_current_pointer_store',0x06006CF6,0x0009,'positions1'),
        ('missing_array_writeback',0x06006D06,0x0009,'positions1'),
        ('missing_interval_reload',0x06006D1A,0x0009,'fields'),
        ('missing_R14_tail_delay',0x06006D34,0x0009,'positions1'),
        ('delta_addition_wraps_wait_into_ready',0x06006BCC,0x327C,'polls1')):
        if family!=selection:continue
        changed=bytearray(data);offset=pc-pinned.BASE;changed[offset:offset+2]=word.to_bytes(2,'big')
        chosen=selected[::max(1,len(selected)//48)]
        for flag in (1,2,3,4):
            for target in (0,17):
                witness=next((c for c in selected if c[4]==flag and c[3]==target and
                              (family=='flag-bytes' or c[2] in (MASK,17))),None)
                if witness is not None:chosen.append(witness)
        if family=='polls1':
            chosen.append(next(c for c in selected if c[2]==MASK and c[3]==0 and c[4]==1 and c[5]==MASK
                               and (c[6]-c[7])&MASK==2))
        chosen=sorted(set(chosen));rejected=0;budget_only=0;reasons=set();first=None;first_budget=None
        for case in chosen:
            try:run_case(changed,emu,case)
            except CaseFailure as fault:
                actual=fault.evidence['actual']
                if actual['error'] and actual['error']['reason']=='Handoff instruction budget exceeded':
                    budget_only+=1
                    if first_budget is None:first_budget=fault.evidence
                else:
                    rejected+=1;reasons.add(str(fault))
                    if first is None:first=fault.evidence
        if not rejected:raise ValueError('No semantic/permission rejection, only budget or surviving cases: '+name)
        controls[name]={'pc':pc,'tested':len(chosen),'semantic_or_permission_rejections':rejected,
                        'budget_only_refusals_not_counted':budget_only,'reasons':sorted(reasons),
                        'mutated_kernel_sha256':pinned.digest(changed),'first_rejection':first,'first_budget_refusal':first_budget}
    short=None
    if family=='positions0':
        case=('positions0',0,MASK,17,1,1,0,0,7,0)
        short=run_case(data,emu,case,budget=128)
        if short['outcome']!='incomplete_short_guard' or short['instructions_executed']!=128:
            raise ValueError('Original128 short profile did not retain an incomplete refusal')
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original128_short_profile':short,'original_game_bytes_executed':True,
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(data[lo-pinned.BASE:hi-pinned.BASE]) for lo,hi in RANGES},
            'literal_sha256':{f'{pc:x}':pinned.digest(data[pc-pinned.BASE:pc-pinned.BASE+4]) for pc in LITERALS}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=('positions0','positions1','fields','flag-bytes','polls0','polls1','waits'),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    names=('probe_record_selection.py','sh2_selection_profile.py','sh2_handoff_profile.py','probe_context_handoff.py',
           'probe_record_delta.py','probe_kernel_records.py','probe_kernel.py','probe_split_add.py','probe_position_bounds.py')
    report={'schema':'neptune.original-sh2-record-selection.v1','experiment':'EXP-SAT-CODE-021','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,
            'interpreter_sources':pinned.SOURCE_HASHES,'source_sha256':{name:pinned.digest(Path(__file__).with_name(name).read_bytes()) for name in names},
            'guard_derivation':{'accepted_source_sha256':profile.GUARD_SHA256,'derived_sha256':profile.DERIVED_SHA256,
                                'only_change':'MAX_STEPS=128 ->1024 in fresh namespace; older source/global unchanged'},
            'selection':args.family,'max_instructions':profile.MAX_STEPS,'original_game_bytes_executed':False,
            'limitations':['Constructed full table/root/arrays/header and static sample; no natural scheduler capture',
                           'Selected task transfers are incomplete handoffs; bounded waits/short refusals remain failed executions',
                           'No injected ticks, task execution, callee stubs, simultaneous CPUs, timing or independent-engine proof',
                           'Unknown whole executable/function/dynamic-target denominators; programme active/incomplete']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            data=pinned.kernel_bytes(args.kernel);emu=pinned.interpreter(args.saturn_recomp)
            phase='owned_smoke';report['owned_smoke']=owned_smoke(emu)
            phase='original_execution';report['original_game_bytes_executed']=None
            report.update(execute(data,emu,args.family),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':str(error)}
            if isinstance(error,CaseFailure):report['failure_evidence']=error.evidence;report['original_game_bytes_executed']=True
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'selection':args.family}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
