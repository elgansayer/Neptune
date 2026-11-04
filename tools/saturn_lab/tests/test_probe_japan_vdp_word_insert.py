import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_vdp_word_insert as probe


class JapanVDPWordInsertTests(unittest.TestCase):
    def test_original_range_and_observed_selectors(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x06095C24, 0x06095C8C))
        self.assertEqual(probe.SELECTORS, (0x0101, 0x0201, 0x0301, 0x0401, 0x0501))
        self.assertEqual((probe.STACK_BASE, probe.SP), (0x06001FEC, 0x06002000))
        self.assertEqual((probe.TARGET, probe.LIMIT), (0x06003000, 256))

    def test_distinct_original_caller_corpus_and_bitfield_formula(self):
        corpus = [(sel, value, old) for sel in probe.SELECTORS
                  for value in probe.VALUES for old in probe.OLD_WORDS]
        self.assertEqual(len(corpus), 640)
        self.assertEqual(len(set(corpus)), 640)
        for selector, value, old in corpus:
            updated, returned = probe.contract(old, value, selector)
            gap = selector >> 8
            bit = 32 - gap - 1
            expected = (old & ~(1 << bit)) | ((value & 1) << bit)
            self.assertEqual(updated, expected & 0xFFFFFFFF)
            self.assertEqual(returned, value & 1)

    def test_undeclared_selector_refuses(self):
        with self.assertRaises(ValueError):
            probe.contract(0, 1, 0x0601)
        with self.assertRaises(ValueError):
            probe.contract(0, 1, 0x0102)


if __name__ == "__main__":
    unittest.main()
