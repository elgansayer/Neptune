import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_dispatch_index0_busy as probe


class JapanDispatchIndex0BusyTests(unittest.TestCase):
    def test_composed_ranges_and_original_table_entry(self):
        self.assertEqual((probe.DISPATCH, probe.DISPATCH_END), (0x060A6C94, 0x060A6CB2))
        self.assertEqual((probe.TARGET, probe.BUSY_END), (0x060A8154, 0x060A8178))
        self.assertEqual((probe.CLEANUP, probe.TARGET_END), (0x060A820C, 0x060A8218))
        self.assertEqual((probe.DISPATCH_ENTRY, probe.EXPECTED_TARGET), (0x060B2168, 0x060A8154))

    def test_corpus_covers_occupied_words_registers_and_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.BUSY_VALUES) * len(probe.R5_VALUES) * len(probe.SEEDS))
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({busy for busy, _, _ in cases}, set(probe.BUSY_VALUES))
        self.assertEqual({r5 for _, r5, _ in cases}, set(probe.R5_VALUES))
        self.assertEqual({seed for _, _, seed in cases}, set(probe.SEEDS))

    def test_input_and_table_mutation_are_narrowly_limited(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 2, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 4)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (probe.DISPATCH_ENTRY + 4, probe.TARGET))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (probe.DISPATCH_ENTRY, 0x100000000))


if __name__ == '__main__':
    unittest.main()
