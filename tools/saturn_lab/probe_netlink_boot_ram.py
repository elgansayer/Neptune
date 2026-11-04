#!/usr/bin/env python3
"""Unvalidated NLSND35DE RAM contract/probe; not natural boot or audio evidence."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_scsp_long as native
import probe_netlink_pointer as leaf
import probe_netlink_records as records
import probe_netlink_slot_effects as effects

ENTRY, END, LONGS = 0x35DE, 0x362A, 0xBF1
EXTENT = LONGS * 4
LAYOUTS = ((0x7000, 0x9FFC), (0x10000, 0x12FFC))
MASK = 0xFFFFFFFF


def selection():
    cases = set(itertools.product(range(2), effects.SR_VALUES,
                                 (0, 1, 0x12345678, 0x80000000, MASK), (0, 1)))
    cases.update((0, 0x271F, seed, 0) for seed in range(256))
    return sorted(cases)


def contract(layout, sr, seed, variant, device):
    if (type(layout) is not int or layout not in (0, 1) or sr not in effects.SR_VALUES
            or type(seed) is not int or not 0 <= seed <= MASK
            or type(variant) is not int or variant not in (0, 1)):
        raise ValueError('Undeclared boot RAM case')
    base, sp = LAYOUTS[layout]
    before = records.base_regs(ENTRY, sr)
    if variant:
        before[:15] = [value ^ MASK for value in before[:15]]
    before[14:18] = [base, sp, ENTRY, sr]
    ram = bytes(((seed >> (8 * (i % 4))) + 37 * i) & 255
                for i in range(EXTENT + 32))
    stack = bytes([0xAD]) * 16 + leaf.STOP.to_bytes(4, 'big') + bytes([0xDA]) * 16
    regions = [(base - 16, ram, True), (sp - 16, stack, False)]
    result = bytearray(ram)
    result[16:16 + EXTENT] = bytes(EXTENT)
    # Destination words are column-major; values are row-major. This closed
    # form specifies the final table independently of the CPU's index updates.
    table = [((slot % 4) * 8 + slot // 4) * 0x40 for slot in range(32)]
    result[16 + 0x18C0:16 + 0x1900] = b''.join(v.to_bytes(2, 'big') for v in table)
    result[16 + 0x182A:16 + 0x182C] = (32).to_bytes(2, 'big')
    result[16 + 0x1890:16 + 0x18A0] = bytes(range(16))
    after = list(before)
    after[0], after[2], after[6], after[7] = 16, 8, 0xFFFF, 0xFFFF
    after[8], after[9], after[11] = base + EXTENT, base + 0x18C0, base + 0x18A0
    # The final byte increment 15->16 clears X/N/Z/V/C, including initial X.
    after[15:18] = [sp + 4, leaf.STOP, sr & ~31]
    events = [[2, base + 4 * i, 4, 0] for i in range(LONGS)]
    events += [[2, base + 0x18C0 + 2 * row + 8 * column, 2,
                (row * 8 + column) * 0x40]
               for row in range(4) for column in range(8)]
    events += [[2, base + 0x182A, 2, 32]]
    events += [[2, base + 0x1890 + i, 1, i] for i in range(16)]
    events += [[1, sp, 4, leaf.STOP]]
    pcs = [0x35DE, 0x35E4, 0x35E6]
    pcs += [pc for _ in range(LONGS) for pc in (0x35E8, 0x35EA)]
    pcs += [0x35EE, 0x35F0, 0x35F4]
    for _ in range(4):
        pcs += [0x35F6]
        pcs += [pc for _ in range(8) for pc in (0x35F8, 0x35FC, 0x3600, 0x3604, 0x3606)]
        pcs += [0x360A, 0x360E]
    pcs += [0x3612, 0x3618, 0x361C, 0x361E]
    pcs += [pc for _ in range(16) for pc in (0x3620, 0x3622, 0x3624)]
    pcs += [0x3628]
    return before, regions, {'registers': after, 'regions_after': [bytes(result), stack],
                             'events': events, 'pcs': pcs, 'steps': len(pcs),
                             'device_after': device, 'reference_bus_events': []}


def run_case(code, library, case):
    registers, regions, _ = contract(*case, {})
    actual = library.run(code, ENTRY, leaf.STOP, [(ENTRY, END)], regions,
                         registers, budget=8192, device=(case[2], case[2] & 1))
    effects.compare(actual, contract(*case, actual['device_before'])[2])
    return actual


def controls(code, library):
    result = {}
    edits = (('short_clear', 0x35E3, b'\xEF'),
             ('nonzero_clear', 0x35E5, b'\x01'),
             ('wrong_table_value', 0x3603, b'\x20'),
             ('wrong_table_permutation', 0x360D, b'\x3C'),
             ('wrong_default', 0x3615, b'\x21'),
             ('wrong_byte_sequence', 0x3622, b'\x54'))
    cases = [(layout, 0x271F, seed, variant)
             for layout, seed, variant in itertools.product((0, 1), (0x12345678, MASK), (0, 1))]
    for name, at, replacement in edits:
        changed = bytearray(code)
        changed[at:at + len(replacement)] = replacement
        if bytes(changed) == bytes(code):
            raise ValueError('Ineffective original instruction mutation')
        reasons = set()
        for case in cases:
            registers, regions, _ = contract(*case, {})
            actual = library.run(changed, ENTRY, leaf.STOP, [(ENTRY, END)], regions,
                                 registers, budget=8192, device=(case[2], case[2] & 1))
            if actual['status_code'] != 1:
                raise ValueError('Mutation failed to reach terminal semantics')
            try:
                effects.compare(actual, contract(*case, actual['device_before'])[2])
            except ValueError as error:
                reasons.add(str(error))
            else:
                raise ValueError('Terminal original mutation escaped comparison')
        result[name] = {'offset': hex(at), 'replacement_hex': replacement.hex(),
                        'terminal_tested': len(cases), 'rejected': len(cases),
                        'reasons': sorted(reasons),
                        'changed_source_sha256': hashlib.sha256(changed).hexdigest()}
    return result


def experiment(code, library):
    digest = hashlib.sha256()
    steps, cycles = set(), set()
    for case in selection():
        actual = run_case(code, library, case)
        steps.add(actual['steps'])
        cycles.add(actual['model_cycles'])
        row = {key: value for key, value in actual.items()
               if key not in ('regions_after', 'device_before', 'device_after')}
        row.update(case=case,
                   regions_after_sha256=[hashlib.sha256(data).hexdigest() for data in actual['regions_after']],
                   device_sha256=hashlib.sha256(json.dumps(actual['device_after'], sort_keys=True).encode()).hexdigest())
        digest.update(json.dumps(row, sort_keys=True).encode() + b'\n')
    return {'cases': len(selection()), 'instructions': sorted(steps),
            'model_cycles': sorted(cycles), 'observations_sha256': digest.hexdigest(),
            'range_sha256': hashlib.sha256(code[ENTRY:END]).hexdigest(),
            'terminal_controls': controls(code, library),
            'natural_caller_or_boot_proven': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.original-boot-ram.v1', 'status': 'failure',
              'original_game_bytes_executed': False,
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Constructed isolated35DE RAM/return contract only; natural boot, device clocks, audio and Godot parity open'}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a new writable private path')
        return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            code = sound.source_bytes(args.source_file, 'NLSND')
            phase = 'native_identity'
            report['native_identity'] = native.identity()
            phase = 'native_load'
            library = native.Library(args.prepared)
            report.update(driver_sha256=hashlib.sha256(code).hexdigest(),
                          native_binary_sha256=hashlib.sha256(library.path.read_bytes()).hexdigest())
            phase = 'original_contract'
            report['original_game_bytes_executed'] = True
            report['experiment'] = experiment(code, library)
            report['status'] = 'success'
        except Exception as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__, 'message': str(error)}
        finally:
            output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('experiment', {}).get('cases'),
                      'natural_boot_proven': False}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
