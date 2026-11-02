#!/usr/bin/env python3
"""Original first-task table initialization and selected library validation paths.

89AC returns completely. 89C8/623A stop at89FC after the real89AC return;
95B04 either returns a parameter error or stops before its BIOS/library calls.
No positive library implementation, device model or substitute callee is added.
"""
import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned
import probe_kernel_records as records
import sh2_handoff_profile as short
import sh2_selection_profile as longer

LEAF, INIT, CALLER, PREFIX = 0x060089AC, 0x060089C8, 0x0600623A, 0x060089FC
DATA, POINTER, RETURN = 0x060BD8C4, 0x00200000, 0xFFFFFFF0
LIBRARY, LIBRARY_READY, ERROR, DESCRIPTOR = 0x06095B04, 0x06095B54, 0x060FA8C4, 0x060E0100
FAMILIES = ("leaf", "init-prefix", "caller-prefix", "library-validation")
LITERALS = {0x06008BF0: DATA, 0x06008BF8: DATA+16, 0x06008BFC: POINTER,
            0x06008C00: DATA+32, 0x06008C04: DATA+80, 0x06006314: INIT,
            0x06095BD4: ERROR}
MASK = 0xFFFFFFFF


class Model(records.Model):
    """Independent scalar/register/transaction model; never decodes opcodes."""
    def read(self, address, size):
        if address in LITERALS and size == 4:
            value = LITERALS[address]
            self.events.append([1, address, size, value])
            return value
        return super().read(address, size)

    def fill(self):
        r = self.reg
        self.step(LEAF); r['r7'] = self.read(0x06008BF0, 4)
        self.step(LEAF+2); r['r5'] = MASK
        self.step(LEAF+4); r['r4'] = r['r7']
        self.step(LEAF+6); r['r6'] = r['r7']
        self.step(LEAF+8); r['r6'] += 16
        for _ in range(4):
            self.step(0x060089B6); self.write(r['r4'], 4, r['r5'])
            self.step(0x060089B8); r['r4'] += 4
            self.step(0x060089BA); self.t(r['r4'] >= r['r6'])
            self.step(0x060089BC)
        self.step(0x060089BE)
        self.step(0x060089C0, True)
        r['pc'] = r['pr']

    def initialization(self):
        r = self.reg
        self.step(INIT); self.push(r['r14'])
        self.step(INIT+2); self.push(r['pr'])
        self.step(INIT+4); r['r7'] = self.read(0x06008BF8, 4)
        self.step(INIT+6); r['r15'] -= 4
        self.step(INIT+8); r['r5'] = self.read(0x06008BFC, 4)
        self.step(INIT+10); r['r4'] = r['r7']
        self.step(INIT+12); r['r6'] = r['r7']
        self.step(INIT+14); r['r6'] += 16
        for _ in range(4):
            self.step(0x060089D8); self.write(r['r4'], 4, r['r5'])
            self.step(0x060089DA); r['r4'] += 4
            self.step(0x060089DC); self.t(r['r4'] >= r['r6'])
            self.step(0x060089DE)
        self.step(0x060089E0); r['r6'] = self.read(0x06008C00, 4)
        self.step(0x060089E2); r['r7'] = 0
        self.step(0x060089E4); r['r4'] = self.read(0x06008C04, 4)
        self.step(0x060089E6); self.write(r['r15'], 4, r['r4'])
        self.step(0x060089E8); r['r14'] = r['r4']
        self.step(0x060089EA); r['r14'] += 24
        for _ in range(12):
            self.step(0x060089EC); self.write(r['r4'], 2, r['r7'])
            self.step(0x060089EE); r['r4'] += 2
            self.step(0x060089F0); self.write(r['r6'], 4, r['r5'])
            self.step(0x060089F2); self.t(r['r4'] >= r['r14'])
            self.step(0x060089F4)
            self.step(0x060089F6, True); r['r6'] += 4
        self.step(0x060089F8); r['pr'] = PREFIX
        self.step(0x060089FA, True)
        self.fill()

    def caller(self):
        self.step(CALLER); self.reg['r2'] = self.read(0x06006314, 4)
        self.step(CALLER+2); self.reg['pr'] = CALLER+6
        self.step(CALLER+4, True)
        self.initialization()

    def library_return(self):
        r = self.reg
        self.step(0x06095BC4); r['r15'] += 4
        self.step(0x06095BC6); r['pr'] = self.pop()
        self.step(0x06095BC8); r['r13'] = self.pop()
        self.step(0x06095BCA)
        self.step(0x06095BCC, True); r['r14'] = self.pop()
        r['pc'] = r['pr']

    def library(self):
        r = self.reg
        self.step(LIBRARY); self.push(r['r14'])
        self.step(LIBRARY+2); r['r3'] = 0
        self.step(LIBRARY+4); r['r2'] = self.read(0x06095BD4, 4)
        self.step(LIBRARY+6); r['r1'] = 1
        self.step(LIBRARY+8); self.push(r['r13'])
        self.step(LIBRARY+10); r['r13'] = r['r4']
        self.step(LIBRARY+12); self.push(r['pr'])
        self.step(LIBRARY+14); self.t(records.signed(r['r13'], 32) >= 1)
        self.step(LIBRARY+16); r['r15'] -= 4
        self.step(LIBRARY+18); self.write(r['r15'], 4, r['r5'])
        self.step(LIBRARY+20); self.write(r['r2'], 4, r['r3'])
        self.step(LIBRARY+22)
        self.step(LIBRARY+24, True); r['r14'] = r['r6']
        invalid_count = not r['sr'] & 1
        if not invalid_count:
            self.step(0x06095B1E); r['r0'] = 24
            self.step(0x06095B20); self.t(records.signed(r['r13'], 32) > 24)
            self.step(0x06095B22)
            invalid_count = bool(r['sr'] & 1)
        if invalid_count:
            self.step(0x06095B24)
            self.step(0x06095B26, True); r['r0'] = (-5) & MASK
            self.library_return(); return
        self.step(0x06095B28); r['r0'] = self.read(r['r15'], 4)
        self.step(0x06095B2A); self.t(not r['r0'] & 3)
        self.step(0x06095B2C)
        if not r['sr'] & 1:
            self.step(0x06095B2E)
            self.step(0x06095B30, True); r['r0'] = (-21) & MASK
            self.library_return(); return
        self.step(0x06095B32); self.t(r['r14'] == 0)
        self.step(0x06095B34)
        invalid_descriptor = False
        if r['r14']:
            self.step(0x06095B36); r['r4'] = self.read(r['r14'], 4)
            self.step(0x06095B38); self.t(r['r4'] == 0)
            self.step(0x06095B3A)
            if r['r4']:
                self.step(0x06095B3C); r['r0'] = r['r4']
                self.step(0x06095B3E); self.t(r['r0'] == 1)
                self.step(0x06095B40)
                invalid_descriptor = not bool(r['sr'] & 1)
            if not invalid_descriptor:
                self.step(0x06095B42); r['r2'] = 2
                self.step(0x06095B44); r['r3'] = self.read(r['r14']+4, 4)
                self.step(0x06095B46); self.t(records.signed(r['r3'], 32) >= 2)
                self.step(0x06095B48)
                invalid_descriptor = not bool(r['sr'] & 1)
            if not invalid_descriptor:
                self.step(0x06095B4A); r['r0'] = self.read(r['r14']+8, 4)
                self.step(0x06095B4C); self.t(r['r0'] == 0)
                self.step(0x06095B4E)
                invalid_descriptor = bool(r['sr'] & 1)
        if invalid_descriptor:
            self.step(0x06095B50)
            self.step(0x06095B52, True); r['r0'] = (-4) & MASK
            self.library_return(); return
        r['pc'] = LIBRARY_READY


