"""Owned record boundary examples; not original instruction evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_kernel_records as p


class KernelRecordTests(unittest.TestCase):
    def test_selection_retains_all_flags_counters_records_and_wrap_boundaries(self):
        rows=p.cases()
        self.assertEqual(len(rows),18722)
        self.assertEqual(len(set(rows)),len(rows))
        self.assertEqual({c[2] for c in rows if c[0]=='mark'},set(range(256)))
        self.assertEqual({c[2] for c in rows if c[0]=='clear-all'},set(range(256)))
        self.assertTrue({372,373,0xFFFF,0x10000}.issubset({c[1] for c in rows if c[0]=='mark'}))

    def test_marker_signed_truncation_and_MACL_delay_restore(self):
        _,m=p.contract(('mark',373,255,0,1))
        self.assertEqual(m.reg['r4'],p.RECORDS-0x7FC8)
        self.assertEqual(m.reg['macl'],m.before['macl'])
        self.assertEqual(m.reg['r15'],p.SP)
        self.assertEqual(m.reg['sr'],0)
        self.assertEqual(m.events[-1],[1,p.SP-4,4,0x89ABCDEF])
        self.assertEqual(m.trace[-1],[0x06006B54,True])
        self.assertIn([2,p.RECORDS-0x7FC8,4,1],m.events)

    def test_all_eighteen_real_marker_calls_and_unsigned_category_compare(self):
        _,m=p.contract(('mark-all',255,(1<<18)-1,(1<<18)-1,1))
        self.assertEqual(sum(pc==p.MARK for pc,_ in m.trace),18)
        self.assertEqual(m.reg['r4'],p.RECORDS+17*88)
        self.assertEqual(m.reg['sr'],1)
        table=m.buffers[1]
        self.assertTrue(all(table[i*88:i*88+4]==bytes.fromhex('00000001') and table[i*88+81]==0 for i in range(18)))
        self.assertTrue(all(m.reg[name]==m.before[name] for name in ('r11','r12','r13','r14','r15','pr','macl','mach')))
        _,high=p.contract(('mark-all',0xFFFFFFFF,(1<<18)-1,(1<<18)-1,1))
        self.assertFalse(any(pc==p.MARK for pc,_ in high.trace))
        self.assertTrue(all(high.buffers[1][i*88+81]==255 for i in range(18)))

    def test_clear_preserves_sign_extended_counter_result_and_zero_index_reads_nothing(self):
        _,m=p.contract(('clear',1,255,128,0))
        self.assertEqual(m.reg['r2'],0xFFFFFF7F)
        self.assertEqual(m.reg['r4'],p.COUNT)
        self.assertEqual(m.buffers[2],bytes([127]))
        self.assertEqual(m.reg['sr'],0x3F2)
        _,zero=p.contract(('clear',0,0,255,0))
        self.assertEqual(zero.events,[])
        self.assertEqual(zero.reg['r4'],0)
        self.assertEqual(zero.reg['sr'],0x3F3)

    def test_all_sixteen_actual_calls_wrap_counter_and_restore_delay_register(self):
        _,m=p.contract(('clear-all',0xFFFF,0,0,1))
        self.assertEqual(sum(pc==p.CLEAR for pc,_ in m.trace),16)
        self.assertTrue(all(m.buffers[1][i*16+11]==0 for i in range(16)))
        self.assertEqual(m.buffers[2],bytes([240]))
        self.assertEqual(m.reg['r2'],0xFFFFFFF0)
        self.assertEqual(m.trace[-1],[0x06009448,True])
        self.assertTrue(all(m.reg[name]==m.before[name] for name in ('r13','r14','r15','pr','macl','mach')))

    def test_failure_report_is_exclusive_private_and_stops_before_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--kind','mark','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            original=report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'],'source_identity')
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),original)


if __name__=='__main__':unittest.main()
