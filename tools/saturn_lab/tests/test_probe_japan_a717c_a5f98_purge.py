import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_a5f98_purge as probe


class A717CA5F98PurgeTests(unittest.TestCase):
    def test_corpus_uses_the_two_a717c_caller_bases(self):
        self.assertEqual(probe.cases(), [(0x06009000, 4), (0x06009004, 4)])

    def test_both_caller_bases_select_the_same_aligned_cache_line(self):
        self.assertEqual(probe.purge_line(0x06009000), 0x46009000)
        self.assertEqual(probe.purge_line(0x06009004), 0x46009000)

    def test_expected_path_includes_call_delay_and_rts_delay(self):
        self.assertEqual(probe.CALLER_PCS[-2:], (0x060A7240, 0x060A7242))
        self.assertEqual(probe.HELPER_PCS[-2:], (0x060A5FB0, 0x060A5FB2))
        self.assertEqual(probe.STOP, 0x060A7244)


if __name__ == "__main__":
    unittest.main()