def cases(family):
    if family not in FAMILIES:
        raise ValueError('Unknown first-task family')
    if family == 'library-validation':
        counts = (0, 1, 2, 16, 23, 24, 25, 0x7FFFFFFF, 0x80000000, MASK)
        descriptors = ((None, 0, 0), (0, 2, 1), (1, 32, DESCRIPTOR+64),
                       (2, 2, 1), (MASK, 2, 1), (0, 1, 1), (1, 0x80000000, 1), (1, 2, 0))
        return [(family, variant, seed, count, alignment, *descriptor)
                for variant, seed, count, alignment, descriptor in itertools.product(
                    range(2), (0, 255), counts, range(4), descriptors)]
    rows = [(family, variant, seed, None, 0)
            for variant, seed in itertools.product(range(2), range(256))]
    words = (0, 1, MASK, 0x80000000, 0x7FFFFFFF, 0x55555555, 0xAAAAAAAA)
    words = tuple(dict.fromkeys(words + tuple(1 << bit for bit in range(32))))
    for field, word, variant in itertools.product(records.NAMES, words, range(2)):
        if field in ('pc', 'r15', 'sr', 'pr'):
            continue
        rows.append((family, variant, 37, field, word))
    rows += [(family, variant, 37, 'pr', RETURN-16)
             for variant in range(2)]
    return rows


