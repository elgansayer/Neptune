#!/usr/bin/env python3
"""Original NetLink wrapper/helper/indirect-target samples; stop before handlers."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_netlink_pointer as leaf
import probe_kernel as pinned

WRAPPERS = {0x40C8: 0x4124, 0x40D2: 0x414C, 0x40DC: 0x4138, 0x40E6: 0x4160, 0x40F0: 0x4174}
COMMON_PCS = [0x4108, 0x410C, 0x4110, 0x4112, 0x4114, 0x4116, 0x411A, 0x411E, 0x4120, 0x4122]


def cases():
    return list(itertools.product(WRAPPERS, range(8), range(8), (0, 0xFFFFFF00),
                                  (0x2700, 0x201F), (0x8000, 0x10000)))


def contract(entry, index, selector, upper, sr, base):
    d0 = upper | index
    tag = (0x80 if upper else 0) | selector
    address = base + 0x2100 + 96 * index + 2
    target = WRAPPERS[entry] + 4 * selector
    regs = [0xA5A5A5A5] * 18
    regs[0], regs[15], regs[16], regs[17] = d0, leaf.SP, entry, sr
    expected = list(regs)
    expected[0], expected[7] = (d0 & 0xFFFF0000) | index, selector * 4
    expected[10] = target
    expected[12:15] = [(base+0x2000) & leaf.MASK, (base+0x2400) & leaf.MASK, address-2]
    expected[16], expected[17] = target, (sr & ~31) | (4 if selector == 0 else 0)
    return regs, expected, tag, address, target


def run_case(code, library, entry, index, selector, upper, sr, base):
    before, expected, tag, address, target = contract(entry, index, selector, upper, sr, base)
    stack = bytes([0xCD])*4 + leaf.STOP.to_bytes(4, 'big')
    regions = [(leaf.POINTER, base.to_bytes(4, 'big'), False),
               (leaf.SP-4, stack, True), (address, bytes([tag]), False)]
    actual = library.run(code, entry, target, [(entry,entry+10), (0x4104,0x4124), (leaf.ENTRY,leaf.END)],
                         regions, before, budget=64)
    if actual['status_code'] != 1:
        raise ValueError('Native guard: ' + actual['status'])
    if actual['registers'] != expected:
        raise ValueError('Indirect target/register/CCR result differs from independent contract')
    pcs = [entry,entry+6,0x4104] + leaf.PCS + COMMON_PCS
    if actual['steps'] != 20 or actual['pcs'] != pcs:
        raise ValueError('Wrapper/helper/return/indirect-PC path differs')
    events = [[2,leaf.SP-4,4,0x4108], [1,leaf.POINTER,4,base],
              [1,leaf.SP-4,4,0x4108], [1,address,1,tag]]
    if (actual['events'] != events or not actual['code_unchanged'] or actual['regions_after'] != [
            regions[0][1], (0x4108).to_bytes(4,'big') + stack[4:], regions[2][1]]):
        raise ValueError('Declared data accesses, stack or unchanged bytes differ')
    return {'entry':hex(entry),'index':index,'selector':selector,'upper_bits':upper,'initial_sr':sr,
            'base':base,'descriptor_tag':tag,'descriptor_address':hex(address),
            'indirect_target':hex(target),'after_SR':expected[17],
            'instructions':actual['steps'],'pcs':[hex(pc) for pc in actual['pcs']],
            'model_cycles':actual['model_cycles'],'data_events':events,
            'SP_preserved':True,'unaffected_mapped_bytes_equal':True,'stop_before_destination':True}


def execute(code, library):
    selected = cases()
    if len(selected) != 2560 or len(set(selected)) != 2560:
        raise ValueError('Case selection changed')
    rows = [run_case(code,library,*case) for case in selected]
    controls = {}
    for name, offset, replacement in (
        ('wrong_first_table_base',0x40CC,(0x4128).to_bytes(2,'big')),
        ('selector_mask_three',0x411C,(3).to_bytes(2,'big')),
        ('missing_upper_D7_clear',0x4114,bytes.fromhex('4e71')),
    ):
        mutated = bytearray(code)
        mutated[offset:offset+len(replacement)] = replacement
        rejected, reasons = 0, set()
        # Complete 5*8*8 subset; test one state/base variant per index/selector.
        controls_selected = selected[::8]
        for case in controls_selected:
            try:
                run_case(mutated,library,*case)
            except ValueError as error:
                rejected += 1
                reasons.add(str(error))
        if not rejected:
            raise ValueError('Original-copy dispatch mutation survived')
        controls[name] = {'address':hex(offset),'tested':len(controls_selected),'rejected':rejected,
                          'reasons':sorted(reasons),'mutated_driver_sha256':pinned.digest(mutated)}
    return {'cases':len(rows),'results':rows,'results_sha256':pinned.digest(json.dumps(rows,sort_keys=True).encode()),
            'original_game_bytes_executed':True,'instruction_controls':controls,
            'ranges_sha256':{f'{start:x}:{end:x}':pinned.digest(code[start:end])
                for start,end in [(e,e+10) for e in WRAPPERS]+[(0x4104,0x4124),(leaf.ENTRY,leaf.END)]},
            'observed_constructed_targets':{hex(e):sorted({r['indirect_target'] for r in rows if r['entry']==hex(e)})
                                             for e in WRAPPERS}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    report={'schema':'neptune.original-m68k-dispatch.v1','status':'failure','experiment':'EXP-SAT-CODE-006',
            'release':'usa-mk81070-v1003','module':'NLSND','cpu':'m68000','load_address':0,
            'lifetime':'netlink-sound-driver','source_path':'NETLINK/SNDDRV.BIN',
            'driver_sha256':sound.SOURCES['NLSND'][1], 'native_identity':native.identity(),
            'probe_sha256':pinned.digest(Path(__file__).read_bytes()),
            'leaf_adapter_sha256':pinned.digest(Path(leaf.__file__).read_bytes()),
            'bridge_sha256':pinned.digest(Path(native.__file__).read_bytes()),
            'limitations':['Constructed inputs; stop at indirect destination before executing its handler',
                           'No natural sound-event semantics, device/SCSP/DSP model or hardware timing',
                           'Not every caller, memory state, dynamic target or whole-program function']}
    try: fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path');return 1
    with os.fdopen(fd,'w') as output:
        phase='source_identity'
        try:
            code=sound.source_bytes(args.source_file,'NLSND');phase='prepared_identity'
            library=native.Library(args.prepared);report['prepared_binary_sha256']=pinned.digest(library.path.read_bytes())
            phase='owned_smoke';report['owned_smoke']=native.smoke(library)
            phase='original_execution';report.update(execute(code,library),status='success')
        except Exception as error:
            report['error']={'phase':phase,'type':type(error).__name__,'reason':'Identity, execution or contract failed'}
        output.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'cases':report.get('cases',0)}))
    return 0 if report['status']=='success' else 1


if __name__=='__main__': raise SystemExit(main())
