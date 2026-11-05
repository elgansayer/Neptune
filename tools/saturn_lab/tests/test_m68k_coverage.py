"""Owned synthetic tests for the natural 68000 coverage observer and its runner.

No original game, BIOS or emulator bytes are used. The native observer header is
compiled into a tiny owned harness with a minimal M68K struct; a missing
compiler is a test failure, as elsewhere in this suite.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import m68k_coverage_core as core  # noqa: E402
import run_m68k_coverage as runner  # noqa: E402

HARNESS = r'''
#include <stdint.h>
typedef struct M68K { uint32_t PC; uint32_t A[8]; } M68K;
#include "m68k_coverage.h"
static M68K cpu;
void t_reset(uint32_t pc, uint32_t ssp) { cpu.PC = pc; cpu.A[7] = ssp; neptune_m68kcov_reset(&cpu); }
void t_step(uint32_t pc, uint16_t op) { cpu.PC = pc + 2u; neptune_m68kcov_step(&cpu, op); }
void t_exception(uint32_t vec, uint32_t saved) { neptune_m68kcov_exception(&cpu, vec, saved); }
void t_many(uint32_t n) { for(uint32_t i = 0; i < n; i++) t_step(0x2000u + 2u * (i % 0x30000u), 0x4E71); }
'''


def owned_sources():
    m68k = (b'/* owned */\n#include "m68k_private.h"\n'
            b'x\n\t\t\t\t\t z->XPending &= ~XPENDING_MASK_RESET;\n'
            b'y\n ReadOp(z);\n ReadOp(z);\n z->PC -= 4;\n}\n'
            b'z\n\t uint16_t instr = ReadOp(z);\n')
    link = b'{\n   global: retro_*;\n   local: *;\n};\n'
    return {'mednafen/hw_cpu/m68k/m68k.c': m68k, 'link.T': link}


class PatchTests(unittest.TestCase):
    def test_inserts_each_hook_once_after_its_anchor(self):
        content = owned_sources()
        pins = {k: hashlib.sha256(v).hexdigest() for k, v in content.items()}
        with patch.dict(core.SOURCES, pins, clear=True):
            out = core.patch_sources(content, b'/* header */')
        text = out['mednafen/hw_cpu/m68k/m68k.c'].decode()
        for hook in ('#include "neptune_m68k_coverage.h"', 'neptune_m68kcov_reset(z);',
                     'neptune_m68kcov_exception(z, vecnum, PC_save);', 'neptune_m68kcov_step(z, instr);'):
            self.assertEqual(text.count(hook), 1)
        self.assertLess(text.index('uint16_t instr = ReadOp(z);'), text.index('neptune_m68kcov_step'))
        exports = out['link.T'].decode()
        for name in core.EXPORTS:
            self.assertIn('neptune_m68kcov_' + name + ';', exports)
        self.assertEqual(out['mednafen/hw_cpu/m68k/neptune_m68k_coverage.h'], b'/* header */')

    def test_rejects_source_drift_and_ambiguous_anchor(self):
        content = owned_sources()
        with self.assertRaises(ValueError):
            core.patch_sources(content, b'')  # pinned upstream hashes differ
        doubled = dict(content)
        doubled['mednafen/hw_cpu/m68k/m68k.c'] += b'\t uint16_t instr = ReadOp(z);\n'
        pins = {k: hashlib.sha256(v).hexdigest() for k, v in doubled.items()}
        with patch.dict(core.SOURCES, pins, clear=True):
            with self.assertRaises(ValueError):
                core.patch_sources(doubled, b'')

    def test_edge_keys_reject_missing_marker_and_unknown_kind(self):
        good = (0x1000 << 40) | (0x1002 << 16) | (0x80 << 8)
        self.assertEqual(core.decode_edge(good), {'from': 0x1000, 'to': 0x1002, 'kind': 'flow', 'vector': 0})
        with self.assertRaises(ValueError):
            core.decode_edge(good & ~(0x80 << 8))
        with self.assertRaises(ValueError):
            core.decode_edge((0x1000 << 40) | (0x85 << 8))


class NativeObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        (root / 'harness.c').write_text(HARNESS)
        cls.library = root / 'harness.so'
        built = subprocess.run(['cc', '-std=c11', '-O1', '-shared', '-fPIC', '-I', str(core.HERE),
                                '-o', str(cls.library), str(root / 'harness.c')], capture_output=True, text=True)
        if built.returncode:
            raise AssertionError('Owned observer harness failed to compile: ' + built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fresh(self):
        # Each test copies the harness so process-global observer state starts clean.
        path = Path(self.temporary.name) / ('h%d.so' % id(self))
        path.write_bytes(self.library.read_bytes())
        dll = ctypes.CDLL(str(path))
        for name, args in (('t_reset', [ctypes.c_uint32] * 2), ('t_step', [ctypes.c_uint32, ctypes.c_uint16]),
                           ('t_exception', [ctypes.c_uint32] * 2), ('t_many', [ctypes.c_uint32])):
            getattr(dll, name).argtypes = args
            getattr(dll, name).restype = None
        return dll, core.Coverage(dll)

    def test_epochs_edges_and_opcode_witness(self):
        dll, cov = self.fresh()
        dll.t_step(0x0500, 0x4E71)  # before begin: ignored entirely
        cov.begin()
        cov.frame(3)
        dll.t_step(0x0600, 0x4E71)  # before any reset: counted only
        dll.t_reset(0x1000, 0xA000)
        cov.frame(4)
        dll.t_step(0x1000, 0x6008)
        dll.t_step(0x100A, 0x4E71)
        dll.t_exception(26, 0x100C)
        dll.t_step(0x1734, 0x4E73)
        dll.t_step(0x100C, 0x4E75)
        cov.frame(9)
        dll.t_step(0x1000, 0x6010)  # changed fetched word at an executed address
        dll.t_step(0x80000, 0x4E71)  # outside sound RAM
        status = cov.status()
        self.assertEqual((status['epochs'], status['unepoched_steps'], status['on']), (1, 1, 1))
        epoch = cov.epoch(0)
        self.assertEqual((epoch['reset_pc'], epoch['reset_ssp'], epoch['first_frame'], epoch['last_frame']),
                         (0x1000, 0xA000, 3, 9))
        self.assertEqual((epoch['steps'], epoch['outside_steps'], epoch['opcode_changes']), (6, 1, 1))
        self.assertEqual(epoch['first_outside_pc'], 0x80000)
        self.assertEqual(epoch['exceptions'], {'26': 1})
        words = {w[0]: w[1:] for w in epoch['words']}
        self.assertEqual(words[0x1000], [2, 4, 0x6008, 1])
        self.assertEqual(words[0x1734], [1, 4, 0x4E73, 0])
        edges = {(e[0], e[1], e[2], e[3]): e[4] for e in epoch['edges']}
        self.assertEqual(edges, {(0, 0x1000, 'epoch', 0): 1, (0x1000, 0x100A, 'flow', 0): 1,
                                 (0x100C, 0x1734, 'exception', 26): 1, (0x1734, 0x100C, 'flow', 0): 1,
                                 (0x100C, 0x1000, 'flow', 0): 1, (0x1000, 0x80000, 'flow', 0): 1})
        cov.stop()
        dll.t_step(0x1002, 0x4E71)
        self.assertEqual(cov.epoch(0)['steps'], 6)
        with self.assertRaises(ValueError):
            cov.begin()  # one observation window per process

    def test_reset_starts_separate_epoch_and_capacity_is_reported(self):
        dll, cov = self.fresh()
        cov.begin()
        dll.t_reset(0x1000, 0xA000)
        dll.t_step(0x1000, 0x4E71)
        dll.t_reset(0x2000, 0x9000)
        dll.t_step(0x1000, 0x4AFC)  # same address, different program lifetime
        first, second = cov.epoch(0), cov.epoch(1)
        self.assertEqual(first['words'][0][3], 0x4E71)
        self.assertEqual((second['reset_pc'], second['words'][0][3], second['opcode_changes']), (0x2000, 0x4AFC, 0))
        dll.t_many(60000)
        self.assertGreater(cov.epoch(1)['edge_overflow'], 0)
        for _ in range(20):
            dll.t_reset(0x1000, 0xA000)
        self.assertGreater(cov.status()['epoch_overflow'], 0)


class RunnerTests(unittest.TestCase):
    def write_run(self, root, name, mode, frames, state, coverage=None):
        path = root / name
        path.mkdir()
        (path / 'observations.json').write_text(json.dumps({'av': {}, 'frames': frames}))
        (path / 'final.state').write_bytes(state)
        result = {'status': 'success', 'mode': mode, 'frames': len(frames), 'actions_sha256': 'a',
                  'reference_lock_file_sha256': 'l', 'av': {}, 'frame_observations_sha256': runner.digest(frames),
                  'final_state_sha256': runner.sha(state), 'video_sha256': 'v', 'audio_sha256': 'p'}
        if coverage is not None:
            (path / 'coverage.json').write_bytes(coverage)
            result['coverage_sha256'] = runner.sha(coverage)
        (path / 'result.json').write_text(json.dumps(result))
        return path

    def test_compare_requires_identical_observations_state_and_coverage(self):
        frames = [{'frame': 0, 'video': {'sha256': 'x'}, 'audio_sha256': 'y', 'audio_frames': 2, 'inputs': [0]}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref = self.write_run(root, 'ref', 'reference', frames, b'S')
            one = self.write_run(root, 'one', 'enabled', frames, b'S', b'{"c":1}')
            two = self.write_run(root, 'two', 'enabled', frames, b'S', b'{"c":1}')
            args = type('A', (), {'reference': ref, 'enabled': [one, two]})
            self.assertEqual(runner.compare(args)['status'], 'success')
            other = self.write_run(root, 'other', 'enabled', frames, b'S', b'{"c":2}')
            args.enabled = [one, other]
            with self.assertRaises(ValueError):
                runner.compare(args)
            moved = [dict(frames[0], audio_sha256='z')]
            bad = self.write_run(root, 'bad', 'enabled', moved, b'S', b'{"c":1}')
            args.enabled = [bad]
            with self.assertRaises(ValueError):
                runner.compare(args)
            state = self.write_run(root, 'state', 'enabled', frames, b'T', b'{"c":1}')
            args.enabled = [state]
            with self.assertRaises(ValueError):
                runner.compare(args)

    def test_png_capture_is_lossless_rgb(self):
        ppm = b'P6\n2 1\n255\n' + bytes([1, 2, 3, 4, 5, 6])
        data = runner.png(ppm)
        self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
        import zlib
        idat = data[data.index(b'IDAT') + 4:data.index(b'IEND') - 8]
        self.assertEqual(zlib.decompress(idat), b'\0' + bytes([1, 2, 3, 4, 5, 6]))


if __name__ == '__main__':
    unittest.main()
