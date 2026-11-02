"""Owned library-initializer contracts; no original instructions are fixtures."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_library_tables as p


class LibraryTableTests(unittest.TestCase):
    def test_case_selection_retains_all_valid_counts_and_signed_skip_boundaries(self):
        callbacks, tables = (p.cases(f) for f in p.FAMILIES)
        self.assertEqual((len(callbacks), len(tables)), (1536, 162))
        self.assertEqual(len(set(callbacks)), len(callbacks))
        self.assertEqual(len(set(tables)), len(tables))
        self.assertEqual({c[3] for c in callbacks}, set(range(256)))
        self.assertEqual({c[3] for c in tables}, {*range(25), 0x80000000, 0xFFFFFFFF})
        for count in (25, 0x7FFFFFFF):
            with self.assertRaisesRegex(ValueError, 'bounded'):
                p.contract(('tables', 0, 0, count))

    def test_callback_addresses_are_stored_without_calling_them_or_changing_stack(self):
        _, m, regions = p.contract(('callbacks', 1, 37, 255))
        self.assertEqual(len(m.trace), 12)
        self.assertEqual(m.trace[-1], [0x06096A96, True])
        self.assertEqual(m.reg['pc'], m.before['pr'])
        self.assertEqual(m.reg['r15'], m.before['r15'])
        self.assertEqual(m.reg['sr'], m.before['sr'])
        self.assertEqual(m.reg['r4'], p.BLOCK+4)
        self.assertEqual([e for e in m.events if e[0] == 2],
                         [[2, p.BLOCK+4+4*i, 4, value] for i, value in enumerate(p.CALLBACK_VALUES)])
        self.assertEqual(m.buffers[4][:4], regions[4][1][:4])
        self.assertEqual(m.buffers[4][20:], regions[4][1][20:])

    def test_full_initializer_restores_live_context_and_clears_only_selected_words(self):
        _, m, regions = p.contract(('tables', 0, 255, 24))
        for name in ('r13', 'r14', 'r15', 'pr', 'mach', 'macl', 'gbr', 'vbr'):
            self.assertEqual(m.reg[name], m.before[name])
        self.assertEqual(m.reg['pc'], m.before['pr'])
        self.assertEqual(m.reg['r6'], 24)
        self.assertEqual(m.reg['r0'], 0xC4)
        self.assertEqual(m.reg['r5'], p.BLOCK+0x44C)
        self.assertEqual(m.trace[-1], [0x06096B3A, True])
        self.assertIn([0x06096ACE, True], m.trace)
        self.assertEqual(sum(pc == p.CALLBACKS for pc, _ in m.trace), 1)
        self.assertEqual(sum(pc == 0x06096B08 for pc, _ in m.trace), 24)
        for offset in p.ZERO_OFFSETS:
            self.assertEqual(m.buffers[4][offset:offset+4], bytes(4))
        for i in range(24):
            offset = 0xC60+i*0xA8
            self.assertEqual(m.buffers[4][offset:offset+4], bytes(4))
            if i < 23: self.assertEqual(m.buffers[4][offset+4:offset+0xA8], regions[4][1][offset+4:offset+0xA8])
        self.assertEqual(m.buffers[4][0x438:0x460], bytes(40))

    def test_zero_and_negative_counts_skip_marker_loop_and_remain_real_returns(self):
        for count in (0, 0x80000000, 0xFFFFFFFF):
            _, m, regions = p.contract(('tables', 1, 37, count))
            self.assertFalse(any(pc == 0x06096B08 for pc, _ in m.trace))
            self.assertEqual(m.reg['r6'], 0)
            self.assertEqual(m.reg['pc'], m.before['pr'])
            self.assertEqual(m.buffers[4][0xC60:], regions[4][1][0xC60:])
            self.assertEqual(m.buffers[4][:4], count.to_bytes(4, 'big'))

    def test_halfword_literals_are_readonly_original_source_regions_without_guard_changes(self):
        _, m, regions = p.contract(('tables', 0, 0, 1))
        data = bytearray(p.pinned.SIZE)
        literal_bytes = bytes(range(10))
        start = 0x06096BD4-p.pinned.BASE
        data[start:start+10] = literal_bytes
        with patch.object(p.longer, 'observe', return_value={'owned_adapter_check': True}) as capture:
            self.assertEqual(p.observe(data, None, 'tables', m.before, regions), {'owned_adapter_check': True})
        args, kwargs = capture.call_args
        self.assertEqual(args[3][-1], (0x06096BD4, literal_bytes, False))
        self.assertEqual(kwargs['budget'], 256)
        self.assertEqual(kwargs['aliases'], ())
        self.assertEqual(kwargs['terminals'], {m.before['pr']: 'returned'})
        self.assertEqual((p.short.MAX_STEPS, p.longer.MAX_STEPS), (128, 1024))

    def test_every_model_case_keeps_readonly_neighbors_and_fits_selected_budget(self):
        for family in p.FAMILIES:
            for case in p.cases(family):
                _, m, regions = p.contract(case)
                self.assertLessEqual(len(m.trace), 128 if family == 'callbacks' else 256)
                for (_, raw, writable), after in zip(regions, m.buffers):
                    if not writable: self.assertEqual(bytes(after), raw)
                for lo, raw, _ in regions:
                    self.assertTrue(0x06000000 <= lo < lo+len(raw) <= 0x06100000)
                self.assertEqual(m.reg['pc'], m.before['pr'])

    def test_source_identity_failure_report_is_exclusive_and_records_no_original_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); report = root/'failed.json'
            args = ['--kernel', str(root/'missing'), '--saturn-recomp', str(root), '--family', 'tables', '--report', str(report)]
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(p.main(args), 1)
            raw = report.read_bytes(); d = json.loads(raw)
            self.assertEqual(d['error']['phase'], 'source_identity')
            self.assertIs(d['original_game_bytes_executed'], False)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(p.main(args), 1)
            self.assertEqual(report.read_bytes(), raw)


if __name__ == '__main__': unittest.main()
