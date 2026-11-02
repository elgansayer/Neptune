"""Owned synthetic state/record fixtures; no original-game execution evidence."""
import copy
import ctypes as C
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_init_trace as p


def owned_source():
    kernel = bytearray(p.probe_kernel.SIZE)
    for pc, word in ((0x06095B04, 0x2FE6), (0x06095BCA, 0x000B),
                     (0x06095BCC, 0x6EF6), (0x06008A18, 0x0009)):
        kernel[pc-p.probe_kernel.BASE:pc-p.probe_kernel.BASE+2] = word.to_bytes(2, 'big')
    high = bytearray(0x100000); high[0x6000:0x6000+len(kernel)] = kernel
    raw = p.state_graphics.cpu_words(bytes(high), 'little')
    field = bytes([8])+b'WorkRAMH'+struct.pack('<I', len(raw))+raw
    payload = b'MAIN'.ljust(32, b'\0')+struct.pack('<I', len(field))+field
    state = b'MDFNSVST'+bytes(8)+struct.pack('<II', p.state_graphics.VERSION, 32+len(payload))+bytes(8)+payload
    return bytes(kernel), state


def owned_trace(kernel):
    observer = p.observer; records = []
    for index, (kind, pc, opcode) in enumerate(((1, 0x06095B04, 0x2FE6), (8, 0x06095BCA, 0x000B),
                                               (9, 0x06095BCC, 0x6EF6), (10, 0x06008A18, 0x0009))):
        row = observer.Record(); row.sequence, row.kind, row.profile = index, kind, 2
        row.frame, row.timestamp, row.steps = 1200, index, index+1
        row.pc, row.opcode, row.pr, row.r[14] = pc, opcode, 0x06008A18, 0x12345678
        row.r[15] = 0x060FF000-(4 if kind in (8, 9) else 0)
        row.stack_address = row.r[15]-64
        if kind == 9: row.pipe_op = 0x80; row.stack[16] = 0x12345678
        records.append(row)
    status = observer.Status()
    for name, value in dict(abi=1, record_bytes=C.sizeof(observer.Record), capacity=128, count=4,
                            completed=1, requested=1, profile=2, frame_known=1, frame=1200,
                            step_limit=observer.STEP_LIMIT, steps=4, master_dispatches=4, source_checks=5,
                            frame_limit=120, depth_limit=16, witness_words=observer.WITNESS_WORDS).items():
        setattr(status, name, value)
    return observer.validate(records, status, p.source_words(kernel))


