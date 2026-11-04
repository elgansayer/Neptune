import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_request_initializer as probe


class JapanRequestInitializerTests(unittest.TestCase):
    def test_original_composed_range_and_record_layout(self):
        self.assertEqual((probe.ENTRY, probe.CALLER_END, probe.END),
                         (0x060A6D04, 0x060A6D3A, 0x060A6D4A))
        self.assertEqual((probe.TARGET, probe.RECORD_SIZE, probe.LIMIT),
                         (0x06003000, 60, 64))

    def test_corpus_covers_old_state_boundaries_and_record_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 32)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({old for old, _ in cases}, set(probe.OLD_VALUES))
        self.assertEqual({seed for _, seed in cases}, set(probe.RECORD_SEEDS))

    def test_declared_domain_refuses_before_execution(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, -1, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 4)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (0x060A6D4A, 0x0009))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, (0x060A6D3C, 0x10000))


if __name__ == '__main__':
    unittest.main()
