import unittest

import probe_japan_vbr_context_save as probe


class JapanVBRContextSaveTests(unittest.TestCase):
    def test_original_call_and_mapping_bounds(self):
        self.assertEqual((probe.CALL, probe.BOUND), (0x0600AD26, 0x0600AD38))
        self.assertEqual((probe.SAVE, probe.SAVE_END), (0x0600A164, 0x0600A186))
        self.assertEqual(probe.TARGET_LITERAL, 0x0600AD8C)
        self.assertEqual(probe.TABLE_ALIAS, 0x2600A020)
        self.assertEqual(probe.FRAMES, (0x060BDD24, 0x060BDD7C))
        self.assertEqual(probe.LIMIT, 32)
        self.assertEqual(len(probe.PATTERNS), 31)


if __name__ == "__main__":
    unittest.main()
