"""Owned context-layout examples; not original-byte execution evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_kernel_context as p


class KernelContextTests(unittest.TestCase):
    def test_selection_covers_words_walking_bits_and_distinct_fields(self):
        rows=p.cases();self.assertEqual(len(rows),912);self.assertEqual(len(set(rows)),912)
        self.assertEqual({c[2] for c in rows},{0,4,256})
        self.assertTrue(all(word in {p.vector(s)[i] for s in range(76)} for word in p.WORDS for i in range(24)))
        self.assertEqual(len(set(p.vector(12))),24)

    def test_save_duplicates_R8_and_preserves_all_other_state(self):
        _,m=p.contract(('save',12,4,0));address=m.before['r4']
        self.assertEqual(len(m.trace),17);self.assertEqual(len(m.events),12)
        self.assertEqual(m.events[:2],[[2,address,4,m.before['r8']],[2,address+4,4,m.before['r8']]])
        self.assertEqual(m.events[-1],[2,address+36,4,0xFFFFFFF0])
        self.assertEqual(m.trace[-1],[0x060061E4,True])
        self.assertEqual(m.reg,{**m.before,'r0':0,'pc':0xFFFFFFF0})
        self.assertEqual(m.buffers[0][:16],m.regions[0][1][:16])
        self.assertEqual(m.buffers[0][64:],m.regions[0][1][64:])

    def test_restore_loads_context_SP_PR_MAC_and_R4_then_returns_R5(self):
        _,m=p.contract(('restore',13,256,1));address=m.before['r4'];source=m.regions[0][1]
        self.assertEqual(len(m.trace),18);self.assertEqual(len(m.events),12)
        for reg,field in [('r4',0),*[(f'r{i}',4*(i-7)) for i in range(8,16)],('pr',36),('mach',40),('macl',44)]:
            self.assertEqual(m.reg[reg],int.from_bytes(source[16+field:20+field],'big'))
        self.assertNotEqual(m.before['pr'],m.reg['pr'])
        self.assertTrue(all(m.before[f'r{i}']!=m.reg[f'r{i}'] for i in range(8,16)))
        self.assertEqual(m.reg['r0'],m.before['r5'])
        self.assertEqual(m.trace[-1],[0x06006208,True])
        self.assertEqual(m.buffers[0],source)
        self.assertEqual(m.reg['sr'],m.before['sr'])

    def test_report_is_exclusive_private_and_failure_precedes_CPU_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--kind','restore','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            raw=report.read_bytes();d=json.loads(raw)
            self.assertEqual(d['error']['phase'],'source_identity');self.assertIs(d['original_game_bytes_executed'],False)
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),raw)


if __name__=='__main__':unittest.main()
