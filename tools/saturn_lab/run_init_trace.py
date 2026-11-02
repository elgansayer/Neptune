#!/usr/bin/env python3
"""Separate native initialization experiment from a verified original boot state.

Run within existing resource admission and offline read-only guards. Historical
locks/checkpoints and the scheduler observer driver remain unchanged.
"""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/factory'))
import provision
import provision_init_trace_abi as observer
import probe_kernel
import state_graphics
from run_call_trace import REFERENCE_CORE, reference, confined, read_json, sha
from run_context_trace import read_boot_checkpoint

SCHEMA = 'neptune.explicit-init-trace-experiment.v1'


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def source_words(kernel):
    return [int.from_bytes(kernel[address-probe_kernel.BASE+2*i:address-probe_kernel.BASE+2*i+2], 'big')
            for address, count in observer.WITNESS_RANGES for i in range(count)]


def resident(state, kernel):
    parsed = state_graphics.parse(state)
    high = state_graphics.cpu_words(state_graphics.field(parsed, 'MAIN', 'WorkRAMH', 0x100000), 'little')
    witnesses = []
    for address, count in observer.WITNESS_RANGES:
        expected = kernel[address-probe_kernel.BASE:address-probe_kernel.BASE+2*count]
        if high[address-0x06000000:address-0x06000000+len(expected)] != expected:
            raise ValueError('Original initialization source witness is absent from High Work RAM')
        witnesses.append({'address': f'0x{address:08x}', 'bytes': len(expected), 'sha256': sha(expected)})
    return witnesses


def boot_residency(state, kernel):
    """Verified original boot checkpoints may precede the last kernel sectors.

    Malformed states still fail. Native entry/snapshots and final comparison
    require the complete, unchanged witness rather than accepting partial code.
    """
    try:
        return resident(state, kernel)
    except ValueError as error:
        if str(error) != 'Original initialization source witness is absent from High Work RAM': raise
        return []


