import unittest

import probe_japan_a61b0_getuint_runtime as probe


class A61B0GetUintRuntimeTests(unittest.TestCase):
    def test_capture_table_index_and_stop_are_bound_to_original_path(self):
        self.assertEqual(probe.TABLE_WORD, 0x06000A2C)
        self.assertEqual(probe.STUB, 0x0600077C)
        self.assertEqual(probe.STUB_PCS,
            (0x0600077C, 0x0600077E, 0x06000780, 0x06000782))
        self.assertEqual(probe.STOP, 0x060A6224)

    def test_corpus_is_the_declared_sr_and_seed_product(self):
        rows = probe.corpus()
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(set(rows)), 8)
        self.assertEqual({sr for sr, _ in rows}, set(probe.SR_VALUES))
        self.assertEqual({seed for _, seed in rows}, set(probe.SEEDS))


if __name__ == "__main__":
    unittest.main()
