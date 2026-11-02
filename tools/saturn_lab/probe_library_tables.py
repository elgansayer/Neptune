#!/usr/bin/env python3
"""Closed library callback/table initialization; no BIOS or callback execution."""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_task_init as task

pinned, records, short, longer = task.pinned, task.records, task.short, task.longer
CALLBACKS, TABLES = 0x06096A80, 0x06096AC0
CELL, BLOCK, BLOCK_SIZE = 0x060FA8BC, 0x060D0000, 0x1B7C
CALLBACK_VALUES = (0x060A69A2, 0x060A6B08, 0x060A6BFE, 0x060A6BF2)
LITERALS = {0x06096AA8: CELL, 0x06096BE0: CELL,
            **dict(zip((0x06096AB0, 0x06096AB4, 0x06096AB8, 0x06096ABC), CALLBACK_VALUES))}
HALFWORDS = dict(zip(range(0x06096BD4, 0x06096BDE, 2), (0x94, 0xC60, 0xA8, 0x438, 0x44C)))
ZERO_OFFSETS = (0x94, 0xB4, 0xA8, 0xB0, 0xAC, 0xB8, 0xC4)
FAMILIES = ('callbacks', 'tables')


class Model(records.Model):
    def read(self, address, size):
        values = LITERALS if size == 4 else HALFWORDS if size == 2 else {}
        if address in values:
            value = values[address]; self.events.append([1, address, size, value]); return value
        return super().read(address, size)

    def callbacks(self):
        r = self.reg
        self.step(CALLBACKS); r['r3'] = self.read(0x06096AA8, 4)
        self.step(CALLBACKS+2); r['r4'] = self.read(r['r3'], 4)
        self.step(CALLBACKS+4); r['r2'] = self.read(0x06096AB0, 4)
        self.step(CALLBACKS+6); r['r4'] += 4
        self.step(CALLBACKS+8); r['r1'] = self.read(0x06096AB4, 4)
        self.step(CALLBACKS+10); self.write(r['r4'], 4, r['r2'])
        self.step(CALLBACKS+12); self.write(r['r4']+4, 4, r['r1'])
        self.step(CALLBACKS+14); r['r2'] = self.read(0x06096AB8, 4)
        self.step(CALLBACKS+16); r['r1'] = self.read(0x06096ABC, 4)
        self.step(CALLBACKS+18); self.write(r['r4']+8, 4, r['r2'])
        self.step(CALLBACKS+20)
        self.step(CALLBACKS+22, True); self.write(r['r4']+12, 4, r['r1'])
        r['pc'] = r['pr']

    def tables(self):
        r = self.reg
        self.step(TABLES); self.push(r['r14'])
        self.step(TABLES+2); self.push(r['r13'])
        self.step(TABLES+4); self.push(r['pr'])
        self.step(TABLES+6); r['r13'] = r['r4']
        self.step(TABLES+8); r['r14'] = self.read(0x06096BE0, 4)
        self.step(TABLES+10); r['r3'] = self.read(r['r14'], 4)
        self.step(TABLES+12); r['pr'] = 0x06096AD0
        self.step(TABLES+14, True); self.write(r['r3'], 4, r['r4'])
        self.callbacks()
        self.step(0x06096AD0); r['r3'] = self.read(r['r14'], 4)
        self.step(0x06096AD2); r['r4'] = 0
        self.step(0x06096AD4); r['r0'] = self.read(0x06096BD4, 2)
        self.step(0x06096AD6); self.t(0 >= records.signed(r['r13'], 32))
        self.step(0x06096AD8); self.write(r['r3']+r['r0'], 4, 0)
        self.step(0x06096ADA); r['r0'] += 32
        self.step(0x06096ADC); r['r3'] = self.read(r['r14'], 4)
        self.step(0x06096ADE); r['r2'] = r['r3']
        self.step(0x06096AE0); self.write(r['r2']+r['r0'], 4, 0)
        self.step(0x06096AE2); r['r0'] -= 12
        self.step(0x06096AE4); self.write(r['r3']+r['r0'], 4, 0)
        self.step(0x06096AE6); r['r0'] += 8
        self.step(0x06096AE8); r['r3'] = self.read(r['r14'], 4)
        self.step(0x06096AEA); r['r2'] = r['r3']
        self.step(0x06096AEC); self.write(r['r2']+r['r0'], 4, 0)
        self.step(0x06096AEE); r['r0'] -= 4
        self.step(0x06096AF0); self.write(r['r3']+r['r0'], 4, 0)
        self.step(0x06096AF2); r['r0'] += 12
        self.step(0x06096AF4); r['r3'] = self.read(r['r14'], 4)
        self.step(0x06096AF6); self.write(r['r3']+r['r0'], 4, 0)
        self.step(0x06096AF8); r['r3'] = self.read(r['r14'], 4)
        self.step(0x06096AFA); r['r0'] += 12
        self.step(0x06096AFC); self.write(r['r3']+r['r0'], 4, 0)
        self.step(0x06096AFE); r['r5'] = self.read(r['r14'], 4)
        self.step(0x06096B00); r['r3'] = self.read(0x06096BD6, 2)
        self.step(0x06096B02); r['r5'] += r['r3']
        self.step(0x06096B04)
        self.step(0x06096B06, True); r['r6'] = 0
        for _ in range(max(0, records.signed(r['r13'], 32))):
            self.step(0x06096B08); self.write(r['r5'], 4, 0)
            self.step(0x06096B0A); r['r6'] += 1
            self.step(0x06096B0C); r['r3'] = self.read(0x06096BD8, 2)
            self.step(0x06096B0E); self.t(r['r6'] >= records.signed(r['r13'], 32))
            self.step(0x06096B10)
            self.step(0x06096B12, True); r['r5'] += r['r3']
        self.step(0x06096B14); r['r5'] = self.read(r['r14'], 4)
        self.step(0x06096B16); r['r3'] = self.read(0x06096BDA, 2)
        self.step(0x06096B18); r['r2'] = self.read(0x06096BDC, 2)
        self.step(0x06096B1A); r['r5'] += r['r3']
        for pc, offset in zip(range(0x06096B1C, 0x06096B26, 2), (0, 12, 8, 4, 16)):
            self.step(pc); self.write(r['r5']+offset, 4, 0)
        self.step(0x06096B26); r['r5'] = self.read(r['r14'], 4)
        self.step(0x06096B28); r['r5'] += r['r2']
        for pc, offset in zip(range(0x06096B2A, 0x06096B34, 2), (0, 12, 8, 4, 16)):
            self.step(pc); self.write(r['r5']+offset, 4, 0)
        self.step(0x06096B34); r['pr'] = self.pop()
        self.step(0x06096B36); r['r13'] = self.pop()
        self.step(0x06096B38)
        self.step(0x06096B3A, True); r['r14'] = self.pop()
        r['pc'] = r['pr']


