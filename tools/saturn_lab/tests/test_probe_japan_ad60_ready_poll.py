import unittest
import probe_japan_ad60_ready_poll as probe


class AD60ReadyPollTests(unittest.TestCase):
    def test_original_range_and_branch_edges(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x0600AD60, 0x0600AD7A))
        self.assertEqual((probe.ACE8, probe.LITERAL, probe.ALIAS),
                         (0x0600ACE8, 0x0600ADAC, 0x2600A028))

    def test_slot_ready_seed_corpus_and_budget(self):
        self.assertEqual(probe.SLOTS, (0, 1))
        self.assertEqual(probe.READY_VALUES, (0, 1))
        self.assertEqual(probe.SEEDS, (0, 1))
        self.assertEqual(probe.LIMIT, 64)


if __name__ == "__main__":
    unittest.main()
