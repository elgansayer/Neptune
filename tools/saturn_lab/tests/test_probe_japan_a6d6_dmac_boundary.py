import unittest
import probe_japan_a6d6_dmac_boundary as probe


class A6D6BoundaryTests(unittest.TestCase):
    def test_register_contract_addresses(self):
        self.assertEqual(probe.DRCR, (0xFFFFFE71, 0xFFFFFE72))
        self.assertIn(0xFFFFFFB0, probe.ONCHIP_WORDS)
        self.assertNotIn(0xFFFFFFB8, probe.ONCHIP_WORDS)

    def test_bounded_original_range(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600A6D6, 0x0600A714))
        self.assertEqual(len(probe.CODE), (probe.END - probe.ENTRY) // 2)


if __name__ == "__main__":
    unittest.main()
