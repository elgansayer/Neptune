#!/usr/bin/env python3
"""Execute both original SND/XBSND alternating table-byte setter leaves."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records

ENTRIES=(0x51F0,0x520E)
TABLE=0x780
VARIANTS=((0x18000,0x271F),(0x24000,0x2000))


def cases():
    return sorted(set(itertools.product(range(2),range(256),(0,1,127,128,255),range(2))) |
                  set(itertools.product(range(2),(0,1,127,255),range(256),range(2))))


def contract(lane,index,payload,variant):
    entry=ENTRIES[lane];record,sr=VARIANTS[variant]
    before=records.base_regs(entry,sr);before[14]=record
    expected=list(before);expected[15:18]=[leaf.SP+4,leaf.STOP,(sr&~31)|(8 if payload&128 else 4 if payload==0 else 0)]
    descriptor=bytearray([0xCD,index,payload^255,payload^255]);descriptor[2+lane]=payload
    table=bytes((i*37+19)&255 for i in range(512))
    stack=bytes([0xCD])*12+leaf.STOP.to_bytes(4,'big')
    regions=[(record,bytes(descriptor),False),(TABLE,table,True),(leaf.SP-12,stack,True)]
    destination=TABLE+2*index+lane
    events=[e for depth,reg in ((4,8),(8,2),(12,0)) for e in (
        [2,leaf.SP-depth+2,2,before[reg]&0xFFFF],[2,leaf.SP-depth,2,before[reg]>>16])]
    events += [[1,record+2+lane,1,payload],[1,record+1,1,index],[2,destination,1,payload]]
    events += [[1,leaf.SP+offset,4,before[reg]] for offset,reg in ((-12,0),(-8,2),(-4,8))]
    events += [[1,leaf.SP,4,leaf.STOP]]
    changed=bytearray(table);changed[2*index+lane]=payload
    saved=b''.join(before[reg].to_bytes(4,'big') for reg in (0,2,8))+stack[12:]
    after=[bytes(descriptor),bytes(changed),saved]
    pcs=[entry+i for i in (0,4,8,12,14,18,20,24,28)]
    return before,expected,regions,after,events,pcs,destination


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,destination=contract(*case)
    entry=ENTRIES[case[0]]
    actual=library.run(code,entry,leaf.STOP,[(entry,entry+30)],regions,before,budget=32)
    records.check(actual,expected,after,events,pcs)
    return {'case':list(case),'destination':destination,'after_registers':expected,'data_events':events,
            'pcs':pcs,'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'all_visible_registers_checked':True,'unaffected_mapped_bytes_equal':True}


def execute(code,library):
    selected=cases()
    if len(selected)!=9136:raise ValueError('Constructed selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls={}
    for lane,entry in enumerate(ENTRIES):
        controls_selected=list(itertools.product((lane,),(0,127,255),(0,128,255),range(2)))
        for name,offset,replacement in (
                ('other_output_lane',entry+6,(0x781-lane).to_bytes(2,'big')),
                ('other_payload_byte',entry+10,(3-lane).to_bytes(2,'big')),
                ('missing_index_double',entry+18,bytes.fromhex('4e71'))):
            altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
            rejected,reasons=0,set()
            for case in controls_selected:
                try:run_case(altered,library,*case)
                except ValueError as error:rejected+=1;reasons.add(str(error))
            if not rejected:raise ValueError('Altered original survived every selected case')
            controls[f'lane{lane}_{name}']={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':{hex(entry):pinned.digest(code[entry:entry+30]) for entry in ENTRIES},'variants':list(VARIANTS)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--module',choices=('SND','XBSND'),required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-shared-setters.v1','status':'failure','experiment':'EXP-SAT-CODE-013',
            'release':'usa-mk81070-v1003','module':args.module,'cpu':'m68000','load_address':0,
            'lifetime':'shared-sound-driver' if args.module=='SND' else 'xband-sound-driver',
            'source_identity':list(sound.SOURCES[args.module]),'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'limitations':['Two complete leaves on constructed inputs, not whole modules or natural callers',
                           'SND/XBSND byte-equal drivers verified from distinct original containers; no NLSND equivalence',
                           'CPU-only fixed RAM, shared interpreter lineage, no boot/SCSP/DSP/audio/hardware proof',
                           'Whole-program/function/dynamic-target denominators unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,args.module);report['driver_sha256']=pinned.digest(code)
            phase='prepared_identity';library=native.Library(args.prepared)
            report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='owned_smoke';report['owned_smoke']=native.smoke(library)
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, bounded execution or contract failed'}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'module':args.module}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
