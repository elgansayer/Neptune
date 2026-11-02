#!/usr/bin/env python3
"""Original6D36/6DAE handoff and controlled resume through actual saved context."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
import probe_kernel_records as records
import sh2_handoff_profile as profile

YIELD,WRAPPER,END=0x06006D36,0x06006DAE,0x06006DC8
SAVE,RESTORE,CONTEXT_END=0x060061C4,0x060061E6,0x0600620A
CURRENT,PENDING,LIVE,ROOT=0x06006020,0x06006028,0x06006044,0x060BD020
RAW_CURRENT,RAW_PENDING,RAW_LIVE=CURRENT|0x20000000,PENDING|0x20000000,LIVE|0x20000000
OUTBOUND,RETURN=0xFFFFFFE0,0xFFFFFFF0
MASK=0xFFFFFFFF
LITERALS={0x06006E0C:ROOT,0x06006E10:SAVE,0x06006E20:RAW_LIVE,
          0x06006E28:RAW_CURRENT,0x06006E2C:RESTORE,0x06006E30:RAW_PENDING}
RANGES=((SAVE,CONTEXT_END),(YIELD,END))
WORDS=(0,1,2,0x7F,0xFF,0x100,0xFFFF,0x10000,0x7FFFFFFF,0x80000000,0xFFFFFFFE,MASK)


def fixture(case):
    family,cpu,index,argument,live,pending,resume,variant=case
    entry=WRAPPER if family=='wrapper' else YIELD
    before=records.initial(entry,argument,variant)
    before['vbr']=0x06005000|(cpu<<10)|(variant*0x155)
    record=records.RECORDS+88*index
    current=b''.join((record if slot==cpu else 0x060D1000+slot*0x100).to_bytes(4,'big') for slot in range(2))
    roots=[((i+1)*0x01010101+variant*0x22222222)&MASK for i in range(12)]
    roots[8]=0x060E0000+variant*0x100  # loaded as a register, never mapped as an invented task stack
    roots[9]=OUTBOUND
    root=b''.join(value.to_bytes(4,'big') for value in roots)
    table=bytes((i*37+19+variant*83)&255 for i in range(88))
    regions=[(records.SP-32,bytes([0xCD])*32,True),(CURRENT,current,False)]
    for slot in range(2):
        regions.append((PENDING+slot*4,(pending if slot==cpu else 0xFACEFEED).to_bytes(4,'big'),slot==cpu))
    regions.extend(((LIVE,live.to_bytes(4,'big'),False),(ROOT,root,False),(record,table,True)))
    return entry,before,regions


class Model(records.Model):
    """Expected source effects only; actual execution never calls these methods."""
    def read(self,address,size):
        if address in LITERALS and size==4:value=LITERALS[address]
        else:
            physical=address&0x1FFFFFFF if address>>28==2 else address
            value=None
            for (lo,_),buf in zip(self.regions,self.buffers):
                if lo<=physical and physical+size<=lo+len(buf):
                    value=int.from_bytes(buf[physical-lo:physical-lo+size],'big');break
            if value is None:raise ValueError('Expected read outside inputs')
        self.events.append([1,address,size,value]);return value

    def write(self,address,size,value):
        physical=address&0x1FFFFFFF if address>>28==2 else address
        value &= (1<<(8*size))-1
        for (lo,_),buf in zip(self.regions,self.buffers):
            if lo<=physical and physical+size<=lo+len(buf):
                buf[physical-lo:physical-lo+size]=value.to_bytes(size,'big')
                self.events.append([2,address,size,value]);return
        raise ValueError('Expected write outside inputs')

    def save(self):
        r=self.reg;address=r['r4']
        for i,(field,name) in enumerate(((0,'r8'),(4,'r8'),*[(4*(n-7),f'r{n}') for n in range(9,16)])):
            self.step(SAVE+2*i);self.write(address+field,4,r[name])
        for pc,name,field in ((0x060061D6,'mach',40),(0x060061DA,'macl',44),(0x060061DE,'pr',36)):
            self.step(pc);r['r0']=r[name]
            self.step(pc+2);self.write(address+field,4,r['r0'])
        self.step(0x060061E2)
        self.step(0x060061E4,True);r['r0']=0

    def restore(self):
        r=self.reg;address=r['r4']
        for i in range(8):
            self.step(RESTORE+2*i);r[f'r{i+8}']=self.read(address+4+4*i,4)
        for pc,name,field in ((0x060061F6,'macl',44),(0x060061FA,'mach',40),(0x060061FE,'pr',36)):
            self.step(pc);r['r0']=self.read(address+field,4)
            self.step(pc+2);r[name]=r['r0']
        self.step(0x06006202);r['r0']=self.read(address,4)
        self.step(0x06006204);r['r4']=r['r0']
        self.step(0x06006206)
        self.step(0x06006208,True);r['r0']=r['r5']
        r['pc']=r['pr']

    def root_handoff(self):
        r=self.reg
        self.step(0x06006D8A);r['r5']=self.read(r['r15'],4)
        self.step(0x06006D8C);r['r4']=self.read(0x06006E0C,4)
        self.step(0x06006D8E);r['r3']=self.read(0x06006E2C,4)
        self.step(0x06006D90);r['pr']=0x06006D94
        self.step(0x06006D92,True)
        self.restore()

    def resume_tail(self):
        r=self.reg
        self.step(0x06006D86);self.t(r['r0']==0)
        self.step(0x06006D88)
        if r['sr']&1:self.root_handoff();return
        self.step(0x06006D94);r['r0']=self.read(0x06006E30,4)
        self.step(0x06006D96);r['r2']=r['vbr']
        self.step(0x06006D98);r['r2'] >>= 8
        self.step(0x06006D9A);r['r2'] >>= 2
        self.step(0x06006D9C);r['r2'] &= r['r14']
        self.step(0x06006D9E);r['r2'] <<= 2
        self.step(0x06006DA0);r['r3']=0
        self.step(0x06006DA2);self.write(r['r0']+r['r2'],4,0)
        self.step(0x06006DA4);r['r15']+=4
        self.step(0x06006DA6);r['pr']=self.pop()
        self.step(0x06006DA8);r['r13']=self.pop()
        self.step(0x06006DAA)
        self.step(0x06006DAC,True);r['r14']=self.pop()
        r['pc']=r['pr']

    def outbound(self,entry):
        r=self.reg
        if entry==WRAPPER:
            self.step(0x06006DAE);r['r0']=r['vbr']
            self.step(0x06006DB0);r['r1']=self.read(0x06006E30,4)
            self.step(0x06006DB2);r['r0'] >>= 8
            self.step(0x06006DB4);r['r0'] >>= 2
            self.step(0x06006DB6);r['r0'] &= 1
            self.step(0x06006DB8);r['r0'] <<= 2
            self.step(0x06006DBA);r['r1']=self.read(r['r0']+r['r1'],4)
            self.step(0x06006DBC);self.t(r['r1']==0)
            self.step(0x06006DBE)
            if r['sr']&1:
                self.step(0x06006DC4);self.step(0x06006DC6,True);r['pc']=r['pr'];return
            self.step(0x06006DC0)
            self.step(0x06006DC2,True);r['r4']=1
        self.step(0x06006D36);r['r0']=r['vbr']
        self.step(0x06006D38);self.push(r['r14'])
        self.step(0x06006D3A);r['r1']=r['r4']
        self.step(0x06006D3C);self.push(r['r13'])
        self.step(0x06006D3E);r['r14']=1
        self.step(0x06006D40);self.push(r['pr'])
        self.step(0x06006D42);r['r0'] >>= 8
        self.step(0x06006D44);r['r13']=self.read(0x06006E28,4)
        self.step(0x06006D46);r['r15']-=4
        self.step(0x06006D48);self.write(r['r15'],4,r['r4'])
        self.step(0x06006D4A);r['r0'] >>= 2
        self.step(0x06006D4C);r['r0'] &= r['r14']
        self.step(0x06006D4E);r['r0'] <<= 2
        self.step(0x06006D50);r['r3']=self.read(r['r0']+r['r13'],4)
        self.step(0x06006D52);r['r0']=r['vbr']
        self.step(0x06006D54);r['r0'] >>= 8
        self.step(0x06006D56);r['r0'] >>= 2
        self.step(0x06006D58);r['r0'] &= r['r14']
        self.step(0x06006D5A);r['r0'] <<= 2
        self.step(0x06006D5C);r['r2']=self.read(r['r0']+r['r13'],4)
        self.step(0x06006D5E);r['r0']=r['vbr']
        self.step(0x06006D60);self.write(r['r2']+4,4,r['r4'])
        self.step(0x06006D62);r['r0'] >>= 8
        self.step(0x06006D64);self.write(r['r3'],4,r['r1'])
        self.step(0x06006D66);r['r0'] >>= 2
        self.step(0x06006D68);r['r1']=self.read(0x06006E20,4)
        self.step(0x06006D6A);r['r0'] &= r['r14']
        self.step(0x06006D6C);r['r2']=self.read(r['r1'],4)
        self.step(0x06006D6E);r['r0'] <<= 2
        self.step(0x06006D70);r['r3']=self.read(r['r0']+r['r13'],4)
        self.step(0x06006D72);self.write(r['r3']+28,4,r['r2'])
        self.step(0x06006D74);r['r3']=self.read(0x06006E10,4)
        self.step(0x06006D76);r['r0']=r['vbr']
        self.step(0x06006D78);r['r0'] >>= 8
        self.step(0x06006D7A);r['r0'] >>= 2
        self.step(0x06006D7C);r['r0'] &= r['r14']
        self.step(0x06006D7E);r['r0'] <<= 2
        self.step(0x06006D80);r['r4']=self.read(r['r0']+r['r13'],4)
        self.step(0x06006D82);r['pr']=0x06006D86
        self.step(0x06006D84,True);r['r4']+=32
        self.save();self.resume_tail()


def observe(data,emu,entry,regions,before,cpu,budget=profile.MAX_STEPS):
    aliases=((RAW_CURRENT+4*cpu,CURRENT+4*cpu,4,False),(RAW_LIVE,LIVE,4,False),
             (RAW_PENDING+4*cpu,PENDING+4*cpu,4,True))
    return profile.observe(data,emu,entry,regions,before,ranges=RANGES,literals=LITERALS,
                           aliases=aliases,terminals={RETURN:'returned',OUTBOUND:'handoff'},budget=budget)


def model(before,regions):return Model(before,[(lo,buf) for lo,buf,_ in regions])


def cases():
    rows=[]
    for cpu,index,arg,live,resume,v in itertools.product(range(2),(0,17),WORDS,(0,1,MASK),(0,1,0x80000000,MASK),range(2)):
        rows.append(('yield',cpu,index,arg,live,1 if v==0 else MASK,resume,v))
    for cpu,index,arg,pending,live,resume,v in itertools.product(range(2),(0,17),(0,MASK),(0,1,0x80000000,MASK),
                                                               (0,MASK),(0,1,MASK),range(2)):
        rows.append(('wrapper',cpu,index,arg,live,pending,resume,v))
    for cpu,index,arg,live,resume,v in itertools.product(range(2),range(18),(0,1,MASK),(0x7FFFFFFF,0x80000000),
                                                       (1,0x80000000),range(2)):
        rows.append(('records',cpu,index,arg,live,1,resume,v))
    return sorted(rows)


class CaseFailure(ValueError):
    def __init__(self,reason,case,phase,actual):
        super().__init__(reason)
        self.evidence={'case':list(case),'phase':phase,'actual':{k:v for k,v in actual.items() if k!='regions_after'},
                       'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']]}


def compare(case,phase,actual,expected):
    status='returned' if expected.reg['pc']==RETURN else 'handoff'
    reason=None
    if actual['status']=='failed':reason='Original execution failed: '+str(actual['error'])
    elif actual['status']!=status:reason='Return/handoff boundary differs'
    elif actual['registers']!=expected.reg:reason='Register/PC/SR/PR/MAC result differs'
    elif actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):reason='Executed PC/delay path differs'
    elif actual['events']!=expected.events:reason='Exact read/write transactions differ'
    elif actual['regions_after']!=[bytes(buf) for buf in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Controlled outputs/canaries or original bytes differ'
    if reason:raise CaseFailure(reason,case,phase,actual)


def phase_row(actual):
    return {'status':actual['status'],'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],'all_visible_registers_checked':True,
            'unaffected_bytes_equal':True}


def run_case(data,emu,case):
    entry,before,regions=fixture(case);cpu=case[1]
    expected=model(before,regions);expected.outbound(entry)
    actual=observe(data,emu,entry,regions,before,cpu);compare(case,'outbound',actual,expected)
    row={'case':list(case),'outbound':phase_row(actual),'complete_activation_return':actual['status']=='returned',
         'outbound_handoffs':int(actual['status']=='handoff')}
    if actual['status']=='returned':return row
    # Scalar context layout is checked separately from the instruction-effect model.
    argument=1 if entry==WRAPPER else case[3]
    scalar=bytearray(regions[-1][1]);scalar[0:4]=argument.to_bytes(4,'big');scalar[4:8]=argument.to_bytes(4,'big')
    scalar[28:32]=case[4].to_bytes(4,'big')
    fields=[before['r8'],before['r8'],*[before[f'r{i}'] for i in range(9,13)],RAW_CURRENT,1,
            before['r15']-16,0x06006D86,before['mach'],before['macl']]
    scalar[32:80]=b''.join(value.to_bytes(4,'big') for value in fields)
    if actual['regions_after'][-1]!=scalar:raise CaseFailure('Independent saved-context layout differs',case,'outbound',actual)
    # These bytes and registers come from original execution, never from expected.buffers.
    inputs=[(lo,buf,write) for (lo,_,write),buf in zip(regions,actual['regions_after'])]
    resume_before={**actual['registers'],'r4':regions[-1][0]+32,'r5':case[6],'pc':RESTORE}
    expected_resume=model(resume_before,inputs);expected_resume.restore();expected_resume.resume_tail()
    resumed=observe(data,emu,RESTORE,inputs,resume_before,cpu);compare(case,'resume',resumed,expected_resume)
    saved=actual['regions_after'][-1][32:80];resume_input=inputs[-1][1][32:80]
    if saved!=resume_input:raise ValueError('Resume input differs from actual saved context')
    row.update(resume=phase_row(resumed),resume_before_registers=resume_before,
               actual_saved_context_hex=saved.hex(),actual_saved_context_sha256=pinned.digest(saved),
               resume_input_context_sha256=pinned.digest(resume_input),resume_uses_actual_outbound_memory=True,
               complete_activation_return=resumed['status']=='returned',
               outbound_handoffs=row['outbound_handoffs']+int(resumed['status']=='handoff'))
    if row['complete_activation_return']!=(case[6]!=0):raise ValueError('Resume scalar termination differs')
    return row


def owned_smoke(emu):
    image=bytearray(pinned.SIZE);offset=YIELD-pinned.BASE
    image[offset:offset+10]=bytes.fromhex('2102 6322 6412 000b 0009')
    positives=[];controls={}
    for cpu in range(2):
        entry,before,regions=fixture(('yield',cpu,0,0,0,1,1,0))
        before.update(r0=0x11223344,r1=RAW_PENDING+4*cpu,r2=PENDING+4*cpu)
        good=observe(image,emu,entry,regions,before,cpu)
        if (good['status']!='returned' or good['registers']!={**before,'r3':0x11223344,'r4':0x11223344,'pc':RETURN}
            or good['events']!=[[2,RAW_PENDING+4*cpu,4,0x11223344],[1,PENDING+4*cpu,4,0x11223344],
                                [1,RAW_PENDING+4*cpu,4,0x11223344]] or not good['original_unaffected_bytes_equal']):
            raise ValueError('Owned bidirectional alias coherence failed')
        expected_buffers=[bytes.fromhex('11223344') if i==2+cpu else buf for i,(_,buf,_) in enumerate(regions)]
        if good['regions_after']!=expected_buffers:raise ValueError('Owned alias write changed neighboring canaries')
        positives.append({'cpu_slot':cpu,'instructions':good['steps'],'alias_write_canonical_alias_reads_equal':True})
        for name,words,address,pr,budget,reason in (
            ('readonly_alias','2102',RAW_CURRENT+4*cpu,RETURN,8,'Write through readonly RAM alias'),
            ('neighbor_alias','2102',RAW_PENDING+4*(1-cpu),RETURN,8,'Access through undeclared RAM alias'),
            ('neighbor_canonical','2102',PENDING+4*(1-cpu),RETURN,8,'Write outside writable canonical inputs'),
            ('alias_overrun','6012',RAW_PENDING+4*cpu+2,RETURN,8,'Access through undeclared RAM alias'),
            ('code_as_data','6012',YIELD,RETURN,8,'Read outside literals and controlled inputs'),
            ('code_write','2102',YIELD,RETURN,8,'Write outside writable canonical inputs'),
            ('unknown_task_stack','6012',0x060E0000,RETURN,8,'Read outside literals and controlled inputs'),
            ('unknown_return_target','000b 0009',RAW_PENDING+4*cpu,0xDEAD0000,8,'Instruction fetch outside declared code'),
            ('alias_fetch','412b 0009',YIELD|0x20000000,RETURN,8,'Instruction fetch outside declared code'),
            ('short_loop','affe 0009',RAW_PENDING+4*cpu,RETURN,8,'Handoff instruction budget exceeded'),
            ('full_loop','affe 0009',RAW_PENDING+4*cpu,RETURN,profile.MAX_STEPS,'Handoff instruction budget exceeded')):
            data=bytearray(image);blob=bytes.fromhex(words);data[offset:offset+len(blob)]=blob
            result=observe(data,emu,entry,regions,{**before,'r1':address,'pr':pr},cpu,budget)
            if result['status']!='failed' or result['error']['reason']!=reason or not result['original_unaffected_bytes_equal']:
                raise ValueError('Owned guard failed: '+name)
            controls[f'{cpu}:{name}']={'status':result['status'],'reason':reason,'executed_instructions':len(result['trace'])}
        data=bytearray(image);data[offset:offset+4]=bytes.fromhex('000b 0009')
        stopped=observe(data,emu,entry,regions,{**before,'pr':OUTBOUND},cpu)
        if stopped['status']!='handoff' or stopped['steps']!=2 or stopped['registers']['pc']!=OUTBOUND:
            raise ValueError('Owned outbound boundary was mistaken for a return')
        if observe(image,emu,entry,regions,before,cpu)!=good:raise ValueError('Owned recovery differs')
    for name,alias in (('readonly_alias_backing',(RAW_CURRENT,CURRENT,4,True)),
                       ('invalid_alias_translation',(RAW_PENDING,PENDING+4,4,True))):
        try:
            profile.observe(image,emu,YIELD,regions,before,ranges=RANGES,literals=LITERALS,aliases=(alias,),
                            terminals={RETURN:'returned',OUTBOUND:'handoff'})
        except ValueError:controls[name]={'rejected':True}
        else:raise ValueError('Invalid alias permissions accepted: '+name)
    try:
        profile.observe(image,emu,YIELD,regions,before,ranges=RANGES,literals=LITERALS,aliases=(),
                        terminals={YIELD:'handoff'})
    except ValueError:controls['executable_terminal_configuration']={'rejected':True}
    else:raise ValueError('Executable address accepted as an outbound terminal')
    return {'original_game_bytes_executed':False,'both_cpu_alias_coherence':positives,
            'failure_controls':controls,'handoff_distinct_from_return':True,'fresh_after_failure':True}


def execute(data,emu,family):
    selected=[c for c in cases() if c[0]==family];rows=[run_case(data,emu,c) for c in selected];controls={}
    for name,pc,word,selection in (
        ('missing_record_saved_argument',0x06006D60,0x0009,'yield'),
        ('missing_record_word_store',0x06006D64,0x0009,'yield'),
        ('missing_record_live_word',0x06006D72,0x0009,'yield'),
        ('missing_save_context_offset_delay',0x06006D84,0x0009,'yield'),
        ('wrapper_argument_zero',0x06006DC2,0xE400,'wrapper'),
        ('wrapper_inverted_pending_skip',0x06006DBE,0x8B01,'wrapper'),
        ('missing_pending_clear',0x06006DA2,0x0009,'records'),
        ('missing_epilogue_R14_delay_restore',0x06006DAC,0x0009,'records'),
        ('missing_context_PR_restore',0x06006200,0x0009,'records'),
        ('missing_context_result_delay',0x06006208,0x0009,'records')):
        if selection!=family:continue
        changed=bytearray(data);o=pc-pinned.BASE;changed[o:o+2]=word.to_bytes(2,'big')
        chosen=selected[::max(1,len(selected)//64)]
        for cpu,resume in itertools.product(range(2),(0,1)):
            witness=next((c for c in selected if c[1]==cpu and c[6]==resume and c[5]!=0),None)
            if witness is not None:chosen.append(witness)
        chosen=sorted(set(chosen));rejected=0;reasons=set();first=None
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
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(data[lo-pinned.BASE:hi-pinned.BASE]) for lo,hi in RANGES},
            'literal_sha256':{f'{pc:x}':pinned.digest(data[pc-pinned.BASE:pc-pinned.BASE+4]) for pc in LITERALS}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--family',choices=('yield','wrapper','records'),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-sh2-context-handoff.v1','experiment':'EXP-SAT-CODE-020','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,
            'interpreter_sources':pinned.SOURCE_HASHES,'source_sha256':{name:pinned.digest(Path(__file__).with_name(name).read_bytes())
                for name in ('probe_context_handoff.py','sh2_handoff_profile.py','probe_kernel_records.py','probe_kernel.py',
                             'probe_split_add.py','probe_position_bounds.py')},
            'selection':args.family,'max_steps_per_phase':profile.MAX_STEPS,'original_game_bytes_executed':False,
            'limitations':['Constructed outbound root context and controlled resume ABI; no natural task code executed',
                           'Incomplete handoffs remain separate from complete activations; actual saved context feeds resume',
                           'CPU-only, no natural caller/scheduler/hardware timing/independent-engine validation',
                           'Explicit known high RAM views only; whole executable/function/dynamic-target denominators unknown']}
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
