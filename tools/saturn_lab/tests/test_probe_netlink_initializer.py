"""Owned contract/failure examples, not original-game execution evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_netlink_initializer as p


class InitializerTests(unittest.TestCase):
    def test_declared_modes_and_input_coverage(self):
        rows = p.cases()
        self.assertEqual(len(rows), 12800)
        self.assertEqual(len(set(rows)), 12800)
        for mode in p.MODES:
            self.assertEqual({r[3] for r in rows if r[0] == mode}, set(range(256)))
        self.assertEqual({r[5] for r in rows if r[0] == 'dispatcher'}, set(p.dispatch.WORDS))

    def test_fixed_initializer_record_defaults_and_canaries(self):
        before, after, regions, buffers, events, pcs = p.contract('initializer',0x8000,0x2700,0,0,0)
        self.assertEqual(buffers[1][16:27], bytes.fromhex('0000200000000053000020'))
        self.assertEqual(buffers[1][48:94], bytes.fromhex('000000002000000000000000000000002000'+'0000'*14))
        for lo, hi in ((0,16),(27,48),(94,104)):
            self.assertEqual(buffers[1][lo:hi], regions[1][1][lo:hi])
        self.assertEqual(after[:15], before[:15])
        self.assertEqual(after[15:18], [p.leaf.SP+4,p.leaf.STOP,0x2704])
        self.assertEqual(len(pcs), 40)
        self.assertEqual(len(events), 80)
        self.assertEqual(events[30], [1,0x412,4,0x8000])
        self.assertEqual(events[-1], [1,p.leaf.SP,4,p.leaf.STOP])

    def test_movem_word_order_and_restored_negative_d0_keeps_last_write_flags(self):
        before, after, _, _, events, _ = p.contract('initializer',0x10000,0x271F,255,1,0xFFFF)
        self.assertEqual(events[:2], [[2,p.leaf.SP-2,2,0x8000],[2,p.leaf.SP-4,2,2]])
        self.assertEqual(events[28:30], [[2,p.leaf.SP-58,2,0xFFFF],[2,p.leaf.SP-60,2,0xA5A5]])
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[0], 0xA5A5FFFF)
        self.assertEqual(after[17], 0x2714)

    def test_real_handler_return_and_nested_stack_extent(self):
        _, after, _, _, events, pcs = p.contract('handler',0x8000,0x2015,128,0,0)
        self.assertEqual(events[0], [2,p.leaf.SP-4,4,0x1E66])
        self.assertEqual(min(e[1] for e in events if e[1] >= p.leaf.SP-96), p.leaf.SP-64)
        self.assertEqual(pcs[0], 0x1E62)
        self.assertEqual(pcs[-1], 0x1E66)
        self.assertEqual(len(pcs), 42)
        self.assertEqual(after[15:18], [p.leaf.SP+4,p.leaf.STOP,0x2014])

    def test_dispatcher_restores_outer_state_and_uses_distinct_absolute_context(self):
        before, after, regions, _, events, pcs = p.contract('dispatcher',0x8000,0x271F,0,0,0xFFFF)
        self.assertEqual(after[0], 0x1122FFFF)
        self.assertEqual(after[7], 0x1122004C)
        self.assertEqual(after[12], 0x18000)
        self.assertEqual(after[13:15], before[13:15])
        self.assertEqual(regions[0][1], bytes.fromhex('00008000'))
        self.assertIn([1,0x412,4,0x8000], events)
        self.assertIn([2,p.leaf.SP-12,4,0x1868], events)
        self.assertIn([2,p.leaf.SP-16,4,0x1E66], events)
        self.assertEqual(pcs[-3:], [0x1E66,0x1868,0x186C])
        self.assertEqual(len(pcs), 55)
        self.assertEqual(after[17], 0x2704)

    def test_rejects_undeclared_cases(self):
        case = ['initializer',0x8000,0x2700,0,0,0]
        for index, value in ((0,'unknown'),(1,0x1000),(2,0),(3,True),(3,256),(4,True),(5,0x10000)):
            changed = list(case)
            changed[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                p.contract(*changed)

    def test_budget_failure_is_not_a_semantic_mutation_rejection(self):
        class Guard:
            def run(self, *args, **kwargs):
                return {'status_code':2, 'status':'instruction-budget'}
        with self.assertRaisesRegex(ValueError, 'terminal semantic comparison'):
            p.semantic_control(bytes(23920), Guard(), 0x512A, 0x21,
                               [('initializer',0x8000,0x2700,0,0,0)])

    def test_input_failure_is_private_preserved_and_before_native_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root/'failed.json'
            args = ['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(report)]
            with patch.object(p.native, 'Library') as library, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
                library.assert_not_called()
            data = report.read_bytes()
            self.assertEqual(json.loads(data)['error']['phase'], 'source_identity')
            self.assertNotIn('cases', json.loads(data))
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args), 1)
            self.assertEqual(report.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
