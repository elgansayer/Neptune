import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_counter_adjust as probe


class JapanRecordCounterAdjustTests(unittest.TestCase):
    def test_source_and_table_bounds(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AB30, 0x0600AB78))
        self.assertEqual((probe.RECORD_BASE, probe.STRIDE, probe.COUNT),
                         (0x060BCEEC, 88, 18))
        cases = list(probe.corpus())
        self.assertEqual(len(cases), 320)
        self.assertEqual(len(set(cases)), 320)

    def test_floor_and_unsigned_delta_contract_at_boundaries(self):
        for delta in (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
            self.assertIsNone(probe.adjust_value(False, 0xFFFFFFFF, delta))
            self.assertIsNone(probe.adjust_value(True, 0, delta))
            self.assertIsNone(probe.adjust_value(True, 1, delta))
            self.assertEqual(probe.adjust_value(True, 2, delta),
                             1 if 2 <= delta else 2 - delta)
            self.assertEqual(probe.adjust_value(True, 0xFFFFFFFF, delta),
                             0xFFFFFFFF - delta if 0xFFFFFFFF > delta else 1)


if __name__ == "__main__":
    unittest.main()
