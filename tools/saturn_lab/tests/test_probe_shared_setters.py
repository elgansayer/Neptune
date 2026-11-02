"""Owned setter examples and wrapper custody, not original evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_shared_setters as p


class SetterTests(unittest.TestCase):
    def test_declared_products(self):
        rows=p.cases()
        self.assertEqual(len(rows),9136)
        for lane in range(2):
            self.assertEqual({r[1] for r in rows if r[0]==lane},set(range(256)))
            self.assertEqual({r[2] for r in rows if r[0]==lane},set(range(256)))

    def test_different_payload_offsets_and_last_table_lane(self):
        for lane in range(2):
            before,expected,regions,after,events,pcs,destination=p.contract(lane,255,128,0)
            self.assertEqual(destination,0x97E+lane)
            self.assertEqual(regions[0][1][2+lane],128)
            self.assertEqual(regions[0][1][3-lane],127)
            self.assertEqual(after[1][510+lane],128)
            self.assertEqual(after[1][511-lane],regions[1][1][511-lane])
            self.assertEqual(expected[17],0x2708)  # ADD.W clears initial X
            self.assertEqual(expected[:15],before[:15])
            self.assertEqual(len(pcs),9)
            self.assertEqual(len(events),13)

    def test_saved_register_order_and_zero_flags(self):
        before,expected,regions,after,events,pcs,destination=p.contract(0,0,0,1)
        self.assertEqual(after[2][:12],b''.join(before[r].to_bytes(4,'big') for r in (0,2,8)))
        self.assertEqual(events[:2],[[2,p.leaf.SP-2,2,before[8]&65535],[2,p.leaf.SP-4,2,before[8]>>16]])
        self.assertEqual(expected[17],0x2004)
        self.assertEqual(expected[15],p.leaf.SP+4)

    def test_failure_report_exclusive_private_and_module_restricted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--source-file',str(root/'missing'),'--module','XBSND','--prepared',str(root),'--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            original=report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'],'source_identity')
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),original)


if __name__=='__main__':unittest.main()
