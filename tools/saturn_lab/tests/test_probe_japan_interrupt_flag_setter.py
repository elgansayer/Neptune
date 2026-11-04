import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_interrupt_flag_setter as probe


class JapanInterruptFlagSetterTests(unittest.TestCase):
    def test_original_code_literal_and_cache_through_target(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600B3BC, 0x0600B3C4))
        self.assertEqual((probe.LITERAL, probe.TARGET, probe.PHYSICAL),
                         (0x0600B3F4, 0x2600A03C, 0x0600A03C))

    def test_input_patterns_are_distinct_full_width_words(self):
        values = [(i * 0x9E3779B1 + 0xA5A55A5A) & probe.MASK
                  for i in range(64)]
        self.assertEqual(len(set(values)), 64)
        self.assertTrue(all(0 <= value <= probe.MASK for value in values))


if __name__ == "__main__":
    unittest.main()
