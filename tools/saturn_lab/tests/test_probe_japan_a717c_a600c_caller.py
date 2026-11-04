import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_a600c_caller as probe


class A717CA600CCallerTests(unittest.TestCase):
    def test_corpus_covers_signed_caller_and_channel_boundaries(self):
        rows = probe.cases()
        self.assertEqual(len(rows), 216)
        self.assertEqual({row[0] for row in rows}, set(probe.R8_VALUES))
        self.assertEqual({row[1] for row in rows}, set(probe.STACK_TOP_VALUES))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[5] for row in rows}, {0, 2, 3})

    def test_a717c_delay_slot_path_tracks_r8_sign(self):
        negative = probe.caller_pcs(0xFFFFFFFF, 0)
        zero = probe.caller_pcs(0, 0)
        positive = probe.caller_pcs(1, 0)
        self.assertIn(0x060A71DA, negative)
        self.assertIn(0x060A71E0, zero)
        self.assertIn(0x060A71D0, positive)
        self.assertNotIn(0x060A71D0, negative)

    def test_stack_top_selects_descriptor_word_sixteen(self):
        self.assertIn(0x060A71EA, probe.caller_pcs(1, 1))
        self.assertIn(0x060A721C, probe.caller_pcs(1, 0))
        self.assertIn(0x060A71F8, probe.caller_pcs(1, 0xFFFFFFFF))

    def test_stops_after_a6100_return_before_a5f98(self):
        trace = probe.caller_pcs(0, 0)
        self.assertEqual(trace[-2:], (0x060A7232, 0x060A7234))
        self.assertEqual(probe.STOP, 0x060A723C)
        self.assertEqual(probe.FLAGS, 0x2FF)


if __name__ == "__main__":
    unittest.main()
