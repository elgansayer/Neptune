"""Owned contracts and failure controls; originals are a separate guarded job."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_netlink_boot_ram as p


class BootRamTests(unittest.TestCase):
    def test_exact_clear_extent_canaries_stack_and_all_other_registers(self):
        for layout, (base, sp) in enumerate(p.LAYOUTS):
            before, regions, result = p.contract(layout, 0x271F, 0x12345678, 1, {'sentinel': 37})
            self.assertEqual(p.EXTENT, 0x2FC4)
            ram = result['regions_after'][0]
            self.assertEqual(ram[:16], regions[0][1][:16])
            self.assertEqual(ram[-16:], regions[0][1][-16:])
            changed = set(range(0x182A, 0x182C)) | set(range(0x1890, 0x18A0)) | set(range(0x18C0, 0x1900))
            self.assertTrue(all(ram[16 + i] == 0 for i in range(p.EXTENT) if i not in changed))
            self.assertEqual(result['regions_after'][1], regions[1][1])
            self.assertFalse(regions[1][2])
            self.assertGreater(sp - 16, base + p.EXTENT + 16)
            self.assertEqual(result['registers'][8:12], [base + 0x2FC4, base + 0x18C0, before[10], base + 0x18A0])
            self.assertEqual(result['registers'][15:18], [sp + 4, p.leaf.STOP, 0x2700])
            for index in (1, 3, 4, 5, 10, 12, 13, 14):
                self.assertEqual(result['registers'][index], before[index])
            self.assertEqual(result['device_after'], {'sentinel': 37})
            self.assertEqual(result['reference_bus_events'], [])

    def test_table_is_a_complete_permutation_with_known_independent_rows(self):
        _, _, result = p.contract(0, 0x2700, 255, 0, {})
        table = result['regions_after'][0][16 + 0x18C0:16 + 0x1900]
        values = [int.from_bytes(table[i:i + 2], 'big') for i in range(0, 64, 2)]
        self.assertEqual(values[:8], [0, 0x200, 0x400, 0x600, 0x40, 0x240, 0x440, 0x640])
        self.assertEqual(values[-4:], [0x1C0, 0x3C0, 0x5C0, 0x7C0])
        self.assertEqual(sorted(values), list(range(0, 0x800, 0x40)))
        writes = result['events'][p.LONGS:p.LONGS + 32]
        self.assertEqual(len({event[1] for event in writes}), 32)
        self.assertEqual([event[3] for event in writes], list(range(0, 0x800, 0x40)))
        self.assertEqual(writes[:3], [[2, 0x88C0, 2, 0], [2, 0x88C8, 2, 0x40], [2, 0x88D0, 2, 0x80]])

    def test_defaults_sequence_and_final_flags_are_seed_and_variant_independent(self):
        for sr in p.effects.SR_VALUES:
            _, _, result = p.contract(0, sr, p.MASK, 1, {})
            ram = result['regions_after'][0]
            self.assertEqual(ram[16 + 0x182A:16 + 0x182C], b'\x00\x20')
            self.assertEqual(ram[16 + 0x1890:16 + 0x18A0], bytes(range(16)))
            self.assertEqual(result['registers'][:8:2], [16, 8, p.records.base_regs(p.ENTRY, sr)[4] ^ p.MASK, 0xFFFF])
            self.assertEqual(result['registers'][7], 0xFFFF)
            self.assertEqual(result['registers'][17], sr & ~31)

    def test_complete_pc_and_data_counts_fit_existing_abi_without_new_capacity(self):
        _, _, result = p.contract(0, 0x2700, 0, 0, {})
        self.assertEqual(result['steps'], 6345)
        self.assertEqual(len(result['pcs']), 6345)
        self.assertEqual(result['pcs'].count(0x35E8), 3057)
        self.assertEqual(result['pcs'].count(0x35FC), 32)
        self.assertEqual(result['pcs'].count(0x3620), 16)
        self.assertEqual(result['pcs'][-1], 0x3628)
        self.assertEqual(len(result['events']), 3107)
        self.assertEqual(result['events'][0], [2, 0x7000, 4, 0])
        self.assertEqual(result['events'][3056], [2, 0x9FC0, 4, 0])
        self.assertEqual(result['events'][-1], [1, 0x9FFC, 4, p.leaf.STOP])
        self.assertLess(result['steps'], p.native.MAX_STEPS)
        self.assertLess(len(result['events']), p.native.MAX_EVENTS)

    def test_comparison_rejects_every_observable_and_incomplete_results(self):
        _, _, expected = p.contract(0, 0x271F, 1, 0, {'sentinel': 1})
        actual = {'status_code': 1, 'status': 'stop-reached', 'code_unchanged': True, **deepcopy(expected)}
        p.effects.compare(actual, expected)
        for field in expected:
            changed = deepcopy(actual)
            if field == 'steps':
                changed[field] += 1
            elif field == 'device_after':
                changed[field]['sentinel'] = 2
            elif field == 'regions_after':
                changed[field][0] = b'wrong'
            elif field in ('events', 'reference_bus_events'):
                changed[field].append([2, 0, 1, 0])
            else:
                changed[field][0] ^= 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.effects.compare(changed, expected)
        for key, value in (('status_code', 2), ('code_unchanged', False)):
            with self.assertRaises(ValueError):
                p.effects.compare({**actual, key: value}, expected)

    def test_selection_and_invalid_domains(self):
        cases = p.selection()
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({row[2] for row in cases if row[2] < 256}, set(range(256)))
        self.assertEqual({row[0] for row in cases}, {0, 1})
        self.assertEqual({row[1] for row in cases}, set(p.effects.SR_VALUES))
        self.assertEqual({row[3] for row in cases}, {0, 1})
        initial = [0, 0x271F, 0, 0]
        for index, value in ((0, True), (0, 2), (1, 0), (2, True), (2, -1), (2, 2**32), (3, True), (3, 2)):
            changed = initial[:]
            changed[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                p.contract(*changed, {})

    def test_guard_is_never_counted_as_terminal_semantic_rejection(self):
        class Incomplete:
            def run(self, *args, **kwargs):
                return {'status_code': 2}
        with self.assertRaisesRegex(ValueError, 'terminal semantics'):
            p.controls(bytes(23920), Incomplete())

    def test_input_failure_is_private_exclusive_and_precedes_native_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'failed.json'
            args = ['--source-file', str(root / 'missing'), '--prepared', str(root), '--report', str(report)]
            with patch.object(p.native, 'Library') as library, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
                library.assert_not_called()
            data = report.read_bytes()
            self.assertFalse(json.loads(data)['original_game_bytes_executed'])
            self.assertEqual(json.loads(data)['error']['phase'], 'source_identity')
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
            self.assertEqual(report.read_bytes(), data)

    def test_native_identity_failure_is_recorded_without_loading_or_executing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'identity-failure.json'
            args = ['--source-file', str(root / 'source'), '--prepared', str(root),
                    '--report', str(report)]
            with patch.object(p.sound, 'source_bytes', return_value=bytes(23920)), \
                    patch.object(p.native, 'identity', side_effect=FileNotFoundError('missing source lock')), \
                    patch.object(p.native, 'Library') as library, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
                library.assert_not_called()
            data = json.loads(report.read_text())
            self.assertEqual(data['status'], 'failure')
            self.assertEqual(data['error']['phase'], 'native_identity')
            self.assertFalse(data['original_game_bytes_executed'])
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_native_load_failure_records_identity_without_claiming_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'load-failure.json'
            args = ['--source-file', str(root / 'source'), '--prepared', str(root),
                    '--report', str(report)]
            with patch.object(p.sound, 'source_bytes', return_value=bytes(23920)), \
                    patch.object(p.native, 'identity', return_value={'abi': 8}), \
                    patch.object(p.native, 'Library', side_effect=ValueError('invalid prepared receipt')), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
            data = json.loads(report.read_text())
            self.assertEqual(data['status'], 'failure')
            self.assertEqual(data['error']['phase'], 'native_load')
            self.assertEqual(data['native_identity'], {'abi': 8})
            self.assertFalse(data['original_game_bytes_executed'])


if __name__ == '__main__':
    unittest.main()
