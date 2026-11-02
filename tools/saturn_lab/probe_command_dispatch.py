#!/usr/bin/env python3
"""Original NLSND17F2 returns, indexed calls, and guarded illegal landings."""
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

ENTRY, END = 0x17F2, 0x18F2
HIGH_TARGETS=(0x1A9C,0x1AE0,0x1B24,0x1B30,0x1B38,0x1B3A,0x1DE2,0x1582,
              0x1E2E,0x1EEE,0x1D2C,0x186E,None,0x186E,0x186E,None)
LOW_TARGETS=(0x1872,0x18F2,0x1910,0x1958,0x1962,0x196C,0x197A,0x1982,
             0x168E,0x1990,0x19B6,0x19BE,0x19C6,0x19D8,0x1A1C,0x186E,
             0x1E68,0x1E56,0x1E4C,0x1E62,*([0x186E]*12))
WORDS=(0,1,0x7F,0x80,0xFF,0x100,0x7FFF,0x8000,0xFFFF)


def cases():
    return list(itertools.product(range(256),WORDS,(0,0xA5A5FF00),(0x2700,0x271F),(0x8000,0x10000)))


def word_flags(value,x=0):
    return x | (8 if value&0x8000 else 4 if value==0 else 0)


def contract(command,word,upper,sr,base):
    before=records.base_regs(ENTRY,sr)
    before[0]=(0x88770000 if upper else 0x11220000)|word
    before[7]=upper|command;before[13],before[14]=0x24000,base
    expected=list(before);expected[7]=(before[7]&0xFFFF0000)|command
    stack=bytes([0xCD])*24+leaf.STOP.to_bytes(4,'big')
    after=bytearray(stack);regions=[(leaf.SP-24,stack,True)]
    events=[];pcs=[0x17F2,0x17F6,0x17F8]
    stop=leaf.STOP;outcome='complete-return';flags=word_flags(word,sr&16)
    if command>=0x80:
        pcs += [0x17FA,0x17FE]
        if command<0x91:
            index=command&15;landing=0x180E+index*4;target=HIGH_TARGETS[index]
            expected[7]=(before[7]&0xFFFF0000)|index*4
            pcs += [0x1800,0x1804,0x1806,0x1808,landing]
            events += [[2,leaf.SP-4,4,0x180C]]
            after[20:24]=(0x180C).to_bytes(4,'big')
            flags=4 if index==0 else 0
            if target is None:
                # Pinned 68000 illegal instruction: stack PPC and SR, then read
                # vector4 at10. The vector is deliberately NOT mapped/supplied.
                outcome='unresolved-exception-vector';expected[15]=leaf.SP-10
                expected[16]=landing+2
                events += [[2,leaf.SP-8,4,landing],[2,leaf.SP-10,2,(sr&~31)|flags]]
                after[16:20]=landing.to_bytes(4,'big');after[14:16]=((sr&~31)|flags).to_bytes(2,'big')
            elif target==0x186E:
                if index==13:
                    expected[0] |= 0x6E
                    pcs += [0x1846]
                pcs += [0x186E,0x1870,0x180C,0x186E,0x1870]
                events += [[1,leaf.SP-4,4,0x180C],[1,leaf.SP,4,leaf.STOP]]
                flags=word_flags(expected[0]&0xFFFF)
            else:
                stop=target;outcome='handler-prefix';expected[15]=leaf.SP-4
        else:
            pcs += [0x186E,0x1870];events += [[1,leaf.SP,4,leaf.STOP]]
    else:
        pcs += [0x1854,0x1858]
        if command<0x20:
            target=LOW_TARGETS[command];landing=0x1872+command*4
            expected[7]=(before[7]&0xFFFF0000)|command*4
            expected[12]=base
            pcs += [0x185A,0x185C,0x185E,0x1860,0x1864,landing]
            for depth,reg in ((4,14),(8,13)):
                events += [[2,leaf.SP-depth+2,2,before[reg]&0xFFFF],[2,leaf.SP-depth,2,before[reg]>>16]]
            events += [[2,leaf.SP-12,4,0x1868]]
            after[12:24]=(0x1868).to_bytes(4,'big')+before[13].to_bytes(4,'big')+before[14].to_bytes(4,'big')
            flags=4 if command==0 else 0
            if command==0 or target==0x186E:
                if command!=0:
                    pcs += [0x186E,0x1870];flags=word_flags(word)
                events += [[1,leaf.SP-12,4,0x1868],[1,leaf.SP-8,4,before[13]],
                           [1,leaf.SP-4,4,before[14]],[1,leaf.SP,4,leaf.STOP]]
                pcs += [0x1868,0x186C]
            else:
                stop=target;outcome='handler-prefix';expected[15]=leaf.SP-12
        else:
            pcs += [0x186E,0x1870];events += [[1,leaf.SP,4,leaf.STOP]]
    if outcome=='complete-return':expected[15]=leaf.SP+4
    if outcome!='unresolved-exception-vector':expected[16]=stop
    expected[17]=(sr&~31)|flags
    return before,expected,regions,[bytes(after)],events,pcs,stop,outcome


