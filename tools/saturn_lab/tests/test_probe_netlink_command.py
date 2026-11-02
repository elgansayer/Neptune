"""Owned byte/register examples and wrapper guards, not original CPU evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_command as p


class CommandTests(unittest.TestCase):
    def test_all_status_and_counter_values_in_declared_products(self):
        rows=p.cases()
        self.assertEqual(len(rows),9136)
        self.assertEqual(len(set(rows)),9136)
        self.assertEqual({r[0] for r in rows},set(range(256)))
        self.assertEqual({r[1] for r in rows if r[0]==0x90},set(range(256)))

    def test_wrap_packing_and_saved_sr_fixed_example(self):
        before,after,regions,expected,events,pcs,destination=p.contract(0x9F,255,1)
        self.assertEqual(expected[3],bytes.fromhex('013f7f00'))
        self.assertEqual(expected[2],b'\x00')
        self.assertEqual(destination,0x11DFC)
        self.assertEqual(after[10],0x11E00)
        self.assertEqual(after[17],0x2714)
        self.assertEqual(after[0],0x5A5A0090)
        self.assertEqual(after[3],0x5A5A0010)
        self.assertEqual(after[5:8],before[5:8])
        self.assertEqual(events[-1],[1,p.leaf.SP,4,p.leaf.STOP])

    def test_selected_subtract_clamps_and_other_status_leaves_byte_unchanged(self):
        for variant,wanted in ((0,0),(1,0),(2,128),(3,0)):
            _,_,_,expected,_,_,_=p.contract(0x90,0,variant)
            self.assertEqual(expected[3][3],wanted)
            _,_,_,other,_,_,_=p.contract(0x80,0,variant)
            self.assertEqual(other[3][3],p.VARIANTS[variant][4])

    def test_conditional_reads_and_branch_paths(self):
        _,_,_,_,regular,regular_pcs,_=p.contract(0x80,0,0)
        self.assertNotIn(p.RECORD+0x22,{e[1] for e in regular})
        _,_,_,_,special,special_pcs,_=p.contract(0x90,0,3)
        self.assertIn([1,p.RECORD+0x24,1,255],special)
        self.assertIn(0x4C60,special_pcs)
        self.assertEqual(len(regular_pcs),32)
        self.assertEqual(len(special_pcs),39)

    def test_native_failure_never_becomes_a_passing_case(self):
        class Failed:
            def run(self,*args,**kwargs):return {'status_code':4,'status':'unmapped-data-read'}
        with self.assertRaisesRegex(ValueError,'Native guard'):
            p.run_case(bytes(23920),Failed(),0,0,0)

    def test_missing_source_retains_private_failure_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            original=report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'],'source_identity')
            self.assertNotIn(str(root),original.decode())
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),original)


if __name__=='__main__':unittest.main()
