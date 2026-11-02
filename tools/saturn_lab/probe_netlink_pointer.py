#!/usr/bin/env python3
"""Bounded original NetLink 68000 helper samples, not natural runtime validation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_kernel as pinned

ENTRY, END, POINTER, SP, STOP = 0x4B00, 0x4B1C, 0x450, 0x70000, 0xFFF000
PCS = [0x4B00, 0x4B04, 0x4B0A, 0x4B0C, 0x4B0E, 0x4B14, 0x4B1A]
MASK = 0xFFFFFFFF


def cases():
    return [(base, sr, poison) for base in (0, 1, 0x7FFF, 0x8000, 0xFFFF, 0x10000,
            0x7FFFFFFF, 0x80000000, 0xFFFFDFFF, 0xFFFFE000, 0xFFFFFFFF)
            for sr in (0x2700, 0x271F, 0x200A, 0x2015) for poison in (0xA5A5A5A5, 0x5A5A5A5A)]


def expected_registers(before, base):
    after = list(before)
    after[12:15] = [(base + offset) & MASK for offset in (0x2000, 0x2400, 0x2100)]
    after[15], after[16] = SP+4, STOP
    return after


def run_case(code, library, base, sr, poison):
    regs = [poison] * 18
    regs[15:18] = [SP, ENTRY, sr]
    regions = [(POINTER, base.to_bytes(4, 'big'), False), (SP, STOP.to_bytes(4, 'big'), False)]
    actual = library.run(code, ENTRY, STOP, [(ENTRY, END)], regions, regs, budget=32)
    if actual['status_code'] != 1:
        raise ValueError('Native guard: ' + actual['status'])
    if actual['registers'] != expected_registers(regs, base):
        raise ValueError('Original register result differs from independent contract')
    if actual['pcs'] != PCS or actual['steps'] != 7:
        raise ValueError('Missing or changed original executed-PC evidence')
    if (actual['events'] != [[1, POINTER, 4, base], [1, SP, 4, STOP]]
            or actual['regions_after'] != [r[1] for r in regions] or not actual['code_unchanged']):
        raise ValueError('Read/write or unaffected-memory contract failed')
    return {'base_bits': base, 'initial_sr': sr, 'initial_poison': poison,
            'A4': actual['registers'][12], 'A5': actual['registers'][13], 'A6': actual['registers'][14],
            'A2_preserved': actual['registers'][10] == regs[10], 'SP_after': actual['registers'][15],
            'SR_after': actual['registers'][17], 'PC_after': actual['registers'][16],
            'instructions': actual['steps'], 'pcs': [hex(pc) for pc in actual['pcs']],
            'model_cycles': actual['model_cycles'], 'reads': actual['events'], 'writes': 0,
            'unaffected_mapped_bytes_equal': True, 'other_visible_registers_preserved': True}


def execute(code, library):
    selected = cases()
    if len(selected) != 88 or len(set(selected)) != 88:
        raise ValueError('Incomplete case selection')
    rows = [run_case(code, library, *case) for case in selected]
    controls = {}
    for kind, offset, replacement in (
        ('changed_A4_increment', 0x4B08, (0x2001).to_bytes(2, 'big')),
        ('missing_A6_copy', 0x4B0C, bytes.fromhex('4e71')),
        ('nonreturning', 0x4B1A, bytes.fromhex('60fe')),
    ):
        changed = bytearray(code)
        changed[offset:offset+len(replacement)] = replacement
        count, reasons = 0, set()
        for case in selected:
            try:
                run_case(changed, library, *case)
            except ValueError as error:
                count += 1
                reasons.add(str(error))
        if count == 0:
            raise ValueError('Altered original instruction survived all selected cases')
        controls[kind] = {'address': hex(offset), 'tested': len(selected), 'rejected': count,
                          'reasons': sorted(reasons), 'mutated_driver_sha256': pinned.digest(changed)}
    return {'cases': len(rows), 'results': rows,
            'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
            'instruction_controls': controls, 'instruction_range_sha256': pinned.digest(code[ENTRY:END]),
            'original_game_bytes_executed': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.original-m68k-pointer.v1', 'status': 'failure',
              'experiment': 'EXP-SAT-CODE-005', 'release': 'usa-mk81070-v1003', 'cpu': 'm68000',
              'module': 'NLSND', 'source_path': 'NETLINK/SNDDRV.BIN',
              'driver_sha256': sound.SOURCES['NLSND'][1], 'load_address': 0, 'entry': ENTRY, 'exclusive_end': END,
              'lifetime': 'netlink-sound-driver', 'native_identity': native.identity(),
              'probe_sha256': pinned.digest(Path(__file__).read_bytes()),
              'source_adapter_sha256': pinned.digest(Path(sound.__file__).read_bytes()),
              'bridge_sha256': pinned.digest(Path(native.__file__).read_bytes()),
              'limitations': ['Isolated original instructions with constructed data/stack/register state',
                             'No natural load/caller, hardware timing, SCSP/DSP or audio semantics',
                             'Musashi lineage is not an independent hardware oracle',
                             'Unknown whole-program/function denominator; programme incomplete']}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires fresh writable path')
        return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            code = sound.source_bytes(args.source_file, 'NLSND')
            phase = 'prepared_identity'
            library = native.Library(args.prepared)
            report['prepared_binary_sha256'] = pinned.digest(library.path.read_bytes())
            phase = 'owned_smoke'
            report['owned_smoke'] = native.smoke(library)
            phase = 'original_execution'
            report.update(execute(code, library), status='success')
        except Exception as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__,
                               'reason': 'Input, prepared tool, original execution or contract failed'}
        output.write(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('cases', 0)}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
