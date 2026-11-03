import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_record_caller as probe


class JapaneseRecordCallerTests(unittest.TestCase):
    def test_exact_original_caller_and_callee_ranges(self):
        self.assertEqual(probe.CALLER_END - probe.CALLER_ENTRY, 16)
        self.assertEqual(probe.CALLEE_END - probe.CALLEE_ENTRY, 18)
        self.assertEqual(probe.CALLER_TARGET_LITERAL, 0x0600CCA4)
        self.assertEqual(probe.CALLBACK_LITERAL, 0x0600CCA8)

    def test_all_eighteen_record_indices_fit_declared_single_record_mapping(self):
        self.assertEqual(probe.INDICES, tuple(range(18)))
        self.assertEqual(probe.record_address(17) + probe.RECORD_SIZE,
                         probe.RECORD_BASE + 18 * probe.RECORD_STRIDE)
        self.assertEqual(probe.RECORD_CALLBACK_OFFSET + 4, 16)

    def test_mutation_sites_are_call_argument_callee_and_rts_delay_slot(self):
        self.assertEqual(probe.CALLER_ENTRY + 4, 0x0600CC60)
        self.assertEqual(probe.CALLEE_ENTRY, 0x0600AEF2)
        self.assertEqual(probe.CALLER_ENTRY + 14, 0x0600CC6A)
        self.assertLessEqual(probe.MAX_STEPS, 40)

    def test_unsupported_record_index_rejected(self):
        with self.assertRaises(ValueError):
            probe.execute(None, None, 18)


if __name__ == "__main__":
    unittest.main()
