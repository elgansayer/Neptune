import unittest
import probe_japan_ab30_count_update as probe


class AB30CountUpdateTests(unittest.TestCase):
    def test_range_and_table_shape(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AB30, 0x0600AB78))
        self.assertEqual((probe.ROWS, probe.ROW_SIZE, probe.TABLE_SIZE), (18, 88, 1584))

    def test_unsigned_delta_and_counter_floor(self):
        before = bytearray(probe.initial_table(probe.CASES["subtract_and_floor"]))
        after = probe.expected_table(before, 13, 10)
        self.assertEqual(int.from_bytes(after[0:4], "big"), 5)
        self.assertEqual(int.from_bytes(after[88:92], "big"), 1)
        self.assertEqual(int.from_bytes(after[176:180], "big"), 1)
        self.assertEqual(int.from_bytes(after[264:268], "big"), 9)
        self.assertEqual(int.from_bytes(after[17 * 88:17 * 88 + 4], "big"), 0)

    def test_equal_count_shortcut_and_wrap(self):
        table = probe.initial_table(probe.CASES["unsigned_wrap_delta"])
        self.assertEqual(probe.expected_table(table, 7, 7), table)
        after = probe.expected_table(table, 2, 0xFFFFFFFF)
        self.assertEqual(int.from_bytes(after[0:4], "big"), 7)
        self.assertEqual(int.from_bytes(after[88:92], "big"), 1)


if __name__ == "__main__":
    unittest.main()
