#!/usr/bin/env python3
"""Original NLSND reset gate/handoff, not complete or natural boot."""
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
import probe_netlink_records as records

ENTRY,HANDOFF,TAG,SIGNATURE,BUDGET=0x1000,0x1080,0x5D6C,0x53454741,63
RANGES=[(0x1000,0x1020),(0x1060,0x1080)]
PREFIX=[0x1000,0x1004,0x100E,0x1010,0x1012,0x1014,0x1016,0x1018,0x101A,0x101C,0x101E]
SUFFIX=[0x1060,0x1062,0x1064,0x1066,0x1068,0x106A,0x106C,0x106E,0x1070,0x1074,0x107A]


def selection():
    tags={SIGNATURE,0,0xFFFFFFFF,0x80000000,0x7FFFFFFF}
    for index,value in itertools.product(range(4),range(256)):
        shift=index*8;tags.add((SIGNATURE&~(255<<shift))|(value<<shift))
    return sorted(itertools.product(tags,records.SR_VALUES,(0,1)))


def cmp_flags(value):
    difference=(value-SIGNATURE)&0xFFFFFFFF
    return ((4 if difference==0 else 0)|(8 if difference&0x80000000 else 0)
            |(2 if (value^SIGNATURE)&(value^difference)&0x80000000 else 0)|(1 if value<SIGNATURE else 0))


