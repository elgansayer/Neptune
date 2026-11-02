#!/usr/bin/env python3
"""Original KRNL6DC8 signed-index record transition; selected CPU contract."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
import probe_kernel_records as records
import sh2_profile

ENTRY,END,LITERAL,TABLE=0x06006DC8,0x06006DFE,0x06006E08,records.RECORDS
MASK=0xFFFFFFFF
MAX_STEPS=64


def accepted(argument):return records.signed(argument,32)<18


def pointer(argument):return (TABLE+records.signed(88*records.signed(argument,16),16))&MASK


class Model(records.Model):
    def read(self,address,size):
        if address==LITERAL and size==4:
            self.events.append([1,address,size,TABLE]);return TABLE
        return super().read(address,size)

    def transition(self):
        r=self.reg
        self.step(0x06006DC8);self.push(r['macl'])
        self.step(0x06006DCA);r['r3']=18
        self.step(0x06006DCC);self.t(records.signed(r['r4'],32)>=18)
        self.step(0x06006DCE)
        success=False
        if not r['sr']&1:
            self.step(0x06006DD0);r['r2']=self.read(LITERAL,4)
            self.step(0x06006DD2);r['r0']=80
            self.step(0x06006DD4);r['r1']=88
            self.step(0x06006DD6);r['macl']=(88*records.signed(r['r4'],16))&MASK
            self.step(0x06006DD8);r['r4']=r['macl']
            self.step(0x06006DDA);r['r4']=records.signed(r['r4'],16)&MASK
            self.step(0x06006DDC);r['r4']=(r['r4']+TABLE)&MASK
            self.step(0x06006DDE);r['r0']=records.signed(self.read(r['r4']+80,1),8)&MASK
            self.step(0x06006DE0);r['r0'] &= 255
            self.step(0x06006DE2);self.t(r['r0']==1)
            self.step(0x06006DE4)
            success=bool(r['sr']&1)
            if success:
                self.step(0x06006DE6);r['r2']=2
                self.step(0x06006DE8);r['r0']=80
                self.step(0x06006DEA);r['r3']=0
                self.step(0x06006DEC);self.write(r['r4']+80,1,2)
                self.step(0x06006DEE);r['r0']=81
                self.step(0x06006DF0);self.write(r['r4']+81,1,0)
                self.step(0x06006DF2);r['r0']=0
                self.step(0x06006DF4)
                self.step(0x06006DF6,True);r['macl']=self.pop()
        if not success:
            self.step(0x06006DF8);r['r0']=MASK
            self.step(0x06006DFA)
            self.step(0x06006DFC,True);r['macl']=self.pop()
        r['pc']=0xFFFFFFF0


def contract(case):
    family,argument,flag,category,variant=case
    before=records.initial(ENTRY,argument,variant)
    regions=[(records.SP-32,bytes([0xCD])*32)]
    if accepted(argument):
        buf=bytearray((i*37+19+variant*83)&255 for i in range(88));buf[80]=flag;buf[81]=category
        regions.append((pointer(argument),bytes(buf)))
    model=Model(before,regions);model.transition()
    # Independent scalar checks, separate from the PC/register-effect model.
    success=accepted(argument) and flag==1
    if model.reg['r0']!=(0 if success else MASK):raise ValueError('Scalar return contract differs')
    if accepted(argument):
        scalar=bytearray(regions[1][1])
        if success:scalar[80]=2;scalar[81]=0
        if model.buffers[1]!=scalar:raise ValueError('Scalar record contract differs')
    if model.reg['macl']!=before['macl'] or model.reg['r15']!=before['r15']:
        raise ValueError('Saved MACL/stack contract differs')
    return model


def observe(data,emu,regions,before,budget=MAX_STEPS):
    if not 0<budget<=MAX_STEPS:raise ValueError('Invalid transition instruction budget')
    return sh2_profile.observe(data,emu,ENTRY,[(lo,buf,True) for lo,buf in regions],before,
                               ranges=((ENTRY,END),),literals=(LITERAL,),aliases=(),budget=budget)


class CaseFailure(ValueError):
    def __init__(self,reason,case,actual):
        super().__init__(reason)
        self.evidence={'case':list(case),'actual':{k:v for k,v in actual.items() if k!='regions_after'},
                       'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']]}


def run_case(data,emu,case):
    expected=contract(case);actual=observe(data,emu,expected.regions,expected.before);reason=None
    if actual['status']!='returned':reason='Original execution failed: '+str(actual['error'])
    elif actual['registers']!=expected.reg:reason='Register/PC/SR/PR/MAC result differs'
    elif actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):reason='Executed PC/delay path differs'
    elif actual['events']!=expected.events:reason='Exact read/write transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Controlled output/canaries or original bytes differ'
    if reason:raise CaseFailure(reason,case,actual)
    return {'case':list(case),'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],'all_visible_registers_checked':True,
            'unaffected_bytes_equal':True,'return_sentinel_reached':True}


def cases():
    rows=[]
    for arg,flag,v in itertools.product((0,1,17,MASK,MASK-1,0xFFFF8000,0x80000000,0x8000FFFF),range(256),range(2)):
        rows.append(('flags',arg,flag,(flag*37+arg+v)&255,v))
    for arg,category,v in itertools.product((0,17,MASK,0x80000000),range(256),range(2)):
        rows.append(('categories',arg,1,category,v))
    indices=sorted(set(range(20))|{127,255,371,372,373,0x7FFF,0x8000,0xFFFF,0x10000,0x10001,
                   0x7FFFFFFE,0x7FFFFFFF,0x80000000,0x80000001,0x8000FFFF,0xFFFF0000,0xFFFF0001,
                   0xFFFF7FFF,0xFFFF8000,0xFFFF8001,0xFFFFFE8B,0xFFFFFE8C,MASK-1,MASK})
    for arg,flag,category,v in itertools.product(indices,(0,1,2,127,128,255),(0,1,128,255),range(2)):
        rows.append(('indices',arg,flag,category,v))
    return sorted(rows)


def owned_smoke(emu):
    data=bytearray(pinned.SIZE);offset=ENTRY-pinned.BASE
    data[offset:offset+6]=bytes.fromhex('6012 000b 0009')
    data[LITERAL-pinned.BASE:LITERAL-pinned.BASE+4]=bytes.fromhex('11223344')
    before={**records.initial(ENTRY,0,0),'r1':LITERAL}
    regions=[(records.SP-32,bytes([0xCD])*32)]
    good=observe(data,emu,regions,before)
    if (good['status']!='returned' or good['registers']!={**before,'r0':0x11223344,'pc':0xFFFFFFF0}
        or good['events']!=[[1,LITERAL,4,0x11223344]] or good['trace']!=[[ENTRY,False],[ENTRY+2,False],[ENTRY+4,True]]
        or good['regions_after']!=[regions[0][1]] or not good['original_unaffected_bytes_equal']):
        raise ValueError('Owned literal/profile smoke failed')
    controls={}
    for name,words,address,budget,reason in (
        ('unknown_read','6012',0x060D0000,8,'Read outside literals and controlled inputs'),
        ('alias_read','6012',LITERAL|0x20000000,8,'Read through undeclared alias'),
        ('code_as_data','6012',ENTRY,8,'Read outside literals and controlled inputs'),
        ('code_write','2102',ENTRY,8,'Write outside writable canonical inputs'),
        ('short_loop','affe 0009',LITERAL,8,'Local instruction budget exceeded'),
        ('full_loop','affe 0009',LITERAL,MAX_STEPS,'Local instruction budget exceeded')):
        image=bytearray(data);blob=bytes.fromhex(words);image[offset:offset+len(blob)]=blob
        actual=observe(image,emu,regions,{**before,'r1':address},budget)
        if actual['status']!='failed' or actual['error']['reason']!=reason or not actual['original_unaffected_bytes_equal']:
            raise ValueError('Owned guard failed: '+name)
        controls[name]={'status':actual['status'],'reason':reason,'executed_instructions':len(actual['trace'])}
    image=bytearray(data);image[offset:offset+2]=bytes.fromhex('2102')
    written=observe(image,emu,regions,{**before,'r1':records.SP-4})
    if (written['status']!='returned' or written['events']!=[[2,records.SP-4,4,before['r0']]]
        or written['regions_after']!=[regions[0][1][:-4]+before['r0'].to_bytes(4,'big')]):
        raise ValueError('Owned controlled-write smoke failed')
    if observe(data,emu,regions,before)!=good:raise ValueError('Owned recovery differs')
    return {'original_game_bytes_executed':False,'literal_read':True,'controlled_write':True,
            'failure_controls':controls,'fresh_after_failure':True}


def execute(data,emu,family):
    selected=[c for c in cases() if c[0]==family];rows=[run_case(data,emu,c) for c in selected];controls={}
    for name,pc,word,selection in (
        ('unsigned_upper_bound',0x06006DCC,0x3432,'indices'),
        ('strict_upper_bound',0x06006DCC,0x3437,'indices'),
        ('missing_signed_result_truncation',0x06006DDA,0x0009,'indices'),
        ('flag_zero_instead_of_one',0x06006DE2,0x8800,'flags'),
        ('flag_three_instead_of_two',0x06006DE6,0xE203,'flags'),
        ('missing_category_clear',0x06006DF0,0x0009,'categories'),
        ('missing_success_result',0x06006DF2,0x0009,'categories'),
        ('zero_failure_result',0x06006DF8,0xE000,'indices'),
        ('missing_success_MACL_delay_restore',0x06006DF6,0x0009,'flags'),
        ('missing_failure_MACL_delay_restore',0x06006DFC,0x0009,'indices')):
        if selection!=family:continue
        changed=bytearray(data);o=pc-pinned.BASE;changed[o:o+2]=word.to_bytes(2,'big')
        chosen=selected[::max(1,len(selected)//64)]
        # Keep successful, rejected18, and signed-negative witnesses even when stride sampling misses them.
        for argument in (0,17,18,MASK,0xFFFF8000):
            witness=next((c for c in selected if c[1]==argument and c[2]==1),None)
            if witness is not None:chosen.append(witness)
        chosen=sorted(set(chosen))
        rejected=0;reasons=set();first=None
        for case in chosen:
            try:run_case(changed,emu,case)
            except ValueError as fault:
                if 'budget exceeded' in str(fault):raise ValueError('Budget failure is not semantic evidence')
                rejected+=1;reasons.add(str(fault))
                if first is None and isinstance(fault,CaseFailure):first=fault.evidence
        if not rejected:raise ValueError('Altered original survived: '+name)
        controls[name]={'pc':pc,'tested':len(chosen),'rejected':rejected,'reasons':sorted(reasons),
                        'mutated_kernel_sha256':pinned.digest(changed),'first_rejection':first}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':pinned.digest(data[ENTRY-pinned.BASE:END-pinned.BASE]),
            'literal_sha256':pinned.digest(data[LITERAL-pinned.BASE:LITERAL-pinned.BASE+4])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=('flags','categories','indices'),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-sh2-record-transition.v1','experiment':'EXP-SAT-CODE-019','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,
            'interpreter_sources':pinned.SOURCE_HASHES,'source_sha256':{name:pinned.digest(Path(__file__).with_name(name).read_bytes())
                for name in ('probe_record_transition.py','sh2_profile.py','probe_kernel_records.py','probe_kernel.py',
                             'probe_split_add.py','probe_position_bounds.py')},
            'selection':args.family,'max_steps_per_call':MAX_STEPS,'original_game_bytes_executed':False,
            'limitations':['Constructed index/record/stack/registers; negative indices are not naturally validated',
                           'Selected CPU-only function, no natural caller/task/timing/independent-engine proof',
                           'No new aliases or executable targets; whole executable/function/dynamic-target denominators unknown']}
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
