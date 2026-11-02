"""Owned synthetic inputs; these tests do not execute original game code."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_split_add as probe
import probe_kernel as pinned


class SplitAddTests(unittest.TestCase):
    def test_cases_include_sign_carry_wrap_and_all_indices(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 560)
        self.assertEqual(len(set(rows)), 560)
        self.assertIn((0xFFFF, 0xFFFFFFFF, 1), rows)
        controls = rows[::9]
        self.assertEqual({r[0] for r in controls}, {r[0] for r in rows})
        self.assertEqual({r[2] for r in controls}, {r[2] for r in rows})

    def test_scalar_oracle_boundary_values(self):
        for value, delta, low, high in (
            (0xFFFF, 1, 0, 1), (0xFFFFFFFF, 1, 0, 0),
            (0, 0xFFFFFFFF, 0xFFFF, 0xFFFF),
            (0x7FFFFFFF, 1, 0, 0x8000), (0x80000000, 0x80000000, 0, 0)):
            with self.subTest(value=value, delta=delta):
                self.assertEqual(probe.expected_halfwords(value, delta), (low, high))

    def test_disjoint_mapping_preserves_all_noncontrolled_source_bytes(self):
        class Memory:
            def __init__(self): self.regions = []
            def add(self, lo, size, data):
                self.assert_size = size == len(data)
                self.regions.append((lo, bytes(data)))
        original = bytes([0xCC]) * pinned.SIZE
        for address in (probe.OBJECTS, pinned.BASE + pinned.SIZE - 4,
                        probe.OBJECTS + ((0xFFFF * 84) & 0xFFFF)):
            memory = Memory()
            overlays = [(probe.INDEX, b'\x12\x34'), (address, bytes(84)), (probe.SP-4, bytes(4))]
            probe.map_inputs(memory, original, overlays)
            ordered = sorted(memory.regions)
            for (lo, data), (next_lo, _) in zip(ordered, ordered[1:]):
                self.assertLessEqual(lo + len(data), next_lo)
            self.assertEqual(sum(len(data) for lo, data in ordered),
                             pinned.SIZE + 4 + min(84, max(0, address + 84 - (pinned.BASE+pinned.SIZE))))
            for lo, data in ordered:
                if (lo, data) not in overlays:
                    self.assertEqual(data, bytes([0xCC]) * len(data))

    def test_mapping_rejects_overlaps_and_incomplete_original(self):
        for data, overlays in ((bytes(pinned.SIZE), [(probe.INDEX, bytes(4)), (probe.INDEX+2, bytes(2))]),
                               (b'', [])):
            with self.assertRaises(ValueError):
                probe.map_inputs(None, data, overlays)

    def test_invalid_entry_or_index_fails_before_cpu(self):
        for entry, index in ((0, 0), (0x0600A25E, -1), (0x0600A25E, 0x10000)):
            with self.assertRaises(ValueError):
                probe.run_case(bytes(pinned.SIZE), None, entry, index, 0, 0)

    def test_failed_source_is_private_immutable_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'report.json'
            args = ['--kernel', str(root / 'absent'), '--saturn-recomp', str(root), '--report', str(report)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(args), 1)
            data = report.read_bytes()
            self.assertEqual(json.loads(data)['error']['phase'], 'source_identity')
            self.assertNotIn(str(root), data.decode())
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(args), 1)
            self.assertEqual(report.read_bytes(), data)

    def test_execution_exception_cannot_become_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'failed.json'
            with patch.object(pinned, 'kernel_bytes', return_value=bytes(pinned.SIZE)), \
                 patch.object(pinned, 'interpreter', return_value=None), \
                 patch.object(probe, 'execute', side_effect=ValueError('private diagnostic')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(['--kernel','unused','--saturn-recomp','unused',
                                             '--report',str(report)]), 1)
            d = json.loads(report.read_text())
            self.assertEqual(d['status'], 'failure')
            self.assertEqual(d['error']['phase'], 'original_execution')
            self.assertNotIn('private diagnostic', report.read_text())


if __name__ == '__main__': unittest.main()
