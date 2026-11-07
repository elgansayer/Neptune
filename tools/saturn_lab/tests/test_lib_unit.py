"""Library-unit extraction and masked matching: synthetic assembly and bytes only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lib_unit  # noqa: E402

# Synthetic cc1-style output: a constant, a static helper, a global caller, BSS.
CC1 = """\t.file\t"x.c"
\t.data
gcc2_compiled.:
___gnu_compiled_c:
\t.lcomm _state.2,16
\t.text
\t.align 2
LC0:
\t.long\t0
\t.align 2
_helper:
\tmov.l\tL2,r1
\tjmp\t@r1
\tnop
\t.align 2
L2:
\t.long\t_state.2
\t.align 2
\t.global\t_caller
_caller:
\tmov.l\tL5,r0
\tbt.s\tL4
\tnop
L4:
\trts
\tnop
\t.align 2
L5:
\t.long\t_helper
"""


class ExtractTests(unittest.TestCase):
    def lines(self):
        return lib_unit.text_lines(CC1.splitlines())

    def test_units_split_at_symbols_and_constants_not_at_internal_labels(self):
        names = [n for _, n in lib_unit.top_labels(self.lines())]
        self.assertEqual(names, ["LC0", "_helper", "_caller"])

    def test_chunk_keeps_the_literal_pool_and_leaves_the_next_align_to_the_next_unit(self):
        unit = lib_unit.chunk(self.lines(), "_helper")
        self.assertEqual(unit[:2], ["\t.align 2", "_helper:"])
        self.assertIn("\t.long\t_state.2", unit)
        self.assertNotIn("_caller:", unit)

    def test_rewrite_localises_labels_and_resolves_external_references(self):
        unit = lib_unit.chunk(self.lines(), "_caller")
        out = lib_unit.rewrite(unit, "06001000", {"_helper": 0x06000F00})
        self.assertIn(".L06001000_caller:", out)
        self.assertIn("\tmov.l\t.L06001000_L5,r0", out)
        self.assertIn("\tbt.s\t.L06001000_L4", out)
        self.assertIn("\t.long\t0x06000F00", out)
        self.assertIn("\t.align 2,0", out)
        self.assertFalse(any(".global" in l for l in out))

    def test_unresolved_references_are_reported_and_extra_ones_rejected(self):
        unit = lib_unit.chunk(self.lines(), "_helper")
        self.assertEqual(lib_unit.unresolved(unit), ["_state.2"])
        with self.assertRaises(lib_unit.UnresolvedReference):
            lib_unit.rewrite(unit, "X", {})
        with self.assertRaises(ValueError):
            lib_unit.rewrite(unit, "X", {"_state.2": 1, "_other": 2})

    def test_semicolon_separated_statements_are_split(self):
        out = lib_unit.rewrite(["_f:", "\trotcl\tr4 ; div1\tr5,r0"], "T", {})
        self.assertEqual(out, [".LT_f:", "\trotcl\tr4", "\tdiv1\tr5,r0"])


def body(callee: int) -> bytes:
    """A synthetic 16-byte routine whose last word is a callee address."""
    return bytes.fromhex("d1012b0b00090009") + bytes(4) + callee.to_bytes(4, "big")


class MatchTests(unittest.TestCase):
    def test_masked_search_finds_the_unit_and_reads_its_reference(self):
        unit = body(0)
        blob = bytes(6) + body(0x06004000) + bytes(10)
        hits = lib_unit.find(unit, {12: "_callee"}, blob, 0x06000000)
        self.assertEqual(hits, [(0x06000006, {"_callee": 0x06004000})])

    def test_a_changed_unmasked_byte_is_not_a_match(self):
        unit = body(0)
        blob = bytearray(body(0x06004000))
        blob[3] ^= 1
        self.assertEqual(lib_unit.find(unit, {12: "_callee"}, bytes(blob), 0), [])

    def test_identical_wrappers_are_told_apart_by_their_references(self):
        # two places hold the same wrapper bytes; only one calls the _parts actually placed
        parts = lib_unit.Unit("o", "_parts", 80, [(0x980, {})], is_global=False)
        add = lib_unit.Unit("o", "_add", 16, [(0x100, {"_parts": 0x900}), (0x200, {"_parts": 0x980})])
        placed = {u.symbol: a for u, a, _ in lib_unit.resolve([parts, add])}
        self.assertEqual(placed, {"_parts": 0x980, "_add": 0x200})

    def test_a_unit_whose_places_are_all_inconsistent_stays_out(self):
        parts = lib_unit.Unit("o", "_parts", 80, [(0x980, {})], is_global=False)
        add = lib_unit.Unit("o", "_add", 16, [(0x100, {"_parts": 0x900})])
        placed = [u.symbol for u, _, _ in lib_unit.resolve([parts, add])]
        self.assertEqual(placed, ["_parts"])

    def test_object_order_places_identical_bodies(self):
        same = [(0x100, {}), (0x140, {}), (0x180, {})]
        units = [lib_unit.Unit("o", "_first", 70, [(0x0C0, {})]),
                 lib_unit.Unit("o", "_eq", 64, list(same)),
                 lib_unit.Unit("o", "_ne", 64, list(same))]
        placed = [(u.symbol, a) for u, a, _ in lib_unit.resolve(units)]
        self.assertEqual(placed, [("_first", 0x0C0), ("_eq", 0x100), ("_ne", 0x140)])

    def test_an_address_has_one_name_and_larger_units_go_first(self):
        # a 24-byte wrapper says its callee at 0x500 is _locale_r; the 52-byte unit really
        # at 0x500 is _rand_r.  Resolved larger-first, the look-alike is refused.
        rand_r = lib_unit.Unit("rand_r.o", "_rand_r", 52, [(0x500, {})])
        wrapper = lib_unit.Unit("locale.o", "_localeconv", 24, [(0x540, {"_locale_r": 0x500})])
        placed = [u.symbol for u, _, _ in lib_unit.resolve([wrapper, rand_r])]
        self.assertEqual(placed, ["_rand_r"])

    def test_small_wrappers_need_a_confirmed_reference(self):
        big = lib_unit.Unit("o", "_big", 200, [])
        ok = lib_unit.Unit("o", "_w1", 24, [])
        lone = lib_unit.Unit("p", "_w2", 24, [])
        placed = [(big, 0x100, {"_core": 0x500}), (ok, 0x300, {"_core": 0x500}), (lone, 0x400, {"_x": 0x777})]
        kept = [u.symbol for u, _, _ in lib_unit.confirm(placed)]
        self.assertEqual(kept, ["_big", "_w1"])


if __name__ == "__main__":
    unittest.main()
