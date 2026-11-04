import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a72e0_caller_epilogue as probe


class A72E0CallerEpilogueTests(unittest.TestCase):
    def test_original_instruction_fence_and_delay_slot(self):
        self.assertEqual(probe.ENTRY, 0x060A72FE)
        self.assertEqual(probe.CODE_END, 0x060A7306)
        self.assertEqual(probe.PCS, (0x060A72FE, 0x060A7300, 0x060A7302, 0x060A7304))
        self.assertEqual(probe.STOP, 0x060A73B8)

    def test_staged_stack_geometry_matches_add24_then_pop_pr(self):
        self.assertEqual(probe.STACK + 24, 0x06007F9C)
        self.assertEqual(probe.STACK + 28, probe.FINAL_SP)
        self.assertEqual(probe.SAVED_PR, 0x060A73B8)


if __name__ == "__main__":
    unittest.main()