def contract(case):
    family, variant, seed = case[:3]
    entry = {'leaf': LEAF, 'init-prefix': INIT, 'caller-prefix': CALLER,
             'library-validation': LIBRARY}[family]
    before = records.initial(entry, 0x11223344, variant)
    before['r15'] -= 0x100+variant*0x1000
    if family != 'library-validation' and case[3] is not None:
        before[case[3]] = case[4]
    canary = lambda n: bytes((seed + 37*i) & 255 for i in range(n))
    if family == 'library-validation':
        _, _, _, count, alignment, mode, length, address = case
        before.update(r4=count, r5=0x060E8000+alignment, r6=DESCRIPTOR if mode is not None else 0)
        regions = [(ERROR-16, canary(16), False), (ERROR, canary(4), True),
                   (ERROR+4, canary(16), False)]
        if mode is not None:
            descriptor = b''.join(value.to_bytes(4, 'big') for value in (mode, length, address))
            regions.append((DESCRIPTOR-16, canary(16)+descriptor+canary(16), False))
        stack_size = 16
    else:
        count = 16 if family == 'leaf' else 104
        regions = [(DATA-16, canary(16), False), (DATA, canary(count), True),
                   (DATA+count, canary(120-count), False)]
        stack_size = 0 if family == 'leaf' else 12
    sp = before['r15']
    regions.append((sp-64, canary(64-stack_size), False))
    if stack_size:
        regions.append((sp-stack_size, canary(stack_size), True))
    regions.append((sp, canary(64), False))
    model = Model(before, [(lo, value) for lo, value, _ in regions])
    {'leaf': model.fill, 'init-prefix': model.initialization, 'caller-prefix': model.caller,
     'library-validation': model.library}[family]()
    # Scalar output rules independent of the ordered instruction model.
    if family == 'library-validation':
        error = (-5 if not 1 <= records.signed(count, 32) <= 24 else -21 if alignment else
                 -4 if mode is not None and (mode not in (0, 1) or records.signed(length, 32) < 2 or not address) else None)
        if error is not None and (model.reg['pc'] != before['pr'] or model.reg['r0'] != error & MASK):
            raise ValueError('Scalar library parameter error differs')
        if error is None and model.reg['pc'] != LIBRARY_READY:
            raise ValueError('Valid library parameters must remain an incomplete prefix')
        if model.buffers[1] != bytes(4):
            raise ValueError('Library error word was not cleared')
    else:
        expected = bytes([255])*16
        if family != 'leaf': expected += POINTER.to_bytes(4, 'big')*16 + bytes(24)
        if model.buffers[1] != expected:
            raise ValueError('Scalar initialization array differs')
    for (_, value, writable), after in zip(regions, model.buffers):
        if not writable and bytes(after) != value:
            raise ValueError('Model changed a readonly canary/input')
    return entry, model, regions


