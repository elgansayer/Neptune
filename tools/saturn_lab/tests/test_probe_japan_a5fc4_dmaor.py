import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a5fc4_dmaor as probe


class JapanA5FC4DMAORTests(unittest.TestCase):
    def test_corpus_covers_flag_value_and_register_bits(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 16384)
        self.assertEqual(len(set(rows)), 16384)
        self.assertEqual({row[0] for row in rows}, set(range(16)))
        self.assertEqual({row[3] for row in rows}, set(range(16)))
        self.assertEqual({row[1] for row in rows}, set(probe.VALUES))

    def test_all_flags_clear_status_and_set_requested_control_bits(self):
        for old in range(16):
            written, final = probe.scalar(15, 0, 1, old)
            self.assertEqual(written, 1)
            self.assertEqual(final, 1)

    def test_branch_masks_change_only_their_original_regions(self):
        self.assertNotIn(0x060A5FD2, probe.expected_pcs(0))
        self.assertIn(0x060A5FD2, probe.expected_pcs(1))
        self.assertNotIn(0x060A5FE4, probe.expected_pcs(7))
        self.assertIn(0x060A5FE4, probe.expected_pcs(15))
        self.assertEqual(probe.expected_pcs(15)[-2:], (0x060A6008, 0x060A600A))


if __name__ == "__main__":
    unittest.main()
