#!/usr/bin/env python3
"""Execute original NLSND 10B2 output prefix with clock-frozen SCSP FIFO effects."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_scsp_fifo as native
import probe_kernel as pinned
import probe_netlink_records as records

ENTRY, STOP, GATE, DEVICE = 0x10B2, 0x10DE, 0x4E1, 0x100000
VARIANTS = ((0x8000,0x271F,1), (0x10000,0x2000,0), (0x8000,0x2015,-1))


def cases():
    return sorted(set(itertools.product(range(256),(0,127,255),(0,3,4),(0,3),(0,0x200),(0,))) |
                  set(itertools.product((0,0x20,0x40,0x60,0x80,0xE0,0xFF),range(256),(0,4),(0,),(0x200,),(1,))) |
                  set(itertools.product((0x20,0x40,0x60,0xFF),range(256),(0,3,4),(0,),(0x200,),(2,))))


def subtraction_flags(a,b):
    result=(a-b)&255
    return (8 if result&128 else 0) | (4 if result==0 else 0) | (2 if (a^b)&(a^result)&128 else 0) | (1 if a<b else 0)


def increment_flags(a):
    result=(a+1)&255
    return (17 if a==255 else 0) | (8 if result&128 else 0) | (4 if result==0 else 0) | (2 if a==127 else 0)


def contract(gate,index,count,rp,pending,variant):
    base,sr,difference=VARIANTS[variant]
    writer=(index+difference)&255
    before=records.base_regs(ENTRY,sr)
    before[13],before[14]=DEVICE,base
    queue=bytes((i*37+19)&255 for i in range(256))
    regions=[(GATE,bytes([gate]),False),
             (base+0x1841,bytes([writer,0xCD,index]),True),
             (base+0x1F00,queue,False)]
    after=[r[1] for r in regions]
    expected=list(before);expected[16]=STOP
    expected[0]=(before[0]&~255)|(gate&0x60)
    events=[[1,GATE,1,gate]]
    pcs=[0x10B2,0x10B6,0x10BA]
    flags=(sr&16)|4
    outcome='disabled'
    push=None
    if gate&0x60:
        expected[4]=index
        events += [[1,base+0x1843,1,index],[1,base+0x1841,1,writer]]
        pcs += [0x10BC,0x10BE,0x10C2,0x10C6]
        flags=(sr&16)|subtraction_flags(index,writer)
        outcome='software-empty'
        if index!=writer:
            expected[10]=base+0x1F00
            device_before=native.fifo_contract(count,rp,0x12345678,pending)
            events += [[1,DEVICE+0x404,1,device_before['flags']]]
            pcs += [0x10C8,0x10CC,0x10D2]
            # BTST changes only Z; the other flags still describe the CMP.
            flags=(flags&~4)|(0 if count==4 else 4)
            outcome='device-full'
            if count<4:
                push=queue[index]
                events += [[1,base+0x1F00+index,1,push],[2,DEVICE+0x407,1,push],
                           [1,base+0x1843,1,index],[2,base+0x1843,1,(index+1)&255]]
                pcs += [0x10D4,0x10DA]
                after[1]=bytes([writer,0xCD,(index+1)&255])
                flags=increment_flags(index)
                outcome='one-byte-pushed'
    expected[17]=(sr&~31)|flags
    fixture=(count,rp,0x12345678,pending)
    return before,expected,regions,after,events,pcs,fixture,native.fifo_contract(*fixture,push=push),outcome


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,fixture,device_after,outcome=contract(*case)
    actual=library.run(code,ENTRY,STOP,[(ENTRY,STOP)],regions,before,budget=32,device=fixture)
    records.check(actual,expected,after,events,pcs)
    if actual['device_before']!=native.fifo_contract(*fixture) or actual['device_after']!=device_after:
        raise ValueError('Reference FIFO/interrupt state differs from independent contract')
    return {'case':list(case),'outcome':outcome,'after_registers':expected,
            'device_before':actual['device_before'],'device_after':actual['device_after'],
            'instructions':actual['steps'],'model_cycles':actual['model_cycles'],
            'pcs':pcs,'data_events':events,'all_visible_registers_checked':True,
            'unaffected_mapped_bytes_equal':True}


def execute(code,library):
    selected=cases()
    if len(selected)!=15872:raise ValueError('Constructed selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls_selected=list(itertools.product((0,0x20,0x40,0x60,0xFF),(0,127,255),(0,3,4),(0,),(0x200,),(0,1)))
    controls={}
    for name,offset,replacement in (
            ('gate_bit6_only',0x10B8,bytes.fromhex('0040')),
            ('test_empty_instead_of_full',0x10CE,bytes.fromhex('0003')),
            ('missing_read_cursor_increment',0x10DA,bytes.fromhex('4e71 4e71')),
            ('wrong_device_write_lane',0x10D8,bytes.fromhex('0406')),
            ('reverse_full_branch',0x10D2,bytes.fromhex('670a'))):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived every control case')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'outcomes':{name:sum(r['outcome']==name for r in rows) for name in sorted({r['outcome'] for r in rows})},
            'range_sha256':pinned.digest(code[ENTRY:STOP]),'variants':list(VARIANTS)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-scsp-fifo.v1','status':'failure','experiment':'EXP-SAT-CODE-011',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'bridge_sha256':pinned.digest(Path(native.__file__).read_bytes()),
            'limitations':['Constructed registers, software RAM and FIFO fixtures; not natural boot or gameplay',
                           'Stops before JSR130E; no complete main-loop, sound protocol or audio claim',
                           'Reference FIFO serial clock frozen, interrupt enables zero; no SCSP/DSP timing',
                           'Reference full-write behavior is an upstream hardware TODO; positive original never writes full',
                           'Shared interpreter lineage, not independent hardware validation; whole-program denominators unknown']}
    try:fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');phase='prepared_identity'
            library=native.Library(args.prepared);report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='owned_smoke';report['owned_smoke']=native.smoke(library)
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, bounded execution or contract failed'}
        output.write(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
