import unittest

import probe_japan_ad38_restore_continuation as probe


class JapanAD38RestoreContinuationTests(unittest.TestCase):
    def test_original_ranges_literals_and_limits(self):
        self.assertEqual((probe.CALL, probe.BOUND), (0x0600AD38, 0x0600AD60))
        self.assertEqual((probe.RESTORE, probe.RESTORE_END), (0x0600A186, 0x0600A1AA))
        self.assertEqual(probe.FRAME, 0x060BDD7C)
        self.assertEqual(probe.READY_ALIAS, 0x2600A028)
        self.assertEqual((probe.LIT_FRAME, probe.LIT_RESTORE, probe.LIT_READY),
                         (0x0600AD88, 0x0600ADA8, 0x0600ADAC))
        self.assertEqual(probe.LIMIT, 48)


if __name__ == "__main__":
    unittest.main()
