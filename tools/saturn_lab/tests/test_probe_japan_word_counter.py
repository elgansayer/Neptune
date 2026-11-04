import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_word_counter as probe


class JapanWordCounterTests(unittest.TestCase):
    def test_location_identity_and_machine_word_wrap(self):
        self.assertEqual((probe.BASE, probe.ENTRY, probe.END), (0x0600A000, 0x0600A5E4, 0x0600A5EE))
        self.assertEqual(probe.WORD, 0x060B3D40)
        self.assertEqual((0 + 1) & 0xFFFF, 1)
        self.assertEqual((0x7FFF + 1) & 0xFFFF, 0x8000)
        self.assertEqual((0xFFFF + 1) & 0xFFFF, 0)


if __name__ == "__main__":
    unittest.main()
