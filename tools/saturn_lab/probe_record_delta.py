#!/usr/bin/env python3
"""Original KRNL6B9C: full18-record unsigned delta update, explicit read alias."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
import probe_kernel_records as records
import sh2_profile

MASK=0xFFFFFFFF
ENTRY,END=0x06006B9C,0x06006BE4
SAMPLE,RAW_SAMPLE,PREVIOUS,TABLE=0x06006038,0x26006038,0x060BD050,records.RECORDS
LITERALS={0x06006E00:RAW_SAMPLE,0x06006E04:PREVIOUS,0x06006E08:TABLE}
ALIASES=((RAW_SAMPLE,SAMPLE,4),)
ALL=(1<<18)-1
WORDS=(0,1,2,0x7F,0xFF,0x100,0xFFFF,0x10000,0x7FFFFFFF,0x80000000,0xFFFFFFFE,MASK)
PATTERNS=(0,1,2,3,0x7FFFFFFF,0x80000000,0xFFFFFFFE,MASK,None)


def timers(pattern):
    return [WORDS[i%len(WORDS)] for i in range(18)] if pattern==8 else [PATTERNS[pattern]]*18


class Model(records.Model):
    """Selected instruction effects, independent of the reference opcode decoder."""
    def read(self,address,size):
        if address in LITERALS and size==4:value=LITERALS[address]
        else:
            canonical=SAMPLE+address-RAW_SAMPLE if RAW_SAMPLE<=address and address+size<=RAW_SAMPLE+4 else address
            value=None
            for (lo,_),buf in zip(self.regions,self.buffers):
                if lo<=canonical and canonical+size<=lo+len(buf):
                    value=int.from_bytes(buf[canonical-lo:canonical-lo+size],'big');break
            if value is None:raise ValueError('Expected read outside declared inputs')
        self.events.append([1,address,size,value]);return value

    def delta(self):
        r=self.reg
        self.step(0x06006B9C);self.push(r['r14'])
        self.step(0x06006B9E);r['r3']=self.read(0x06006E00,4)
        self.step(0x06006BA0);r['r2']=self.read(0x06006E04,4)
        self.step(0x06006BA2);r['r14']=self.read(r['r3'],4)
        self.step(0x06006BA4);r['r4']=self.read(r['r2'],4)
        self.step(0x06006BA6);self.t(r['r4']==r['r14'])
        self.step(0x06006BA8)
        if not r['sr']&1:
            self.step(0x06006BAA);r['r7']=r['r14']
            self.step(0x06006BAC);r['r7']=(r['r7']-r['r4'])&MASK
            self.step(0x06006BAE);r['r5']=1
            self.step(0x06006BB0);r['r4']=self.read(0x06006E08,4)
            self.step(0x06006BB2)
            self.step(0x06006BB4,True);r['r6']=18
            self.step(0x06006BD8);self.t(r['r6']==0)
            self.step(0x06006BDA)
            for i in range(18):
                self.step(0x06006BB6);r['r0']=80
                self.step(0x06006BB8);r['r3']=records.signed(self.read(r['r4']+80,1),8)&MASK
                self.step(0x06006BBA);self.t(r['r3']==0)
                self.step(0x06006BBC)
                if r['r3']:
                    self.step(0x06006BBE);r['r2']=self.read(r['r4'],4)
                    self.step(0x06006BC0);self.t(r['r2']>1)
                    self.step(0x06006BC2)
                    if r['sr']&1:
                        self.step(0x06006BC4);r['r1']=self.read(r['r4'],4)
                        self.step(0x06006BC6);self.t(r['r1']>r['r7'])
                        self.step(0x06006BC8)
                        if r['sr']&1:
                            self.step(0x06006BCA);r['r2']=self.read(r['r4'],4)
                            self.step(0x06006BCC);r['r2']=(r['r2']-r['r7'])&MASK
                            self.step(0x06006BCE)
                            self.step(0x06006BD0,True);self.write(r['r4'],4,r['r2'])
                        else:
                            self.step(0x06006BD2);self.write(r['r4'],4,1)
                self.step(0x06006BD4);r['r6']-=1
                self.step(0x06006BD6);r['r4']+=88
                self.step(0x06006BD8);self.t(r['r6']==0)
                self.step(0x06006BDA)
            self.step(0x06006BDC);r['r3']=self.read(0x06006E04,4)
            self.step(0x06006BDE);self.write(r['r3'],4,r['r14'])
        self.step(0x06006BE0)
        self.step(0x06006BE2,True);r['r14']=self.pop()
        r['pc']=0xFFFFFFF0


def contract(case):
    family,current,previous,mask,pattern,flag,variant=case
    before=records.initial(ENTRY,0xDEADBEEF,variant)
    table=bytearray((i*37+19+variant*83)&255 for i in range(18*88))
    values=timers(pattern)
    for i,old in enumerate(values):
        table[88*i:88*i+4]=old.to_bytes(4,'big');table[88*i+80]=flag if mask>>i&1 else 0
    regions=[(SAMPLE,current.to_bytes(4,'big')),(PREVIOUS,previous.to_bytes(4,'big')),
             (TABLE,bytes(table)),(records.SP-32,bytes([0xCD])*32)]
    model=Model(before,regions);model.delta()
    # A separate scalar contract does not follow the PC/register model.
    scalar=bytearray(table)
    for i,old in enumerate(values):
        if current!=previous and mask>>i&1 and flag and old>1:
            scalar[88*i:88*i+4]=max(1,old-((current-previous)&MASK)).to_bytes(4,'big')
    if model.buffers[2]!=scalar or model.buffers[1]!=(current if current!=previous else previous).to_bytes(4,'big'):
        raise ValueError('Path model differs from scalar contract')
    return model


def observe(data,emu,regions,before,budget=sh2_profile.MAX_STEPS):
    return sh2_profile.observe(data,emu,ENTRY,[(lo,buf,lo!=SAMPLE) for lo,buf in regions],before,
                               ranges=((ENTRY,END),),literals=LITERALS,aliases=ALIASES,budget=budget)


class CaseFailure(ValueError):
    def __init__(self,reason,case,actual):
        super().__init__(reason)
        self.evidence={'case':list(case),'actual':{k:v for k,v in actual.items() if k!='regions_after'},
                       'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']]}


def run_case(data,emu,case):
    expected=contract(case);actual=observe(data,emu,expected.regions,expected.before)
    if actual['status']!='returned':raise CaseFailure('Original execution failed: '+str(actual['error']),case,actual)
    if actual['registers']!=expected.reg:raise CaseFailure('Register/PC/SR/PR result differs',case,actual)
    if actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):raise CaseFailure('Executed PC/delay path differs',case,actual)
    if actual['events']!=expected.events:raise CaseFailure('Exact read/write transactions differ',case,actual)
    if actual['regions_after']!=[bytes(v) for v in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        raise CaseFailure('Controlled outputs/canaries or original bytes differ',case,actual)
    return {'case':list(case),'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],'all_visible_registers_checked':True,
            'unaffected_bytes_equal':True,'return_sentinel_reached':True}


def cases():
    rows=[]
    for cur,prev,mask,v in itertools.product(WORDS,WORDS,(0,ALL),range(2)):
        rows.append(('boundary',cur,prev,mask,8,0x80 if v else 1,v))
    masks=(0,ALL,*[1<<i for i in range(18)])
    for delta,prev,pattern,mask,v in itertools.product((0,1,2,0x7FFFFFFF,0x80000000,MASK),
                                                     (0,MASK,0x80000000),range(9),masks,range(2)):
        rows.append(('records',(prev+delta)&MASK,prev,mask,pattern,0xFF if v else 1,v))
    for flag,v in itertools.product(range(256),range(2)):
        rows.append(('flags',1,MASK,ALL,5,flag,v))
    return sorted(rows)


def owned_smoke(emu):
    """Authored canonical write -> alias read -> canonical read, then strict guards."""
    data=bytearray(pinned.SIZE);offset=ENTRY-pinned.BASE
    data[offset:offset+10]=bytes.fromhex('2102 6322 6412 000b 0009')
    before={**records.initial(ENTRY,0,0),'r0':0x11223344,'r1':SAMPLE,'r2':RAW_SAMPLE}
    regions=[(SAMPLE,bytes(4),True)]
    def call(image=data,regs=before,inputs=regions,entry=ENTRY,budget=8):
        return sh2_profile.observe(image,emu,entry,inputs,regs,ranges=((ENTRY,END),),
                                   literals=LITERALS,aliases=ALIASES,budget=budget)
    good=call()
    if (good['status']!='returned' or good['registers']!={**before,'r3':0x11223344,'r4':0x11223344,'pc':0xFFFFFFF0}
        or good['events']!=[[2,SAMPLE,4,0x11223344],[1,RAW_SAMPLE,4,0x11223344],[1,SAMPLE,4,0x11223344]]
        or good['regions_after']!=[bytes.fromhex('11223344')] or not good['original_unaffected_bytes_equal']):
        raise ValueError('Owned coherent alias smoke failed')
    controls={}
    for name,words,address,writable,entry,budget,reason in (
        ('readonly_sample','2102',SAMPLE,False,ENTRY,8,'Write outside writable canonical inputs'),
        ('alias_write','2102',RAW_SAMPLE,True,ENTRY,8,'Write outside writable canonical inputs'),
        ('unknown_alias','6012',RAW_SAMPLE+4,True,ENTRY,8,'Read through undeclared alias'),
        ('partial_alias_overrun','6012',RAW_SAMPLE+2,True,ENTRY,8,'Read through undeclared alias'),
        ('code_as_data','6012',ENTRY,True,ENTRY,8,'Read outside literals and controlled inputs'),
        ('code_write','2102',ENTRY,True,ENTRY,8,'Write outside writable canonical inputs'),
        ('alias_fetch','412b 0009',ENTRY|0x20000000,True,ENTRY,8,'Instruction fetch outside declared code'),
        ('short_loop','affe 0009',SAMPLE,True,ENTRY,8,'Local instruction budget exceeded'),
        ('full_loop','affe 0009',SAMPLE,True,ENTRY,sh2_profile.MAX_STEPS,'Local instruction budget exceeded')):
        image=bytearray(data);blob=bytes.fromhex(words);image[offset:offset+len(blob)]=blob
        result=call(image,{**before,'r1':address},[(SAMPLE,bytes(4),writable)],entry,budget)
        if result['status']!='failed' or result['error']['reason']!=reason or not result['original_unaffected_bytes_equal']:
            raise ValueError('Owned guard failed: '+name)
        controls[name]={'reason':reason,'executed_instructions':len(result['trace']),'status':result['status']}
    try:
        sh2_profile.observe(data,emu,ENTRY,regions,before,ranges=((ENTRY,END),),literals=LITERALS,
                            aliases=((RAW_SAMPLE,SAMPLE+4,4),))
    except ValueError:controls['invalid_alias_configuration']={'rejected':True}
    else:raise ValueError('Invalid alias configuration accepted')
    if call()!=good:raise ValueError('Owned recovery differs')
    return {'original_game_bytes_executed':False,'coherent_canonical_alias_reads':True,
            'failure_controls':controls,'fresh_after_failure':True}


def execute(data,emu,family):
    selected=[c for c in cases() if c[0]==family]
    rows=[run_case(data,emu,c) for c in selected]
    chosen=selected[::max(1,len(selected)//64)]
    controls={}
    for name,pc,word,size in (
        ('missing_equality_skip',0x06006BA8,0x0009,2),
        ('signed_first_comparison',0x06006BC0,0x3257,2),
        ('signed_delta_comparison',0x06006BC6,0x3177,2),
        ('addition_instead_of_subtraction',0x06006BCC,0x327C,2),
        ('zero_floor_and_threshold',0x06006BAE,0xE500,2),
        ('only_seventeen_records',0x06006BB4,0xE611,2),
        ('missing_subtraction_delay_store',0x06006BD0,0x0009,2),
        ('missing_R14_return_delay_restore',0x06006BE2,0x0009,2),
        ('undeclared_adjacent_alias',0x06006E00,RAW_SAMPLE+4,4)):
        changed=bytearray(data);o=pc-pinned.BASE;changed[o:o+size]=word.to_bytes(size,'big')
        rejected=0;reasons=set()
        for case in chosen:
            try:run_case(changed,emu,case)
            except ValueError as fault:
                if 'budget exceeded' in str(fault):raise ValueError('Budget failure is not a semantic control')
                rejected+=1;reasons.add(str(fault))
        # Some families intentionally contain no equality/signed-delta cases.
        controls[name]={'pc':pc,'tested':len(chosen),'rejected':rejected,'reasons':sorted(reasons),
                        'mutated_kernel_sha256':pinned.digest(changed)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':pinned.digest(data[ENTRY-pinned.BASE:END-pinned.BASE]),
            'literal_sha256':pinned.digest(data[0x06006E00-pinned.BASE:0x06006E0C-pinned.BASE])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=('boundary','records','flags'),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-sh2-record-delta.v1','experiment':'EXP-SAT-CODE-017','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'entry':ENTRY,'end_exclusive':END,'kernel_sha256':pinned.KERNEL_SHA256,
            'interpreter_revision':pinned.INTERPRETER_REVISION,'interpreter_sources':pinned.SOURCE_HASHES,
            'source_sha256':{name:pinned.digest(Path(__file__).with_name(name).read_bytes()) for name in
                             ('probe_record_delta.py','sh2_profile.py','probe_kernel_records.py','probe_kernel.py',
                              'probe_split_add.py','probe_position_bounds.py')},
            'selection':args.family,'max_steps_per_call':sh2_profile.MAX_STEPS,
            'readonly_aliases':ALIASES,'original_game_bytes_executed':False,
            'limitations':['Constructed sample/previous/records/registers; natural clock/timer/gameplay role unknown',
                           'Complete18-record CPU routine on selected cases; not all machine states or whole kernel',
                           'Pinned CPU-only interpreter, no hardware/timing/independent-engine validation',
                           'Whole-program/function/dynamic-target denominators remain unknown']}
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
            if isinstance(error,CaseFailure):
                report['failure_evidence']=error.evidence;report['original_game_bytes_executed']=True
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'selection':args.family}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
