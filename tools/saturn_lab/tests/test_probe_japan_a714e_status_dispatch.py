import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a714e_status_dispatch as probe


class JapanA714EStatusDispatchTests(unittest.TestCase):
    def test_composed_original_ranges_and_snapshot_literals(self):
        self.assertEqual((probe.A714E, probe.A714E_END), (0x060A714E, 0x060A7178))
        self.assertEqual((probe.A6280, probe.A6280_END), (0x060A6280, 0x060A62B4))
        self.assertEqual((probe.FUNCTION_LITERAL, probe.GLOBAL_LITERAL), (0x060A7210, 0x060A7200))

    def test_domain_covers_priority_seed_and_branch_values(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 128)
        self.assertEqual(len(set(cases)), 128)
        self.assertEqual({flag for flag, _, _ in cases}, {0, 1, 2, 255})
        self.assertEqual({priority for _, priority, _ in cases}, set(range(16)))
        self.assertEqual({seed for _, _, seed in cases}, {0, 1})

    def test_pc_fence_only_allows_the_two_original_functions(self):
        self.assertTrue(probe.allowed_pc(probe.A6280))
        self.assertTrue(probe.allowed_pc(probe.A714E))
        self.assertTrue(probe.allowed_pc(0x060A7176))
        self.assertFalse(probe.allowed_pc(0x060A7178))
        self.assertFalse(probe.allowed_pc(0x060A62B4))


if __name__ == "__main__":
    unittest.main()
