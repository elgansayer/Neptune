import unittest

import probe_japan_a61b0_setters_scu as probe


class A61B0SettersScuTests(unittest.TestCase):
    def test_corpus_covers_all_three_service_indices(self):
        rows = probe.corpus()
        self.assertEqual(len(rows), 12)
        self.assertEqual({row[0] for row in rows}, {0, 1, 2})
        self.assertEqual({probe.SERVICES[row[0]] for row in rows}, {73, 74, 75})
        self.assertEqual(len(rows), len(set(rows)))

    def test_original_tail_and_captured_setter_stub_fences(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A6236, 0x060A6280))
        self.assertEqual(probe.STUBS[0], 0x06000784)
        self.assertEqual(probe.STUBS[-1], 0x060007A0)
        self.assertNotIn(0x060007A4, probe.STUBS)

    def test_scu_events_are_per_channel_and_keep_d0en_value(self):
        addresses = [probe.SCU_BASE + index * 32 for index in probe.INDICES]
        self.assertEqual(addresses, [0x25FE0010, 0x25FE0030, 0x25FE0050])
        self.assertEqual(probe.SCU_VALUE, 0x0101)


if __name__ == "__main__":
    unittest.main()
