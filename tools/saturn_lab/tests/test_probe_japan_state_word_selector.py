import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_state_word_selector as probe


class JapanStateWordSelectorTests(unittest.TestCase):
    def test_bounds_and_complete_halfword_domains(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600B272, 0x0600B290))
        self.assertEqual((probe.DATA_BASE, probe.DATA_SIZE), (0x060BDDB4, 12))
        self.assertEqual({probe.output_word(x) for x in range(65536)},
                         set(range(65536)))

    def test_inclusive_status_window_and_signed_word_return(self):
        for status in range(65536):
            value = probe.output_word(status)
            self.assertEqual(probe.contract(status, value),
                             value if 12 <= status <= 16 else 0)
        self.assertEqual(probe.contract(12, 0xFFFF), 0xFFFF)
        with self.assertRaises(ValueError):
            probe.contract(-1, 0)
        with self.assertRaises(ValueError):
            probe.contract(0, 0x10000)


if __name__ == "__main__":
    unittest.main()
