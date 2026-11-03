import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_state_halfword_clear as probe


class JapanStateHalfwordClearTests(unittest.TestCase):
    def test_original_bounds_and_literal_destinations(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600B256, 0x0600B272))
        self.assertEqual([target for _source, target in probe.LITERALS],
                         [0x060BDDB8, 0x060BDDB6, 0x060BDDB4,
                          0x060BDDBE, 0x060BDDBC, 0x060BDDBA])

    def test_input_corpus_is_distinct_and_clears_all_halfwords(self):
        inputs = [probe.pattern(i) for i in range(64)]
        self.assertEqual(len(set(inputs)), 64)
        for initial in inputs:
            self.assertEqual(len(initial), 12)
            self.assertNotEqual(initial, bytes(12))
        self.assertEqual(probe.WRITE_OFFSETS, (4, 2, 0, 10, 8, 6))


if __name__ == "__main__":
    unittest.main()
