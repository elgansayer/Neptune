import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_resident_module import matching_ranges


class MatchingRangesTests(unittest.TestCase):
    def test_reports_only_contiguous_exact_source_ranges(self):
        source = bytes(range(32))
        ram = bytearray(0x100000)
        ram[0x100:0x108] = source[:8]
        ram[0x108:0x110] = source[8:16]
        ram[0x111:0x120] = source[17:]
        self.assertEqual(matching_ranges(source, bytes(ram), 0x100, 8),
                         [(0, 16), (17, 32)])

    def test_validates_mapping_and_threshold_bounds(self):
        source = b"a" * 16
        ram = bytes(0x100000)
        with self.assertRaises(ValueError):
            matching_ranges(source, ram, -1)
        with self.assertRaises(ValueError):
            matching_ranges(source, ram, 0x100000 - 8)
        with self.assertRaises(ValueError):
            matching_ranges(source, ram, 0, 0)


if __name__ == "__main__":
    unittest.main()
