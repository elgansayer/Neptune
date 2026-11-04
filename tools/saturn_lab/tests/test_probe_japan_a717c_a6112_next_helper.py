import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_a6112_next_helper as probe


class JapanA717CA6112NextHelperTests(unittest.TestCase):
    def test_corpus_covers_declared_composition(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 8192)
        self.assertEqual(len(set(cases)), 8192)
        self.assertEqual({row[0] for row in cases}, {0, 1})
        self.assertEqual({row[1] for row in cases}, set(probe.CHCR_VALUES))

    def test_boundary_includes_original_nop_delay_slot(self):
        self.assertEqual(probe.CALLER_HELPER, 0x060A6112)
        self.assertEqual(probe.NEXT_HELPER, 0x060A5FC4)
        self.assertEqual(probe.AFTER_CALL_PCS[-2:], (0x060A71BC, 0x060A71BE))
        self.assertEqual(probe.EXPECTED_PCS[-2:], (0x060A71BC, 0x060A71BE))
        self.assertEqual(probe.STACK - 92, 0x06007FA4)
        self.assertNotIn(probe.STACK - 96, probe.LOCAL_WRITES)


if __name__ == "__main__":
    unittest.main()
