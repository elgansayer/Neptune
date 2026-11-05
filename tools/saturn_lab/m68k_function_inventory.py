#!/usr/bin/env python3
"""Join a pinned static 68000 descent with natural coverage into a function inventory.

Static: the pinned saturn-recomp/Musashi descent supplies instruction lengths
and resolved jump tables; this module classifies control flow from opcode bits,
derives function entries (vectors, direct and table calls, natural call and
exception targets) and each entry's intra-procedural body.

Natural: an enabled run of run_m68k_coverage.py supplies the executed
instruction starts, fetched opcode words and the complete observed control-flow
edge set of one 68000 reset epoch. Every executed word must match the resident
image and decode as an instruction start; every observed edge must be explained
by the static model of the instruction it leaves. Built-in altered-copy controls
must be rejected by those same checks before a report can succeed.

The report is derived data (addresses, counts, hashes). Original bytes,
disassembly and raw coverage stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SCHEMA = 'neptune.m68k-function-inventory.v1'
RET = {0x4E75: 'rts', 0x4E73: 'rte', 0x4E77: 'rtr'}
STOPS = {0x4AFC}  # ILLEGAL: no successor in the static model


def sha(data):
    return hashlib.sha256(data).hexdigest()


def u16(img, a):
    return int.from_bytes(img[a:a + 2], 'big')


def s16(img, a):
    return int.from_bytes(img[a:a + 2], 'big', signed=True)


def u32(img, a):
    return int.from_bytes(img[a:a + 4], 'big')


def flow(img, a, length, table_targets=None):
    """(kind, static targets, falls through) of the instruction at `a` from its opcode bits.

    kinds: return, stop, jump, branch, call, trap, plain. Indirect JMP/JSR take
    resolved table targets when supplied, otherwise they are 'indirect'.
    """
    op = u16(img, a)
    if op in RET:
        return 'return', [], False
    if op in STOPS:
        return 'stop', [], False
    if op & 0xF000 == 0x6000:
        disp = op & 0xFF
        target = a + 2 + (s16(img, a + 2) if disp == 0 else (disp - 256 if disp & 0x80 else disp))
        cond = op & 0x0F00
        if cond == 0x0000:
            return 'jump', [target], False
        if cond == 0x0100:
            return 'call', [target], True
        return 'branch', [target], True
    if op & 0xF0F8 == 0x50C8:
        return 'branch', [a + 2 + s16(img, a + 2)], True
    if op & 0xFFF0 == 0x4E40 or op == 0x4E76:
        return 'trap', [], True
    if op & 0xFF80 == 0x4E80:
        call, mode = not op & 0x40, op & 0x3F
        if mode == 0x38:
            targets = [s16(img, a + 2) & 0xFFFFFF]
        elif mode == 0x39:
            targets = [u32(img, a + 2) & 0xFFFFFF]
        elif mode == 0x3A:
            targets = [a + 2 + s16(img, a + 2)]
        elif table_targets is not None:
            targets = list(table_targets)
        else:
            return ('call' if call else 'jump'), None, call  # unresolved indirect
        return ('call' if call else 'jump'), targets, call
    return 'plain', [], True


class Model:
    """Static instruction/flow model of one image plus explicit extra entries."""

    def __init__(self, img, code, tables, vectors, extra_entries=(), natural_targets=None):
        self.img, self.code = img, dict(code)  # address -> length
        # Observed targets of statically unresolved indirect transfers (kept separate
        # from static flow so natural edges are never used to explain themselves).
        self.natural = {a: set(t) for a, t in (natural_targets or {}).items()}
        self.flows = {}
        for a, n in self.code.items():
            self.flows[a] = flow(img, a, n, tables.get(a))
        self.vectors = vectors  # vector number -> target (in-image, even)
        entries = {}
        for number, target in vectors.items():
            kind = 'reset' if number == 1 else 'exception'
            entries.setdefault(target, set()).add(kind)
        for a, (kind, targets, _) in self.flows.items():
            if kind == 'call' and targets:
                for t in targets:
                    entries.setdefault(t, set()).add('table-call' if a in tables else 'call')
        for target, kind in extra_entries:
            entries.setdefault(target, set()).add(kind)
        self.entries = {a: sorted(k) for a, k in entries.items()}

    def successors(self, a):
        """Intra-procedural successors; calls fall through, jumps to an entry are tail calls."""
        kind, targets, falls = self.flows[a]
        out = []
        if falls:
            out.append(a + self.code[a])
        if kind in ('branch', 'jump') and targets:
            out += [t for t in targets if not (kind == 'jump' and t in self.entries)]
        if kind == 'jump' and targets is None:
            out += [t for t in self.natural.get(a, ()) if t not in self.entries]
        return out

    def body(self, entry):
        seen, todo = set(), [entry]
        while todo:
            a = todo.pop()
            if a in seen or a not in self.code:
                continue
            seen.add(a)
            todo += self.successors(a)
        return seen


def extents(addresses, code):
    out = []
    for a in sorted(addresses):
        end = a + code[a]
        if out and out[-1][1] == a:
            out[-1][1] = end
        else:
            out.append([a, end])
    return out


def explain(model, edge, return_sites, dynamic_targets):
    """Why a natural edge is consistent with the static model, or None."""
    src, dst, kind, vector = edge[:4]
    if kind == 'epoch':
        return 'reset-entry' if model.vectors.get(1) == dst else None
    if kind == 'exception':
        return 'exception-vector' if model.vectors.get(vector) == dst else None
    if src not in model.code:
        return None
    k, targets, falls = model.flows[src]
    if falls and dst == src + model.code[src]:
        return 'fall-through'
    if k == 'return':
        return 'return-to-call-site' if dst in return_sites else None
    if targets and dst in targets:
        return {'call': 'call', 'jump': 'jump', 'branch': 'branch-taken'}[k]
    if targets is None and k in ('call', 'jump'):
        dynamic_targets.setdefault(src, set()).add(dst)
        return 'indirect-' + k
    return None


def check_natural(model, epoch, image_name):
    """Exact natural-vs-static consistency; returns (summary, failures)."""
    failures = []
    executed = {w[0]: w for w in epoch['words']}
    for a, w in executed.items():
        if a >= len(model.img):
            failures.append(['executed-outside-image', a])
        elif w[3] != u16(model.img, a):
            failures.append(['opcode-differs-from-' + image_name, a])
        elif a not in model.code:
            failures.append(['executed-not-static-instruction', a])
    if epoch['outside_steps'] or epoch['opcode_changes']:
        failures.append(['outside-or-changed-opcode-steps', epoch['outside_steps'], epoch['opcode_changes']])
    return_sites = {a + model.code[a] for a, (k, _, _) in model.flows.items() if k in ('call', 'trap')}
    return_sites |= {e[0] for e in epoch['edges'] if e[2] == 'exception'}  # stacked interrupt PCs
    reasons, dynamic_targets = {}, {}
    for edge in epoch['edges']:
        why = explain(model, edge, return_sites, dynamic_targets)
        if why is None:
            failures.append(['unexplained-edge'] + edge[:4])
        else:
            reasons[why] = reasons.get(why, 0) + 1
    return {'executed_words': len(executed), 'edges': len(epoch['edges']), 'edge_reasons': reasons,
            'dynamic_indirect_targets': {f'0x{k:04X}': sorted(f'0x{t:04X}' for t in v)
                                         for k, v in sorted(dynamic_targets.items())}}, failures


def inventory(model, epoch=None):
    executed = {w[0]: w for w in (epoch or {}).get('words', [])}
    calls_in, callers = {}, {}
    if epoch:
        for src, dst, kind, vector, count, _ in epoch['edges']:
            if kind == 'flow' and src in model.code and model.flows[src][0] == 'call' and dst in model.entries:
                calls_in[dst] = calls_in.get(dst, 0) + count
                callers.setdefault(dst, set()).add(src)
            if kind == 'exception' and dst in model.entries:
                calls_in[dst] = calls_in.get(dst, 0) + count
    static_callers = {}
    for a, (k, targets, _) in model.flows.items():
        if k == 'call' and targets:
            for t in targets:
                static_callers.setdefault(t, set()).add(a)
    functions, owners = [], {}
    for entry in sorted(model.entries):
        body = model.body(entry)
        for a in body:
            owners.setdefault(a, []).append(entry)
        callees = sorted({t for a in body for t in (model.flows[a][1] or model.natural.get(a, ()))
                          if model.flows[a][0] == 'call'}
                         | {t for a in body for t in (model.flows[a][1] or [])
                            if model.flows[a][0] == 'jump' and t in model.entries})
        unresolved = sorted(a for a in body if model.flows[a][1] is None)
        hit = [a for a in body if a in executed]
        functions.append({
            'entry': f'0x{entry:04X}', 'kinds': model.entries[entry], 'instructions': len(body),
            'bytes': sum(model.code[a] for a in body), 'extents': [[f'0x{a:04X}', f'0x{b:04X}'] for a, b in extents(body, model.code)],
            'returns': sum(1 for a in body if model.flows[a][0] == 'return'),
            'static_call_sites': sorted(f'0x{a:04X}' for a in static_callers.get(entry, ())),
            'callees': [f'0x{t:04X}' for t in callees], 'unresolved_indirect': [f'0x{a:04X}' for a in unresolved],
            'natural': None if epoch is None else {
                'entry_executed': entry in executed, 'executed_instructions': len(hit),
                'entry_hits': executed[entry][1] if entry in executed else 0,
                'observed_calls_or_exceptions': calls_in.get(entry, 0),
                'observed_call_sites': sorted(f'0x{a:04X}' for a in callers.get(entry, ())),
                'first_frame': executed[entry][2] if entry in executed else None}})
    interior = sorted(e for e in model.entries if any(e in model.body(o) and o != e for o in model.entries if o < e))
    owned = set(owners)
    return functions, {
        'entries': len(model.entries), 'interior_entries': len(interior),
        'static_instructions': len(model.code), 'static_code_bytes': sum(model.code.values()),
        'owned_instructions': len(owned), 'shared_instructions': sum(1 for v in owners.values() if len(v) > 1),
        'unowned_instructions': len(set(model.code) - owned),
        'executed_entries': None if epoch is None else sum(1 for f in functions if f['natural']['entry_executed']),
        'executed_instructions': None if epoch is None else len(set(executed) & set(model.code))}


def resident_patches(disc, resident, code):
    """Classify resident-vs-disc differences as code (inside decoded instructions) or data."""
    owner = {}
    for a, n in code.items():
        for b in range(a, a + n):
            owner[b] = a
    code_sites, data = {}, []
    for b in range(len(disc)):
        if disc[b] != resident[b]:
            if b in owner:
                code_sites.setdefault(owner[b], []).append(b)
            else:
                data.append(b)
    return code_sites, data


def ranges(values):
    out = []
    for v in sorted(values):
        if out and out[-1][1] == v:
            out[-1][1] = v + 1
        else:
            out.append([v, v + 1])
    return [[f'0x{a:04X}', b - a] for a, b in out]


def build(module, library, disc, epoch=None, resident=None):
    """Full static+natural analysis of one driver image; returns (report, failures)."""
    def descend(image, extra=()):
        img = module.Image(image, library)
        program = module.Program(img, sorted(set(module.Program(img).vectors()) | set(extra)))
        tables = {j: t for j, t in program._targets.items()}
        return img, program, tables
    vectors = {n: u32(disc, 4 * n) for n in range(1, 256)
               if 0x400 <= u32(disc, 4 * n) < len(disc) and not u32(disc, 4 * n) & 1}
    img, program, tables = descend(disc)
    disc_model = Model(disc, program.code, tables, vectors)
    report = {'driver_bytes': len(disc), 'driver_sha256': sha(disc), 'vectors': {
        str(n): f'0x{t:04X}' for n, t in sorted(vectors.items()) if t != vectors.get(4) or n == 4},
        'default_vector_target': f'0x{vectors.get(4, 0):04X}',
        'disc_static': {'instructions': len(program.code), 'code_bytes': len(program.code_bytes()),
                        'data_bytes': len(program.data), 'unclassified_bytes': sum(n for _, n in program.gaps()),
                        'tables': [[f'0x{j:04X}', k, f'0x{f:04X}', n] for j, k, f, n in program.tables],
                        'unresolved_indirect': [f'0x{a:04X}' for a in sorted(program.unresolved)],
                        'bad_paths': {f'0x{a:04X}': why for a, why in sorted(program.bad.items())}}}
    failures = []
    image, name = disc, 'disc'
    if resident is not None:
        code_sites, data = resident_patches(disc, resident, program.code)
        patched = bytearray(disc)
        for site, offsets in code_sites.items():
            for b in offsets:
                patched[b] = resident[b]
        image, name = bytes(patched), 'resident'
        report['resident'] = {'code_patch_sites': [{'instruction': f'0x{a:04X}', 'changed_bytes': len(v),
                                                    'first': f'0x{v[0]:04X}'} for a, v in sorted(code_sites.items())],
                              'data_changed_ranges': ranges(data), 'data_changed_bytes': len(data),
                              'patched_image_sha256': sha(image)}
    extra, natural_targets = [], {}
    if epoch is not None:
        # Observed targets of statically unresolved indirect transfers become explicit
        # descent seeds; indirect call targets also become function entries.
        _, probe_program, probe_tables = descend(image)
        probe = Model(image, probe_program.code, probe_tables, vectors)
        for src, dst, kind, vector, count, _ in epoch['edges']:
            if kind == 'flow' and src in probe.code:
                k, targets, falls = probe.flows[src]
                if k in ('call', 'jump') and targets is None:
                    extra.append((dst, 'natural-indirect-' + k))
                    natural_targets.setdefault(src, set()).add(dst)
    img2, program2, tables2 = descend(image, [d for d, _ in extra])
    model = Model(image, program2.code, tables2, vectors, [(d, k) for d, k in extra if k.endswith('call')],
                  natural_targets)
    report['analysed_image'] = {'name': name, 'sha256': sha(image), 'instructions': len(program2.code),
                                'code_bytes': len(program2.code_bytes()), 'data_bytes': len(program2.data),
                                'unclassified_bytes': sum(n for _, n in program2.gaps()),
                                'unclassified_ranges': [[f'0x{a:04X}', n] for a, n in program2.gaps()],
                                'unresolved_indirect': [f'0x{a:04X}' for a in sorted(program2.unresolved)],
                                'bad_paths': {f'0x{a:04X}': why for a, why in sorted(program2.bad.items())},
                                'natural_extra_entries': sorted({f'0x{d:04X}' for d, _ in extra})}
    report['analysed_image']['gap_evidence'] = [
        {'start': f'0x{a:04X}', 'bytes': n, 'content': kind, 'return_words': returns,
         'code_references_into': pointers, 'clean_descent_instructions': decodes}
        for a, n, kind, returns, pointers, decodes in module.evidence(program2)]
    if epoch is not None:
        summary, failures = check_natural(model, epoch, name)
        report['natural_consistency'] = summary
        # Natural dispatch through each statically resolved table: flow edges only,
        # so an interrupt taken at the table instruction is not counted as a dispatch.
        observed = {}
        for src, dst, kind, vector, count, _ in epoch['edges']:
            if kind == 'flow' and src in tables2:
                observed.setdefault(src, {})[dst] = observed.setdefault(src, {}).get(dst, 0) + count
        report['natural_tables'] = [
            {'jump': f'0x{j:04X}', 'kind': k, 'first': f'0x{f:04X}', 'static_entries': n,
             'observed_targets': [[f'0x{t:04X}', c] for t, c in sorted(observed.get(j, {}).items())]}
            for j, k, f, n in program2.tables]
    functions, totals = inventory(model, epoch)
    report['functions'] = functions
    report['totals'] = totals
    if resident is not None:
        # The original file bytes remain the code denominator: routines whose only
        # call sites are patched out at runtime are original functions, not data.
        disc_functions, disc_totals = inventory(disc_model)
        resident_entries = {f['entry'] for f in functions}
        report['disc_image_inventory'] = {'totals': disc_totals, 'entries_not_in_resident': [
            {k: f[k] for k in ('entry', 'kinds', 'instructions', 'bytes', 'static_call_sites')}
            for f in disc_functions if f['entry'] not in resident_entries]}
        disc_entries = {f['entry'] for f in disc_functions}
        report['union_entries'] = len(disc_entries | resident_entries)
        report['resident_only_entries'] = sorted(resident_entries - disc_entries)
    return report, failures


def controls(module, library, disc, epoch, resident):
    """Altered copies that the natural checks must reject; returns control outcomes."""
    outcomes = {}
    executed = sorted(w[0] for w in epoch['words'])
    target = next(a for a in executed if a > 0x1100)
    # 1. Image control: change one executed opcode word in the resident image.
    altered = bytearray(resident)
    altered[target] ^= 0x01
    _, f1 = build(module, library, disc, epoch, bytes(altered))
    outcomes['changed_executed_opcode'] = any(f[0].startswith('opcode-differs') for f in f1)
    # 2. Patch control: analyse the unpatched disc image against the natural epoch.
    _, f2 = build(module, library, disc, epoch, None)
    outcomes['patches_ignored'] = any(f[0].startswith('opcode-differs') for f in f2)
    # 3. Edge control: a fabricated transfer from a non-branching instruction.
    fake = json.loads(json.dumps(epoch))
    plain = next(w[0] for w in fake['words'] if w[0] > 0x1100 and w[0] + 0x40 < len(disc)
                 and flow(resident, w[0], 2)[0] == 'plain')
    fake['edges'].append([plain, plain + 0x40, 'flow', 0, 1, 0])
    _, f3 = build(module, library, disc, fake, resident)
    outcomes['fabricated_edge'] = any(f[0] == 'unexplained-edge' for f in f3)
    # 4. Coverage control: a fabricated executed word inside an unclassified gap.
    fake = json.loads(json.dumps(epoch))
    fake['words'].append([len(disc) - 2, 1, 0, u16(resident, len(disc) - 2), 0])
    _, f4 = build(module, library, disc, fake, resident)
    outcomes['fabricated_executed_word'] = any(f[0] == 'executed-not-static-instruction' for f in f4)
    return outcomes


def select_epoch(coverage, image, minimum=64):
    """Index of the single epoch whose executed opcode words match `image` (>= 99%)."""
    matches = []
    for index, epoch in enumerate(coverage['epochs']):
        words = [w for w in epoch['words'] if w[0] + 2 <= len(image)]
        same = sum(1 for w in words if w[3] == u16(image, w[0]))
        if len(words) >= minimum and same >= 0.99 * len(epoch['words']):
            matches.append(index)
    if len(matches) != 1:
        raise ValueError('Expected exactly one epoch matching the driver image, found %d' % len(matches))
    return matches[0]


def main(argv=None):
    sys.path.insert(0, str(HERE))
    import analyze_sound_driver as sound
    import run_m68k_coverage as natural
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--module', choices=tuple(sound.SOURCES), required=True)
    parser.add_argument('--saturn-recomp', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--coverage-run', type=Path, help='enabled run directory (coverage.json, result.json)')
    parser.add_argument('--resident-state', type=Path, help='natural state for resident patch classification')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path', file=sys.stderr)
        return 1
    report = {'schema': SCHEMA, 'status': 'failure', 'module': args.module, 'release': 'usa-mk81070-v1003',
              'cpu': 'm68000', 'candidate_load_address': 0, 'source_identity': list(sound.SOURCES[args.module]),
              'decoder_sources': sound.TOOL_HASHES, 'tool_sha256': sha(Path(__file__).read_bytes()),
              'limitations': ['Static bodies assume calls return and resolved tables are complete',
                              'Natural coverage is one bounded Beetle/Mednafen window, not all game states',
                              'Function entries are call/vector targets; names and semantics are not recovered here']}
    try:
        disc = sound.source_bytes(args.source_file, args.module)
        module = sound.decoder(args.saturn_recomp)
        library = module.library(str(args.cache))
        epoch = resident = None
        if args.coverage_run:
            run = json.loads(args.coverage_run.joinpath('result.json').read_text())
            raw = args.coverage_run.joinpath('coverage.json').read_bytes()
            if run.get('status') != 'success' or sha(raw) != run.get('coverage_sha256'):
                raise ValueError('Coverage file differs from its successful run receipt')
            coverage = json.loads(raw)
            if not args.resident_state:
                raise ValueError('Natural join requires the resident state that classifies runtime patches')
            state = args.resident_state.read_bytes()
            resident = natural.sound_ram(state)[:len(disc)]
            index = select_epoch(coverage, resident)
            epoch = coverage['epochs'][index]
            report['natural_run'] = {'result_sha256': sha(args.coverage_run.joinpath('result.json').read_bytes()),
                                     'coverage_sha256': run['coverage_sha256'], 'epoch_index': index,
                                     'epochs_observed': len(coverage['epochs']),
                                     'resident_state_sha256': sha(state),
                                     'frames': run['frames'], 'actions_sha256': run['actions_sha256'],
                                     'epoch': {k: epoch[k] for k in ('reset_pc', 'reset_ssp', 'first_frame', 'last_frame',
                                                                     'steps', 'exceptions', 'opcode_changes', 'outside_steps')},
                                     'other_epochs': [{k: e[k] for k in ('reset_pc', 'first_frame', 'last_frame', 'steps')}
                                                      | {'executed_words': len(e['words'])}
                                                      for i, e in enumerate(coverage['epochs']) if i != index]}
        body, failures = build(module, library, disc, epoch, resident)
        report.update(body)
        if epoch is not None:
            outcomes = controls(module, library, disc, epoch, resident)
            report['negative_controls'] = outcomes
            if not all(outcomes.values()):
                failures.append(['negative-control-not-detected', sorted(k for k, v in outcomes.items() if not v)])
        report['failures'] = failures[:64]
        report['failure_count'] = len(failures)
        report['status'] = 'success' if not failures else 'failure'
    except (ValueError, OSError, KeyError, StopIteration) as error:
        report['error'] = {'type': type(error).__name__, 'reason': str(error)}
    with os.fdopen(fd, 'w') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report.get(k) for k in ('status', 'failure_count', 'totals')}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    sys.exit(main())
