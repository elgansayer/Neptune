import unittest

import probe_japan_a717c_a5fc4_composed as probe


class JapanA717CA5FC4CompositionTests(unittest.TestCase):
    def test_corpus_covers_declared_product_without_duplicates(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 23328)
        self.assertEqual(len(set(cases)), len(cases))
        self.assertEqual({row[0] for row in cases}, set(probe.MODES))
        self.assertEqual({row[1] for row in cases}, set(probe.CHCR_VALUES))
        self.assertEqual({row[2] for row in cases}, set(probe.DMAOR_VALUES))
        self.assertEqual({row[8] for row in cases}, set(probe.R6_VALUES))

    def test_composed_path_contains_both_original_calls_and_returns(self):
        path = probe.expected_pcs()
        self.assertEqual(path[:len(probe.CALLER_PREFIX)], probe.CALLER_PREFIX)
        first_call = len(probe.CALLER_PREFIX)
        self.assertEqual(path[first_call:first_call + len(probe.a6112.EXPECTED_PCS)],
            probe.a6112.EXPECTED_PCS)
        self.assertIn(probe.STOP - 8, probe.CALLER_RESUME)
        self.assertEqual(path[-len(probe.a5fc4.expected_pcs(15)):],
            probe.a5fc4.expected_pcs(15))
        self.assertEqual(path[-1], probe.a5fc4.expected_pcs(15)[-1])


if __name__ == "__main__":
    unittest.main()
