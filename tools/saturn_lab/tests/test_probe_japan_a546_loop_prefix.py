import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a546_loop_prefix as probe


class JapanA546LoopPrefixTests(unittest.TestCase):
    def test_contiguous_entry_and_stop_before_onchip_register_path(self):
        self.assertEqual((probe.ENTRY, probe.STOP), (0x0600A4C4, 0x0600A6D6))
        self.assertIn(0x0600A6D6, (probe.STOP,))
        self.assertNotIn(probe.STOP, probe.CODE)

    def test_four_iteration_bounds_and_captured_memory(self):
        self.assertEqual(probe.LOOP_COUNT, 4)
        self.assertEqual((probe.POLL_WORD, probe.COUNTER), (0x060B3D40, 0x060B3D42))
        self.assertEqual((probe.LONG_DEST, probe.HALF_DEST), (0x25E80000, 0x25F00800))
        self.assertEqual((probe.EXPECTED_LONG_WRITES, probe.EXPECTED_HALF_WRITES), (131072, 1024))

    def test_explicit_poll_corpus_and_scu_intent_extent(self):
        self.assertEqual(probe.POLL_SAMPLES, (5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 9))
        self.assertEqual(len(probe.POLL_SAMPLES), probe.LOOP_COUNT * 3)
        self.assertEqual(1 + 256 + 2 * 256, 769)
        self.assertEqual(probe.LIMIT, 800000)


if __name__ == "__main__":
    unittest.main()
