import unittest

import probe_japan_a717c_tail_from_boundary as probe


class JapanA717CTailBoundaryTests(unittest.TestCase):
    def test_tail_corpus_covers_channel_status_sign_and_stack_boundaries(self):
        cases = probe.selected_inputs()
        self.assertEqual(len(cases), 1728)
        self.assertEqual(len(set(cases)), len(cases))
        self.assertEqual({row[0] for row in cases}, {0, 1})
        self.assertEqual({row[1] for row in cases}, {0, 3})
        self.assertEqual({row[2] for row in cases}, {0, 3, 15})
        self.assertEqual({row[8] for row in cases}, set(probe.R6_VALUES))

    def test_input_key_uses_full_boundary_identity(self):
        source = (1, 3, 15, 0x06009004, 0x55667788, 0xF1234567, 15, 1, 0xFFFFFFFF)
        row = {"inputs": {"mode":source[0], "chcr_before":source[1],
            "dmaor_before":source[2], "base":source[3], "r7":source[4],
            "stack_top":source[5], "priority":source[6], "seed":source[7], "r6":source[8]}}
        self.assertEqual(probe.input_key(row), source)


if __name__ == "__main__":
    unittest.main()
