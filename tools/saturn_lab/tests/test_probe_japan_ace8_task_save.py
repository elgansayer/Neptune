import unittest
import probe_japan_ace8_task_save as probe


class ACE8TaskSaveTests(unittest.TestCase):
    def test_original_ranges_and_stopping_boundary(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600ACE8, 0x0600AD60))
        self.assertEqual((probe.SAVE, probe.SAVE_END, probe.RESTORE_EDGE),
                         (0x0600A164, 0x0600A186, 0x0600A186))
        self.assertNotIn(probe.RESTORE_EDGE, probe.CODE)

    def test_captured_restore_target_is_outside_executed_range(self):
        self.assertEqual(probe.RESTORE_CONTEXT, 0x060BDD7C)
        self.assertEqual(probe.RESTORE_CONTEXT_BYTES, 48)
        self.assertEqual(probe.RESUME_PC, 0x0600AB94)
        self.assertEqual(probe.RESTORE_END, 0x0600A1AA)

    def test_vbr_slots_select_distinct_rows(self):
        self.assertEqual(probe.CASES, ((0, 3), (1, 12)))
        self.assertEqual(probe.ALIASES[0x2600A020], 0x0600A020)
        self.assertEqual(probe.ALIASES[0x2600A024], 0x0600A024)
        self.assertEqual(probe.ALIASES[0x2600A028], 0x0600A028)

    def test_context_model_duplicates_r8_and_preserves_pr_mac(self):
        registers = [0x1000 + i for i in range(16)]
        frame, values = probe.expected_frame(registers, 0x12345678, 0xABCDEF01, 0x0600AD36)
        self.assertEqual(frame[0:4], frame[4:8])
        self.assertEqual(int.from_bytes(frame[36:40], "big"), 0x0600AD36)
        self.assertEqual(int.from_bytes(frame[40:44], "big"), 0x12345678)
        self.assertEqual(int.from_bytes(frame[44:48], "big"), 0xABCDEF01)
        self.assertEqual(values[32], registers[15])


if __name__ == "__main__":
    unittest.main()
