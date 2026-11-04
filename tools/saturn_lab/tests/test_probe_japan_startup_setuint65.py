import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_startup_setuint65 as probe


class JapanStartupSetuint65Tests(unittest.TestCase):
    def test_original_boundaries_and_captured_vectors(self):
        self.assertEqual((probe.CALLER, probe.STOP), (0x0600A338, 0x0600A350))
        self.assertEqual((probe.CHGSCUIM_STUB, probe.SETUINT_STUB), (0x060007C0, 0x06000794))
        self.assertEqual((probe.CHG_SLOT, probe.SLOT, probe.MASK_SLOT),
                         (0x06000344, 0x06000300, 0x06000348))

    def test_expected_scu_effects_and_original_literals(self):
        self.assertEqual(probe.CHG_LITERALS[0x060007E8], (4, 0x25FE00A0))
        self.assertEqual(probe.CHG_LITERALS[0x060007EC], (4, probe.MASK_SLOT))
        self.assertEqual(probe.CHG_LITERALS[0x06000828], (2, 0x00F0))
        self.assertEqual(probe.case_inputs(), [(s, 0x1800 + s * 4, 0x76000000 + s * 0x01010101)
                                               for s in range(4)])

    def test_captured_state_write_allowlist_excludes_unmodeled_hardware(self):
        self.assertEqual(probe.LIMIT, 64)
        self.assertEqual(probe.SR, 0xF0)
        self.assertNotIn(0x25FE00A8, (0x25FE00A0, 0x25FE00A4))


if __name__ == "__main__":
    unittest.main()
