import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_address as probe


class JapaneseRecordAddressTests(unittest.TestCase):
    def test_contract_uses_signed_low_word_product(self):
        self.assertEqual(probe.expected(0), probe.RECORD_BASE)
        self.assertEqual(probe.expected(17), probe.RECORD_BASE + 17 * 88)
        self.assertEqual(probe.expected(18), probe.RECORD_BASE + 18 * 88)
        self.assertEqual(probe.expected(0x8000), probe.expected(-32768))

    def test_case_set_covers_valid_record_indices_and_signed_boundaries(self):
        self.assertEqual(len(probe.CASES), len(set(probe.CASES)))
        self.assertTrue(set(range(18)).issubset(probe.CASES))
        self.assertIn(0x7FFFFFFF, probe.CASES)
        self.assertIn(0x80000000, probe.CASES)
        self.assertIn(0xFFFFFFFF, probe.CASES)

    def test_original_code_and_literal_are_disjoint_bounded_ranges(self):
        self.assertEqual(probe.CODE_END, probe.LITERAL)
        self.assertEqual(probe.CODE_END - probe.ENTRY, 18)
        self.assertEqual(probe.LITERAL_END - probe.LITERAL, 4)
        self.assertLessEqual(probe.MAX_STEPS, 32)

    def test_out_of_range_index_type_rejected_before_execution(self):
        with self.assertRaises(ValueError):
            probe.execute(None, None, 1 << 32)


if __name__ == "__main__":
    unittest.main()