def cases(family):
    if family not in FAMILIES: raise ValueError('Unknown library table family')
    counts = range(256) if family == 'callbacks' else (*range(25), 0x80000000, task.MASK)
    return [(family, variant, seed, count) for variant, seed, count in itertools.product(range(2), (0, 37, 255), counts)]


def contract(case):
    family, variant, seed, count = case
    if family not in FAMILIES or family == 'tables' and records.signed(count, 32) > 24:
        raise ValueError('Outside explicit bounded library table contract')
    entry = CALLBACKS if family == 'callbacks' else TABLES
    before = records.initial(entry, count, variant); before['r15'] -= 0x100+variant*0x1000
    canary = lambda n: bytes((seed+37*i) & 255 for i in range(n))
    size = 36 if family == 'callbacks' else BLOCK_SIZE
    regions = [(CELL-16, canary(16), False), (CELL, BLOCK.to_bytes(4, 'big'), False), (CELL+4, canary(16), False),
               (BLOCK-16, canary(16), False), (BLOCK, canary(size), True), (BLOCK+size, canary(16), False)]
    sp = before['r15']; depth = 0 if family == 'callbacks' else 12
    regions.append((sp-64, canary(64-depth), False))
    if depth: regions.append((sp-depth, canary(depth), True))
    regions.append((sp, canary(64), False))
    model = Model(before, [(lo, value) for lo, value, _ in regions])
    getattr(model, family)()
    scalar = bytearray(regions[4][1])
    scalar[4:20] = b''.join(value.to_bytes(4, 'big') for value in CALLBACK_VALUES)
    if family == 'tables':
        scalar[:4] = count.to_bytes(4, 'big')
        offsets = (*ZERO_OFFSETS, *range(0x438, 0x460, 4),
                   *(0xC60+0xA8*i for i in range(max(0, records.signed(count, 32)))))
        for offset in offsets: scalar[offset:offset+4] = bytes(4)
    if bytes(model.buffers[4]) != scalar: raise ValueError('Independent scalar table contract differs')
    return entry, model, regions


def observe(data, emu, family, before, regions):
    ranges = ((CALLBACKS, 0x06096A98),)
    budget, profile = (128, short) if family == 'callbacks' else (256, longer)
    source_regions = []
    if family == 'tables':
        ranges += ((TABLES, 0x06096B3C),)
        # Original halfword literal bytes are read from the verified source;
        # do not synthesize/replace them or widen the accepted guard API.
        source_regions = [(0x06096BD4, bytes(data[0x06096BD4-pinned.BASE:0x06096BDE-pinned.BASE]), False)]
    literals = tuple(LITERALS) if family == 'tables' else tuple(x for x in LITERALS if x != 0x06096BE0)
    return profile.observe(data, emu, before['pc'], regions+source_regions, before, ranges=ranges,
                           literals=literals, aliases=(), terminals={before['pr']: 'returned'}, budget=budget)


