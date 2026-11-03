import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_dispatch_busy_return as probe


class JapanDispatchBusyReturnTests(unittest.TestCase):
    def test_busy_branch_ranges_exclude_success_callback_path(self):
        self.assertEqual((probe.ENTRY, probe.BUSY_END, probe.CLEANUP, probe.END),
                         (0x060A8154, 0x060A8178, 0x060A820C, 0x060A8218))

    def test_corpus_covers_busy_markers_and_caller_arguments(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.BUSY_VALUES) * 16)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({row[0] for row in cases}, set(probe.BUSY_VALUES))
        self.assertEqual({row[1] for row in cases}, set(probe.R4_VALUES))
        self.assertEqual({row[2] for row in cases}, set(probe.R5_VALUES))

    def test_input_and_mutation_domains_are_fenced(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (0x060A8170, 0x10000))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (0x060A8154, 0x0009))


if __name__ == '__main__':
    unittest.main()
