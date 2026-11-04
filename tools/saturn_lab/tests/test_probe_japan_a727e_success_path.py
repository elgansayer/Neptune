import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a727e_success_path as probe


class A727ESuccessPathTests(unittest.TestCase):
    def test_input_matrix_covers_status_and_copy_lengths(self):
        rows = probe.corpus()
        self.assertEqual(len(rows), 34)
        self.assertEqual({row[0] for row in rows}, {0, 1, 2, 3})
        self.assertEqual({row[1] for row in rows if row[1] is not None}, {0, 1, 2, 3})

    def test_status_bit_two_selects_a74e0_branch(self):
        self.assertIn(0x060A728E, probe.expected_pcs(0, None))
        self.assertIn(0x060A74E0, probe.expected_pcs(2, 0))
        self.assertIn(0x060A74F6, probe.expected_pcs(2, 1))
        self.assertEqual(probe.expected_pcs(2, 0)[-5:],
            (0x060A72A4, 0x060A72A6, 0x060A72A8, 0x060A72AA, 0x060A72AC))


if __name__ == "__main__":
    unittest.main()
