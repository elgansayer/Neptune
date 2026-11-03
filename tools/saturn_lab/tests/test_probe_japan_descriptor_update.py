import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_descriptor_update as probe


class JapanDescriptorUpdateTests(unittest.TestCase):
    def test_original_range_and_table_boundaries(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600CD74, 0x0600CDA0))
        self.assertEqual((probe.TYPE_TABLE, probe.PTR_TABLE, probe.TYPE_WORDS),
                         (0x060BEA3C, 0x060BEA4C, 0x060BEA7C))
        self.assertEqual((probe.N, probe.LIMIT), (12, 64))

    def test_corpus_covers_four_types_all_indices_and_rejected_types(self):
        cases = probe.case_corpus()
        self.assertEqual(len(cases), 101)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({t for t, i in cases if t < 4}, {0, 1, 2, 3})
        self.assertTrue(all(any(t == typ and (i & 0xFFFF) == idx for t, i in cases)
                            for typ in range(4) for idx in range(12)))
        self.assertTrue(all(any(t == typ for t, _ in cases) for typ in (4, 0x100, 0xFFFF, 0x10000, 0x80000000)))

    def test_case_inputs_are_unsigned_words(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0x100000000)

    def test_mutation_location_is_inside_original_function(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 4, 5, (0x0600CDA0, 0x0009))


if __name__ == '__main__':
    unittest.main()