class InitExperimentTests(unittest.TestCase):
    def test_real_state_parser_checks_all_source_words_and_endianness(self):
        kernel, state = owned_source(); regions = p.resident(state, kernel)
        self.assertEqual(sum(region['bytes'] for region in regions), p.observer.WITNESS_WORDS*2)
        changed = bytearray(kernel); changed[0x06095B04-p.probe_kernel.BASE] ^= 1
        with self.assertRaisesRegex(ValueError, 'absent'): p.resident(state, bytes(changed))
        with self.assertRaises(ValueError): p.resident(b'owned invalid state', kernel)

    def test_decoder_revalidates_actual_private_witness_root_linkage_and_exact_fields(self):
        kernel, _ = owned_source(); trace = owned_trace(kernel)
        self.assertEqual(p.decoded_trace(trace, kernel), trace)
        for index, field, value in ((0, 'pr', 0), (1, 'opcode', 9), (2, 'pipe_op', 0),
                                    (-1, 'steps', 99), (-1, 'stack_address', 0)):
            changed = copy.deepcopy(trace); changed['records'][index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError): p.decoded_trace(changed, kernel)
        for field, value in (('library', [1]*64), ('r', [1]), ('steps', True), ('extra', 0)):
            changed = copy.deepcopy(trace); changed['records'][0][field] = value
            with self.assertRaises(ValueError): p.decoded_trace(changed, kernel)
        changed_kernel = bytearray(kernel); changed_kernel[0x06095BCA-p.probe_kernel.BASE] ^= 1
        with self.assertRaisesRegex(ValueError, 'witness'): p.decoded_trace(trace, changed_kernel)

    def six_owned_runs(self, root):
        kernel, state = owned_source(); witness = p.resident(state, kernel); trace = owned_trace(kernel)
        frames = [{'frame': 1200+i, 'inputs': [0]*12, 'video': {'sha256': '1'*64},
                   'audio_sha256': '2'*64, 'audio_frames': 1} for i in range(2)]
        paths = []
        for mode in ('reference', 'disabled', 'enabled'):
            for repeat in range(2):
                out = root/f'{mode}-{repeat}'; out.mkdir(); paths.append(out)
                (out/'imported.state').write_bytes(state); (out/'final.state').write_bytes(state)
                report = dict(schema=p.SCHEMA, status='success', mode=mode, init_profile=2,
                              driver_sha256='3'*64, source_modules={}, reference_identity={'owned': True},
                              reference_lock_file_sha256='4'*64, reference_checkpoint_file_sha256='5'*64,
                              reference_state_sha256='6'*64, reference_frame=1200, frames=2, port_zero_start_frames=0,
                              input_boot_checkpoint_verified=True, original_kernel_sha256=p.sha(kernel),
                              completed_original_frames=2, original_game_bytes_executed=True, original_execution_attempted=True, av={},
                              imported_state_bytes=len(state), imported_state_sha256=p.sha(state), final_state_sha256=p.sha(state),
                              frame_observations_sha256=p.digest(frames), video_sha256=p.digest([f['video'] for f in frames]),
                              audio_sha256=p.digest([(f['audio_sha256'], f['audio_frames']) for f in frames]), audio_frames=2,
                              resident_code_before=witness, resident_code_after=witness, input_polls=[2]*12,
                              delivered_masks=[[0]]*12, emulation_wall_seconds=1.0,
                              selected_core_sha256=p.REFERENCE_CORE if mode == 'reference' else '7'*64)
                if mode != 'reference': report['prepared_recipe_sha256'] = '8'*64
                if mode == 'enabled':
                    raw = (json.dumps(trace, indent=2, sort_keys=True)+'\n').encode(); (out/'init-trace.json').write_bytes(raw)
                    report.update(trace_sha256=p.sha(raw), completed_roots=1)
                (out/'observations.json').write_text(json.dumps({'av': {}, 'frames': frames}))
                (out/'result.json').write_text(json.dumps(report))
        return paths, kernel

    def test_six_run_comparison_rechecks_actual_state_frames_trace_and_core_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, kernel = self.six_owned_runs(Path(temporary)); result = p.compare(paths, kernel)
            self.assertEqual(result['runs'], 6)
            self.assertEqual(result['whole_program_status'], 'active; incomplete')
            bad = paths[-1]/'init-trace.json'; original = bad.read_bytes()
            changed = json.loads(original); changed['records'][-1]['r'][15] ^= 4
            bad.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): p.compare(paths, kernel)
            bad.write_bytes(original)
            for field, value in (('completed_roots', 0), ('prepared_recipe_sha256', '9'*64),
                                 ('selected_core_sha256', p.REFERENCE_CORE), ('init_profile', 1),
                                 ('input_boot_checkpoint_verified', False), ('original_kernel_sha256', '0'*64)):
                file = paths[-1]/'result.json'; report = json.loads(file.read_text()); changed = dict(report, **{field: value})
                file.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError): p.compare(paths, kernel)
                file.write_text(json.dumps(report))
            (paths[0]/'imported.state').write_bytes(b'torn owned state')
            with self.assertRaises(ValueError): p.compare(paths, kernel)

    def test_frame_artifact_and_duplicate_directory_controls_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, kernel = self.six_owned_runs(Path(temporary))
            with self.assertRaises(ValueError): p.compare(paths[:5]+[paths[0]], kernel)
            file = paths[1]/'observations.json'; value = json.loads(file.read_text())
            value['frames'][0]['inputs'][0] = 8; file.write_text(json.dumps(value))
            with self.assertRaises(ValueError): p.compare(paths, kernel)

    def fake_run(self, root, mode='reference'):
        kernel, state = owned_source(); checkpoint = root/'checkpoint.json'; checkpoint.write_text('owned checkpoint')
        (root/'core').write_bytes(b'owned not a library')
        class Driver:
            def __init__(self, *args):
                self.frame, self.video = 0, None; self.polls, self.delivered = [0]*12, [set() for _ in range(12)]
                self.dll = object()
            def load(self, *args): return {}
            def restore(self, value):
                if value != state: raise AssertionError('Wrong owned state imported')
            def save_state(self): return state
            def step(self, masks):
                frame = self.frame; self.frame += 1
                return {'frame': frame, 'video': {'sha256': '1'*64}, 'audio_sha256': '2'*64,
                        'audio_frames': 1, 'inputs': masks}
            def close(self): pass
        module = types.SimpleNamespace(Core=Driver)
        lock = {'inputs': {'emulator': 'core', 'disc': 'disc.cue'}}
        profile = {'system_directory': 'system', 'options': {}, 'log_shim': {'path': 'shim'}, 'controller_devices': [1]*12}
        meta = {'frame': 1200, 'state_sha256': p.sha(state), 'last_video': {}}
        args = types.SimpleNamespace(profile=2, frames=2, start_frames=0, mode=mode, output=root/'out',
                                     reference_root=root, lock=root/'lock', expected_lock='0'*64,
                                     boot_checkpoint=checkpoint, kernel=root/'kernel', prepared=root)
        return args, kernel, state, module, lock, profile, meta

    def test_run_retains_imported_and_final_state_and_never_rewrites_boot_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); args, kernel, state, module, lock, profile, meta = self.fake_run(root)
            with patch.object(p, 'reference', return_value=(module, lock, profile, {}, b'seed')), \
                 patch.object(p, 'read_boot_checkpoint', return_value=(meta, state)), \
                 patch.object(p.probe_kernel, 'kernel_bytes', return_value=kernel), \
                 patch.object(p.os, 'statvfs', return_value=types.SimpleNamespace(f_flag=p.os.ST_RDONLY)):
                result = p.run(args)
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['completed_original_frames'], 2)
            self.assertEqual((args.output/'imported.state').read_bytes(), state)
            self.assertEqual((args.output/'final.state').read_bytes(), state)
            self.assertEqual(args.boot_checkpoint.read_text(), 'owned checkpoint')
            self.assertFalse((args.output/'checkpoint.json').exists())
            with self.assertRaisesRegex(ValueError, 'fresh'): p.run(args)

    def test_failed_enabled_capture_retains_partial_native_records_and_executed_frames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); args, kernel, state, module, lock, profile, meta = self.fake_run(root, 'enabled')
            class Trace:
                def __init__(self, *args): self.started = False; self.dll = types.SimpleNamespace(neptune_init_stop=lambda: None)
                def start(self, profile, roots, words): self.started = True; self.words = words
                def witness(self, *args): return self.words
                def frame(self, frame): pass
                def finish(self): raise ValueError('Owned incomplete initialization')
                def snapshot(self): return [], p.observer.Status()
            with patch.object(p, 'reference', return_value=(module, lock, profile, {}, b'seed')), \
                 patch.object(p, 'read_boot_checkpoint', return_value=(meta, state)), \
                 patch.object(p.probe_kernel, 'kernel_bytes', return_value=kernel), \
                 patch.object(p.os, 'statvfs', return_value=types.SimpleNamespace(f_flag=p.os.ST_RDONLY)), \
                 patch.object(p.provision, 'cached', return_value=root/'core'), patch.object(p.observer, 'Trace', Trace):
                with self.assertRaisesRegex(ValueError, 'Owned incomplete'): p.run(args)
            report = json.loads((args.output/'result.json').read_text())
            self.assertEqual(report['status'], 'failure'); self.assertEqual(report['completed_original_frames'], 2)
            self.assertFalse(json.loads((args.output/'failed-init-records.json').read_text())['accepted'])
            self.assertTrue((args.output/'final.state').is_file())
            self.assertTrue((args.output/'partial-observations.json').is_file())

    def test_absent_source_or_mutable_inputs_stop_before_core_load(self):
        for failure in ('source', 'mount'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); args, kernel, state, module, lock, profile, meta = self.fake_run(root)
                bad_kernel = bytes(len(kernel)) if failure == 'source' else kernel
                with patch.object(p, 'reference', return_value=(module, lock, profile, {}, b'seed')), \
                     patch.object(p, 'read_boot_checkpoint', return_value=(meta, state)), \
                     patch.object(p.probe_kernel, 'kernel_bytes', return_value=bad_kernel), \
                     patch.object(p.os, 'statvfs', return_value=types.SimpleNamespace(f_flag=0 if failure == 'mount' else p.os.ST_RDONLY)), \
                     patch.object(module, 'Core', side_effect=AssertionError('Must not load')) as load:
                    with self.assertRaises(ValueError): p.run(args)
                load.assert_not_called()
                report = json.loads((args.output/'result.json').read_text())
                self.assertIs(report['original_game_bytes_executed'], False)

    def test_first_frame_failure_retains_actual_partial_state_without_claiming_no_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); args, kernel, state, module, lock, profile, meta = self.fake_run(root)
            def fail(self, masks): raise ValueError('Owned mid-frame failure')
            module.Core.step = fail
            with patch.object(p, 'reference', return_value=(module, lock, profile, {}, b'seed')), \
                 patch.object(p, 'read_boot_checkpoint', return_value=(meta, state)), \
                 patch.object(p.probe_kernel, 'kernel_bytes', return_value=kernel), \
                 patch.object(p.os, 'statvfs', return_value=types.SimpleNamespace(f_flag=p.os.ST_RDONLY)):
                with self.assertRaisesRegex(ValueError, 'mid-frame'): p.run(args)
            report = json.loads((args.output/'result.json').read_text())
            self.assertIsNone(report['original_game_bytes_executed'])
            self.assertTrue(report['original_execution_attempted'])
            self.assertEqual(report['completed_original_frames'], 0)
            self.assertEqual((args.output/'partial.state').read_bytes(), state)
            self.assertEqual(report['partial_state_sha256'], p.sha(state))


if __name__ == '__main__': unittest.main()
