#!/usr/bin/env python3
"""Natural cold-boot sound-68000 coverage experiment on the accepted USA reference.

`run --mode reference` executes the locked reference core; `run --mode enabled`
executes the separately prepared coverage core (m68k_coverage_core.py) with the
same lock, profile, options, inputs and frame count. `compare` requires exact
per-frame video/audio/input observations and final state equality between the
reference and every enabled run (observer non-perturbation) and identical
coverage between enabled runs (repeatability). Use fresh private outputs; raw
states, captures and coverage tables never belong in Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/saturn_lab'))
import m68k_coverage_core as coverage  # noqa: E402
from run_call_trace import reference, confined, read_json  # noqa: E402
import state_graphics  # noqa: E402

SCHEMA = 'neptune.m68k-natural-coverage-experiment.v1'
COMPARISON = 'neptune.m68k-natural-coverage-comparison.v1'
MAX_FRAMES = 36000
SOUND_RAM = 0x80000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def png(ppm):
    """Lossless PNG rendering of the frontend's private P6 capture (viewing aid only)."""
    header, _, rest = ppm.partition(b'\n255\n')
    _, size = header.split(b'\n')
    width, height = map(int, size.split())
    rows = b''.join(b'\0' + rest[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def sound_ram(state):
    """Sound RAM as the 68000 sees it (big-endian bytes) from a pinned Beetle state."""
    parsed = state_graphics.parse(state)
    words = state_graphics.field(parsed, 'SCSP', 'RAM', SOUND_RAM)
    return state_graphics.cpu_words(words, 'little')


def residency(state, driver_bytes):
    ram = sound_ram(state)
    resident = ram[:len(driver_bytes)]
    differing = [a for a in range(len(driver_bytes)) if resident[a] != driver_bytes[a]]
    return {'sound_ram_sha256': sha(ram), 'driver_window_sha256': sha(resident),
            'driver_bytes': len(driver_bytes), 'driver_sha256': sha(driver_bytes),
            'differing_bytes': len(differing), 'first_differing': differing[:16]}


def dsp_summary(state):
    """Identity of the SCSP DSP program/coefficients/addresses in a pinned Beetle state."""
    parsed = state_graphics.parse(state)
    mprog = state_graphics.field(parsed, 'SCSP', 'DSP.MPROG', 1024)
    steps = [mprog[i:i + 8] for i in range(0, 1024, 8)]
    return {'mprog_sha256': sha(mprog), 'mprog_nonzero_steps': sum(any(step) for step in steps),
            'mprog_last_nonzero_step': max((i for i, step in enumerate(steps) if any(step)), default=None),
            'coef_sha256': sha(state_graphics.field(parsed, 'SCSP', 'DSP.COEF', 128)),
            'madrs_sha256': sha(state_graphics.field(parsed, 'SCSP', 'DSP.MADRS', 64)),
            'rbp': state_graphics.field(parsed, 'SCSP', 'RBP', 1)[0],
            'rbl': state_graphics.field(parsed, 'SCSP', 'RBL', 1)[0]}


def run(args):
    if type(args.frames) is not int or not 1 <= args.frames <= MAX_FRAMES:
        raise ValueError('Require 1..%d bounded original frames' % MAX_FRAMES)
    if args.mode not in ('reference', 'enabled'):
        raise ValueError('Require reference or enabled mode')
    if args.output.exists():
        raise ValueError('Use fresh private output; never overwrite evidence')
    captures = sorted(set(args.capture))
    snapshots = sorted(set(args.snapshot))
    if any(not 0 <= f < args.frames for f in captures) or any(not 1 <= f <= args.frames for f in snapshots):
        raise ValueError('Capture/snapshot frames outside the declared window')
    if len(captures) > 64 or len(snapshots) > 16:
        raise ValueError('Too many captures or snapshots')
    driver_bytes = args.driver.read_bytes() if args.driver else None
    if driver_bytes is not None and sha(driver_bytes) != args.driver_sha256:
        raise ValueError('Supplied driver witness differs from the declared original identity')
    args.output.mkdir(mode=0o700, parents=True)
    result = {'schema': SCHEMA, 'status': 'failure', 'mode': args.mode, 'frames_requested': args.frames,
              'start': 'cold boot from power-on, no checkpoint import', 'model_calls': 0,
              'driver_sha256': sha(Path(__file__).read_bytes()),
              'source_modules': {name: sha((ROOT / 'tools/saturn_lab' / name).read_bytes()) for name in (
                  'm68k_coverage_core.py', 'm68k_coverage.h', 'run_call_trace.py', 'state_graphics.py')}}
    core_driver, observer, frames, phase = None, None, [], 'input_identity'
    try:
        module, lock, profile, identity, seed = reference(args.reference_root, args.lock, args.expected_lock)
        actions = module.validate_actions(read_json(args.actions)['actions'] if args.actions else [], args.frames)
        core = confined(args.reference_root, lock['inputs']['emulator'])
        if args.mode == 'enabled':
            core, receipt = coverage.load_prepared(args.prepared)
            result['prepared_receipt'] = {k: receipt[k] for k in ('binary_sha256', 'header_sha256', 'patched_hashes',
                                                                  'reference_revision', 'observer_abi')}
        result.update(reference_identity=identity, reference_lock_file_sha256=args.expected_lock,
                      selected_core_sha256=sha(core.read_bytes()), actions=actions,
                      actions_sha256=digest(actions))
        phase = 'core_load'
        save = args.output / 'save'
        save.mkdir()
        disc = confined(args.reference_root, lock['inputs']['disc'])
        for name in (disc.stem + '.smpc', 'mednafen_saturn_libretro_shared.smpc'):
            (save / name).write_bytes(bytes(seed))
        core_driver = module.Core(core, args.reference_root / profile['system_directory'], save, profile['options'],
                                  confined(args.reference_root, profile['log_shim']['path']))
        av = core_driver.load(disc, profile['controller_devices'])
        result['av'] = av
        if args.mode == 'enabled':
            observer = coverage.Coverage(core_driver.dll)
            observer.begin()
        phase = 'original_frame_execution'
        started, snaps = time.monotonic(), []
        for relative in range(args.frames):
            masks = [0] * 12
            for action in actions:
                if action['start'] <= relative < action['end']:
                    masks[action['port']] |= action['mask']
            if observer is not None:
                observer.frame(relative)
            frames.append(core_driver.step(masks))
            if relative in captures:
                ppm = args.output / f'frame-{relative:06}.ppm'
                module.write_capture(core_driver, ppm)
                (args.output / f'frame-{relative:06}.png').write_bytes(png(ppm.read_bytes()))
            if relative + 1 in snapshots:
                state = core_driver.save_state()
                (args.output / f'snapshot-{relative + 1:06}.state').write_bytes(state)
                snap = {'frame': relative + 1, 'state_sha256': sha(state), 'dsp': dsp_summary(state)}
                if driver_bytes is not None:
                    snap['residency'] = residency(state, driver_bytes)
                snaps.append(snap)
        result['emulation_wall_seconds'] = round(time.monotonic() - started, 3)
        final = core_driver.save_state()
        (args.output / 'final.state').write_bytes(final)
        observations = {'av': av, 'frames': frames}
        (args.output / 'observations.json').write_text(json.dumps(observations, sort_keys=True) + '\n')
        result.update(frames=len(frames), final_state_sha256=sha(final), frame_observations_sha256=digest(frames),
                      video_sha256=digest([f['video'] for f in frames]),
                      audio_sha256=digest([(f['audio_sha256'], f['audio_frames']) for f in frames]),
                      audio_frames=sum(f['audio_frames'] for f in frames), snapshots=snaps,
                      input_polls=core_driver.polls)
        result['final_dsp'] = dsp_summary(final)
        if driver_bytes is not None:
            result['final_residency'] = residency(final, driver_bytes)
        if observer is not None:
            phase = 'coverage_read'
            observer.stop()
            status = observer.status()
            if status['epoch_overflow'] or status['alloc_failed'] or status['on']:
                raise ValueError('Observer capacity/allocation failure; coverage is not evidence')
            epochs = [observer.epoch(i) for i in range(status['epochs'])]
            if any(e['edge_overflow'] for e in epochs):
                raise ValueError('Observer edge capacity exhausted; coverage is not evidence')
            raw = (json.dumps({'schema': 'neptune.m68k-natural-coverage.v1', 'status': status, 'epochs': epochs},
                              sort_keys=True, separators=(',', ':')) + '\n').encode()
            (args.output / 'coverage.json').write_bytes(raw)
            result.update(coverage_sha256=sha(raw), observer_status=status, epochs=[{
                k: e[k] for k in ('reset_pc', 'reset_ssp', 'first_frame', 'last_frame', 'steps', 'outside_steps',
                                  'opcode_changes', 'exceptions')} | {'executed_words': len(e['words']),
                                                                     'edges': len(e['edges'])} for e in epochs])
        result['status'] = 'success'
        return result
    except Exception as error:
        result['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': str(error)}
        raise
    finally:
        result['completed_original_frames'] = len(frames)
        if result['status'] != 'success' and frames:
            (args.output / 'partial-observations.json').write_text(json.dumps({'frames': frames}, sort_keys=True) + '\n')
        try:
            if core_driver is not None:
                core_driver.close()
        finally:
            (args.output / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


def compare(args):
    runs = {}
    for path in [args.reference, *args.enabled]:
        result = read_json(path / 'result.json')
        if result.get('status') != 'success':
            raise ValueError('Comparison requires successful runs: ' + str(path))
        observations = json.loads((path / 'observations.json').read_text())
        if digest(observations['frames']) != result['frame_observations_sha256']:
            raise ValueError('Observation file differs from its result digest: ' + str(path))
        if sha((path / 'final.state').read_bytes()) != result['final_state_sha256']:
            raise ValueError('Final state differs from its result digest: ' + str(path))
        runs[str(path)] = (result, observations)
    ref, ref_obs = runs[str(args.reference)]
    if ref['mode'] != 'reference' or any(runs[str(p)][0]['mode'] != 'enabled' for p in args.enabled):
        raise ValueError('Require one reference and enabled observer runs')
    report = {'schema': COMPARISON, 'status': 'failure', 'reference': str(args.reference),
              'enabled': [str(p) for p in args.enabled], 'frames': ref['frames'], 'checks': []}
    for path in args.enabled:
        result, obs = runs[str(path)]
        for key in ('frames', 'actions_sha256', 'reference_lock_file_sha256', 'av'):
            if result[key] != ref[key]:
                raise ValueError('Run declaration differs (%s): %s' % (key, path))
        first = next((i for i, (a, b) in enumerate(zip(ref_obs['frames'], obs['frames'])) if a != b), None)
        if first is not None or result['final_state_sha256'] != ref['final_state_sha256']:
            raise ValueError('Observer perturbed emulation; first differing frame %s in %s' % (first, path))
        report['checks'].append({'run': str(path), 'frames_equal': len(obs['frames']),
                                 'final_state_equal': True, 'coverage_sha256': result['coverage_sha256']})
    hashes = {runs[str(p)][0]['coverage_sha256'] for p in args.enabled}
    if len(hashes) != 1:
        raise ValueError('Enabled runs produced different coverage tables')
    for path in args.enabled:
        if sha((path / 'coverage.json').read_bytes()) != runs[str(path)][0]['coverage_sha256']:
            raise ValueError('Coverage file differs from its result digest: ' + str(path))
    report.update(status='success', coverage_sha256=hashes.pop(), final_state_sha256=ref['final_state_sha256'],
                  video_sha256=ref['video_sha256'], audio_sha256=ref['audio_sha256'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run')
    r.add_argument('--reference-root', type=Path, required=True)
    r.add_argument('--lock', type=Path, required=True)
    r.add_argument('--expected-lock', required=True)
    r.add_argument('--mode', required=True)
    r.add_argument('--prepared', type=Path)
    r.add_argument('--frames', type=int, required=True)
    r.add_argument('--actions', type=Path)
    r.add_argument('--capture', type=int, action='append', default=[])
    r.add_argument('--snapshot', type=int, action='append', default=[])
    r.add_argument('--driver', type=Path)
    r.add_argument('--driver-sha256', default='c8842cc957bf82693ddd72d996353c9cb92feb34fe5f2834c0651aebacb4bd04')
    r.add_argument('--output', type=Path, required=True)
    c = sub.add_parser('compare')
    c.add_argument('--reference', type=Path, required=True)
    c.add_argument('--enabled', type=Path, action='append', required=True)
    c.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            result = run(args)
            print(json.dumps({k: result.get(k) for k in ('status', 'frames', 'final_state_sha256', 'coverage_sha256',
                                                         'emulation_wall_seconds')}))
        else:
            if args.report.exists():
                raise ValueError('Comparison report requires a fresh path')
            report = compare(args)
            args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
            print(json.dumps({k: report[k] for k in ('status', 'frames', 'coverage_sha256')}))
    except Exception as error:  # noqa: BLE001 - CLI boundary reports any failure
        print('FAIL: %s: %s' % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
