import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_tag_scan as probe


class JapaneseRecordTagScanTests(unittest.TestCase):
    def test_scenarios_cover_each_slot_and_both_latch_states(self):
        cases = probe.scenarios()
        by_name = {case[0]: case for case in cases}
        self.assertEqual(len(cases), 39)
        for index in range(probe.COUNT):
            for state in ("inactive", "active"):
                name = f"single_{index}_{state}"
                _, tag, tags, flags = by_name[name]
                self.assertEqual([i for i, value in enumerate(tags) if value == tag], [index])
                self.assertEqual(flags[index], int(state == "active"))

    def test_expected_table_marks_only_matching_tag_and_active_word(self):
        tags = [0xFE] * probe.COUNT
        flags = [0] * probe.COUNT
        tags[3] = tags[9] = 0x55
        flags[9] = 1
        table = probe.expected_table(tags, flags)
        self.assertEqual(table[3 * probe.STRIDE + 81], 0x55)
        self.assertEqual(table[9 * probe.STRIDE + 80], 1)
        self.assertEqual(table[3 * probe.STRIDE:3 * probe.STRIDE + 4], (0xC0100003).to_bytes(4, "big"))


if __name__ == "__main__":
    unittest.main()
