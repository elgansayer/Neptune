import unittest
import probe_japan_a208_ae3a_scheduler_edge as probe


class A208AE3ASchedulerEdgeTests(unittest.TestCase):
    def test_original_callsite_and_composed_scheduler_ranges(self):
        self.assertEqual((probe.CALL, probe.CALL_END), (0x0600A208, 0x0600A20E))
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AE3A, 0x0600AE96))
        self.assertEqual(probe.ACE8, 0x0600ACE8)
        self.assertEqual((probe.ACE8_END, probe.SAVE, probe.SAVE_END),
                         (0x0600AD60, 0x0600A164, 0x0600A186))
        self.assertEqual((probe.RESTORE, probe.RESTORE_END, probe.RESUME_PC),
                         (0x0600A186, 0x0600A1AA, 0x0600AB94))

    def test_captured_task_cursor_and_vbr_selector(self):
        self.assertEqual(probe.TASK_CURSOR, 0x060BCC80)
        self.assertEqual(probe.SELECTOR_ALIAS, 0x2600A020)
        self.assertEqual(probe.TABLE, 0x060BCEEC)
        self.assertEqual(probe.ROW_SIZE, 88)


if __name__ == "__main__":
    unittest.main()
