import unittest
import probe_japan_a95610_copy_sizes as probe


class A95610CopySizesTests(unittest.TestCase):
    def test_short_dispatch_domains(self):
        self.assertEqual(probe.SHORT_LENGTHS, tuple(range(0, 65, 4)))
        self.assertEqual(len(probe.UNALIGNED_SHORT_LENGTHS), 48)
        self.assertNotIn(64, probe.UNALIGNED_SHORT_LENGTHS)

    def test_long_path_boundaries(self):
        self.assertEqual(probe.LONG_LENGTHS, (65, 67, 68, 88))
        self.assertEqual(tuple((n // 4) * 4 for n in probe.LONG_LENGTHS), (64, 64, 68, 88))


if __name__ == "__main__":
    unittest.main()
