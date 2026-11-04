import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a717c_caller_zero_divisor as probe


class JapanA717CCallerZeroDivisorTests(unittest.TestCase):
    def test_original_caller_and_callee_addresses(self):
        self.assertEqual((probe.CALLER, probe.CALLEE, probe.END),
            (0x060A72B0, 0x060A717C, 0x060A72D8))

    def test_corpus_covers_stack_argument_and_caller_registers(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 4096)
        self.assertEqual(len(set(cases)), len(cases))
        self.assertEqual({row[0] for row in cases}, {0, 1, 2, 3})
        self.assertEqual({row[1] for row in cases}, set(probe.CALLER_R4_VALUES))
        self.assertEqual({row[6] for row in cases}, set(range(16)))

    def test_composed_pc_path_calls_original_body_and_returns(self):
        self.assertEqual(len(probe.EXPECTED_PCS), 69)
        self.assertEqual(probe.EXPECTED_PCS[14:16], (0x060A72CC, 0x060A72CE))
        self.assertEqual(probe.EXPECTED_PCS[16:65], probe.body.EXPECTED_PCS)
        self.assertEqual(probe.EXPECTED_PCS[-4:], (0x060A72D0, 0x060A72D2, 0x060A72D4, 0x060A72D6))
        self.assertNotIn(0x060A71A6, probe.EXPECTED_PCS)


if __name__ == "__main__":
    unittest.main()
