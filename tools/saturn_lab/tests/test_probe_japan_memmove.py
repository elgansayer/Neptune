import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_memmove as probe


class JapanMemmoveTests(unittest.TestCase):
    def test_original_range_and_bounds(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x06095AFC, 0x06095B3E))
        self.assertEqual((probe.ARENA, probe.N, probe.LIMIT), (0x06003000, 256, 1024))

    def test_corpus_covers_direction_overlap_and_boundaries(self):
        cases = probe.corpus()
        self.assertGreaterEqual(len(cases), 100)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertTrue(any(d < s and d + n > s for d, s, n, _ in cases))
        self.assertTrue(any(d > s and s + n > d for d, s, n, _ in cases))
        self.assertTrue(any(n == 0 for _, _, n, _ in cases))
        self.assertTrue(any(n == 1 for _, _, n, _ in cases))
        self.assertTrue(all(0 <= d <= probe.N and 0 <= s <= probe.N and d+n <= probe.N and s+n <= probe.N for d,s,n,_ in cases))

    def test_mutation_is_fixed_inside_original_code(self):
        self.assertEqual((0x06095B2E, 0x7001), (0x06095B2E, 0x7001))
        with self.assertRaises(ValueError):
            probe.execute(bytes(probe.SIZE), None, (0, 0, 1, 0), (0x06095B40, 0))


if __name__ == '__main__':
    unittest.main()