def observe(data, emu, family, before, regions, *, force_short=False):
    if family == 'library-validation':
        ranges, literals, budget = ((LIBRARY, LIBRARY_READY), (0x06095BC4, 0x06095BCE)), (0x06095BD4,), 64
        terminals = {before['pr']: 'returned', LIBRARY_READY: 'handoff'}
    else:
        ranges = ((LEAF, 0x060089C2),)
        literals, budget = (0x06008BF0,), 128
        if family != 'leaf':
            ranges += ((INIT, PREFIX),)
            literals += (0x06008BF8, 0x06008BFC, 0x06008C00, 0x06008C04)
        if family == 'caller-prefix':
            ranges += ((CALLER, CALLER+6),)
            literals += (0x06006314,)
            budget = 128 if force_short else 144
        terminals = {before['pr']: 'returned'} if family == 'leaf' else {PREFIX: 'handoff'}
    profile = longer if budget > 128 else short
    entry = {'leaf': LEAF, 'init-prefix': INIT, 'caller-prefix': CALLER, 'library-validation': LIBRARY}[family]
    return profile.observe(data, emu, entry, regions, before, ranges=ranges, literals=literals,
                           aliases=(), terminals=terminals, budget=budget)


class CaseFailure(ValueError):
    def __init__(self, reason, case, actual):
        super().__init__(reason)
        self.evidence = {'case': list(case), 'actual': {k: v for k, v in actual.items() if k != 'regions_after'},
                         'regions_after_sha256': [pinned.digest(value) for value in actual['regions_after']]}


def run_case(data, emu, case):
    _, model, regions = contract(case)
    actual = observe(data, emu, case[0], model.before, regions)
    expected_status = 'returned' if case[0] == 'leaf' or model.reg['pc'] == model.before['pr'] else 'handoff'
    reason = None
    if actual['status'] != expected_status: reason = 'Original execution failed before declared boundary: ' + str(actual['error'])
    elif actual['registers'] != model.reg: reason = 'Register/PC/SR/PR/MAC output differs'
    elif actual['trace'] != model.trace or actual['steps'] != len(model.trace): reason = 'Executed PC/delay path differs'
    elif actual['events'] != model.events: reason = 'Exact read/write transactions differ'
    elif actual['regions_after'] != [bytes(value) for value in model.buffers] or not actual['original_unaffected_bytes_equal']:
        reason = 'Controlled output/canaries or original bytes differ'
    if reason: raise CaseFailure(reason, case, actual)
    return {'case': list(case), 'status': expected_status, 'outcome': 'complete_return' if expected_status == 'returned' else 'incomplete_prefix',
            'instructions': actual['steps'], 'after_registers': actual['registers'], 'trace': actual['trace'],
            'data_events': actual['events'], 'regions_after_sha256': [pinned.digest(value) for value in actual['regions_after']],
            'all_visible_registers_checked': True, 'unaffected_bytes_equal': True}


