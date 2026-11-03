import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_kernel_rng as probe


class KernelRngFormulaTests(unittest.TestCase):
    def test_bound_contract_for_all_byte_values_at_small_and_edge_bounds(self):
        for value in range(256):
            for bound in (0, 1, 2, 10, 255, 256):
                with self.subTest(value=value, bound=bound):
                    self.assertEqual(probe.formula(value, bound), (value * bound >> 8) & 0xFF)

    def test_unsigned_multiply_then_shift_and_truncate(self):
        self.assertEqual(probe.formula(0x123456E8, 10), 9)
        self.assertEqual(probe.formula(0x74E8, 255), 231)
        self.assertEqual(probe.formula(0x74E8, 256), 232)

    def test_invalid_inputs_reject(self):
        for word, bound in ((-1, 1), (0x100000000, 1), (0, -1), (0, 0x100000000), (True, 1)):
            with self.subTest(word=word, bound=bound), self.assertRaises(ValueError):
                probe.formula(word, bound)


if __name__ == "__main__":
    unittest.main()
