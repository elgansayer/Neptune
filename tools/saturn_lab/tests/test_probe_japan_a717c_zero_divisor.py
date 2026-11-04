import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_zero_divisor as probe


class JapanA717CZeroDivisorTests(unittest.TestCase):
    def test_original_body_and_global_pointer(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A717C, 0x060A727E))
        self.assertEqual((probe.GLOBAL_LITERAL, probe.GLOBAL_BASE), (0x060A7364, 0x060FCD30))

    def test_corpus_covers_zero_shift_inputs_and_saved_values(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 2048)
        self.assertEqual(len(set(cases)), 2048)
        self.assertEqual({arg for arg, *_ in cases}, {0, 1, 2, 3})
        self.assertEqual({priority for *_, priority, seed in cases}, set(range(16)))
        self.assertEqual({seed for *_, seed in cases}, {0, 1})

    def test_exact_pc_path_excludes_unresolved_calls(self):
        self.assertEqual(len(probe.EXPECTED_PCS), 49)
        self.assertIn(0x060A71A2, probe.EXPECTED_PCS)
        self.assertIn(0x060A7244, probe.EXPECTED_PCS)
        self.assertNotIn(0x060A71A6, probe.EXPECTED_PCS)
        self.assertNotIn(0x060A7232, probe.EXPECTED_PCS)


if __name__ == "__main__":
    unittest.main()