def contract(tag,sr,variant):
    if (type(tag) is not int or not 0<=tag<=0xFFFFFFFF or sr not in records.SR_VALUES
            or type(variant) is not int or variant not in (0,1)):raise ValueError('Undeclared gate case')
    before=records.base_regs(ENTRY,sr)
    if variant:before[:15]=[v^0xFFFFFFFF for v in before[:15]]
    before[15]=0x70000 if variant else 0xA000
    regions=[(TAG,tag.to_bytes(4,'big'),False),(0x9FF0,bytes([0xCD])*32,False),(0x6FFF0,bytes([0xAD])*32,False)]
    after=list(before)
    if tag==SIGNATURE:
        pcs=PREFIX+SUFFIX;after[:18]=[0]*13+[0x100000,0x7000,0xA000,HANDOFF,0x2704]
        status,address,outcome=1,0,'gate-transfer'
        events=[[1,TAG,4,tag]]
    else:
        pcs=[pc for _ in range(BUDGET//3) for pc in PREFIX[:3]]
        after[16:18]=[ENTRY,0x2700|cmp_flags(tag)]
        status,address,outcome=2,ENTRY,'bounded-wait-not-completed-boot'
        events=[[1,TAG,4,tag] for _ in range(BUDGET//3)]
    expected={'registers':after,'pcs':pcs,'steps':len(pcs),'events':events,
              'regions_after':[b for _,b,_ in regions],'status_code':status,'error_address':address,'error_size':0,'reference_bus_events':[]}
    return before,regions,expected,outcome


def compare(actual,expected):
    if not actual['code_unchanged']:raise ValueError('Original code changed')
    if actual['device_before']!=actual['device_after']:raise ValueError('Untouched device changed')
    for name,value in expected.items():
        if actual[name]!=value:raise ValueError('Independent reset gate mismatch: '+name)


def run_case(code,library,case):
    before,regions,expected,outcome=contract(*case)
    actual=library.run(code,ENTRY,HANDOFF,RANGES,regions,before,budget=BUDGET,device=(0xFFFFFFFF,1) if case[2] else (0x12345678,0))
    try:compare(actual,expected)
    except ValueError as error:
        raise ValueError(str(error)+' '+json.dumps({'case':case,'status':actual['status'],'registers':actual['registers'],'expected_registers':expected['registers'],
                'steps':actual['steps'],'expected_steps':expected['steps'],'error_address':hex(actual['error_address']),'error_size':actual['error_size'],
                'pcs':actual['pcs'],'events':actual['events']})) from error
    return actual,outcome


def controls(code,library):
    results={}
    edits=(('seed_one',0x1011,b'\x01'),('missing_D2_clear',0x1014,bytes.fromhex('4e71')),
           ('skip_D7_clear',0x101F,b'\x42'),('RAM_base',0x1072,bytes.fromhex('7001')),
           ('stack_base',0x1076,bytes.fromhex('0000a004')),('SCSP_base',0x107C,bytes.fromhex('00100020')))
    for name,at,replacement in edits:
        changed=bytearray(code);changed[at:at+len(replacement)]=replacement;reasons=set()
        for sr,variant in itertools.product(records.SR_VALUES,(0,1)):
            case=(SIGNATURE,sr,variant);before,regions,expected,_=contract(*case)
            actual=library.run(changed,ENTRY,HANDOFF,RANGES,regions,before,budget=BUDGET,device=(0xFFFFFFFF,1) if variant else (0x12345678,0))
            if actual['status_code']!=1:raise ValueError('Mutation did not reach normal gate handoff: '+name)
            try:compare(actual,expected)
            except ValueError as error:reasons.add(str(error))
            else:raise ValueError('Gate mutation escaped independent semantic check: '+name)
        results[name]={'offset':hex(at),'replacement_hex':replacement.hex(),'terminal_handoffs':8,'rejected':8,'reasons':sorted(reasons),'changed_source_sha256':hashlib.sha256(changed).hexdigest()}
    return results


def gap_guard(code,library):
    changed=bytearray(code);changed[0x101F]=2
    before,regions,_,_=contract(SIGNATURE,0x271F,0)
    actual=library.run(changed,ENTRY,HANDOFF,RANGES,regions,before,budget=BUDGET)
    after=list(before);after[:7]=[0]*7;after[16:18]=[0x1022,0x2704]
    expected={'registers':after,'pcs':PREFIX,'steps':len(PREFIX),'events':[[1,TAG,4,SIGNATURE]],
              'regions_after':[b for _,b,_ in regions],'status_code':3,'error_address':0x1022,'error_size':0,'reference_bus_events':[]}
    compare(actual,expected)
    return {'status':actual['status'],'error_address':hex(actual['error_address']),'instructions':actual['steps'],'semantic_mutation_qualified':False,'scope':'Intentional wrong branch into data is a fetch-guard diagnostic, not a completed gate or reset'}


def execute(code,library):
    selected=selection()
    if len(selected)!=8200:raise ValueError('Declared boot-gate selection changed')
    digest=hashlib.sha256();counts=Counter();cycles={};samples=[]
    for case in selected:
        actual,outcome=run_case(code,library,case);counts[outcome]+=1;cycles.setdefault(outcome,set()).add(actual['model_cycles'])
        row={'case':case,'outcome':outcome,'registers':actual['registers'],'pcs':actual['pcs'],'events':actual['events'],'model_cycles':actual['model_cycles'],
             'regions_after_sha256':[hashlib.sha256(b).hexdigest() for b in actual['regions_after']],
             'device_after_sha256':hashlib.sha256(json.dumps(actual['device_after'],sort_keys=True).encode()).hexdigest()}
        digest.update(json.dumps(row,sort_keys=True).encode()+b'\n')
        if case[1:]==(0x271F,0) and case[0] in (0,SIGNATURE,0xFFFFFFFF):samples.append(row)
    if counts!={'gate-transfer':8,'bounded-wait-not-completed-boot':8192}:raise ValueError('Gate outcome partition changed')
    return {'cases':len(selected),'outcomes':dict(counts),'observations_sha256':digest.hexdigest(),'model_cycles':{k:sorted(v) for k,v in cycles.items()},
            'range_sha256':{hex(lo)+'-'+hex(end):hashlib.sha256(code[lo:end]).hexdigest() for lo,end in RANGES},
            'samples':samples,'terminal_controls':controls(code,library),'data_gap_guard':gap_guard(code,library),'whole_reset_complete':False,'natural_execution':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-file',type=Path,required=True);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(argv)
    report={'schema':'neptune.original-nlsnd-boot-gate.v1','status':'failure','original_game_bytes_executed':False,'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,'lifetime':'netlink-sound-driver','native_identity':native.identity(),
            'scope':'Only1000..1080 marker gate/register transfer, excluding1020..105F data; bounded wrong-tag waits are incomplete; no natural boot/full reset, device clock, DSP/audio, Godot or whole-game claim'}
    try:fd=os.open(a.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh private path');return 1
    with os.fdopen(fd,'w') as out:
        phase='source_identity'
        try:
            code=sound.source_bytes(a.source_file,'NLSND')
            if int.from_bytes(code[TAG:TAG+4],'big')!=SIGNATURE:raise ValueError('Pinned image tail marker differs')
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),source_image_globals={hex(at):hex(int.from_bytes(code[at:at+4],'big')) for at in (0x404,0x412,0x450)},vector_sp=hex(int.from_bytes(code[:4],'big')))
            phase='native_load';library=native.Library(a.prepared);report['native_binary_sha256']=hashlib.sha256(library.path.read_bytes()).hexdigest()
            phase='original_gate';report['original_game_bytes_executed']=True;report['result']=execute(code,library);report['status']='success'
        except Exception as error:report['error']={'phase':phase,'type':type(error).__name__,'message':str(error)}
        finally:out.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'outcomes':report.get('result',{}).get('outcomes',{})}));return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
