#!/usr/bin/env python3
"""Original SH-2 context save/restore, with preserved entry PR and bounded RAM."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
from types import SimpleNamespace

import probe_kernel as pinned
import probe_kernel_records as records
import sh2_profile

SAVE,RESTORE,END=0x060061C4,0x060061E6,0x0600620A
CTX=0x060CF100
MAX_STEPS=64
WORDS=(0,1,2,0x7F,0xFF,0x100,0xFFFF,0x10000,0x7FFFFFFF,0x80000000,0xFFFFFFFE,0xFFFFFFFF)


def observe(data,emu,entry,regions,before,budget=MAX_STEPS):
    """Use original step/exec/fetch; unlike CPU.call, do not reset entry PR.

    Termination is still the fixed non-executable sentinel. No new executable
    targets, instruction allowance or alias permission is granted by this driver.
    """
    if not 0<budget<=MAX_STEPS:raise ValueError('Invalid context instruction budget')
    class ContextCPU(emu.CPU):
        def call(self,entry,max_steps,**kwargs):
            if kwargs:raise ValueError('Unexpected argument overrides')
            self.pc=entry
            while self.pc!=emu.RETURN_SENTINEL:
                self.step()
                if self.steps>max_steps:raise ValueError('Context instruction budget exceeded')
            return self.r[0]
    facade=SimpleNamespace(CPU=ContextCPU,Memory=emu.Memory,RETURN_SENTINEL=emu.RETURN_SENTINEL)
    return sh2_profile.observe(data,facade,entry,[(lo,buf,entry==SAVE) for lo,buf in regions],before,
                               ranges=((SAVE,RESTORE),) if entry==SAVE else ((RESTORE,END),),
                               literals=(),aliases=(),budget=budget)


def vector(selector):
    # Uniform words plus distinct per-field walking-one/complement patterns.
    if selector<len(WORDS):return [WORDS[selector]]*24
    bit=(selector-len(WORDS))//2;invert=(selector-len(WORDS))%2
    return [((1<<((bit+5*i)%32))^(0xFFFFFFFF if invert else 0)) for i in range(24)]


def contract(case):
    kind,selector,offset,variant=case;entry=SAVE if kind=='save' else RESTORE
    values=vector(selector);before=records.initial(entry,CTX+offset,variant)
    for i in range(16):
        if i!=4:before[f'r{i}']=values[i]^(0x5A5A5A5A if kind=='restore' else 0)
    before.update(macl=values[16],mach=values[17],gbr=values[18],vbr=values[19],
                  pr=0xFFFFFFF0 if kind=='save' else values[20])
    address=CTX+offset
    buf=bytearray((i*37+19+variant*83)&255 for i in range(80))
    if kind=='restore':
        for i in range(12):buf[16+i*4:20+i*4]=values[(i+7)%24].to_bytes(4,'big')
        buf[16+36:20+36]=(0xFFFFFFF0).to_bytes(4,'big')
    model=records.Model(before,[(address-16,bytes(buf))]);r=model.reg
    if kind=='save':
        for pc,field,reg in ((SAVE,0,'r8'),(SAVE+2,4,'r8'),(SAVE+4,8,'r9'),(SAVE+6,12,'r10'),
                             (SAVE+8,16,'r11'),(SAVE+10,20,'r12'),(SAVE+12,24,'r13'),
                             (SAVE+14,28,'r14'),(SAVE+16,32,'r15')):
            model.step(pc);model.write(address+field,4,r[reg])
        model.step(0x060061D6);r['r0']=r['mach']
        model.step(0x060061D8);model.write(address+40,4,r['r0'])
        model.step(0x060061DA);r['r0']=r['macl']
        model.step(0x060061DC);model.write(address+44,4,r['r0'])
        model.step(0x060061DE);r['r0']=r['pr']
        model.step(0x060061E0);model.write(address+36,4,r['r0'])
        model.step(0x060061E2)
        model.step(0x060061E4,True);r['r0']=0
    else:
        for i in range(8):
            model.step(RESTORE+2*i);r[f'r{i+8}']=model.read(address+4+4*i,4)
        model.step(0x060061F6);r['r0']=model.read(address+44,4)
        model.step(0x060061F8);r['macl']=r['r0']
        model.step(0x060061FA);r['r0']=model.read(address+40,4)
        model.step(0x060061FC);r['mach']=r['r0']
        model.step(0x060061FE);r['r0']=model.read(address+36,4)
        model.step(0x06006200);r['pr']=r['r0']
        model.step(0x06006202);r['r0']=model.read(address,4)
        model.step(0x06006204);r['r4']=r['r0']
        model.step(0x06006206)
        model.step(0x06006208,True);r['r0']=r['r5']
    r['pc']=0xFFFFFFF0
    return entry,model


class CaseFailure(ValueError):
    def __init__(self,reason,case,actual):
        super().__init__(reason)
        self.evidence={'case':list(case),'actual':{k:v for k,v in actual.items() if k!='regions_after'},
                       'regions_after_sha256':[pinned.digest(buf) for buf in actual['regions_after']]}


def run_case(data,emu,case):
    entry,expected=contract(case);actual=observe(data,emu,entry,expected.regions,expected.before)
    reason=None
    if actual['status']!='returned':reason='Original execution failed: '+str(actual['error'])
    elif actual['registers']!=expected.reg:reason='Register/PC/SR/PR/MAC result differs'
    elif actual['trace']!=expected.trace or actual['steps']!=len(expected.trace):reason='Executed PC/delay path differs'
    elif actual['events']!=expected.events:reason='Exact read/write transactions differ'
    elif actual['regions_after']!=[bytes(b) for b in expected.buffers] or not actual['original_unaffected_bytes_equal']:
        reason='Controlled output/canaries or original bytes differ'
    if reason:raise CaseFailure(reason,case,actual)
    return {'case':list(case),'instructions':actual['steps'],'after_registers':actual['registers'],
            'trace':actual['trace'],'data_events':actual['events'],'all_visible_registers_checked':True,
            'unaffected_bytes_equal':True,'return_sentinel_reached':True}


def cases():
    return list(itertools.product(('save','restore'),range(len(WORDS)+64),(0,4,256),range(2)))


def owned_smoke(emu):
    data=bytearray(pinned.SIZE);o=SAVE-pinned.BASE
    data[o:o+6]=bytes.fromhex('402a 000b 0009')  # authored LDS R0,PR; RTS; NOP
    before={**records.initial(SAVE,CTX,0),'pr':0xDEADBEEF,'r0':0xFFFFFFF0}
    good=observe(data,emu,SAVE,[],before)
    if (good['status']!='returned' or good['registers']!={**before,'pr':0xFFFFFFF0,'pc':0xFFFFFFF0}
        or good['trace']!=[[SAVE,False],[SAVE+2,False],[SAVE+4,True]] or good['events']
        or not good['original_unaffected_bytes_equal']):raise ValueError('Owned preserved-entry-PR smoke failed')
    controls={}
    for name,words,registers,reason in (
        ('missing_PR_load','0009 000b 0009',before,'Instruction fetch outside declared code'),
        ('unknown_read','6012 000b 0009',{**before,'r1':0x060D0000},'Read outside literals and controlled inputs'),
        ('undeclared_alias','6012 000b 0009',{**before,'r1':CTX|0x20000000},'Read through undeclared alias'),
        ('code_write','2102 000b 0009',{**before,'r1':SAVE},'Write outside writable canonical inputs'),
        ('bounded_loop','affe 0009',before,'Local instruction budget exceeded')):
        image=bytearray(data);blob=bytes.fromhex(words);image[o:o+len(blob)]=blob
        result=observe(image,emu,SAVE,[],registers,budget=8)
        if result['status']!='failed' or result['error']['reason']!=reason:raise ValueError('Owned guard failed: '+name)
        controls[name]={'status':result['status'],'reason':reason,'executed_instructions':len(result['trace'])}
    if observe(data,emu,SAVE,[],before)!=good:raise ValueError('Owned recovery differs')
    return {'original_game_bytes_executed':False,'entry_PR_preserved':True,'owned_PR_restore_reached_sentinel':True,
            'failure_controls':controls,'fresh_after_failure':True}


def execute(data,emu,kind):
    selected=[c for c in cases() if c[0]==kind];rows=[run_case(data,emu,c) for c in selected]
    controls={}
    for name,pc,word,family in (
        ('save_second_R8_from_R9',0x060061C6,0x1491,'save'),
        ('save_MACH_in_MACL_field',0x060061D8,0x140B,'save'),
        ('missing_save_zero_delay',0x060061E4,0x0009,'save'),
        ('missing_restore_SP',0x060061F4,0x0009,'restore'),
        ('missing_restore_PR',0x06006200,0x0009,'restore'),
        ('missing_restore_R4',0x06006204,0x0009,'restore'),
        ('missing_restore_result_delay',0x06006208,0x0009,'restore')):
        if family!=kind:continue
        changed=bytearray(data);o=pc-pinned.BASE;changed[o:o+2]=word.to_bytes(2,'big')
        rejected=0;reasons=set();first_rejection=None;chosen=selected[::max(1,len(selected)//64)]
        for c in chosen:
            try:run_case(changed,emu,c)
            except ValueError as fault:
                if 'budget exceeded' in str(fault):raise ValueError('Budget failure is not semantic evidence')
                rejected+=1;reasons.add(str(fault))
                if first_rejection is None and isinstance(fault,CaseFailure):first_rejection=fault.evidence
        if not rejected:raise ValueError('Altered original survived selected cases: '+name)
        controls[name]={'pc':pc,'tested':len(chosen),'rejected':rejected,'reasons':sorted(reasons),
                        'mutated_kernel_sha256':pinned.digest(changed),'first_rejection':first_rejection}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':{f'{lo:x}:{hi:x}':pinned.digest(data[lo-pinned.BASE:hi-pinned.BASE])
                            for lo,hi in ((SAVE,RESTORE),(RESTORE,END))}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel',type=Path,required=True);parser.add_argument('--saturn-recomp',type=Path,required=True)
    parser.add_argument('--kind',choices=('save','restore'),required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-sh2-kernel-context.v1','experiment':'EXP-SAT-CODE-018','status':'failure',
            'release':'usa-mk81070-v1003','module':'KRNL','cpu':'sh2','load_address':pinned.BASE,'lifetime':'resident-kernel',
            'kernel_sha256':pinned.KERNEL_SHA256,'interpreter_revision':pinned.INTERPRETER_REVISION,
            'interpreter_sources':pinned.SOURCE_HASHES,'source_sha256':{name:pinned.digest(Path(__file__).with_name(name).read_bytes())
                for name in ('probe_kernel_context.py','sh2_profile.py','probe_kernel_records.py','probe_kernel.py',
                             'probe_split_add.py','probe_position_bounds.py')},
            'selection':args.kind,'entry_PR_preserved':True,'max_steps_per_call':MAX_STEPS,
            'original_game_bytes_executed':False,'limitations':[
                'Constructed48-byte context/registers; restore saved PR fixed to non-executable sentinel',
                'Selected CPU-only routines, no natural caller/scheduler or hardware/timing/independent-engine proof',
                'No new executable targets or aliases; whole executable/function/dynamic-target denominators unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            data=pinned.kernel_bytes(args.kernel);emu=pinned.interpreter(args.saturn_recomp)
            phase='owned_smoke';report['owned_smoke']=owned_smoke(emu)
            phase='original_execution';report['original_game_bytes_executed']=None
            report.update(execute(data,emu,args.kind),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':str(error)}
            if isinstance(error,CaseFailure):report['failure_evidence']=error.evidence;report['original_game_bytes_executed']=True
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'selection':args.kind}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
