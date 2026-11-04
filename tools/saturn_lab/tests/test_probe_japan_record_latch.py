import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_latch as probe


class JapaneseRecordLatchTests(unittest.TestCase):
    def test_record_stride_and_table_end(self):
        self.assertEqual(probe.selected_address(0), probe.RECORD_BASE)
        self.assertEqual(probe.selected_address(1), probe.RECORD_BASE + 88)
        self.assertEqual(probe.selected_address(17), probe.RECORD_BASE + 17 * 88)
        self.assertEqual(probe.selected_address(18), probe.RECORD_BASE + 18 * 88)

    def test_rejects_out_of_table_indices(self):
        for index in (-1, 18, 0xFFFFFFFF):
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe.execute(b"", None, index, False)


if __name__ == "__main__":
    unittest.main()
