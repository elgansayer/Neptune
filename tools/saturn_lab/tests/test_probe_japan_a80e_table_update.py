import unittest
import probe_japan_a80e_table_update as probe


class A80ETableUpdateTests(unittest.TestCase):
    def test_original_ranges_and_eighteen_row_layout(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600A80E, 0x0600A8C2))
        self.assertEqual((probe.CALLBACK, probe.CALLBACK_END), (0x0600AACC, 0x0600AAEA))
        self.assertEqual((probe.ROWS, probe.ROW_SIZE, probe.TABLE_SIZE), (18, 88, 0x630))

    def test_reference_transfer_model_and_case_boundaries(self):
        self.assertEqual(len(probe.CASES), 5)
        self.assertEqual(probe.CASES["last_reference_calls_aacc"]["index"], 17)
        self.assertEqual(probe.CASES["reference_count_wrap"]["fields"][0][83], 0)


if __name__ == "__main__":
    unittest.main()
