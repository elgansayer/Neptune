import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_context_save as probe


class JapanContextSaveTests(unittest.TestCase):
    def test_exact_frame_layout_and_r8_duplicate_are_explicit(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600A164, 0x0600A186))
        self.assertEqual(probe.CONTEXT_BYTES, 48)
        self.assertEqual(probe.LIMIT, 24)
        self.assertEqual(len(probe.PATTERNS), 31)


if __name__ == "__main__":
    unittest.main()
