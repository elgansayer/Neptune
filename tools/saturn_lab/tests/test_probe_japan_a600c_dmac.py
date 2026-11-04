import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a600c_dmac as probe


class JapanA600CDMACTests(unittest.TestCase):
    def test_corpus_covers_flags_channels_chcr_and_descriptor_patterns(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 16384)
        self.assertEqual(len(set(rows)), 16384)
        self.assertEqual({row[0] for row in rows}, set(range(0x400)))
        self.assertEqual({row[1] for row in rows}, {0, 1})

    def test_call_and_leaf_delay_slots_are_on_flag_three_path(self):
        pcs = probe.expected_pcs(0x008)
        self.assertIn(0x060A606A, pcs)
        self.assertIn(0x060959B6, pcs)
        self.assertIn(0x060959BE, pcs)
        self.assertLess(pcs.index(0x060959BE), pcs.index(0x060A606C))
        self.assertNotIn(0x060959B6, probe.expected_pcs(0))

    def test_register_writes_follow_independent_field_masks(self):
        fields = probe.PATTERNS[1]
        written, after, regs = probe.scalar(0x30F, fields, 1, 3)
        self.assertIn((0xFFFFFF90, 4, fields[0]), regs)
        self.assertIn((0xFFFFFF94, 4, fields[1]), regs)
        self.assertIn((0xFFFFFF98, 4, fields[2]), regs)
        self.assertIn((0xFFFFFF9C, 4, written), regs)
        self.assertIn((0xFFFFFE72, 1, fields[8]), regs)
        self.assertEqual(after & 2, 0)

    def test_semantic_controls_detect_dropped_or_shifted_fields(self):
        fields = probe.PATTERNS[1]
        plain_write, _, _ = probe.scalar(0, fields, 0, 0)
        correct_shift, _, _ = probe.scalar(8, fields, 0, 0)
        wrong_shift = (plain_write & 0xFFFF3FFF) | ((fields[3] << 13) & 0xFFFFFFFF)
        self.assertNotEqual(correct_shift, plain_write)
        self.assertNotEqual(correct_shift, wrong_shift)
        no_te_clear, _, _ = probe.scalar(0, fields, 0, 3)
        te_clear, _, _ = probe.scalar(0x200, fields, 0, 3)
        self.assertEqual(no_te_clear & 2, 2)
        self.assertEqual(te_clear & 2, 0)
        no_drcr = probe.scalar(0, fields, 1, 0)[2]
        with_drcr = probe.scalar(0x100, fields, 1, 0)[2]
        self.assertNotEqual(no_drcr, with_drcr)

    def test_all_1024_flag_masks_have_distinct_supported_pc_paths(self):
        paths = [probe.expected_pcs(flags) for flags in range(0x400)]
        self.assertEqual(len(set(paths)), 1024)
        self.assertTrue(all(path[-3:] == (0x060A60E4, 0x060A60E6, 0x060A60E8) for path in paths))


if __name__ == "__main__":
    unittest.main()
