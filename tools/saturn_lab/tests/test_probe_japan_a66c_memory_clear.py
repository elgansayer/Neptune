import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a66c_memory_clear as probe


class JapanA66cMemoryClearTests(unittest.TestCase):
    def test_original_entry_helper_and_captured_pointer(self):
        self.assertEqual((probe.ENTRY, probe.RETURN), (0x0600A66C, 0xFFFFFE00))
        self.assertEqual((probe.POINTER_WORD, probe.POINTER_VALUE), (0x060B3D44, 0x25E80000))

    def test_original_threshold_is_inclusive_for_longword_loop(self):
        self.assertEqual(probe.LITERALS[0x0600A758], (4, 0x1FFFC))
        self.assertEqual(probe.SIZE // 4 + 1, 32768)
        self.assertEqual(probe.DESTINATION + probe.SIZE, 0x25E9FFFC)
        self.assertEqual(probe.DESTINATION + probe.SIZE + 4, 0x25EA0000)
        self.assertEqual(probe.LIMIT, 200000)

    def test_seed_corpus(self):
        self.assertEqual(probe.SEEDS, (0, 1))


if __name__ == "__main__":
    unittest.main()
