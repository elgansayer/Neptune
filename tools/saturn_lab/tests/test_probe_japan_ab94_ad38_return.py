import unittest
import probe_japan_ab94_ad38_return as probe


class AB94AD38ReturnTests(unittest.TestCase):
    def test_code_boundaries_and_context_identity(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AB94, 0x0600AD60))
        self.assertEqual((probe.AB30, probe.AB30_END), (0x0600AB30, 0x0600AB78))
        self.assertEqual((probe.RESTORE, probe.RESTORE_END), (0x0600A186, 0x0600A1AA))
        self.assertEqual((probe.RESUME, probe.STOP), (0x0600AD38, 0x060BCC80))
        self.assertEqual((probe.CONTEXT, probe.CONTEXT_SIZE, probe.SP),
                         (0x060BDD7C, 48, 0x060BD8F4))

    def test_vbr_slots_and_alias_translation(self):
        self.assertEqual(probe.SLOTS, (0, 1))
        self.assertEqual(probe.ALIASES[0x2600A018], 0x0600A018)
        self.assertEqual(probe.ALIASES[0x2600A044], 0x0600A044)

    def test_memory_windows_are_bounded_to_declared_task_table(self):
        self.assertEqual(probe.TABLE, 0x060BCEEC)
        self.assertEqual(probe.COUNT, 18)
        self.assertEqual(probe.ROW_SIZE, 88)
        self.assertEqual(probe.TABLE_END, 0x060BD51C)
        self.assertEqual(probe.LIMIT, 1024)
        self.assertEqual(probe.STACK_WINDOWS[1], (0x060BCB6C, 0x060BCCAC))
        self.assertEqual(probe.STACK_WINDOWS[2], (0x060BE08C, 0x060BE1CC))
        self.assertEqual((probe.ACE8, probe.ACE8_END), (0x0600ACE8, 0x0600AD60))


if __name__ == "__main__":
    unittest.main()
