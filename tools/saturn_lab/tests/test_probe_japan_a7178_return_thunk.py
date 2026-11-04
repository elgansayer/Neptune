import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a7178_return_thunk as probe


class JapanA7178ReturnThunkTests(unittest.TestCase):
    def test_original_range_and_delay_slot_are_explicit(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A7178, 0x060A717C))
        self.assertEqual(probe.RETURN_IMMEDIATE, 0x060A717A)
        self.assertEqual(probe.LIMIT, 4)

    def test_domain_covers_all_priority_values_and_register_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 32)
        self.assertEqual(len(set(cases)), 32)
        self.assertEqual({priority for priority, _ in cases}, set(range(16)))
        self.assertEqual({seed for _, seed in cases}, {0, 1})

    def test_expected_source_mapping_is_japanese_workram(self):
        self.assertEqual(probe.BASE, 0x0600A000)
        self.assertEqual(probe.KERNEL_SIZE, 786432)
        self.assertEqual(probe.WORKRAM_BASE, 0x06000000)


if __name__ == "__main__":
    unittest.main()
