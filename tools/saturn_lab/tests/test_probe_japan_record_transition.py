import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_transition as probe


class JapanRecordTransitionTests(unittest.TestCase):
    def test_record_address_uses_japan_table_and_signed_low_word_product(self):
        self.assertEqual(probe.address(0), probe.TABLE)
        self.assertEqual(probe.address(17), probe.TABLE + 17 * 88)
        self.assertEqual(probe.address(18), probe.TABLE + 18 * 88)
        self.assertEqual(probe.BASE, 0x0600A000)
        self.assertNotEqual(probe.BASE, 0x06006000)

    def test_bounds_are_signed_32_bit(self):
        self.assertLess(probe.common.signed(17, 32), 18)
        self.assertFalse(probe.common.signed(18, 32) < 18)
        self.assertTrue(probe.common.signed(0xFFFFFFFF, 32) < 18)


if __name__ == "__main__":
    unittest.main()
