"""Owned boundary and wrapper checks; original execution is separate evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_fifo as p


class FifoProbeTests(unittest.TestCase):
    def test_declared_products_include_byte_domains_and_four_outcomes(self):
        selected=p.cases()
        self.assertEqual(len(selected),15872)
        self.assertEqual(len(set(selected)),len(selected))
        self.assertEqual({r[0] for r in selected},set(range(256)))
        self.assertEqual({r[1] for r in selected if r[-1]==2},set(range(256)))
        examples=((0,0,0,0,0,0),(0x20,0,0,0,0,1),(0x20,0,4,0,0,0),(0x20,0,0,0,0,0))
        self.assertEqual([p.contract(*r)[-1] for r in examples],
                         ['disabled','software-empty','device-full','one-byte-pushed'])

    def test_wrap_push_clears_pending_and_preserves_other_bytes(self):
        before,after,regions,changed,events,pcs,fixture,fifo,outcome=p.contract(0x20,255,3,3,0x200,0)
        self.assertEqual(after[17],0x2715)
        self.assertEqual(after[4],255)
        self.assertEqual(changed[1],bytes.fromhex('00cd00'))
        self.assertEqual(fifo['count'],4)
        self.assertEqual(fifo['wp'],3)
        self.assertEqual(fifo['flags'],0x11)
        self.assertEqual(fifo['scipd'],0)
        self.assertEqual(fifo['mcipd'],0)
        self.assertEqual(events[-1],[2,0x9843,1,0])
        self.assertEqual(after[15],before[15])
        self.assertEqual(outcome,'one-byte-pushed')

    def test_full_fifo_skips_payload_and_cursor_access(self):
        _,after,_,changed,events,pcs,_,fifo,_=p.contract(0x40,127,4,0,0x200,0)
        self.assertEqual(fifo['scipd'],0x200)
        self.assertEqual(changed[1],bytes.fromhex('80cd7f'))
        self.assertEqual(events[-1],[1,0x100404,1,0x11])
        self.assertNotIn(0x10D4,pcs)
        self.assertEqual(after[17],0x271B)  # CMP 7F-80: N,V,C, preserved X; BTST clears Z

    def test_disabled_and_empty_do_not_touch_device(self):
        for case in ((0x80,255,3,3,0x200,0),(0x60,127,3,3,0x200,1)):
            *_,events,pcs,fixture,fifo,outcome=p.contract(*case)
            self.assertEqual(fifo,p.native.fifo_contract(*fixture))
            self.assertTrue(all(e[1]<0x100000 for e in events))

    def test_missing_source_failure_is_private_and_immutable(self):
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
