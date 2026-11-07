"""Whole-disc code census screens: synthetic byte patterns only, no game bytes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import disc_code_census as census  # noqa: E402


def sh2_function(pad: int = 0) -> bytes:
    """A tiny SH-2 epilogue: lds.l @r15+,pr; mov.l @r15+,r14; rts; nop."""
    return bytes(pad) + bytes.fromhex("4f26 6ef6 000b 0009".replace(" ", ""))


class CensusScreenTests(unittest.TestCase):
    def test_aligned_sh2_epilogues_give_a_signal_and_a_range(self):
        data = b"".join(sh2_function(8) for _ in range(8)) + bytes(64)
        row = census.screen(data)
        self.assertTrue(row["sh2"]["signal"])
        self.assertEqual(row["sh2"]["epilogue_aligned"], 8)
        self.assertEqual(row["sh2"]["epilogue_odd"], 0)
        self.assertEqual(row["sh2"]["ranges"][0]["start"], 0)

    def test_the_same_bytes_shifted_by_one_are_rejected_by_the_odd_alignment_control(self):
        data = b"\x00" + b"".join(sh2_function(8) for _ in range(8)) + bytes(63)
        row = census.screen(data)
        self.assertEqual(row["sh2"]["epilogue_aligned"], 0)
        self.assertEqual(row["sh2"]["epilogue_odd"], 8)
        self.assertFalse(row["sh2"]["signal"])
        self.assertEqual(row["sh2"]["ranges"], [])

    def test_68000_rts_inside_ascii_text_is_not_code(self):
        text = b"Number of players: Num Nu" * 4  # 'Nu' is 0x4E75, the 68000 rts opcode
        padded = b"[" * 12 + text + b"]" * 12
        self.assertEqual(census.m68k_rts(padded), [])
        self.assertEqual(census.m68k_rts(b"Nu" + bytes(30)), [0])  # no full text window: counted
        code = bytes(16) + bytes.fromhex("4cdf7fff4e75") + bytes(16)  # movem.l (sp)+ then rts
        self.assertEqual(census.m68k_epilogues(code), [20])

    def test_signal_needs_a_minimum_and_a_ratio_over_odd_hits(self):
        self.assertFalse(census.signal(3, 0))
        self.assertTrue(census.signal(4, 0))
        self.assertFalse(census.signal(8, 2))  # 8 < 4 * (2 + 1)
        self.assertTrue(census.signal(12, 2))

    def test_ranges_merge_adjacent_hit_blocks_and_drop_isolated_hits(self):
        block = census.BLOCK
        hits = [10, 20, block + 4, block + 8, 3 * block + 2, 3 * block + 6, 9 * block]
        rows = census.ranges(hits, 10 * block)
        self.assertEqual(rows, [{"start": 0, "end": 2 * block, "hits": 4},
                                {"start": 3 * block, "end": 4 * block, "hits": 2}])

    def test_constant_fill_and_profile(self):
        row = census.screen(bytes(4096))
        self.assertTrue(row["constant_fill"])
        self.assertEqual(row["zero_fraction"], 1.0)
        self.assertFalse(row["sh2"]["signal"])
        self.assertFalse(row["m68000"]["signal"])


if __name__ == "__main__":
    unittest.main()