def run(args):
    if type(args.profile) is not int or args.profile not in (1, 2):
        raise ValueError('Require fixed original89C8 or95B04 profile1/2')
    if type(args.frames) is not int or not 1 <= args.frames <= 600:
        raise ValueError('Require1..600 original frames')
    if type(args.start_frames) is not int or not 0 <= args.start_frames <= args.frames:
        raise ValueError('Require bounded port-zero Start pulse')
    if args.mode not in ('reference', 'disabled', 'enabled'):
        raise ValueError('Require reference/disabled/enabled mode')
    if args.output.exists(): raise ValueError('Use fresh private output; never overwrite evidence')
    args.output.mkdir(mode=0o700, parents=True)
    result = {'schema': SCHEMA, 'status': 'failure', 'mode': args.mode,
              'init_profile': args.profile, 'port_zero_start_frames': args.start_frames,
              'driver_sha256': sha(Path(__file__).read_bytes()), 'model_calls': 0,
              'state_import': 'verified original reference boot checkpoint; historical lock unchanged',
              'source_modules': {name: sha((ROOT/path).read_bytes()) for name, path in {
                  'observer': 'tools/factory/provision_init_trace_abi.py',
                  'provisioner': 'tools/factory/provision.py',
                  'state_parser': 'tools/saturn_lab/state_graphics.py',
                  'kernel_identity': 'tools/saturn_lab/probe_kernel.py',
                  'reference_adapter': 'tools/saturn_lab/run_call_trace.py',
                  'boot_checkpoint_adapter': 'tools/saturn_lab/run_context_trace.py'}.items()}}
    driver, tracer, frames, attempted, source_known = None, None, [], False, False
    phase = 'input_identity'
    try:
        module, lock, profile, identity, seed = reference(args.reference_root, args.lock, args.expected_lock)
        original, state = read_boot_checkpoint(module, args.boot_checkpoint, identity, args.expected_lock)
        if original['frame']+args.frames > 4800: raise ValueError('Original boot experiment exceeds4800-frame bound')
        kernel = probe_kernel.kernel_bytes(args.kernel)
        result.update(reference_identity=identity, reference_lock_file_sha256=args.expected_lock,
                      reference_checkpoint_file_sha256=sha(args.boot_checkpoint.read_bytes()),
                      reference_state_sha256=original['state_sha256'], reference_frame=original['frame'],
                      original_kernel_sha256=sha(kernel), input_boot_checkpoint_verified=True)
        inputs = (ROOT, args.reference_root, args.boot_checkpoint.parent, args.kernel.parent)
        if any(not os.statvfs(path).f_flag & os.ST_RDONLY for path in inputs):
            raise ValueError('Run with source/media/boot checkpoint/kernel mounted read-only')
        witness = boot_residency(state, kernel); source_known = bool(witness)
        core = confined(args.reference_root, lock['inputs']['emulator'])
        if args.mode != 'reference':
            if args.prepared is None: raise ValueError('Require separate immutable prepared initialization core')
            _, _, recipe = provision.identity('beetle-saturn-init-trace', ROOT)
            core = provision.cached(args.prepared, 'beetle-saturn-init-trace', recipe, ROOT)
            if not os.statvfs(args.prepared).f_flag & os.ST_RDONLY:
                raise ValueError('Prepared initialization core must be mounted read-only')
            result['prepared_recipe_sha256'] = recipe
        result.update(selected_core_sha256=provision.digest(core), resident_code_before=witness,
                      kernel_witness_complete_before=bool(witness))
        phase = 'core_load_and_verified_original_state_import'
        save = args.output/'save'; save.mkdir()
        disc = confined(args.reference_root, lock['inputs']['disc'])
        for name in (disc.stem+'.smpc', 'mednafen_saturn_libretro_shared.smpc'):
            (save/name).write_bytes(bytes(seed))
        driver = module.Core(core, args.reference_root/profile['system_directory'], save, profile['options'],
                             confined(args.reference_root, profile['log_shim']['path']))
        av = driver.load(disc, profile['controller_devices']); driver.restore(state)
        driver.frame, driver.video = original['frame'], original['last_video']
        imported = driver.save_state(); witness = boot_residency(imported, kernel)
        source_known = source_known or bool(witness)
        (args.output/'imported.state').write_bytes(imported)
        result.update(av=av, imported_state_bytes=len(imported), imported_state_sha256=sha(imported),
                      resident_code_before=witness, kernel_witness_complete_before=bool(witness))
        if args.mode != 'reference':
            tracer = observer.Trace(driver.dll)
            if args.mode == 'enabled':
                tracer.start(args.profile, 1, source_words(kernel))
                if tracer.witness() != source_words(kernel):
                    raise ValueError('Native initialization witness differs from original kernel')
        phase = 'original_frame_execution'; started = time.monotonic()
        for relative in range(args.frames):
            if args.mode == 'enabled': tracer.frame(driver.frame)
            attempted = True
            frames.append(driver.step([8 if relative < args.start_frames else 0]+[0]*11))
        elapsed = time.monotonic()-started; final = driver.save_state()
        (args.output/'final.state').write_bytes(final)
        (args.output/'observations.json').write_text(json.dumps({'av': av, 'frames': frames}, sort_keys=True)+'\n')
        final_witness = resident(final, kernel); source_known = True
        result.update(frames=len(frames), final_state_sha256=sha(final), frame_observations_sha256=digest(frames),
                      video_sha256=digest([f['video'] for f in frames]),
                      audio_sha256=digest([(f['audio_sha256'], f['audio_frames']) for f in frames]),
                      audio_frames=sum(f['audio_frames'] for f in frames), emulation_wall_seconds=elapsed,
                      input_polls=driver.polls, delivered_masks=[sorted(values) for values in driver.delivered],
                      resident_code_after=final_witness)
        if args.mode == 'enabled':
            phase = 'bounded_original_initialization_validation'
            trace = tracer.finish(); raw = (json.dumps(trace, indent=2, sort_keys=True)+'\n').encode()
            (args.output/'init-trace.json').write_bytes(raw)
            result.update(trace_sha256=sha(raw), completed_roots=trace['completed_roots'])
        result['status'] = 'success'; return result
    except Exception as error:
        result['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': str(error)}
        raise
    finally:
        result.update(completed_original_frames=len(frames), original_execution_attempted=attempted,
                      original_game_bytes_executed=True if frames and source_known else None if attempted else False)
        if result['status'] != 'success' and frames:
            (args.output/'partial-observations.json').write_text(json.dumps({'frames': frames}, sort_keys=True)+'\n')
        if result['status'] != 'success' and attempted and driver is not None and not (args.output/'final.state').exists():
            try:
                partial = driver.save_state(); (args.output/'partial.state').write_bytes(partial)
                result['partial_state_sha256'] = sha(partial)
            except Exception as error:
                result['partial_state_error'] = {'type': type(error).__name__, 'reason': str(error)}
        if tracer is not None and tracer.started and result['status'] != 'success':
            try:
                tracer.dll.neptune_init_stop(); records, status = tracer.snapshot()
                result['failed_trace_status'] = observer.serialise(status)
                diagnostic = {'schema': 'neptune.failed-init-trace-diagnostic.v1', 'accepted': False,
                              'status': result['failed_trace_status'], 'records': [observer.serialise(r) for r in records],
                              'first_mismatched_source_witness': tracer.witness(True)}
                (args.output/'failed-init-records.json').write_text(json.dumps(diagnostic, indent=2, sort_keys=True)+'\n')
            except Exception as error:
                result['diagnostic_error'] = {'type': type(error).__name__, 'reason': str(error)}
        try:
            if driver is not None: driver.close()
        except Exception as error:
            result['status'] = 'failure'; result['cleanup_error'] = {'type': type(error).__name__, 'reason': str(error)}
            raise
        finally:
            (args.output/'result.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')


