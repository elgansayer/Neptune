import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_ab78_context_save as probe


class JapanAB78ContextSaveTests(unittest.TestCase):
    def test_caller_frame_stack_and_original_ranges(self):
        self.assertEqual((probe.CALL, probe.BOUND), (0x0600AB78, 0x0600AB94))
        self.assertEqual((probe.SAVE, probe.SAVE_END), (0x0600A164, 0x0600A186))
        self.assertEqual((probe.FRAME, probe.SP, probe.STACK_BYTES), (0x060BDD7C, 0x06002000, 40))
        self.assertEqual(len(probe.PATTERNS), 31)


if __name__ == "__main__":
    unittest.main()
