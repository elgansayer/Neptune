import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a61b0_snapshot_services as probe


class JapanA61B0SnapshotServicesTests(unittest.TestCase):
    def test_original_and_snapshot_ranges_are_explicit(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A61B0, 0x060A6280))
        self.assertEqual(probe.R4_VALUES, (0, 1, 2))
        self.assertEqual(probe.SEEDS, (0, 1))
        self.assertEqual(probe.BIOS_SHA, "dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac")

    def test_execution_pc_fence_excludes_literal_pools(self):
        self.assertTrue(probe.allowed_pc(probe.ENTRY))
        self.assertFalse(probe.allowed_pc(0x060A61E8))
        self.assertFalse(probe.allowed_pc(0x060A62B4))
        self.assertTrue(probe.allowed_pc(0x0600077C))
        self.assertFalse(probe.allowed_pc(0x060007A4))

    def test_case_domain_is_unique_and_complete(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), 6)
        self.assertEqual(len(set(cases)), 6)
        self.assertEqual({index for index, _ in cases}, {0, 1, 2})
        self.assertEqual({seed for _, seed in cases}, {0, 1})


if __name__ == "__main__":
    unittest.main()