def decoded_trace(value, kernel):
    if value.get('schema') != 'neptune.original-first-task-init-trace.v1' or not isinstance(value.get('records'), list):
        raise ValueError('Missing versioned original initialization records')
    if not 4 <= len(value['records']) <= observer.CAPACITY: raise ValueError('Empty/oversized initialization records')
    records = []
    for item in value['records']:
        record = observer.Record()
        if not isinstance(item, dict) or set(item) != {name for name, _ in record._fields_}:
            raise ValueError('Malformed initialization record')
        for name, _ in record._fields_:
            if isinstance(getattr(record, name), observer.C.Array):
                values = item[name]
                if name in ('library', 'tables', 'slots') and item['library_valid'] == 0 and values is None: continue
                if (not isinstance(values, list) or len(values) != len(getattr(record, name)) or
                        any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in values)):
                    raise ValueError('Invalid initialization snapshot vector')
                getattr(record, name)[:] = values
            else:
                low, high = (-0x80000000, 0x7FFFFFFF) if name == 'timestamp' else (0, 0xFFFFFFFF)
                if type(item[name]) is not int or not low <= item[name] <= high:
                    raise ValueError('Invalid initialization scalar')
                setattr(record, name, item[name])
        records.append(record)
    fields = {name for name, _ in observer.Status._fields_}
    if not isinstance(value.get('status'), dict) or set(value['status']) != fields: raise ValueError('Missing exact initialization status')
    status = observer.Status()
    for name in fields:
        number = value['status'][name]
        if type(number) is not int or not 0 <= number <= 0xFFFFFFFF: raise ValueError('Invalid initialization status scalar')
        setattr(status, name, number)
    expected = observer.validate(records, status, source_words(kernel))
    if value != expected: raise ValueError('Initialization summary differs from independently validated records')
    return expected


