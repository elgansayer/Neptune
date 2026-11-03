#!/usr/bin/env python3
"""Original NLSND slot-reset helper contracts and bounded command10 continuation.

Constructed original instructions, clock-frozen reference devices. No natural
caller, audio, timing, complete command10 or whole-game semantic acceptance.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import m68k_scsp_slots as native
import m68k_reset_capacity as previous
import analyze_sound_driver as sound
import probe_netlink_records as records
import probe_netlink_pointer as leaf

MODES={'release':(0x3540,0x355A),'send':(0x355A,0x356E),'volume':(0x356E,0x3592)}
SR_VALUES=(0x2700,0x271F,0x200A,0x2015)
MASK=0xFFFFFFFF


def selection():
    cases=set(itertools.product(MODES,(0,0x12345678,0xFFFFFFFF),SR_VALUES,(0,1),(0,1,16)))
    cases.update(('release',seed,0x271F,0,0) for seed in range(256))
    cases.update((mode,seed,0x271F,variant,base) for mode in ('send','volume')
                 for seed in (0,0x12345678,0xFFFFFFFF) for variant in (0,1) for base in range(17))
    return sorted(cases)


def helper_inputs(mode,seed,sr,variant,base):
    entry,end=MODES[mode];regs=records.base_regs(entry,sr)
    if variant:regs[:15]=[v^MASK for v in regs[:15]]
    regs[13]=0x100000+base*32;regs[14]=0x7000 if variant==0 else 0x50000
    ram=bytes((i*37+seed)&255 for i in range(0x2000))
    regions=[(regs[14],ram,True),(leaf.SP,leaf.STOP.to_bytes(4,'big'),False)]
    return entry,end,regs,regions


def helper_contract(mode,regs,regions,before):
    after=list(regs);device=before;events=[];memory=[v for _,v,_ in regions]
    if mode=='release':
        count,lane,base=32,11,0x100000
        pcs=[0x3540,0x3546,0x354A]+[pc for _ in range(32) for pc in (0x354C,0x3550,0x3554)]+[0x3558]
        for slot in range(32):
            address=base+slot*32+lane
            value=device['slot_values'][slot*native.STRIDE+5]&255
            events.extend(([1,address,1,value],[2,address,1,value|31]))
            device=native.transition(device,address,value|31)
        flags=8 if (value|31)&128 else 0;after[13]=base
    else:
        count,lane,base=16,21 if mode=='send' else 23,regs[13]
        prefix=(0x355A,0x355E,0x3560) if mode=='send' else (0x356E,0x3572,0x3574)
        loop=(0x3562,0x3564,0x3568) if mode=='send' else (0x3576,0x3578,0x357C)
        tail=[0x356C] if mode=='send' else [0x3580,0x3584,0x3588,0x358C,0x3590]
        pcs=list(prefix)+[pc for _ in range(16) for pc in loop]+tail
        for slot in range(count):
            address=base+slot*32+lane;events.append([2,address,1,0]);device=native.transition(device,address,0)
        if mode=='volume':
            ram=bytearray(memory[0]);ram[0x187E:0x188E]=bytes(16);memory[0]=bytes(ram)
            events.extend([2,regs[14]+offset,4,0] for offset in (0x187E,0x1882,0x1886,0x188A))
        after[0]=0;flags=4
    after[7]=65535;after[9]=base+lane+count*32
    after[15:18]=[leaf.SP+4,leaf.STOP,(regs[17]&~15)|flags]
    events.append([1,leaf.SP,4,leaf.STOP])
    return {'registers':after,'pcs':pcs,'events':events,'regions_after':memory,'device_after':device}


def compare(actual,expected):
    if actual['status_code']!=1:raise ValueError('Incomplete original helper: '+actual['status'])
    if not actual['code_unchanged']:raise ValueError('Original code changed')
    for key,value in expected.items():
        if actual[key]!=value:raise ValueError('Independent original helper mismatch: '+key)


def run_helper(code,library,case):
    mode,seed,*_=case;entry,end,regs,regions=helper_inputs(*case)
    actual=library.run(code,entry,leaf.STOP,[(entry,end)],regions,regs,budget=128,device=(seed,seed&1))
    compare(actual,helper_contract(mode,regs,regions,actual['device_before']))
    return actual


def helpers(code,library):
    counts=Counter();step_bounds={};cycle_bounds={};observations=hashlib.sha256();samples=[]
    cases=selection()
    for case in cases:
        actual=run_helper(code,library,case);mode=case[0];counts[mode]+=1
        for bounds,key in ((step_bounds,'steps'),(cycle_bounds,'model_cycles')):
            value=actual[key];old=bounds.get(mode,[value,value]);bounds[mode]=[min(old[0],value),max(old[1],value)]
        row={'case':case,'registers':actual['registers'],'events':actual['events'],'pcs':actual['pcs'],
             'model_cycles':actual['model_cycles'],'regions_after_sha256':[hashlib.sha256(v).hexdigest() for v in actual['regions_after']],
             'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest()}
        observations.update(json.dumps(row,sort_keys=True).encode()+b'\n')
        if case[1]==0 and case[2]==0x271F and case[3]==0 and case[4]==0:samples.append(row)
    controls={}
    for name,mode,offset,replacement in (
        ('release_mask','release',0x354F,0x1E),('release_count','release',0x354B,0x1E),
        ('send_lane','send',0x355D,0x17),('send_count','send',0x355F,0x0E),
        ('volume_lane','volume',0x3571,0x15),('volume_ram_destination','volume',0x358F,0x8E)):
        changed=bytearray(code);changed[offset]=replacement;rejected=0;reasons=set()
        for seed,variant in itertools.product((0,0xFFFFFFFF),(0,1)):
            case=(mode,seed,0x271F,variant,0);entry,end,regs,regions=helper_inputs(*case)
            actual=library.run(changed,entry,leaf.STOP,[(entry,end)],regions,regs,budget=128,device=(seed,seed&1))
            if actual['status_code']!=1:raise ValueError('Mutation failed before terminal helper semantics')
            try:compare(actual,helper_contract(mode,regs,regions,actual['device_before']))
            except ValueError as error:rejected+=1;reasons.add(str(error))
            else:raise ValueError('Terminal changed helper escaped independent contract')
        controls[name]={'offset':hex(offset),'replacement_byte':replacement,'tested_terminal':4,'rejected':rejected,
                        'reasons':sorted(reasons),'changed_driver_sha256':hashlib.sha256(changed).hexdigest()}
    return {'cases':len(cases),'cases_by_mode':dict(counts),'instruction_bounds':step_bounds,'model_cycle_bounds':cycle_bounds,
            'observations_sha256':observations.hexdigest(),'terminal_mutations':controls,'samples':samples,
            'ranges':MODES,'range_sha256':{mode:hashlib.sha256(code[lo:hi]).hexdigest() for mode,(lo,hi) in MODES.items()},
            'all_visible_registers_sr_events_pcs_ram_device_compared':True,'natural_execution':False}


def command10(code,oldlib,library):
    ranges=[(0x1640,0x167A),(0x1DEA,0x1E2E),(0x1E68,0x1EEE),(0x3530,0x35BC),
            (0x4412,0x4442),(0x4B00,0x4B6E),(0x4BB6,0x4BE0),(0x4C2A,0x4C9A),(0x17F2,0x18F2)]
    rows=[]
    for mode,variant,mask in itertools.product(('handler','dispatcher'),(0,1),range(32)):
        entry=0x1E68 if mode=='handler' else 0x17F2;regs=records.base_regs(entry,0x271F if variant==0 else 0x2015)
        if variant:regs[:15]=[r^MASK for r in regs[:15]]
        regs[7]=(regs[7]&0xFFFF0000)|0x10;regs[8]=0x40000;regs[13]=0x100000;regs[14]=0x24000
        pool=bytearray(0x2800);ram=bytearray(0x2000)
        for i in range(8):pool[0x2100+i*0x60+1]=i
        if variant:
            pool[0x1840]=254
            for i in range(32):
                at=0x2400+i*12;pool[at]=0x80|(i&1);pool[at+1:at+4]=bytes((i,127,64))
                pool[at+8:at+12]=(0x22100+(i%8)*0x60).to_bytes(4,'big')
            ram[0x1890:0x18A0]=bytes(0x80+i for i in range(16))
        payload=bytes(1 if mask&(1<<i) else 0 for i in range(5))
        regions=[(0x450,(0x20000).to_bytes(4,'big'),False),(0x404,(0x30000).to_bytes(4,'big'),False),
                 (0x7000,bytes(ram),True),(0x20000,bytes(pool),True),(0x30000,bytes([0xAD])*768,True),
                 (0x40000,payload,False),(leaf.SP-256,bytes([0xCD])*256+leaf.STOP.to_bytes(4,'big'),True)]
        if any(lo+len(data)>0x100000 for lo,data,w in regions):raise ValueError('No fake device RAM')
        before=oldlib.run(code,entry,leaf.STOP,ranges,regions,regs,budget=8192)
        actual=library.run(code,entry,leaf.STOP,ranges,regions,regs,budget=8192)
        remove_slots=lambda d:{k:v for k,v in d.items() if not k.startswith('slot_')}
        if before['device_before']!=remove_slots(actual['device_before']):raise ValueError('Previous DSP fixture changed')
        if before['status_code']==1:
            normalized={**actual,'device_before':remove_slots(actual['device_before']),'device_after':remove_slots(actual['device_after'])}
            if normalized!=before or actual['device_after']!=actual['device_before']:raise ValueError('Previous complete result changed')
            comparison='previous-complete-result-identical'
        else:
            if (actual['events'][:len(before['events'])]!=before['events'] or actual['pcs'][:before['steps']]!=before['pcs']
                    or actual['steps']<=before['steps'] or actual['status_code'] in (2,6)):
                raise ValueError('Previous guarded prefix not preserved/extended')
            comparison='previous-device-guard-extended'
        if not actual['code_unchanged']:raise ValueError('Original code changed')
        rows.append({'mode':mode,'variant':variant,'mask':mask,'comparison':comparison,'prior_steps':before['steps'],
                     'status':actual['status'],'status_code':actual['status_code'],'steps':actual['steps'],'events':len(actual['events']),
                     'error_address':hex(actual['error_address']),'error_size':actual['error_size'],'last_pc':hex(actual['pcs'][-1]),
                     'model_cycles':actual['model_cycles'],'registers':actual['registers'],'tail_pcs':actual['pcs'][-8:],'tail_events':actual['events'][-8:],
                     'regions_after_sha256':[hashlib.sha256(v).hexdigest() for v in actual['regions_after']],
                     'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest(),
                     'code_unchanged':True,'independent_command10_semantics_accepted':False})
    return {'cases':len(rows),'outcomes':dict(Counter(r['status']+'@'+r['error_address'] for r in rows)),
            'previous_complete_identical':sum(r['comparison']=='previous-complete-result-identical' for r in rows),
            'extended_previous_device_guards':sum(r['comparison']=='previous-device-guard-extended' for r in rows),
            'diagnostic_returns':sum(r['status_code']==1 for r in rows),'results':rows,'full_semantic_contract_accepted':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--previous-prepared',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.report.exists():raise ValueError('Use a new private report')
    report={'schema':'neptune.original-slot-effects.v1','status':'failure','original_game_bytes_executed':False,
            'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_identity':native.identity(),
            'scope':'Three complete constructed helper contracts and separate guarded command10 continuation; no natural/timing/audio/full-game claim'}
    with args.report.open('x') as output:
        try:
            code=sound.source_bytes(args.source_file,'NLSND');library=native.Library(args.prepared);oldlib=previous.Library(args.previous_prepared)
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),native_binary_sha256=hashlib.sha256(library.path.read_bytes()).hexdigest(),
                          previous_binary_sha256=hashlib.sha256(oldlib.path.read_bytes()).hexdigest(),original_game_bytes_executed=True)
            report['helpers']=helpers(code,library);report['command10']=command10(code,oldlib,library);report['status']='success'
        except Exception as error:
            report['error']={'type':type(error).__name__,'message':str(error)};raise
        finally:output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'success','helper_cases':report['helpers']['cases'],'terminal_mutations_rejected':sum(c['rejected'] for c in report['helpers']['terminal_mutations'].values()),'command10':report['command10']['outcomes'],'full_command10_accepted':False}))


if __name__=='__main__':main()
