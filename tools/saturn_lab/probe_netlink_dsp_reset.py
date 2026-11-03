#!/usr/bin/env python3
"""Complete constructed NLSND DSP reset helpers; command10 remains diagnostic."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import analyze_sound_driver as sound
import m68k_scsp_long as native
import m68k_scsp_slots as previous
import probe_netlink_pointer as leaf
import probe_netlink_records as records
import probe_netlink_slot_effects as effects
import probe_netlink_low_reset as low

# Entry, destination, longword count, prefix PCs, count-byte mutation, new target.
MODES={
 'program':(0x3592,0x800,256,[0x3592,0x3596,0x359A,0x35B2],0x3599,0xFE,0x880),
 'madrs':(0x359C,0x780,32,[0x359C,0x35A0,0x35A2,0x35B2],0x35A1,0x1E,0x700),
 'coef':(0x35A4,0x700,32,[0x35A4,0x35A8,0x35AA,0x35B2],0x35A9,0x1E,0x780),
 'temp':(0x35AC,0xC00,128,[0x35AC,0x35B0,0x35B2],0x35B1,0x7E,0xA00)}
MASK=0xFFFFFFFF


def selection():
    cases=set(itertools.product(MODES,(0,1,0x12345678,0x80000000,MASK),effects.SR_VALUES,(0,1)))
    cases.update(('temp',seed,0x271F,0) for seed in range(256))
    return sorted(cases)


def contract(mode,seed,sr,variant,device):
    if (mode not in MODES or type(seed) is not int or not 0<=seed<=MASK or sr not in effects.SR_VALUES
            or type(variant) is not int or variant not in (0,1)):raise ValueError('Undeclared reset case')
    entry,offset,count,prefix,*_=MODES[mode];regs=records.base_regs(entry,sr)
    if variant:regs[:15]=[v^MASK for v in regs[:15]]
    regs[13]=0x100000
    stack=bytes((seed+i*29)&255 for i in range(16))+leaf.STOP.to_bytes(4,'big')+bytes([0xAD])*16
    regions=[(leaf.SP-16,stack,False)];after=list(regs)
    after[0]=0;after[7]=((regs[7]&0xFFFF0000) if mode=='program' else 0)|65535
    after[9]=0x100000+offset+4*count;after[15:18]=[leaf.SP+4,leaf.STOP,(sr&~15)|4]
    changed={**device,mode:([0]*128 if mode in ('program','temp') else [0]*64 if mode=='coef' else [0]*32)}
    if mode=='program':changed.pop('program');changed['mprog']=[0]*128;changed['dirty']=1
    events=[[2,0x100000+offset+4*i,4,0] for i in range(count)]+[[1,leaf.SP,4,leaf.STOP]]
    pcs=prefix+[pc for _ in range(count) for pc in (0x35B4,0x35B6)]+[0x35BA]
    bus=[[2,0x100000+offset+2*i,2,0] for i in range(count*2)]
    expected={'registers':after,'regions_after':[stack],'device_after':changed,'events':events,'pcs':pcs,'steps':len(pcs),'reference_bus_events':bus}
    return regs,regions,expected


def run_case(code,library,case):
    regs,regions,_=contract(*case,{})
    actual=library.run(code,regs[16],leaf.STOP,[(regs[16],0x35BC)],regions,regs,budget=600,device=(case[1],case[1]&1))
    effects.compare(actual,contract(*case,actual['device_before'])[2]);return actual


def controls(code,library):
    results={}
    for mode,(entry,offset,count,prefix,count_at,count_value,target) in MODES.items():
        edits=[('value',0x35B3,b'\x01'),('count',count_at,bytes([count_value])),('destination',entry+2,target.to_bytes(2,'big'))]
        if mode!='temp':edits.append(('branch',prefix[2]+1,bytes([0x35B4-(prefix[2]+2)])))
        for name,at,replacement in edits:
            changed=bytearray(code);changed[at:at+len(replacement)]=replacement;rejected=0;reasons=set()
            for seed,variant in itertools.product((0x12345678,MASK),(0,1)):
                case=(mode,seed,0x271F,variant);regs,regions,_=contract(*case,{})
                actual=library.run(changed,entry,leaf.STOP,[(entry,0x35BC)],regions,regs,budget=600,device=(seed,seed&1))
                if actual['status_code']!=1:raise ValueError('Mutation did not reach terminal reset semantics')
                try:effects.compare(actual,contract(*case,actual['device_before'])[2])
                except ValueError as error:rejected+=1;reasons.add(str(error))
                else:raise ValueError('Terminal reset mutation escaped independent comparison')
            results[mode+'_'+name]={'offset':hex(at),'replacement_hex':replacement.hex(),'terminal_tested':4,'rejected':rejected,'reasons':sorted(reasons),'changed_source_sha256':hashlib.sha256(changed).hexdigest()}
    return results


def helpers(code,library):
    digest=hashlib.sha256();counts=Counter();steps={};cycles={}
    for case in selection():
        actual=run_case(code,library,case);mode=case[0];counts[mode]+=1;steps[mode]=actual['steps'];cycles.setdefault(mode,set()).add(actual['model_cycles'])
        row={'case':case,'registers':actual['registers'],'events':actual['events'],'pcs':actual['pcs'],'reference_bus_events':actual['reference_bus_events'],'model_cycles':actual['model_cycles'],
             'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest()}
        digest.update(json.dumps(row,sort_keys=True).encode()+b'\n')
    return {'cases':len(selection()),'cases_by_mode':dict(counts),'instructions':steps,'model_cycles':{k:sorted(v) for k,v in cycles.items()},'observations_sha256':digest.hexdigest(),
            'prefixes_sha256':{mode:hashlib.sha256(code[entry:{'program':0x359C,'madrs':0x35A4,'coef':0x35AC,'temp':0x35B2}[mode]]).hexdigest() for mode,(entry,offset,count,prefix,*_) in MODES.items()},
            'common_loop_sha256':hashlib.sha256(code[0x35B2:0x35BC]).hexdigest(),'terminal_mutations':controls(code,library),'all_registers_sr_pcs_operands_reference_bus_ram_device_compared':True,'natural_execution':False}


def command10(code,oldlib,library):
    rows=[]
    for mode,variant,mask,ranges,entry,regs,regions in effects.command10_inputs():
        low_region=low.low_region(0x12345678^mask);mapped=[*regions,low_region]
        before=oldlib.run(code,entry,leaf.STOP,ranges,mapped,regs,budget=8192)
        actual=library.run(code,entry,leaf.STOP,ranges,mapped,regs,budget=8192)
        if before['status_code']==1:
            for key in ('status_code','steps','error_address','error_size','registers','events','pcs','regions_after','model_cycles','code_unchanged'):
                if actual[key]!=before[key]:raise ValueError('Previous complete CPU/RAM result changed: '+key)
            for key in ('coef','madrs','mprog','dirty','slot_values','slot_unrelated_sha256'):
                if actual['device_after'][key]!=before['device_after'][key]:raise ValueError('Previous common device outcome changed: '+key)
            if (before['device_before']['unrelated_sha256']!=before['device_after']['unrelated_sha256'] or
                    actual['device_before']['unrelated_sha256']!=actual['device_after']['unrelated_sha256'] or
                    actual['device_before']['temp']!=actual['device_after']['temp']):raise ValueError('Previously untouched state changed')
            comparison='previous-complete-CPU-RAM-common-device-identical'
        else:
            if (actual['events'][:len(before['events'])]!=before['events'] or actual['pcs'][:before['steps']]!=before['pcs']
                    or actual['steps']<=before['steps'] or actual['status_code'] in (2,6)):
                raise ValueError('Previous DSP guard prefix not preserved/extended')
            comparison='previous-DSP-width-guard-extended'
        if not actual['code_unchanged']:raise ValueError('Original code changed')
        ram=actual['regions_after'][-1]
        if ram[:16]!=low_region[1][:16] or ram[32:]!=low_region[1][32:]:raise ValueError('Low-data neighbors changed')
        rows.append({'mode':mode,'variant':variant,'mask':mask,'comparison':comparison,'status':actual['status'],'status_code':actual['status_code'],'steps':actual['steps'],'prior_steps':before['steps'],
                     'error_address':hex(actual['error_address']),'error_size':actual['error_size'],'last_pc':hex(actual['pcs'][-1]),'tail_pcs':actual['pcs'][-8:],'tail_events':actual['events'][-8:],
                     'registers':actual['registers'],'model_cycles':actual['model_cycles'],'reference_bus_events':len(actual['reference_bus_events']),
                     'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
                     'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest(),'code_unchanged':True,'independent_full_semantics_accepted':False})
    return {'cases':len(rows),'outcomes':dict(Counter(r['status']+'@'+r['error_address'] for r in rows)),'previous_complete_CPU_RAM_common_device_identical':sum(r['status_code']==1 and r['comparison'].startswith('previous-complete') for r in rows),
            'extended_DSP_guards':sum(r['comparison']=='previous-DSP-width-guard-extended' for r in rows),'diagnostic_returns':sum(r['status_code']==1 for r in rows),
            'results':rows,'full_semantic_contract_accepted':False,'fixture_difference':'ABI8 normalises TEMP to24-bit signed and removes TEMP from untouched hash; common fields compared directly and previously untouched bytes/TEMP checked unchanged within each profile'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-file',type=Path,required=True);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--previous-prepared',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-DSP-long-reset.v1','status':'failure','original_game_bytes_executed':False,'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'native_identity':native.identity(),'scope':'Four complete constructed reset helpers and separate guarded command10; no natural/timing/audio/hardware/full-command or whole-game claim'}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a new private path');return 1
    with os.fdopen(fd,'w') as out:
        phase='source_identity'
        try:
            code=sound.source_bytes(a.source_file,'NLSND');phase='native_load';library=native.Library(a.prepared);oldlib=previous.Library(a.previous_prepared)
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),native_binary_sha256=hashlib.sha256(library.path.read_bytes()).hexdigest(),previous_binary_sha256=hashlib.sha256(oldlib.path.read_bytes()).hexdigest())
            phase='helpers';report['original_game_bytes_executed']=True;report['helpers']=helpers(code,library)
            phase='command10_diagnostic';report['command10']=command10(code,oldlib,library);report['status']='success'
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'message':str(error)}
        finally:out.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'helper_cases':report.get('helpers',{}).get('cases'),'full_command10_accepted':False}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
