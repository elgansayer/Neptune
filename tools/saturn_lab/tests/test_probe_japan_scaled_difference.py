import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_scaled_difference as probe


class JapanScaledDifferenceTests(unittest.TestCase):
    def test_original_leaf_range_and_record_fields(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A750A, 0x060A7518))
        self.assertEqual((probe.TARGET, probe.RECORD_SIZE, probe.LIMIT),
                         (0x06004000, 48, 8))

    def test_cartesian_corpus_covers_all_declared_unsigned_boundaries(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.VALUES) ** 3)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({v for row in cases for v in row}, set(probe.VALUES))

    def test_inputs_and_mutation_are_strictly_bounded(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0x100000000, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0, (0x060A7518, 0x0009))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0, (0x060A7516, 0x10000))


if __name__ == '__main__':
    unittest.main()
