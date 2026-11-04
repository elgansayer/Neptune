import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_null_dispatch_return as probe


class JapanNullDispatchReturnTests(unittest.TestCase):
    def test_branch_fences_exclude_nonnull_path(self):
        self.assertEqual((probe.ENTRY, probe.NULL_END, probe.EPILOGUE, probe.END),
                         (0x060A70B8, 0x060A70C6, 0x060A7144, 0x060A714E))

    def test_corpus_covers_r0_boundaries_and_stack_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.VALUES) * 2)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({r0 for r0, _ in cases}, set(probe.VALUES))
        self.assertEqual({seed for _, seed in cases}, {0, 1})

    def test_input_and_mutation_are_strictly_limited(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 2)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (0x060A70C6, 0x8B3E))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (0x060A70C4, 0x10000))


if __name__ == '__main__':
    unittest.main()
