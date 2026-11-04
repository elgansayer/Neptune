import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_japan_scu_command_writer as probe


class JapanScuCommandWriterTests(unittest.TestCase):
    def test_original_entry_and_scu_literal_addresses(self):
        self.assertEqual((probe.ENTRY, probe.END), (0x060A6150, 0x060A61B0))
        self.assertEqual((probe.SCU_D0R, probe.SCU_D0W, probe.SCU_D0C),
                         (0x25FE0000, 0x25FE0004, 0x25FE0008))

    def test_corpus_covers_descriptor_flags_channels_and_seeds(self):
        cases = probe.corpus()
        self.assertEqual(len(cases), len(probe.FLAGS) * len(probe.CHANNELS) * len(probe.SEEDS))
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual({flags for flags, _, _ in cases}, set(probe.FLAGS))
        self.assertEqual({channel for _, channel, _ in cases}, set(probe.CHANNELS))
        self.assertEqual({seed for _, _, seed in cases}, set(probe.SEEDS))

    def test_invalid_flags_channel_and_seed_are_rejected(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 4, 0, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 2, 0)
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 0, 0, 2)

    def test_mutation_only_accepts_declared_literal_and_word(self):
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (probe.LIT_D0W, probe.SCU_D0W))
        with self.assertRaises(ValueError):
            probe.execute(b'', None, 1, 0, 0, (probe.LIT_D0R, 0x100000000))


if __name__ == '__main__':
    unittest.main()
