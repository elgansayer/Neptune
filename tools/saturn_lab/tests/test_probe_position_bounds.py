"""Owned synthetic guard checks; original-byte execution is a private host experiment."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_position_bounds as probe
import probe_kernel as pinned


class PositionBoundsTests(unittest.TestCase):
    def test_case_selection_is_nonempty_distinct_cartesian_product(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 180)
        self.assertEqual(len(set(rows)), 180)
        self.assertEqual({r[0] for r in rows}, {0, 1, 0x7fff, 0x8000, 0xffff})
        self.assertIn(0x80000000, {r[2] for r in rows})

    def test_signed_loads_truncation_and_two_independent_axes(self):
        record = bytearray([0xA5] * 84)
        record[16:20] = bytes.fromhex('80007fff')
        output = probe.expected_record(record, bytes([0x80, 0x7f, 0x7f, 0x80]), 1, -1)
        self.assertEqual(output[20:28].hex(), '7fff80007f0280fd')
        self.assertEqual(output[:20], record[:20])
        self.assertEqual(output[28:], record[28:])

    def test_leaf_leaves_second_axis_untouched(self):
        record = bytes(84)
        output = probe.expected_record(record, bytes([255, 0, 128, 0]), 0xFFFFFFFF)
        self.assertEqual(output[20:22], b'\x00\x01')
        self.assertEqual(output[24:26], b'\x00\x7e')
        self.assertEqual(output[22:24] + output[26:28], bytes(4))

    def test_missing_input_is_retained_as_failed_phase(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'fresh.json'
            with contextlib.redirect_stdout(io.StringIO()):
                result = probe.main(['--kernel', str(root / 'absent'),
                                     '--saturn-recomp', str(root), '--report', str(report)])
            self.assertEqual(result, 1)
            data = json.loads(report.read_text())
            self.assertEqual(data['error']['phase'], 'source_identity')
            self.assertNotIn(str(root), report.read_text())
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_existing_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'existing.json'
            report.write_text('retain me')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(['--kernel', 'unused', '--saturn-recomp', 'unused',
                                             '--report', str(report)]), 1)
            self.assertEqual(report.read_text(), 'retain me')

    def scripted_emulator(self, failure=None):
        # This scripted CPU tests wrapper rejection, never instruction semantics.
        class Memory:
            def __init__(self): self.regions = []
            def add(self, lo, size, data):
                buf = bytearray(data)
                self.assert_size = len(buf) == size
                self.regions.append((lo, lo + size, buf))
                return buf
            def read(self, address, size):
                for lo, hi, buf in self.regions:
                    if lo <= address and address + size <= hi:
                        return int.from_bytes(buf[address-lo:address-lo+size], 'big')
                raise ValueError('unmapped')
            def write(self, address, size, value):
                for lo, hi, buf in self.regions:
                    if lo <= address and address + size <= hi:
                        buf[address-lo:address-lo+size] = (value & ((1 << (size*8))-1)).to_bytes(size, 'big')
                        return
                raise ValueError('unmapped')
        class CPU:
            def __init__(self, memory):
                self.mem = memory
                self.r = [0]*16
                self.sr = self.pr = self.macl = self.mach = self.gbr = self.vbr = self.steps = 0
            def exec(self, instruction, pc, in_slot=False): pass
            def call(self, entry, max_steps):
                self.exec(None, entry)
                self.steps = 1
                if failure == 'budget':
                    for _ in range(probe.LIMIT): self.exec(None, entry)
                if failure == 'escape': self.exec(None, probe.LEAF - 2)
                if failure == 'kernel-write': self.mem.write(pinned.BASE, 2, 0)
                if failure == 'wrong-width': self.mem.write(probe.BUFFER + 20, 4, 0)
                self.mem.write(probe.BUFFER + 20, 2, 0xFFFF)
                self.mem.write(probe.BUFFER + 24, 2, 0xFFFF)
                if failure == 'missing-store': self.mem.writes.pop()
                if failure == 'clobber': self.r[14] = 0
                self.pc = 0 if failure == 'no-return' else 0xFFFFFFF0
        return types.SimpleNamespace(Memory=Memory, CPU=CPU, RETURN_SENTINEL=0xFFFFFFF0)

    def test_accepts_only_complete_scripted_contract(self):
        row = probe.run_case(bytes(pinned.SIZE), self.scripted_emulator(), probe.LEAF,
                             0, (0, 1, 2, 3), 1)
        self.assertTrue(row['unaffected_bytes_equal'])
        self.assertTrue(row['return_sentinel_reached'])

    def test_rejects_escape_budget_write_abi_and_return_failures(self):
        for failure in ('budget', 'escape', 'kernel-write', 'wrong-width', 'missing-store', 'clobber', 'no-return'):
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.run_case(bytes(pinned.SIZE), self.scripted_emulator(failure), probe.LEAF,
                               0, (0, 1, 2, 3), 1)

    def test_rejects_incomplete_module_or_unknown_entry(self):
        for data, entry in ((b'', probe.LEAF), (bytes(pinned.SIZE), 0)):
            with self.assertRaises(ValueError):
                probe.run_case(data, self.scripted_emulator(), entry, 0, (0, 1, 2, 3), 1)


if __name__ == '__main__': unittest.main()
