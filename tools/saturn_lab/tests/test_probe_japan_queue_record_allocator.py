import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_queue_record_allocator as probe


class JapanQueueRecordAllocatorTests(unittest.TestCase):
    def test_original_leaf_and_shared_slot_layout(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A753C, 0x060A7564))
        self.assertEqual((probe.GLOBAL, probe.TABLE_BASE, probe.SLOT_OFFSET),
                         (0x060FB580, 0x06006000, 0x44C))

    def test_free_and_busy_cases_cover_unsigned_arithmetic_boundaries(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.VALUES) ** 2 * 2)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({case[0] for case in cases}, set(probe.VALUES))
        self.assertEqual({case[1] for case in cases}, set(probe.VALUES))
        self.assertEqual({case[3] for case in cases}, {False, True})

    def test_arguments_and_mutation_are_strictly_bounded(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0, 0, False)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0x100000000, False)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0, False, (0x060A7564, 0x0009))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0, False, (0x060A755E, 0x10000))


if __name__ == '__main__':
    unittest.main()