def compare(directories, kernel):
    if len(directories) != 6 or len({p.resolve() for p in directories}) != 6:
        raise ValueError('Require two distinct fresh original runs per mode')
    runs = []
    for directory in directories:
        report = read_json(directory/'result.json'); observations = read_json(directory/'observations.json')
        if report.get('schema') != SCHEMA or report.get('status') != 'success': raise ValueError('Required original run missing/failed')
        frames = observations.get('frames')
        if (not isinstance(frames, list) or not 1 <= len(frames) <= 600 or report.get('frames') != len(frames) or
                report.get('original_game_bytes_executed') is not True or report.get('completed_original_frames') != len(frames) or
                type(report.get('init_profile')) is not int or report['init_profile'] not in (1, 2) or
                report.get('original_kernel_sha256') != sha(kernel) or report.get('input_boot_checkpoint_verified') is not True or
                report.get('original_execution_attempted') is not True):
            raise ValueError('Missing completed original frames/profile/kernel/boot provenance')
        if (digest(frames) != report['frame_observations_sha256'] or digest([f['video'] for f in frames]) != report['video_sha256'] or
                digest([(f['audio_sha256'], f['audio_frames']) for f in frames]) != report['audio_sha256'] or
                sum(f['audio_frames'] for f in frames) != report['audio_frames'] or observations['av'] != report['av']):
            raise ValueError('Original frame/video/audio artifacts differ from their report')
        pulse = report.get('port_zero_start_frames')
        if type(pulse) is not int or not 0 <= pulse <= len(frames): raise ValueError('Missing bounded input declaration')
        for index, frame in enumerate(frames):
            if frame['frame'] != report['reference_frame']+index or frame['inputs'] != [8 if index < pulse else 0]+[0]*11:
                raise ValueError('Nonconsecutive original frames or unexpected input')
        for name in ('imported', 'final'):
            state = probe_kernel.read_bounded(directory/(name+'.state'), state_graphics.MAX_STATE)
            if sha(state) != report[name+'_state_sha256']: raise ValueError('Private original state artifact differs')
            witness = boot_residency(state, kernel) if name == 'imported' else resident(state, kernel)
            if witness != report['resident_code_before' if name == 'imported' else 'resident_code_after']:
                raise ValueError('Actual private state source witnesses differ')
            if name == 'imported' and len(state) != report['imported_state_bytes']: raise ValueError('Imported state size differs')
            if name == 'imported' and report.get('kernel_witness_complete_before') is not bool(witness):
                raise ValueError('Original boot source-presence declaration differs')
        elapsed = report.get('emulation_wall_seconds')
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed <= 0: raise ValueError('Missing bounded wall observation')
        if report['mode'] == 'enabled':
            raw = probe_kernel.read_bounded(directory/'init-trace.json', 2*1024**2)
            trace = decoded_trace(read_json(directory/'init-trace.json'), kernel)
            if sha(raw) != report['trace_sha256'] or trace['profile'] != report['init_profile'] or report.get('completed_roots') != 1:
                raise ValueError('Original initialization trace differs from report')
        runs.append(report)
    groups = {mode: [r for r in runs if r['mode'] == mode] for mode in ('reference', 'disabled', 'enabled')}
    if any(len(group) != 2 for group in groups.values()): raise ValueError('Require exactly two original runs per declared mode')
    baseline = groups['reference'][0]
    equal = ('driver_sha256', 'source_modules', 'reference_identity', 'reference_lock_file_sha256',
             'reference_checkpoint_file_sha256', 'reference_state_sha256', 'reference_frame', 'frames',
             'port_zero_start_frames', 'init_profile', 'input_boot_checkpoint_verified', 'original_kernel_sha256',
             'completed_original_frames', 'original_game_bytes_executed', 'original_execution_attempted', 'av', 'imported_state_bytes',
             'imported_state_sha256', 'final_state_sha256', 'frame_observations_sha256', 'video_sha256',
             'audio_sha256', 'audio_frames', 'resident_code_before', 'kernel_witness_complete_before',
             'resident_code_after', 'input_polls', 'delivered_masks')
    for run in runs:
        if any(key not in run or run[key] != baseline.get(key) for key in equal):
            raise ValueError('Reference/disabled/enabled state or original output repeatability differs')
    if any(r['selected_core_sha256'] != REFERENCE_CORE for r in groups['reference']): raise ValueError('Wrong original reference core')
    patched = groups['disabled']+groups['enabled']
    if (len({r['selected_core_sha256'] for r in patched}) != 1 or patched[0]['selected_core_sha256'] == REFERENCE_CORE or
            len({r.get('prepared_recipe_sha256') for r in patched}) != 1 or not patched[0].get('prepared_recipe_sha256')):
        raise ValueError('Initialization core/recipe identity missing or differs')
    if groups['enabled'][0]['trace_sha256'] != groups['enabled'][1]['trace_sha256']:
        raise ValueError('Actual original initialization traces are not repeatable')
    medians = {mode: statistics.median(r['emulation_wall_seconds'] for r in group) for mode, group in groups.items()}
    return {'schema': 'neptune.init-observer-comparison.v1', 'status': 'success', 'init_profile': baseline['init_profile'],
            'runs': 6, 'repeats_per_mode': 2, 'frames_per_run': baseline['frames'], 'completed_roots_per_enabled_run': 1,
            'reference_core_sha256': REFERENCE_CORE, 'instrumented_core_sha256': patched[0]['selected_core_sha256'],
            'equal_observations': list(equal), 'trace_sha256': groups['enabled'][0]['trace_sha256'],
            'median_emulation_wall_seconds': medians, 'enabled_vs_disabled_wall_ratio': medians['enabled']/medians['disabled'],
            'disabled_vs_reference_wall_ratio': medians['disabled']/medians['reference'],
            'scope': 'one natural initialization boundary; internal semantics and hardware/gameplay parity remain unresolved',
            'whole_program_status': 'active; incomplete'}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    for limit, bound in ((resource.RLIMIT_AS, 2*1024**3), (resource.RLIMIT_CORE, 0),
                         (resource.RLIMIT_FSIZE, 64*1024**2), (resource.RLIMIT_CPU, 60)):
        soft, hard = resource.getrlimit(limit)
        cap = min([bound]+[value for value in (soft, hard) if value != resource.RLIM_INFINITY])
        resource.setrlimit(limit, (cap, cap))
    if argv and argv[0] == 'compare':
        parser = argparse.ArgumentParser(description='Validate all six private original initialization runs')
        parser.add_argument('directories', type=Path, nargs=6)
        parser.add_argument('--kernel', type=Path, required=True); parser.add_argument('--report', type=Path, required=True)
        args = parser.parse_args(argv[1:]); result = compare(args.directories, probe_kernel.kernel_bytes(args.kernel))
        fd = os.open(args.report, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output: output.write(json.dumps(result, indent=2, sort_keys=True)+'\n')
        print(json.dumps({'status': result['status'], 'runs': result['runs']})); return 0
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--lock', type=Path, required=True); parser.add_argument('--expected-lock', required=True)
    parser.add_argument('--boot-checkpoint', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True); parser.add_argument('--prepared', type=Path)
    parser.add_argument('--profile', type=int, choices=(1, 2), required=True)
    parser.add_argument('--mode', choices=('reference', 'disabled', 'enabled'), required=True)
    parser.add_argument('--frames', type=int, default=600); parser.add_argument('--start-frames', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv); result = run(args)
    print(json.dumps({key: result[key] for key in ('status', 'mode', 'frames', 'selected_core_sha256')})); return 0


if __name__ == '__main__': raise SystemExit(main())
