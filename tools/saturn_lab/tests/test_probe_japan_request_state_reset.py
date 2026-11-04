import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_request_state_reset as probe


class JapanRequestStateResetTests(unittest.TestCase):
    def test_original_range_and_record_layout(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A6D3A, 0x060A6D46))
        self.assertEqual((probe.TARGET, probe.SIZE_RECORD, probe.LIMIT), (0x06003000, 60, 16))

    def test_corpus_covers_old_state_boundaries_and_four_new_states(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 32)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({old for old, _ in cases}, set(probe.OLD_VALUES))
        self.assertEqual({new for _, new in cases}, set(probe.NEW_VALUES))

    def test_inputs_and_mutation_must_fit_declared_words_and_range(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0x100000000)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (0x060A6D46, 0x0009))


if __name__ == '__main__':
    unittest.main()
