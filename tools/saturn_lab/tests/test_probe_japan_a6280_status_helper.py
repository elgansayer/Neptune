import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a6280_status_helper as probe


class JapanA6280StatusHelperTests(unittest.TestCase):
    def test_original_range_and_snapshot_inputs(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A6280, 0x060A62B4))
        self.assertEqual(probe.FLAG_BASE, 0x060FCD2C)
        self.assertEqual(probe.SR_MASK_LITERAL, 0x060A62B6)

    def test_baseline_domain_covers_all_priorities_indexes_and_seeds(self):
        cases = probe.baseline_cases()
        self.assertEqual(len(cases), 96)
        self.assertEqual(len(set(cases)), 96)
        self.assertEqual({index for index, _, _ in cases}, {0, 1, 2})
        self.assertEqual({priority for _, priority, _ in cases}, set(range(16)))
        self.assertEqual({seed for _, _, seed in cases}, {0, 1})

    def test_constructed_byte_matrix_is_exhaustive_for_supported_indexes(self):
        cases = probe.flag_cases()
        self.assertEqual(len(cases), 768)
        self.assertEqual(len(set(cases)), 768)
        self.assertEqual({index for index, _ in cases}, {0, 1, 2})
        self.assertEqual({value for _, value in cases}, set(range(256)))


if __name__ == "__main__":
    unittest.main()
