import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_context_restore as probe


class JapaneseContextRestoreTests(unittest.TestCase):
    def test_context_is_exactly_twelve_words_with_pr_sentinel(self):
        words = probe.context_words(5)
        self.assertEqual(len(words), 12)
        self.assertEqual(words[9], probe.RETURN_SENTINEL)
        self.assertEqual(probe.CONTEXT_BYTES, len(words) * 4)

    def test_register_fields_are_distinct_and_cover_saved_registers(self):
        self.assertEqual(set(probe.SAVED_GPR_OFFSETS), set(range(8, 16)))
        self.assertEqual(len(set(probe.context_words(3))), 12)
        self.assertEqual(probe.SPECIAL_OFFSETS, {"pr": 36, "mach": 40, "macl": 44})


if __name__ == "__main__":
    unittest.main()
