import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a6112_chcr_contract as probe


class JapanA6112CHCRContractTests(unittest.TestCase):
    def test_original_function_and_sh7604_register_addresses(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A6112, 0x060A6124))
        self.assertEqual(probe.CHCR, {0: 0xFFFFFF8C, 1: 0xFFFFFF9C})

    def test_corpus_covers_both_channels_and_control_bits(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 544)
        self.assertEqual(len(set(cases)), len(cases))
        self.assertEqual({channel for channel, _ in cases}, {0, 1})
        self.assertEqual(set(range(256)), {value for _, value in cases if value < 256})
        for bit in range(8, 16):
            self.assertIn((0, 1 << bit), cases)
            self.assertIn((0, (1 << bit) | 1), cases)
            self.assertIn((1, 1 << bit), cases)
            self.assertIn((1, (1 << bit) | 1), cases)

    def test_exact_original_pc_path_and_bit_contract(self):
        self.assertEqual(probe.EXPECTED_PCS,
            (0x060A6112, 0x060A6114, 0x060A6116, 0x060A6118, 0x060A611A,
             0x060A611C, 0x060A611E, 0x060A6120, 0x060A6122))
        self.assertEqual((probe.CHCR_DE, probe.CHCR_TE), (1, 2))


if __name__ == "__main__":
    unittest.main()
