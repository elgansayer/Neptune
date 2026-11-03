#!/usr/bin/env python3
"""Constructed NLSND3530 fixed-data clear and guarded command10 continuation.

No natural caller, timing, audio or independent complete command10 claim.
Only the pinned NLSND lifetime declares the16-byte data object at0780.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import analyze_sound_driver as sound
import m68k_scsp_slots as native
import probe_netlink_pointer as leaf
import probe_netlink_records as records
import probe_netlink_slot_effects as effects

ENTRY,END,LOW,EXTENT=0x3530,0x3540,0x780,16
PCS=[0x3530,0x3532,0x3536,0x3538,0x353A,0x353C,0x353E]
MASK=0xFFFFFFFF


def selection():
    cases=set(itertools.product((0,1,0x12345678,0x80000000,MASK),effects.SR_VALUES,(0,1)))
    cases.update((seed,0x271F,0) for seed in range(256))
    return sorted(cases)


def low_region(seed):
    #16-byte canaries on either side; only0780..078F is the declared object.
    return LOW-16,bytes(((seed>>(8*(i%4)))+i*37)&255 for i in range(48)),True


def contract(seed,sr,variant,before_device):
    if (type(seed) is not int or not 0<=seed<=MASK or sr not in effects.SR_VALUES
            or type(variant) is not int or variant not in (0,1)):
        raise ValueError('Undeclared fixed-data clear case')
    regs=records.base_regs(ENTRY,sr)
    if variant:regs[:15]=[v^MASK for v in regs[:15]]
    stack=bytes((seed+i*29)&255 for i in range(16))+leaf.STOP.to_bytes(4,'big')+bytes([0xAD])*16
    regions=[low_region(seed),(leaf.SP-16,stack,False)]
    after=list(regs);after[0]=0;after[8]=LOW+EXTENT
    after[15:18]=[leaf.SP+4,leaf.STOP,(sr&~15)|4]
    ram=bytearray(regions[0][1]);ram[16:32]=bytes(EXTENT)
    expected={'registers':after,'pcs':PCS,'steps':len(PCS),'events':[[2,LOW+i,4,0] for i in range(0,EXTENT,4)]+[[1,leaf.SP,4,leaf.STOP]],
              'regions_after':[bytes(ram),stack],'device_after':before_device}
    return regs,regions,expected


def run_case(code,library,case):
    regs,regions,_=contract(*case,{})
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END)],regions,regs,budget=16,device=(case[0],case[0]&1))
    effects.compare(actual,contract(*case,actual['device_before'])[2])
    return actual


def semantic_controls(code,library):
    controls={}
    for name,offset,replacement in (('changed_value',0x3531,b'\x01'),('missing_write',0x353C,b'\x4e\x71'),
                                    ('shifted_destination',0x3535,b'\x84')):
        changed=bytearray(code);changed[offset:offset+len(replacement)]=replacement
        reasons=set();rejected=0
        for seed,variant in itertools.product((0x12345678,MASK),(0,1)):
            regs,regions,_=contract(seed,0x271F,variant,{})
            actual=library.run(changed,ENTRY,leaf.STOP,[(ENTRY,END)],regions,regs,budget=16,device=(seed,seed&1))
            if actual['status_code']!=1:raise ValueError('Mutation did not reach terminal semantics')
            try:effects.compare(actual,contract(seed,0x271F,variant,actual['device_before'])[2])
            except ValueError as error:rejected+=1;reasons.add(str(error))
            else:raise ValueError('Terminal changed original escaped the independent contract')
        controls[name]={'offset':hex(offset),'replacement_hex':replacement.hex(),'terminal_tested':4,'rejected':rejected,
                        'reasons':sorted(reasons),'changed_source_sha256':hashlib.sha256(changed).hexdigest()}
    return controls


def helpers(code,library):
    digest=hashlib.sha256();cycles=set();steps=set()
    for case in selection():
        actual=run_case(code,library,case);steps.add(actual['steps']);cycles.add(actual['model_cycles'])
        row={k:v for k,v in actual.items() if k not in ('regions_after','device_before','device_after')}
        row.update(case=case,regions_after_sha256=[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
                   unchanged_device_sha256=hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest())
        digest.update(json.dumps(row,sort_keys=True).encode()+b'\n')
    return {'cases':len(selection()),'instructions':sorted(steps),'model_cycles':sorted(cycles),'observations_sha256':digest.hexdigest(),
            'range_sha256':hashlib.sha256(code[ENTRY:END]).hexdigest(),'terminal_mutations':semantic_controls(code,library),
            'all_visible_registers_sr_pcs_events_ram_device_compared':True,'natural_execution':False}


def command10(code,library):
    rows=[]
    for mode,variant,mask,ranges,entry,regs,regions in effects.command10_inputs():
        before=library.run(code,entry,leaf.STOP,ranges,regions,regs,budget=8192)
        region=low_region(0x12345678^mask)
        actual=library.run(code,entry,leaf.STOP,ranges,[*regions,region],regs,budget=8192)
        trimmed={**actual,'regions_after':actual['regions_after'][:-1]}
        prior_low=before['status_code']==5 and before['error_address']==LOW and before['error_size']==4
        if prior_low:
            if (actual['events'][:len(before['events'])]!=before['events'] or actual['pcs'][:before['steps']]!=before['pcs']
                    or actual['steps']<=before['steps'] or actual['status_code'] in (2,6)):
                raise ValueError('Previous low-data guard prefix was not preserved/extended')
            comparison='previous-low-data-guard-extended'
        else:
            if trimmed!=before:raise ValueError('Previous complete/device-guard outcome changed')
            comparison='previous-outcome-identical'
        low_after=actual['regions_after'][-1]
        if low_after[:16]!=region[1][:16] or low_after[32:]!=region[1][32:]:raise ValueError('Low-data neighbor changed')
        if not actual['code_unchanged']:raise ValueError('Original code changed')
        rows.append({'mode':mode,'variant':variant,'mask':mask,'comparison':comparison,'prior_steps':before['steps'],
                     'status':actual['status'],'status_code':actual['status_code'],'steps':actual['steps'],
                     'error_address':hex(actual['error_address']),'error_size':actual['error_size'],
                     'last_pc':hex(actual['pcs'][-1]),'tail_pcs':actual['pcs'][-8:],'tail_events':actual['events'][-8:],
                     'registers':actual['registers'],'model_cycles':actual['model_cycles'],
                     'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
                     'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest(),
                     'code_unchanged':True,'independent_command10_semantics_accepted':False})
    return {'cases':len(rows),'outcomes':dict(Counter(r['status']+'@'+r['error_address'] for r in rows)),
            'previous_outcomes_identical':sum(r['comparison']=='previous-outcome-identical' for r in rows),
            'previous_low_data_guards_extended':sum(r['comparison']=='previous-low-data-guard-extended' for r in rows),
            'diagnostic_returns':sum(r['status_code']==1 for r in rows),'results':rows,'full_semantic_contract_accepted':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args(argv)
    report={'schema':'neptune.original-low-reset.v1','status':'failure','original_game_bytes_executed':False,
            'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_identity':native.identity(),
            'scope':'Constructed fixed-address clear and separate guarded command10; natural lifetime/timing/audio/full-game open'}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a new writable private path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND')
            phase='native_load';library=native.Library(args.prepared)
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),native_binary_sha256=hashlib.sha256(library.path.read_bytes()).hexdigest(),original_game_bytes_executed=True)
            phase='helper_comparison';report['helper']=helpers(code,library)
            phase='command10_diagnostic';report['command10']=command10(code,library);report['status']='success'
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'message':str(error)}
        finally:output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'helper_cases':report.get('helper',{}).get('cases'),'full_command10_accepted':False}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