def execute(data, emu, family):
    selected = cases(family)
    rows = [run_case(data, emu, case) for case in selected]
    controls = {}
    mutations = [('zero_sentinel', 0x060089AE, 0xE500), ('three_sentinels', 0x060089B4, 0x760C),
                 ('halfword_sentinel', 0x060089B6, 0x2451), ('lost_R0_delay_preservation', 0x060089C0, 0xE000)]
    if family != 'leaf':
        mutations += [('missing_pointer_stride_delay', 0x060089F6, 0x0009), ('eleven_halfwords', 0x060089EA, 0x7E16)]
    if family == 'library-validation':
        mutations = [('zero_count_allowed', 0x06095B0A, 0xE100), ('upper_bound_25', 0x06095B1E, 0xE019),
                     ('wrong_count_error', 0x06095B26, 0xE0FC), ('wrong_alignment_error', 0x06095B30, 0xE0FB),
                     ('wrong_descriptor_error', 0x06095B52, 0xE0FB), ('missing_error_clear', 0x06095B18, 0x0009),
                     ('lost_R14_delay_restore', 0x06095BCC, 0x0009)]
    for name, pc, word in mutations:
        changed = bytearray(data); offset = pc-pinned.BASE; changed[offset:offset+2] = word.to_bytes(2, 'big')
        chosen = selected[::max(1, len(selected)//48)]
        if family == 'library-validation':
            chosen += [c for c in selected if c[1] == 0 and c[2] == 0]
        rejected, reasons, first = 0, set(), None
        for case in chosen:
            try: run_case(changed, emu, case)
            except CaseFailure as error:
                if error.evidence['actual']['error'] and 'budget exceeded' in error.evidence['actual']['error']['reason']:
                    continue
                rejected += 1; reasons.add(str(error))
                if first is None: first = error.evidence
        if not rejected: raise ValueError('Mutation lacks non-budget rejection: ' + name)
        controls[name] = {'pc': pc, 'tested': len(chosen), 'nonbudget_rejections': rejected,
                          'reasons': sorted(reasons), 'first_rejection': first, 'mutated_kernel_sha256': pinned.digest(changed)}
    report = {'cases': len(rows), 'results': rows, 'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
              'instruction_controls': controls, 'original_game_bytes_executed': True,
              'complete_returns': sum(row['outcome'] == 'complete_return' for row in rows),
              'incomplete_prefixes': sum(row['outcome'] == 'incomplete_prefix' for row in rows)}
    if family == 'caller-prefix':
        _, model, regions = contract(selected[0]); refusal = observe(data, emu, family, model.before, regions, force_short=True)
        if (refusal['status'] != 'failed' or refusal['error']['reason'] != 'Handoff instruction budget exceeded' or
                len(refusal['trace']) != 128 or refusal['steps'] != 129 or short.MAX_STEPS != 128):
            raise ValueError('Original128 guard refusal differs')
        report['original128_refusal'] = {k: v for k, v in refusal.items() if k != 'regions_after'}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--saturn-recomp', type=Path, required=True)
    parser.add_argument('--family', choices=FAMILIES, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': 'neptune.original-first-task-contracts.v1', 'status': 'failure', 'selection': args.family,
              'release': 'usa-mk81070-v1003', 'module': 'KRNL', 'cpu': 'sh2', 'load_address': pinned.BASE,
              'lifetime': 'resident-kernel', 'kernel_sha256': pinned.KERNEL_SHA256,
              'interpreter_revision': pinned.INTERPRETER_REVISION, 'interpreter_sources': pinned.SOURCE_HASHES,
              'source_sha256': {name: pinned.digest(Path(__file__).with_name(name).read_bytes()) for name in
                  ('probe_task_init.py', 'probe_kernel.py', 'probe_kernel_records.py', 'sh2_handoff_profile.py',
                   'sh2_selection_profile.py', 'probe_split_add.py', 'probe_position_bounds.py')},
              'original_game_bytes_executed': False,
              'limitations': ['Constructed register/data/stack cases; no natural whole-function validation',
                             '89C8 and623A remain incomplete prefixes; valid95B04 stops before BIOS/library calls',
                             'No stubs, invented device RAM or injected ticks; hardware/gameplay/Godot parity unknown',
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
            if isinstance(error, CaseFailure):
                report['failure_evidence'] = error.evidence; report['original_game_bytes_executed'] = True
        output.write(json.dumps(report, sort_keys=True, separators=(',', ':'))+'\n')
    print(json.dumps({'status': report['status'], 'cases': report.get('cases', 0), 'selection': args.family}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__': raise SystemExit(main())
