import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a638_vdp_init as probe


class JapanA638VdpInitTests(unittest.TestCase):
    def test_original_function_and_helper_ranges(self):
        self.assertEqual((probe.ENTRY, probe.RETURN), (0x0600A638, 0xFFFFFE00))
        self.assertEqual((probe.ARRAY, probe.ARRAY_SIZE), (0x060BCE8C, 96))
        self.assertEqual((probe.VDP1_VRAM, probe.LIMIT), (0x25C00000, 1024))

    def test_literal_contract_and_fences(self):
        self.assertEqual(probe.LITERALS[0x0600A74C], (4, probe.ARRAY))
        self.assertEqual(probe.LITERALS[0x0600A73E], (2, 0x013F))
        self.assertEqual(probe.LITERALS[0x0600A740], (2, 0x8000))
        self.assertEqual(probe.LITERALS[0x0600A754], (4, probe.VDP1_VRAM))
        self.assertIn(0x0600A5AC, probe.EXECUTABLE)
        self.assertIn(0x0600A5B6, probe.EXECUTABLE)
        self.assertNotIn(0x0600A5B8, probe.EXECUTABLE)

    def test_vdp1_intent_extent_is_48_sequential_words(self):
        events = [[probe.VDP1_VRAM + 2*i, 2] for i in range(48)]
        self.assertEqual(events[0], [0x25C00000, 2])
        self.assertEqual(events[-1], [0x25C0005E, 2])


if __name__ == "__main__":
    unittest.main()
