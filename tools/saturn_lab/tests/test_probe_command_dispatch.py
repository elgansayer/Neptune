"""Owned dispatcher examples; original execution remains separate evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_command_dispatch as p


class CommandDispatchTests(unittest.TestCase):
    def test_declared_domains_and_completion_partition(self):
        rows=p.cases()
        self.assertEqual(len(rows),18432)
        self.assertEqual(len(set(rows)),len(rows))
        self.assertEqual({r[0] for r in rows},set(range(256)))
        self.assertEqual(len(p.LOW_TARGETS),32)
        self.assertEqual(len(p.HIGH_TARGETS),16)
        self.assertEqual({c:p.contract(c,0,0,0x2700,0x8000)[-1] for c in (0,1,0x20,0x80,0x8C,0x8D,0x8F,0x90,0x91)},
            {0:'complete-return',1:'handler-prefix',0x20:'complete-return',0x80:'handler-prefix',
             0x8C:'unresolved-exception-vector',0x8D:'complete-return',0x8F:'unresolved-exception-vector',
             0x90:'handler-prefix',0x91:'complete-return'})

    def test_low_zero_real_call_restore_and_preserved_upper_d7(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0,0x8000,0xA5A5FF00,0x271F,0x10000)
        self.assertEqual(expected[7],0xA5A50000)
        self.assertEqual(expected[12],0x10000)
        self.assertEqual(expected[13:15],before[13:15])
        self.assertEqual(expected[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2704])
        self.assertEqual(after[0][12:24],(0x1868).to_bytes(4,'big')+before[13].to_bytes(4,'big')+before[14].to_bytes(4,'big'))
        self.assertEqual(pcs[-3:],[0x1872,0x1868,0x186C])
        self.assertEqual(len(events),9)

    def test_middle_ori_is_executed_before_both_flag_return_operations(self):
        _,expected,_,_,events,pcs,_,outcome=p.contract(0x8D,0,0,0x271F,0x8000)
        self.assertEqual(expected[0],0x1122006E)
        self.assertEqual(expected[7],13*4)
        self.assertEqual(expected[17],0x2700)
        self.assertEqual(pcs.count(0x186E),2)
        self.assertIn(0x1842,pcs)
        self.assertIn(0x1846,pcs)
        self.assertEqual(events,[[2,p.leaf.SP-4,4,0x180C],[1,p.leaf.SP-4,4,0x180C],[1,p.leaf.SP,4,p.leaf.STOP]])

    def test_skip_keeps_x_but_indexed_noop_clears_x(self):
        for command,wanted in ((0x20,0x2714),(0x91,0x2714),(0x1F,0x2704),(0x8B,0x2704)):
            self.assertEqual(p.contract(command,0,0,0x271F,0x8000)[1][17],wanted)

    def test_unmapped_exception_vector_is_never_completed(self):
        _,expected,_,after,events,pcs,_,outcome=p.contract(0x8C,1,0xA5A5FF00,0x271F,0x8000)
        self.assertEqual(expected[15],p.leaf.SP-10)
        self.assertEqual(expected[16],0x10)
        self.assertEqual(events[-2:],[[2,p.leaf.SP-8,4,0x183E],[2,p.leaf.SP-10,2,0x2700]])
        self.assertEqual(after[0][14:20],bytes.fromhex('27000000183e'))
        class Wrong:
            def run(self,*args,**kwargs):return {'status_code':1,'error_address':0,'error_size':0}
        with self.assertRaisesRegex(ValueError,'unmapped exception vector'):
            p.run_case(bytes(23920),Wrong(),0x8C,1,0xA5A5FF00,0x271F,0x8000)

    def test_failure_report_private_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            original=report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'],'source_identity')
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),original)


if __name__=='__main__':unittest.main()
