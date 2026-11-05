"""Cross-module SH-2 function matching: synthetic modules only, no game bytes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sh2_function_match as fm  # noqa: E402


def words(*values):
    return b"".join(v.to_bytes(2, "big") for v in values)


# The same 12-instruction function with different branch/literal displacements,
# as if linked at two addresses, plus a variant with one different opcode.
BODY_A = words(0x2FE6, 0x4F22, 0xD103, 0x410B, 0x0009, 0x8B02, 0xB010, 0x0009,
               0x4F26, 0x000B, 0x6EF6, 0x0009)
BODY_B = words(0x2FE6, 0x4F22, 0xD107, 0x410B, 0x0009, 0x8B05, 0xB3F0, 0x0009,
               0x4F26, 0x000B, 0x6EF6, 0x0009)
BODY_C = words(0x2FE6, 0x4F22, 0xD103, 0x410B, 0x0009, 0x8B02, 0xB010, 0x0009,
               0x4F26, 0x000B, 0x6EF6, 0x6013)  # last word differs


def module(body, base, pad=0):
    data = bytes(pad) + body
    code = set(range(base + pad, base + pad + len(body), 2))
    return data, code, [base + pad]


class FunctionMatchTests(unittest.TestCase):
    def test_masking_clears_only_pc_relative_displacements(self):
        self.assertEqual(fm.mask(0xB123), 0xB000)
        self.assertEqual(fm.mask(0x8D7F), 0x8D00)
        self.assertEqual(fm.mask(0xD31F), 0xD300)
        self.assertEqual(fm.mask(0xC712), 0xC700)
        self.assertEqual(fm.mask(0x6EF6), 0x6EF6)
        self.assertEqual(fm.mask(0x8812), 0x8812)  # cmp/eq #imm is not PC-relative

    def test_relocated_copies_match_and_changed_code_does_not(self):
        mods = {}
        for name, body, base in (("a", BODY_A, 0x06004000), ("b", BODY_B, 0x00200000), ("c", BODY_C, 0x06010000)):
            data, code, entries = module(body, base, pad=8)
            mods[name] = fm.bodies(data, base, code, entries)
        index, pairs = fm.match(mods)
        self.assertEqual(pairs[("a", "b")], 1)
        self.assertEqual(pairs[("a", "c")], 0)
        self.assertEqual(pairs[("b", "c")], 0)

    def test_short_bodies_are_skipped(self):
        data, code, entries = module(BODY_A[:20], 0x1000)
        self.assertEqual(fm.bodies(data, 0x1000, code, entries), {})
        self.assertEqual(len(fm.bodies(data, 0x1000, code, entries, minimum=10)), 1)


if __name__ == "__main__":
    unittest.main()
