import unittest

from tools.saturn_lab import probe_japan_startup_helpers as probe


class JapaneseHelperContractTests(unittest.TestCase):
    def test_positive_lengths_round_up_to_words_and_nonpositive_lengths_do_nothing(self):
        self.assertEqual([probe.word_count(n) for n in (-2, -1, 0, 1, 2, 3, 4, 5)],
                         [0, 0, 0, 1, 1, 2, 2, 3])

    def test_probe_cases_stay_within_the_explicit_buffer_and_step_bounds(self):
        self.assertEqual(max(probe.LENGTHS), 129)
        self.assertEqual(probe.word_count(max(probe.LENGTHS)) * 2, 130)
        self.assertLess(probe.word_count(max(probe.LENGTHS)) * 2, probe.BUFFER_BYTES)
        self.assertLessEqual(probe.LIMIT, 512)

    def test_unsupported_length_is_rejected_before_memory_execution(self):
        with self.assertRaises(ValueError):
            probe.execute(None, b"", "fill", 130)


if __name__ == "__main__":
    unittest.main()
