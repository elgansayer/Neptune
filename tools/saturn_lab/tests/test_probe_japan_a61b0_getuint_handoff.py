import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_a61b0_getuint_handoff as probe


class JapanA61B0GetUintHandoffTests(unittest.TestCase):
    def test_original_prefix_and_bios_call_boundary(self):
        self.assertEqual((probe.ENTRY, probe.HANDOFF), (0x060A61B0, 0x060A6220))
        self.assertEqual((probe.BIOS_SLOT, probe.GETUINT_PTR), (0x06000304, 0x06005000))

    def test_corpus_covers_interrupt_priority_and_seed(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.SR_VALUES) * len(probe.SEEDS))
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({sr for sr, _ in cases}, set(probe.SR_VALUES))
        self.assertEqual({seed for _, seed in cases}, set(probe.SEEDS))

    def test_invalid_state_and_mutation_are_rejected(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0x123, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.SR_VALUES[0], 2)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, probe.SR_VALUES[0], 0, (probe.BIOS_SLOT, probe.GETUINT_PTR))


if __name__ == '__main__':
    unittest.main()
