import unittest
import probe_japan_ae98_vbr_record_store as probe


class AE98VbrRecordStoreTests(unittest.TestCase):
    def test_original_range_and_cache_through_selection(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AE98, 0x0600AEAE))
        self.assertEqual((probe.LITERAL, probe.ALIAS), (0x0600AF08, 0x2600A020))
        self.assertEqual(probe.SLOTS, (0, 1))

    def test_selected_rows_match_scheduler_slots(self):
        self.assertEqual(probe.TABLE, 0x060BCEEC)
        self.assertEqual(probe.ROW_SIZE, 88)
        self.assertEqual(probe.SELECTED_ROWS, {0: 3, 1: 12})


if __name__ == "__main__":
    unittest.main()