def run_case(code,library,*case):
    before,expected,regions,after,events,pcs,stop,outcome=contract(*case)
    actual=library.run(code,ENTRY,stop,[(ENTRY,END)],regions,before,budget=64)
    if outcome=='unresolved-exception-vector':
        if (actual['status_code'],actual['error_address'],actual['error_size'])!=(4,0x10,4):
            raise ValueError('Original illegal landing did not stop at the unmapped exception vector')
        if actual['registers']!=expected:raise ValueError('Illegal-landing exception registers differ')
        if actual['regions_after']!=after or not actual['code_unchanged']:
            raise ValueError('Illegal-landing stack/canary or original code differs')
        if actual['events']!=events:raise ValueError('Illegal-landing exception transactions differ')
        if actual['pcs']!=pcs or actual['steps']!=len(pcs):
            raise ValueError('Illegal-landing executed-PC path differs')
    else:
        records.check(actual,expected,after,events,pcs)
    return {'case':list(case),'outcome':outcome,'completed_original_call':outcome=='complete-return',
            'native_status':actual['status'],'error_address':actual['error_address'],'error_size':actual['error_size'],
            'after_registers':expected,'data_events':events,'pcs':pcs,'instructions':actual['steps'],
            'model_cycles':actual['model_cycles'],'all_visible_registers_checked':True,
            'unaffected_mapped_bytes_equal':True,'code_unchanged':actual['code_unchanged']}


def execute(code,library):
    selected=cases()
    if len(selected)!=18432:raise ValueError('Constructed selection changed')
    rows=[run_case(code,library,*case) for case in selected]
    controls={}
    controls_selected=list(itertools.product((0,1,0x1F,0x20,0x7F,0x80,0x8B,0x8D,0x8E,0x90,0x91,0xFF),
                                             (0,0x8000),(0,0xA5A5FF00),(0x2700,0x271F),(0x8000,)))
    for name,offset,replacement in (
            ('high_limit_90',0x17FC,bytes.fromhex('0090')),
            ('low_limit_1F',0x1856,bytes.fromhex('001f')),
            ('high_mask_seven',0x1802,bytes.fromhex('0007')),
            ('missing_low_index_double',0x185C,bytes.fromhex('4e71')),
            ('missing_return_flag_operation',0x186E,bytes.fromhex('4e71')),
            ('missing_middle_ORI',0x1842,bytes.fromhex('4e71 4e71'))):
        altered=bytearray(code);altered[offset:offset+len(replacement)]=replacement
        rejected,reasons=0,set()
        for case in controls_selected:
            try:run_case(altered,library,*case)
            except ValueError as error:rejected+=1;reasons.add(str(error))
        if not rejected:raise ValueError('Altered original survived every selected control case')
        controls[name]={'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                        'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(altered)}
    outcomes={name:sum(r['outcome']==name for r in rows) for name in sorted({r['outcome'] for r in rows})}
    if outcomes!={'complete-return':16128,'handler-prefix':2160,'unresolved-exception-vector':144}:
        raise ValueError('Declared completion/unsupported partition changed')
    return {'cases':len(rows),'successful_bounded_cases':len(rows)-144,'results':rows,'outcomes':outcomes,
            'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),'instruction_controls':controls,
            'original_game_bytes_executed':True,'range_sha256':pinned.digest(code[ENTRY:END]),
            'unresolved_handler_entries':sorted(set(r['after_registers'][16] for r in rows if r['outcome']=='handler-prefix'))}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-command-dispatch.v1','status':'failure','experiment':'EXP-SAT-CODE-014',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1],'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'contract_adapter_sha256':pinned.digest(Path(records.__file__).read_bytes()),
            'limitations':['Complete declared skip/no-op paths; nontrivial handlers stop at entry',
                           '144 real illegal-landing failures retain unmapped-vector status; no completed handler claim',
                           'Constructed registers/stack; no natural commands, boot, SCSP/DSP/audio or hardware timing',
                           'CPU interpreter lineage shared; whole-program/function/dynamic-target denominators unknown']}
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
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0),'outcomes':report.get('outcomes',{})}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
