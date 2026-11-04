import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a472_services as probe


class JapanA472ServicesTests(unittest.TestCase):
    def test_composed_original_bounds_and_service_targets(self):
        self.assertEqual((probe.CALLER, probe.CALLER_END), (0x0600A324, 0x0600A32C))
        self.assertEqual((probe.ENTRY, probe.STOP), (0x0600A472, 0x0600A4C4))
        self.assertEqual((probe.SET_STUB, probe.CHG_STUB), (0x06000794, 0x060007C0))
        self.assertEqual((probe.SERVICE64, probe.SERVICE65), (0x06000A00, 0x06000A04))

    def test_frame1200_vectors_mask_and_literal_contract(self):
        self.assertEqual((probe.SET_SLOT, probe.CHG_SLOT, probe.MASK_SLOT),
                         (0x06000300, 0x06000344, 0x06000348))
        self.assertEqual((probe.MASK_BEFORE, probe.MASK_AFTER), (0xFFFFD77C, 0xFFFFD77C))
        self.assertEqual(probe.LITERALS[0x060007A4], (4, probe.TABLE_BASE))
        self.assertEqual(probe.LITERALS[0x060007E8], (4, 0x25FE00A0))
        self.assertEqual(probe.LIMIT, 96)

    def test_case_corpus_pairs_status_sr_and_register_seeds(self):
        rows = probe.corpus()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(set(probe.STATUS_SAMPLES), {0x0000, 0x0001, 0x020A, 0x020B})
        self.assertEqual(set(probe.SR_SAMPLES), {0x000000F0, 0x00000301})
        self.assertEqual(set(seed for _, _, seed in rows), {0, 1})


if __name__ == "__main__":
    unittest.main()
