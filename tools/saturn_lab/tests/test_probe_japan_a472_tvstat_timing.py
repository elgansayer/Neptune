import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a472_tvstat_timing as probe


class JapanA472TvstatTimingTests(unittest.TestCase):
    def test_original_code_bounds_and_entry_abi(self):
        self.assertEqual((probe.CALLER_ENTRY, probe.CALLER_END), (0x0600A324, 0x0600A32C))
        self.assertEqual((probe.ENTRY, probe.STOP), (0x0600A472, 0x0600A4A0))
        self.assertEqual((probe.CALLER_SP, probe.STACK_ENTRY, probe.PR_FROM_CALLER),
                         (0x06002000, 0x06001FFC, 0x0600A32C))
        self.assertEqual((probe.TIMING_A, probe.TIMING_B), (0x060BCE88, 0x060BCE8A))

    def test_tvstat_corpus_varies_only_pal_bit_for_each_pair(self):
        rows = probe.corpus()
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(len(rows), 16)
        self.assertEqual(set(probe.STATUS_SAMPLES), {0x0000, 0x0001, 0x020A, 0x020B})
        for sample in (0, 0x020A):
            self.assertIn(sample ^ 1, probe.STATUS_SAMPLES)
            self.assertEqual(sample & 1, 0)
            self.assertEqual((sample ^ 1) & 1, 1)
            self.assertEqual(probe.expected_final_sr(sample, 0x00000301) & 1, 1)
            self.assertEqual(probe.expected_final_sr(sample ^ 1, 0x00000301) & 1, 0)

    def test_original_literals_and_pal_dependent_output_formula(self):
        self.assertEqual(probe.LITERALS[0x0600A510], (4, probe.TVSTAT))
        self.assertEqual(probe.LITERALS[0x0600A4DA], (2, probe.WORD_PAL))
        self.assertEqual(probe.LITERALS[0x0600A4DC], (2, probe.WORD_NTSC))
        self.assertEqual(probe.WORD_NTSC + probe.LINE_DELTA, 0x50DF)
        self.assertEqual(probe.WORD_PAL + probe.LINE_DELTA, 0x50FF)


if __name__ == "__main__":
    unittest.main()
