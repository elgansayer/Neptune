import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_context_callsite as probe


class JapanContextCallsiteTests(unittest.TestCase):
    def test_original_callsite_and_callee_ranges_are_distinct(self):
        self.assertEqual((probe.CALL, probe.BOUND), (0x0600A7D0, 0x0600A7D6))
        self.assertEqual((probe.SAVE, probe.SAVE_END), (0x0600A164, 0x0600A186))
        self.assertEqual(probe.LITERAL, 0x0600A8D4)
        self.assertEqual(probe.FRAME, 0x060BDD24)
        self.assertEqual(len(probe.PATTERNS), 31)


if __name__ == "__main__":
    unittest.main()
