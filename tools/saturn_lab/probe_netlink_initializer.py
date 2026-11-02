#!/usr/bin/env python3
"""Original NLSND initializer, handler13 and dispatcher returns, using explicit RAM.

This is one dependency of issue665. Device-bearing control handlers remain open.
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
import m68k_probe as native
import probe_command_dispatch as dispatch
import probe_kernel as pinned
import probe_netlink_pointer as leaf
import probe_netlink_records as records

INIT, END, HANDLER, POINTER = 0x510E, 0x51B2, 0x1E62, 0x412
MODES = ('initializer', 'handler', 'dispatcher')
BASES = (0x8000, 0x10000)
BYTE_WRITES = ((0x5120,0,0), (0x5124,1,0), (0x5128,2,0x20),
               (0x512E,3,0), (0x5132,4,0), (0x5136,5,0), (0x513A,6,0),
               (0x513E,8,0), (0x5142,9,0), (0x5146,10,0x20))
WORD_WRITES = ((0x514C,0,0), (0x5150,2,0), (0x5154,4,0x2000),
               (0x515A,6,0), (0x515E,8,0), (0x5162,10,0),
               (0x5166,38,0), (0x516A,40,0), (0x516E,42,0),
               (0x5172,12,0), (0x5176,14,0), (0x517A,16,0x2000),
               (0x5180,18,0), (0x5184,20,0), (0x5188,22,0), (0x518C,24,0),
               (0x5190,44,0), (0x5194,26,0), (0x5198,28,0), (0x519C,30,0),
               (0x51A0,32,0), (0x51A4,34,0), (0x51A8,36,0))
INIT_PCS = [INIT,0x5112,0x5116,0x511A,0x511E] + [r[0] for r in BYTE_WRITES + WORD_WRITES] + [0x51AC,0x51B0]


def cases():
    selected = set(itertools.product(MODES, BASES, records.SR_VALUES, range(256), range(2), (0,)))
    selected.update(itertools.product(('dispatcher',), BASES, records.SR_VALUES,
                                     (0,1,128,255), range(2), dispatch.WORDS))
    return sorted(selected)


def contract(mode, base, sr, seed, variant, word):
    if (mode not in MODES or base not in BASES or sr not in records.SR_VALUES
            or type(seed) is not int or not 0 <= seed <= 255 or type(variant) is not int
            or variant not in (0,1) or type(word) is not int or not 0 <= word <= 0xFFFF):
        raise ValueError('Undeclared initializer case')
    entry = INIT if mode == 'initializer' else HANDLER if mode == 'handler' else dispatch.ENTRY
    before = records.base_regs(entry, sr)
    if variant:
        before[:15] = [r ^ 0xFFFFFFFF for r in before[:15]]
    upper = 0xA5A5FF00 if variant else 0x11225A00
    before[0], before[7], before[14] = (upper & 0xFFFF0000) | word, upper | 0x13, 0x28000 if variant else 0x18000
    expected = list(before)
    context = bytes((i * 37 + seed + variant * 113) & 255 for i in range(104))
    stack = bytes((i * 29 + seed * 17) & 255 for i in range(96)) + leaf.STOP.to_bytes(4, 'big')
    regions = [(POINTER, base.to_bytes(4, 'big'), False),
               (base - 8, context, True), (leaf.SP - 96, stack, True)]
    buffers = [bytearray(data) for _, data, _ in regions]
    events, pcs = [], []

    def memory(kind, address, size, value=None):
        for (lo, data, writable), buffer in zip(regions, buffers):
            if lo <= address and address + size <= lo + len(data):
                if kind == 1:
                    value = int.from_bytes(buffer[address-lo:address-lo+size], 'big')
                else:
                    if not writable:
                        raise ValueError('Oracle write outside declared writable RAM')
                    buffer[address-lo:address-lo+size] = value.to_bytes(size, 'big')
                events.append([kind, address, size, value])
                return value
        raise ValueError('Oracle access outside declared RAM')

    sp = leaf.SP

    def push(value):
        nonlocal sp
        sp -= 4
        memory(2, sp, 4, value)

    def pop():
        nonlocal sp
        value = memory(1, sp, 4)
        sp += 4
        return value

    def save(registers, indexes):
        nonlocal sp
        for index in reversed(indexes):
            sp -= 4
            memory(2, sp+2, 2, registers[index] & 0xFFFF)
            memory(2, sp, 2, registers[index] >> 16)

    if mode == 'dispatcher':
        # Reuse the independently validated original13 dispatch PC path. The
        # new nested-state/stack contract is specified here, not supplied by CPU.
        pcs += dispatch.contract(0x13, word, upper, sr, before[14])[5]
        save(before, (13,14))
        push(0x1868)
        expected[7], expected[12] = (before[7] & 0xFFFF0000) | 0x4C, before[14]
    if mode != 'initializer':
        pcs.append(HANDLER)
        push(0x1E66)
    saved = list(expected)
    save(saved, tuple(range(15)))
    memory(1, POINTER, 4)
    for _, offset, value in BYTE_WRITES:
        memory(2, base+8+offset, 1, value)
    for _, offset, value in WORD_WRITES:
        memory(2, base+0x28+offset, 2, value)
    for index in range(15):
        if pop() != saved[index]:
            raise ValueError('Oracle initializer register restore differs')
    if pop() != (leaf.STOP if mode == 'initializer' else 0x1E66):
        raise ValueError('Oracle initializer return differs')
    pcs += INIT_PCS
    if mode != 'initializer':
        pcs.append(0x1E66)
        if pop() != (leaf.STOP if mode == 'handler' else 0x1868):
            raise ValueError('Oracle handler return differs')
    if mode == 'dispatcher':
        pcs += [0x1868,0x186C]
        if [pop(), pop(), pop()] != [before[13], before[14], leaf.STOP]:
            raise ValueError('Oracle outer register/return restore differs')
    if sp != leaf.SP+4:
        raise ValueError('Oracle stack did not balance')
    # The initializer's last MOVE.W writes zero; MOVEM/RTS preserve its CCR.
    # The caller's index shift already cleared X in the dispatcher profile.
    expected[15:18] = [sp, leaf.STOP, (sr & ~31) | (0 if mode == 'dispatcher' else sr & 16) | 4]
    return before, expected, regions, [bytes(b) for b in buffers], events, pcs


def run_case(code, library, *case):
    before, expected, regions, after, events, pcs = contract(*case)
    entry = INIT if case[0] == 'initializer' else HANDLER if case[0] == 'handler' else dispatch.ENTRY
    actual = library.run(code, entry, leaf.STOP,
                         [(INIT,END), (HANDLER,HANDLER+6), (dispatch.ENTRY,dispatch.END)],
                         regions, before, budget=80)
    records.check(actual, expected, after, events, pcs)
    return {'case': list(case), 'registers': actual['registers'], 'events': actual['events'],
            'pcs': actual['pcs'], 'instructions': actual['steps'], 'model_cycles': actual['model_cycles'],
            'regions_after': [b.hex() for b in actual['regions_after']],
            'original_code_unchanged': actual['code_unchanged']}


def semantic_control(code, library, address, word, selected):
    altered = bytearray(code)
    altered[address:address+2] = word.to_bytes(2, 'big')
    if bytes(altered) == bytes(code):
        raise ValueError('Ineffective original-copy control')
    reasons = Counter()
    for case in selected:
        try:
            run_case(bytes(altered), library, *case)
        except ValueError as error:
            if str(error).startswith('Native guard:'):
                raise ValueError('Control did not reach a terminal semantic comparison') from error
            reasons[str(error)] += 1
        else:
            raise ValueError('Original-copy control survived')
    return {'address': hex(address), 'tested': len(selected), 'terminal_semantic_rejections': sum(reasons.values()),
            'reasons': dict(reasons), 'mutated_driver_sha256': pinned.digest(altered)}


def execute(code, library):
    selected = cases()
    if len(selected) != 12800 or len(set(selected)) != 12800:
        raise ValueError('Declared initializer domain changed')
    digest = hashlib.sha256()
    counts, samples = Counter(), []
    for case in selected:
        row = run_case(code, library, *case)
        digest.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode())
        counts[(case[0],row['instructions'])] += 1
        if case[1:3] == (BASES[0],records.SR_VALUES[0]) and case[3] in (0,1,127,128,255) and case[4:] == (0,0):
            samples.append(row)
    controls_selected = list(itertools.product(MODES, BASES, records.SR_VALUES, (0,255), (0,), (0,)))
    controls = {name: semantic_control(code, library, address, word, controls_selected)
                for name,address,word in (('wrong_byte_default',0x512A,0x0021),
                    ('wrong_word_default',0x5156,0x2001), ('shifted_word_destination',0x5118,0x002A))}
    return {'cases': len(selected), 'observations_sha256': digest.hexdigest(), 'selected_full_observations': samples,
            'instruction_counts': [{'mode': k[0], 'instructions': k[1], 'cases': v} for k,v in sorted(counts.items())],
            'instruction_controls': controls, 'original_game_bytes_executed': True,
            'ranges_sha256': {f'{lo:x}:{hi:x}': pinned.digest(code[lo:hi]) for lo,hi in
                              ((INIT,END),(HANDLER,HANDLER+6),(dispatch.ENTRY,dispatch.END))}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.original-m68k-initializer.v1', 'status': 'failure', 'issue': 665,
              'module': 'USA-MK81070-V1.003/NLSND/m68000/load0', 'driver_sha256': sound.SOURCES['NLSND'][1],
              'native_identity': native.identity(), 'probe_sha256': pinned.digest(Path(__file__).read_bytes()),
              'limitations': ['Constructed isolated RAM/registers, not natural commands or boot',
                             'No SCSP/DSP/audio/hardware timing or Godot parity',
                             'Only command13; other issue665 handlers and whole-program denominator remain open',
                             'Shared Musashi lineage; complete domain is declared cases, not all machine states']}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path')
        return 1
    with os.fdopen(fd, 'w') as stream:
        phase = 'source_identity'
        try:
            code = sound.source_bytes(args.source_file, 'NLSND')
            phase = 'prepared_identity'
            library = native.Library(args.prepared)
            phase = 'original_execution'
            report.update(execute(code, library), status='success')
        except Exception as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': str(error)}
        stream.write(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('cases',0)}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
