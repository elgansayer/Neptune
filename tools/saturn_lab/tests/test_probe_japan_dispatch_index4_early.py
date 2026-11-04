import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_dispatch_index4_early as probe


class JapanDispatchIndex4EarlyTests(unittest.TestCase):
    def test_composed_dispatch_branch_and_helper_ranges(self):
        self.assertEqual((probe.DISPATCH, probe.DISPATCH_END), (0x060A6C94, 0x060A6CB2))
        self.assertEqual((probe.TARGET, probe.TARGET_END), (0x060A72D8, 0x060A72DC))
        self.assertEqual((probe.BRANCH, probe.BRANCH_END), (0x060A727E, 0x060A7296))
        self.assertEqual((probe.HELPER, probe.HELPER_END), (0x060A6142, 0x060A6150))
        self.assertEqual((probe.ENTRY, probe.EXPECTED), (0x060B21A8, 0x060A72D8))

    def test_corpus_covers_register_words_and_context_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.VALUES) * 2)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({r5 for r5, _ in cases}, set(probe.VALUES))
        self.assertEqual({seed for _, seed in cases}, {0, 1})

    def test_mutation_location_and_word_are_narrowly_limited(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (probe.ENTRY + 4, probe.TARGET))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (probe.ENTRY, 0x100000000))


if __name__ == '__main__':
    unittest.main()
