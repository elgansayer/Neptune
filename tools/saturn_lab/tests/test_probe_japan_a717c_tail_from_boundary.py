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

    def test_expected_path_includes_purge_call_helper_and_outer_return(self):
        for r8 in probe.R6_VALUES:
            for stack_top in probe.boundary_probe.STACK_TOPS:
                path = probe.expected_path(r8, stack_top)
                self.assertIn(probe.purge.ENTRY, path)
                for segment in (probe.CALL_A5F98_PCS, probe.purge.HELPER_PCS):
                    self.assertTrue(any(path[i:i + len(segment)] == segment
                        for i in range(len(path) - len(segment) + 1)))
                self.assertEqual(path[-len(probe.EPILOGUE_PCS):], probe.EPILOGUE_PCS)
                self.assertEqual(path[-1], probe.EPILOGUE_PCS[-1])


if __name__ == "__main__":
    unittest.main()
