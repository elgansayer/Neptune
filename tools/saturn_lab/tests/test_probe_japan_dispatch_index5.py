import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_dispatch_index5 as probe


class JapanDispatchIndex5Tests(unittest.TestCase):
    def test_composed_original_ranges_and_table_entry(self):
        self.assertEqual((probe.DISPATCH, probe.DISPATCH_END), (0x060A6C94, 0x060A6CB2))
        self.assertEqual((probe.TARGET, probe.TARGET_END), (0x060A730A, 0x060A730E))
        self.assertEqual((probe.TABLE_ENTRY, probe.EXPECTED_TARGET), (0x060B21B8, 0x060A730A))

    def test_corpus_covers_register_values_and_context_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.VALUES) * 2)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({r5 for r5, _ in cases}, set(probe.VALUES))
        self.assertEqual({seed for _, seed in cases}, {0, 1})

    def test_input_and_table_mutation_are_narrowly_limited(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 2)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (probe.TABLE_ENTRY + 4, probe.TARGET))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (probe.TABLE_ENTRY, 0x100000000))


if __name__ == '__main__':
    unittest.main()
