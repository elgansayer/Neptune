import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_post_a5f98_continuation as probe


class A717CPostA5F98ContinuationTests(unittest.TestCase):
    def test_fences_original_instruction_body_and_return_boundary(self):
        self.assertEqual(probe.ENTRY, 0x060A7244)
        self.assertEqual(probe.CODE_END, 0x060A727E)
        self.assertEqual(probe.STOP, 0x060A71A8)
        self.assertEqual(probe.PCS[-2:], (0x060A727A, 0x060A727C))

    def test_declared_inputs_cover_global_arithmetic_and_saved_words(self):
        self.assertEqual(len(probe.R8_VALUES) * len(probe.BASES) *
            len(probe.STACK_WORDS) * len(probe.SAVED_R7), 64)
        self.assertEqual(probe.GLOBAL, 0x060FCD30)


if __name__ == "__main__":
    unittest.main()
