import unittest

import probe_japan_a61b0_getuint_callbacks as probe


class A61B0GetUintCallbackTests(unittest.TestCase):
    def test_three_installed_callbacks_have_distinct_service_ranges(self):
        self.assertEqual([x[0] for x in probe.FUNCTIONS], [0x060A62D8, 0x060A6348, 0x060A63B8])
        self.assertEqual(probe.SERVICES, (75, 74, 73))
        self.assertEqual(len(probe.corpus()), 72)

    def test_corpus_separates_captured_inputs_from_zero_and_nonzero_controls(self):
        names = {row[3] for row in probe.corpus()}
        self.assertEqual(names, {"captured-frame1200", "constructed-zero-defaults", "constructed-nonzero-values"})
        captured = [row for row in probe.corpus() if row[3] == "captured-frame1200"]
        self.assertEqual(len(captured), 24)

    def test_setter_stub_pc_fences_exclude_literals_and_unrelated_code(self):
        self.assertIn(0x06000794, probe.STUB_PCS)
        self.assertIn(0x06000784, probe.STUB_PCS)
        self.assertNotIn(0x060007A4, probe.STUB_PCS)
        self.assertNotIn(0x06000702, probe.STUB_PCS)


if __name__ == "__main__":
    unittest.main()
