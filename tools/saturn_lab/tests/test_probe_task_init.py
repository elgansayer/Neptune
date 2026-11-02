"""Owned contract checks; original execution reports stay outside the repository."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_task_init as p


def library(count=1, alignment=0, mode=None, length=0, address=0, variant=0):
    return p.contract(('library-validation', variant, 37, count, alignment, mode, length, address))[1]


class TaskInitTests(unittest.TestCase):
    def test_selections_cover_bytes_register_bits_and_library_error_precedence(self):
        for family in p.FAMILIES:
            rows = p.cases(family)
            self.assertEqual(len(rows), len(set(rows)))
            self.assertEqual({c[1] for c in rows}, {0, 1})
            if family != 'library-validation':
                self.assertEqual(len(rows), 512 + 19*37*2 + 2)
                self.assertEqual({c[2] for c in rows if c[3] is None}, set(range(256)))
                self.assertTrue({1 << bit for bit in range(32)} <= {c[4] for c in rows if c[3] == 'mach'})
            else:
                self.assertEqual(len(rows), 1280)
                self.assertEqual({c[4] for c in rows}, set(range(4)))
                self.assertTrue({0, 1, 24, 25, 0x7FFFFFFF, 0x80000000, p.MASK} <= {c[3] for c in rows})
        self.assertEqual(library(count=0, alignment=1, mode=2).reg['r0'], p.MASK-4)
        self.assertEqual(library(count=1, alignment=1, mode=2).reg['r0'], p.MASK-20)
        self.assertEqual(library(count=1, mode=2).reg['r0'], p.MASK-3)

    def test_leaf_has_exact_four_sentinel_stores_and_preserves_live_stack(self):
        _, m, regions = p.contract(('leaf', 1, 255, 'r0', 0x80000000))
        self.assertEqual(len(m.trace), 23)
        self.assertEqual(m.trace[-1], [p.LEAF+20, True])
        self.assertEqual(m.events[1:], [[2, p.DATA+4*i, 4, p.MASK] for i in range(4)])
        self.assertEqual(m.reg['r0'], 0x80000000)
        self.assertEqual(m.reg['r15'], m.before['r15'])
        self.assertEqual(m.reg['pc'], m.before['pr'])
        self.assertEqual(m.buffers[1], bytes([255])*16)
        self.assertTrue(all(bytes(after) == raw for (_, raw, write), after in zip(regions, m.buffers) if not write))

    def test_real_caller_sets_saved_PR_and_remains_an_incomplete_parent_prefix(self):
        _, m, regions = p.contract(('caller-prefix', 0, 91, None, 0))
        self.assertEqual((len(m.trace), len(m.events)), (130, 41))
        self.assertEqual(m.reg['pc'], p.PREFIX)
        self.assertEqual(m.reg['pr'], p.PREFIX)
        self.assertEqual(m.reg['r15'], m.before['r15']-12)
        self.assertEqual(m.reg['r14'], p.DATA+104)
        stack = next(bytes(buf) for (lo, _, _), buf in zip(regions, m.buffers) if lo == m.before['r15']-12)
        self.assertEqual(stack, b''.join(value.to_bytes(4, 'big') for value in (p.DATA+80, p.CALLER+6, m.before['r14'])))
        self.assertEqual(m.buffers[1], bytes([255])*16 + p.POINTER.to_bytes(4, 'big')*16 + bytes(24))
        self.assertEqual(sum(delay for _, delay in m.trace), 15)

    def test_closed_error_paths_restore_context_and_read_descriptors_only_when_needed(self):
        for count, alignment, mode, length, address, expected in (
                (0, 3, 2, 0, 0, -5), (25, 0, None, 0, 0, -5),
                (0x80000000, 0, None, 0, 0, -5), (24, 3, 2, 0, 0, -21),
                (1, 0, 2, 2, 1, -4), (1, 0, 0, 1, 1, -4), (1, 0, 1, 2, 0, -4)):
            m = library(count, alignment, mode, length, address, variant=1)
            self.assertEqual(m.reg['r0'], expected & p.MASK)
            for name in ('r13', 'r14', 'r15', 'pr', 'mach', 'macl', 'gbr', 'vbr'):
                self.assertEqual(m.reg[name], m.before[name])
            self.assertEqual(m.reg['pc'], m.before['pr'])
            self.assertEqual(m.trace[-1], [0x06095BCC, True])
            self.assertIn([0x06095B1C, True], m.trace)
            self.assertEqual(m.buffers[1], bytes(4))
            if expected in (-5, -21):
                self.assertFalse(any(kind == 1 and p.DESCRIPTOR <= addr < p.DESCRIPTOR+12 for kind, addr, _, _ in m.events))

    def test_valid_descriptor_null_and_nonnull_paths_stop_before_bios_without_unwinding(self):
        for mode, length, address in ((None, 0, 0), (0, 2, 1), (1, 0x7FFFFFFF, 0xFFFFFFFF)):
            m = library(count=24, mode=mode, length=length, address=address)
            self.assertEqual(m.reg['pc'], p.LIBRARY_READY)
            self.assertEqual(m.reg['r15'], m.before['r15']-16)
            self.assertEqual(m.reg['r13'], 24)
            self.assertEqual(m.reg['r14'], 0 if mode is None else p.DESCRIPTOR)
            self.assertNotIn([p.LIBRARY_READY, False], m.trace)
            self.assertFalse(any(addr == 0x06000344 for _, addr, _, _ in m.events))

    def test_all_scalar_contracts_fit_unchanged_profiles_and_keep_readonly_inputs(self):
        counts = {}
        for family in p.FAMILIES:
            complete = incomplete = 0
            for case in p.cases(family):
                _, m, regions = p.contract(case)
                self.assertLessEqual(len(m.trace), 144 if family == 'caller-prefix' else 128)
                if m.reg['pc'] == m.before['pr']: complete += 1
                else: incomplete += 1
                for (_, raw, writable), after in zip(regions, m.buffers):
                    if not writable: self.assertEqual(bytes(after), raw)
            counts[family] = (complete, incomplete)
        self.assertEqual(counts, {'leaf': (1920, 0), 'init-prefix': (0, 1920),
                                  'caller-prefix': (0, 1920), 'library-validation': (1220, 60)})
        self.assertEqual(p.short.MAX_STEPS, 128)
        self.assertEqual(p.longer.MAX_STEPS, 1024)

    def test_failed_identity_report_is_private_exclusive_and_has_no_original_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); report = root/'failed.json'
            args = ['--kernel', str(root/'missing'), '--saturn-recomp', str(root), '--family', 'leaf', '--report', str(report)]
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(p.main(args), 1)
            raw = report.read_bytes(); data = json.loads(raw)
            self.assertEqual(data['error']['phase'], 'source_identity')
            self.assertIs(data['original_game_bytes_executed'], False)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(p.main(args), 1)
            self.assertEqual(report.read_bytes(), raw)


if __name__ == '__main__': unittest.main()
