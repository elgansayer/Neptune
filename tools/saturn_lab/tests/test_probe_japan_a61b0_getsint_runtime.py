import unittest

import probe_japan_a61b0_getsint_runtime as probe


class A61B0GetSintRuntimeTests(unittest.TestCase):
    def test_actual_vbr_index_and_return_boundary_are_fixed(self):
        self.assertEqual(probe.EXPECTED_VBR, 0x06000000)
        self.assertEqual(probe.VBR_ENTRY, 0x0600012C)
        self.assertEqual(probe.EXPECTED_GETSINT, 0x0600087C)
        self.assertEqual(probe.STOP, 0x060A6236)

    def test_both_runtime_stubs_are_explicitly_fenced(self):
        self.assertIn(probe.GETSINT_STUB, probe.STUB_PCS)
        self.assertIn(probe.GETUINT_STUB, probe.STUB_PCS)
        self.assertEqual(len(probe.corpus()), 8)


if __name__ == "__main__":
    unittest.main()
