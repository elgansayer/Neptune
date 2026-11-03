import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_descriptor_caller as probe
import probe_japan_descriptor_update as leaf


class JapanDescriptorCallerTests(unittest.TestCase):
    def test_original_ranges_and_caller_budget(self):
        self.assertEqual((probe.CALLER, probe.CALLER_END), (0x0600CDA0, 0x0600CDC4))
        self.assertEqual((leaf.ENTRY, leaf.END), (0x0600CD74, 0x0600CDA0))
        self.assertEqual((leaf.N, probe.LIMIT), (12, 512))

    def test_caller_types_include_accepted_and_unsigned_rejections(self):
        self.assertEqual(probe.case_values(), (0, 1, 2, 3, 4, 0x100, 0xFFFF, 0x80000000))
        self.assertTrue(all(value < 4 for value in probe.case_values()[:4]))
        self.assertTrue(all(value >= 4 for value in probe.case_values()[4:]))

    def test_caller_argument_rejects_non_word_values(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0x100000000)


if __name__ == '__main__':
    unittest.main()
