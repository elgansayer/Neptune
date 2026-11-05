"""Owned synthetic tests for the static/natural 68000 function inventory join.

The program below is hand-assembled for these tests; it is not game code.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import m68k_function_inventory as inv  # noqa: E402

PROGRAM = {
    0x400: '4EB900000410',  # jsr $410.l
    0x406: '61000010',      # bsr.w $418
    0x40A: '60FE',          # bra.s $40A
    0x40C: '4E714E71',      # unreached words (not decoded as code below)
    0x410: '4E71',          # nop
    0x412: '6702',          # beq.s $416
    0x414: '4E71',          # nop
    0x416: '4E75',          # rts
    0x418: '4ED0',          # jmp (a0): statically unresolved
    0x41A: '4E73',          # rte
    0x41C: '4E71',          # natural indirect target
    0x41E: '4E75',          # rts
}
CODE = {0x400: 6, 0x406: 4, 0x40A: 2, 0x410: 2, 0x412: 2, 0x414: 2, 0x416: 2, 0x418: 2, 0x41A: 2,
        0x41C: 2, 0x41E: 2}


def image():
    data = bytearray(0x420)
    for address, words in PROGRAM.items():
        raw = bytes.fromhex(words)
        data[address:address + len(raw)] = raw
    data[4:8] = (0x400).to_bytes(4, 'big')
    data[26 * 4:26 * 4 + 4] = (0x41A).to_bytes(4, 'big')
    return bytes(data)


def model(natural=None):
    img = image()
    return inv.Model(img, CODE, {}, {1: 0x400, 26: 0x41A}, natural_targets=natural)


def epoch(extra_words=(), extra_edges=()):
    img = image()
    executed = [0x400, 0x406, 0x40A, 0x410, 0x412, 0x416, 0x418, 0x41A, 0x41C, 0x41E]
    words = [[a, 1, 0, inv.u16(img, a), 0] for a in executed] + list(extra_words)
    edges = [[0, 0x400, 'epoch', 0, 1, 0], [0x400, 0x410, 'flow', 0, 1, 0], [0x410, 0x412, 'flow', 0, 1, 0],
             [0x412, 0x416, 'flow', 0, 1, 0], [0x416, 0x406, 'flow', 0, 1, 0], [0x406, 0x418, 'flow', 0, 1, 0],
             [0x418, 0x41C, 'flow', 0, 1, 0], [0x41C, 0x41E, 'flow', 0, 1, 0], [0x41E, 0x40A, 'flow', 0, 1, 0],
             [0x40A, 0x41A, 'exception', 26, 1, 0], [0x41A, 0x40A, 'flow', 0, 1, 0]] + list(extra_edges)
    return {'words': words, 'edges': edges, 'outside_steps': 0, 'opcode_changes': 0}


class FlowTests(unittest.TestCase):
    def test_opcode_flow_classes(self):
        img = image()
        self.assertEqual(inv.flow(img, 0x400, 6), ('call', [0x410], True))
        self.assertEqual(inv.flow(img, 0x406, 4), ('call', [0x418], True))
        self.assertEqual(inv.flow(img, 0x40A, 2), ('jump', [0x40A], False))
        self.assertEqual(inv.flow(img, 0x412, 2), ('branch', [0x416], True))
        self.assertEqual(inv.flow(img, 0x416, 2), ('return', [], False))
        self.assertEqual(inv.flow(img, 0x418, 2), ('jump', None, False))
        self.assertEqual(inv.flow(img, 0x418, 2, [0x41C]), ('jump', [0x41C], False))
        self.assertEqual(inv.flow(img, 0x410, 2), ('plain', [], True))

    def test_entries_and_bodies(self):
        m = model({0x418: {0x41C}})
        self.assertEqual(m.entries, {0x400: ['reset'], 0x41A: ['exception'], 0x410: ['call'], 0x418: ['call']})
        self.assertEqual(m.body(0x410), {0x410, 0x412, 0x414, 0x416})
        self.assertEqual(m.body(0x400), {0x400, 0x406, 0x40A})
        self.assertEqual(m.body(0x418), {0x418, 0x41C, 0x41E})  # observed indirect target joins the body
        self.assertEqual(model().body(0x418), {0x418})


class NaturalJoinTests(unittest.TestCase):
    def test_consistent_epoch_explains_every_edge(self):
        summary, failures = inv.check_natural(model(), epoch(), 'disc')
        self.assertEqual(failures, [])
        self.assertEqual(summary['edge_reasons'], {'reset-entry': 1, 'call': 2, 'fall-through': 2,
                                                   'branch-taken': 1, 'return-to-call-site': 3,
                                                   'indirect-jump': 1, 'exception-vector': 1})
        self.assertEqual(summary['dynamic_indirect_targets'], {'0x0418': ['0x041C']})

    def test_rejections(self):
        img = image()
        cases = {
            'unexplained-edge': epoch(extra_edges=[[0x410, 0x416, 'flow', 0, 1, 0]]),
            'opcode-differs-from-disc': epoch(extra_words=[[0x414, 1, 0, 0x4E75, 0]]),
            'executed-not-static-instruction': epoch(extra_words=[[0x40C, 1, 0, inv.u16(img, 0x40C), 0]]),
        }
        for expected, data in cases.items():
            _, failures = inv.check_natural(model(), data, 'disc')
            self.assertIn(expected, [f[0] for f in failures], expected)
        wrong_vector = epoch(extra_edges=[[0x410, 0x416, 'exception', 25, 1, 0]])
        self.assertTrue(inv.check_natural(model(), wrong_vector, 'disc')[1])
        bad_return = epoch(extra_edges=[[0x416, 0x414, 'flow', 0, 1, 0]])  # 0x414 is not a return site
        self.assertTrue(inv.check_natural(model(), bad_return, 'disc')[1])
        changed = dict(epoch(), opcode_changes=1)
        self.assertTrue(inv.check_natural(model(), changed, 'disc')[1])

    def test_inventory_counts_natural_calls(self):
        functions, totals = inv.inventory(model({0x418: {0x41C}}), epoch())
        by_entry = {f['entry']: f for f in functions}
        self.assertEqual(totals['entries'], 4)
        self.assertEqual(totals['executed_entries'], 4)
        self.assertEqual(by_entry['0x0410']['natural']['observed_call_sites'], ['0x0400'])
        self.assertEqual(by_entry['0x041A']['natural']['observed_calls_or_exceptions'], 1)
        self.assertEqual(by_entry['0x0400']['callees'], ['0x0410', '0x0418'])
        self.assertEqual(by_entry['0x0410']['returns'], 1)

    def test_resident_patch_classification(self):
        disc = image()
        resident = bytearray(disc)
        resident[0x412:0x414] = bytes.fromhex('4E71')  # code patch inside a decoded instruction
        resident[0x40C] ^= 0xFF                         # undecoded byte: data/work area
        sites, data = inv.resident_patches(disc, bytes(resident), CODE)
        self.assertEqual(sites, {0x412: [0x412, 0x413]})
        self.assertEqual(data, [0x40C])

    def test_select_epoch_requires_one_match(self):
        img = image()
        good = {'words': [[a, 1, 0, inv.u16(img, a), 0] for a in range(0x400, 0x420, 2)]}
        bad = {'words': [[a, 1, 0, 0xFFFF, 0] for a in range(0x400, 0x420, 2)]}
        self.assertEqual(inv.select_epoch({'epochs': [bad, good]}, img, minimum=8), 1)
        with self.assertRaises(ValueError):
            inv.select_epoch({'epochs': [good, good]}, img, minimum=8)
        with self.assertRaises(ValueError):
            inv.select_epoch({'epochs': [bad]}, img, minimum=8)


if __name__ == '__main__':
    unittest.main()
