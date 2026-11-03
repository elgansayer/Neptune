import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a70b8_scu_handoff as probe


class JapanA70B8ScuHandoffTests(unittest.TestCase):
    def test_original_main_writer_and_handoff_ranges(self):
        self.assertEqual((probe.MAIN, probe.MAIN_END), (0x060A70B8, 0x060A7150))
        self.assertEqual((probe.WRITER, probe.WRITER_END), (0x060A6150, 0x060A61B0))
        self.assertEqual(probe.HANDOFF, 0x060A7136)

    def test_corpus_covers_pointer_classes_and_call_arguments(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.POINTERS) * 2 * 2 * 2)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({p for p, _, _, _ in cases}, set(probe.POINTERS))
        self.assertEqual({r5 for _, r5, _, _ in cases}, set(probe.R5_VALUES))
        self.assertEqual({r7 for _, _, r7, _ in cases}, set(probe.R7_VALUES))

    def test_arguments_and_mutation_are_narrowly_limited(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0x06000000, 0, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.POINTERS[0], 2, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.POINTERS[0], 0, 2, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.POINTERS[0], 0, 0, 2)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.POINTERS[0], 0, 0, 0, (0x060A61F0, 0x25FE0004))


if __name__ == '__main__':
    unittest.main()
