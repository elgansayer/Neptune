import unittest
import probe_japan_ab94_a8e8_continuation as probe


class AB94A8E8ContinuationTests(unittest.TestCase):
    def test_original_caller_and_bounded_exits(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600A8E8, 0x0600A946))
        self.assertEqual(probe.EXIT, {0x0600A79C: "error_loop", 0x0600ACE8: "scheduler_handoff"})
        self.assertEqual(probe.LIMIT, 4096)
        self.assertIn(0x0600A8E8, probe.CODE)
        self.assertIn(probe.a80e.ENTRY, probe.CODE)
        self.assertIn(probe.a80e.CALLBACK, probe.CODE)

    def test_alias_and_stack_fences(self):
        self.assertEqual(probe.ALIASES[0x2600A030], 0x0600A030)
        self.assertEqual(probe.SP - 256, 0x06001F00)


if __name__ == "__main__":
    unittest.main()
