import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_frame1200_sys_getuint_stub as probe


class Frame1200SysGetUintTests(unittest.TestCase):
    def test_captured_stub_and_table_index_addresses(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600077C, 0x06000784))
        self.assertEqual((probe.LITERAL, probe.TABLE, probe.INDEX),
                         (0x060007A4, 0x06000900, 75))
        self.assertEqual(probe.TABLE_ENTRY, 0x06000A2C)

    def test_corpus_contains_distinct_register_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 16)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual(set(cases), set(range(16)))

    def test_invalid_seed_and_mutation_are_rejected(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 16)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, (probe.TABLE_ENTRY + 4, probe.EXPECTED_TABLE))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, (probe.TABLE_ENTRY, 0x100000000))


if __name__ == '__main__':
    unittest.main()
