"""Owned synthetic contract/failure tests; original CPU evidence is host-private."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import m68k_probe as native
import probe_netlink_pointer as probe


class ContractLibrary:
    """A scripted native response, explicitly not an instruction interpreter."""
    def __init__(self, failure=None): self.failure = failure
    def run(self, code, entry, stop, ranges, regions, regs, budget):
        base = int.from_bytes(regions[0][1], 'big')
        after = probe.expected_registers(regs, base)
        actual = {'status_code': 1, 'status': 'stop-reached', 'registers': after,
                  'pcs': probe.PCS, 'steps': 7, 'model_cycles': 0,
                  'events': [[1, probe.POINTER, 4, base], [1, probe.SP, 4, probe.STOP]],
                  'regions_after': [r[1] for r in regions], 'code_unchanged': True}
        if self.failure == 'A2': after[10] ^= 1
        if self.failure == 'SR': after[17] ^= 1
        if self.failure == 'SP': after[15] -= 4
        if self.failure == 'PC': after[16] = entry
        if self.failure == 'read': actual['events'] = actual['events'][1:]
        if self.failure == 'write': actual['regions_after'] = [b'changed']
        if self.failure == 'code': actual['code_unchanged'] = False
        if self.failure == 'instructions': actual['pcs'] = probe.PCS[:-1]
        if self.failure == 'bound': actual['status_code'], actual['status'] = 2, 'instruction-budget'
        return actual


class NetlinkPointerTests(unittest.TestCase):
    def test_complete_sign_overflow_state_selection(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 88)
        self.assertEqual(len(set(rows)), 88)
        self.assertIn((0xFFFFFFFF, 0x271F, 0xA5A5A5A5), rows)

    def test_fixed_unsigned_wrap_oracle(self):
        before = [0]*18
        result = probe.expected_registers(before, 0xFFFFE000)
        self.assertEqual(result[12:15], [0, 0x400, 0x100])
        self.assertEqual(result[:12], before[:12])
        self.assertEqual(result[15:18], [probe.SP+4, probe.STOP, 0])

    def test_scripted_complete_contract(self):
        row = probe.run_case(bytes(23920), ContractLibrary(), 0, 0x271F, 0xA5A5A5A5)
        self.assertTrue(row['A2_preserved'])
        self.assertTrue(row['unaffected_mapped_bytes_equal'])

    def test_rejects_abi_memory_pc_and_native_failures(self):
        for failure in ('A2','SR','SP','PC','read','write','code','instructions','bound'):
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.run_case(bytes(23920), ContractLibrary(failure), 0, 0x271F, 0xA5A5A5A5)

    def test_missing_input_retains_private_failure_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root/'failure.json'
            args = ['--source-file', str(root/'missing'), '--prepared', str(root), '--report', str(report)]
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(probe.main(args), 1)
            original = report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'], 'source_identity')
            self.assertNotIn(str(root), original.decode())
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(probe.main(args), 1)
            self.assertEqual(report.read_bytes(), original)

    def test_tampered_source_fails_before_compiler_or_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = {'files': {'bad.c': '0'*64}}
            (root/'bad.c').write_text('changed')
            with patch.object(native, 'SOURCE_LOCK', root/'lock.json'):
                (root/'lock.json').write_text(json.dumps(lock))
                with patch.object(native.subprocess, 'run') as run, self.assertRaises(ValueError):
                    native.prepare(root, root/'cache')
                run.assert_not_called()
            self.assertFalse((root/'cache').exists())

    def test_tampered_prepared_receipt_never_loads_native_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'receipt.json').write_text(json.dumps({'status':'ready','identity':{}}))
            with patch.object(native.c, 'CDLL') as load, self.assertRaises(ValueError): native.Library(root)
            load.assert_not_called()


if __name__ == '__main__': unittest.main()
