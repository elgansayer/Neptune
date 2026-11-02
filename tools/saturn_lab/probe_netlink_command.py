#!/usr/bin/env python3
"""Original NetLink four-byte writer and saturating-byte samples; no devices."""
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

ENTRY, END, PTR, RECORD = 0x4C2A, 0x4C9A, 0x450, 0x18000
# tag, flags, primary subtract, alternate subtract, D2 byte, D3 byte, D1 byte, SR, base, register upper bits
VARIANTS = ((0,0,0x20,0x7F,0x10,0,0,0x2700,0x8000,0xA5A50000),
            (9,0x10,0x80,0x10,0x10,1,0x7F,0x271F,0x10000,0x5A5A0000),
            (0xFF,0,0x7F,0x80,0xFF,0xFF,0xFF,0x200A,0x8000,0x11220000),
            (0x18,0x10,0,0xFF,0x80,0x80,0x80,0x2015,0x10000,0x77880000))
PREFIX = [0x4C2A,0x4C2E,0x4C32,0x4C36,0x4C3A,0x4C3C,0x4C3E,0x4C42,0x4C46]
SUFFIX = [0x4C62,0x4C64,0x4C68,0x4C6C,0x4C6E,0x4C70,0x4C74,0x4C76,0x4C78,0x4C7A,
          0x4C7C,0x4C80,0x4C82,0x4C84,0x4C86,0x4C88,0x4C8A,0x4C8C,0x4C8E,0x4C90,0x4C92,0x4C94,0x4C98]


def cases():
    # Every status byte at wrap boundaries, and every counter byte across five
    # status classes. This is not the Cartesian space of every byte argument.
    return sorted(set(itertools.product(range(256),(0,1,127,255),range(4))) |
                  set(itertools.product((0x0F,0x80,0x90,0x9F,0xFF),range(256),range(4))))


def contract(status,counter,variant):
    tag,flag,primary,alternate,payload,flag_byte,data,sr,base,upper=VARIANTS[variant]
    before=records.base_regs(ENTRY,sr)
    before[:4]=[upper|status,upper|data,upper|payload,upper|flag_byte]
    initial_record=bytearray((i*37+19)&255 for i in range(0x25))
    initial_record[0],initial_record[1]=flag,tag
    initial_record[0x22],initial_record[0x24]=primary,alternate
    amount=alternate if flag&0x10 else primary
    adjusted=max(0,payload-amount) if status&0xF0==0x90 else payload
    packed=bytes([(status>>4)&7,(status&15)|((flag_byte<<4)&255)|((tag<<5)&255),data,adjusted])
    destination=base+0x1A00+4*counter
    saved_sr=(sr&~31)|4|(16 if tag&8 else 0)
    expected=list(before)
    expected[0]=(before[0]&~255)|(status&0xF0)
    expected[2]=(before[2]&~255)|adjusted
    expected[3]=(before[3]&~255)|((flag_byte<<4)&255)
    expected[8:11]=[base,base+0x1840,destination+4]
    expected[15:18]=[leaf.SP+4,leaf.STOP,saved_sr]
    stack=bytes([0xCD])*14+leaf.STOP.to_bytes(4,'big')
    regions=[(PTR,base.to_bytes(4,'big'),False),(RECORD,bytes(initial_record),False),
             (base+0x1840,bytes([counter]),True),(destination,bytes.fromhex('e36c5a96'),True),
             (leaf.SP-14,stack,True)]
    events=[e for offset,reg in ((4,7),(8,6),(12,5)) for e in (
        [2,leaf.SP-offset+2,2,before[reg]&0xFFFF],[2,leaf.SP-offset,2,before[reg]>>16])]
    events += [[1,PTR,4,base]]
    pcs=list(PREFIX)
    if status&0xF0==0x90:
        events += [[1,RECORD+0x22,1,primary],[1,RECORD,1,flag]]
        pcs += [0x4C4A,0x4C4E,0x4C52]
        if flag&0x10:
            events += [[1,RECORD+0x24,1,alternate]]
            pcs += [0x4C56]
        pcs += [0x4C5A,0x4C5C]
        if payload<amount:pcs += [0x4C60]
    pcs += SUFFIX
    events += [[1,RECORD+1,1,tag],[2,leaf.SP-14,2,saved_sr],
               [1,base+0x1840,1,counter],[1,base+0x1840,1,counter],
               [2,base+0x1840,1,(counter+1)&255]]
    events += [[2,destination+i,1,value] for i,value in enumerate(packed)]
    events += [[1,leaf.SP-14,2,saved_sr]]
    events += [[1,leaf.SP+offset,4,before[reg]] for offset,reg in ((-12,5),(-8,6),(-4,7))]
    events += [[1,leaf.SP,4,leaf.STOP]]
    saved=saved_sr.to_bytes(2,'big')+b''.join(before[i].to_bytes(4,'big') for i in (5,6,7))+stack[14:]
    after=[regions[0][1],regions[1][1],bytes([(counter+1)&255]),packed,saved]
    return before,expected,regions,after,events,pcs,destination


def run_case(code,library,status,counter,variant):
    before,expected,regions,after,events,pcs,destination=contract(status,counter,variant)
    actual=library.run(code,ENTRY,leaf.STOP,[(ENTRY,END)],regions,before,budget=64)
    records.check(actual,expected,after,events,pcs)
    return {'status_byte':status,'counter_before':counter,'variant':variant,
            'counter_after':(counter+1)&255,'packed':after[3].hex(),'destination':hex(destination),
            'initial_SR':before[17],'after_SR':expected[17],'after_D0':expected[0],
            'after_D2':expected[2],'after_D3':expected[3],'instructions':actual['steps'],
            'model_cycles':actual['model_cycles'],'pcs':[hex(pc) for pc in actual['pcs']],
            'data_events':events,'all_visible_registers_checked':True,'unaffected_mapped_bytes_equal':True}


def execute(code,library):
    selected=cases()
    if len(selected)!=9136:raise ValueError('Constructed selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls_selected=[(s,c,v) for s in (0x40,0x70,0x80,0x90,0x9F,0xFF) for c in (0,255) for v in range(4)]
    controls={}
    for name,offset,replacement in (
        ('missing_saturation_clear',0x4C60,bytes.fromhex('4e71')),
        ('missing_counter_increment',0x4C82,bytes.fromhex('4e71')),
        ('group_mask_three',0x4C66,(3).to_bytes(2,'big')),
        ('missing_tag_bits',0x4C76,bytes.fromhex('4e71')),
    ):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived all selected cases')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'instruction_controls':controls,'original_game_bytes_executed':True,
            'range_sha256':pinned.digest(code[ENTRY:END]),'variants':list(VARIANTS)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-command.v1','status':'failure','experiment':'EXP-SAT-CODE-008',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'bridge_sha256':pinned.digest(Path(native.__file__).read_bytes()),
            'limitations':['Constructed data/registers, not natural sound commands or validated device effects',
                           'No SCSP/DSP/hardware timing or whole-program coverage; interpreter lineage shared']}
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
        output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
