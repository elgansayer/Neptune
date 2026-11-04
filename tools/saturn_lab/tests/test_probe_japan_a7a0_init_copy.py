import unittest
import probe_japan_a7a0_init_copy as probe


class A7A0InitCopyTests(unittest.TestCase):
    def test_original_ranges_and_record_dimensions(self):
        self.assertEqual((probe.ENTRY, probe.EXIT), (0x0600A7A0, 0x0600A80E))
        self.assertEqual((probe.SAVE, probe.SAVE_END), (0x0600A164, 0x0600A186))
        self.assertEqual((probe.COPY, probe.COPY_END), (0x06095610, 0x060956D0))
        self.assertEqual((probe.TABLE_SIZE // probe.ROW_SIZE, probe.ROW_SIZE), (18, 88))

    def test_count_mutation_changes_one_full_row(self):
        self.assertEqual(probe.TABLE_SIZE - probe.ROW_SIZE, 0x5D8)
        self.assertEqual((probe.TABLE_SIZE - probe.ROW_SIZE) // probe.ROW_SIZE, 17)


if __name__ == "__main__":
    unittest.main()