def run_case(data, emu, case):
    _, model, regions = contract(case)
    actual = observe(data, emu, case[0], model.before, regions)
    expected_regions = [bytes(value) for value in model.buffers]
    if case[0] == 'tables': expected_regions.append(bytes(data[0x06096BD4-pinned.BASE:0x06096BDE-pinned.BASE]))
    reason = None
    if actual['status'] != 'returned': reason = 'Original library initializer did not return: '+str(actual['error'])
    elif actual['registers'] != model.reg: reason = 'Library initializer register/PC/SR/PR/MAC differs'
    elif actual['trace'] != model.trace or actual['steps'] != len(model.trace): reason = 'Library initializer PC/delay trace differs'
    elif actual['events'] != model.events: reason = 'Library initializer transactions differ'
    elif actual['regions_after'] != expected_regions or not actual['original_unaffected_bytes_equal']:
        reason = 'Library initializer output/canaries/source bytes differ'
    if reason: raise task.CaseFailure(reason, case, actual)
    return {'case': list(case), 'status': 'returned', 'instructions': actual['steps'], 'after_registers': actual['registers'],
            'trace': actual['trace'], 'data_events': actual['events'],
            'regions_after_sha256': [pinned.digest(value) for value in actual['regions_after']], 'all_visible_state_checked': True}


def execute(data, emu, family):
    selected = cases(family); rows = [run_case(data, emu, case) for case in selected]
    mutations = [('callback_offset', 0x06096A86, 0x7408), ('missing_last_callback_delay', 0x06096A96, 0x0009)]
    if family == 'tables':
        mutations += [('lost_count_delay_store', 0x06096ACE, 0x0009), ('missing_slot_stride_delay', 0x06096B12, 0x0009),
                      ('lost_table_clear', 0x06096B32, 0x0009), ('lost_R14_restore_delay', 0x06096B3A, 0x0009)]
    controls = {}
    for name, pc, word in mutations:
        changed = bytearray(data); changed[pc-pinned.BASE:pc-pinned.BASE+2] = word.to_bytes(2, 'big')
        rejected = 0; first = None
        chosen = selected[::max(1, len(selected)//48)]
        for case in chosen:
            try: run_case(changed, emu, case)
            except task.CaseFailure as error:
                fault = error.evidence['actual']['error']
                if fault and 'budget exceeded' in fault['reason']: continue
                rejected += 1
                if first is None: first = error.evidence
        if not rejected: raise ValueError('Mutation has no non-budget rejection: '+name)
        controls[name] = {'pc': pc, 'tested': len(chosen), 'nonbudget_rejections': rejected,
                          'first_rejection': first, 'mutated_kernel_sha256': pinned.digest(changed)}
    return {'cases': len(rows), 'results': rows, 'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
            'instruction_controls': controls, 'original_game_bytes_executed': True, 'complete_returns': len(rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--saturn-recomp', type=Path, required=True)
    parser.add_argument('--family', choices=FAMILIES, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.original-library-initializers.v1', 'status': 'failure', 'selection': args.family,
              'release': 'usa-mk81070-v1003', 'module': 'KRNL', 'cpu': 'sh2', 'load_address': pinned.BASE,
              'lifetime': 'resident-kernel', 'kernel_sha256': pinned.KERNEL_SHA256,
              'interpreter_revision': pinned.INTERPRETER_REVISION, 'interpreter_sources': pinned.SOURCE_HASHES,
              'source_sha256': {name: pinned.digest(Path(__file__).with_name(name).read_bytes()) for name in
                  ('probe_library_tables.py', 'probe_task_init.py', 'probe_kernel.py', 'probe_kernel_records.py',
                   'sh2_handoff_profile.py', 'sh2_selection_profile.py', 'probe_split_add.py', 'probe_position_bounds.py')},
              'original_game_bytes_executed': False,
              'limitations': ['Constructed high-RAM block/stack; no natural initializer/callback execution',
                             '95B04 successful BIOS/library path and89C8 complete return unresolved',
                             'No device model, callee stubs or injected ticks; gameplay/hardware parity unknown',
                             'Whole module/function/dynamic-target denominators unknown']}
    try: fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError: print('FAIL: report requires a fresh writable path'); return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            data = pinned.kernel_bytes(args.kernel); emu = pinned.interpreter(args.saturn_recomp)
            phase = 'original_execution'; report['original_game_bytes_executed'] = None
            report.update(execute(data, emu, args.family), status='success')
        except Exception as error:
            report['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': str(error)}
            if isinstance(error, task.CaseFailure):
                report['failure_evidence'] = error.evidence; report['original_game_bytes_executed'] = True
        output.write(json.dumps(report, sort_keys=True, separators=(',', ':'))+'\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('cases', 0), 'selection': args.family}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__': raise SystemExit(main())
