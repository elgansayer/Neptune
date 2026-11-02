"""Owned contract examples; they do not replace original execution."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_capture as p


class CaptureTests(unittest.TestCase):
    def test_declared_domains(self):
        rows=p.cases()
        self.assertEqual(len(rows),7522)
        self.assertEqual(len(set(rows)),len(rows))
        self.assertEqual({r[0] for r in rows},set(range(256)))
        self.assertEqual({r[3] for r in rows},set(range(256)))
        self.assertEqual({r[4]&0x7F0 for r in rows},set(range(0,0x800,16)))
        self.assertEqual({r[5] for r in rows},set(range(256)))

    def test_timestamped_log_differs_from_raw_forwarded_packet(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0x20,0x80,3,0x5A,0xFFFF,255,0)
        raw=regions[1][1][48:64]
        self.assertEqual(after[3][-16:],raw[:14]+bytes.fromhex('a17e'))
        forwarded=bytes(after[6][(255+i)&255] for i in range(16))
        self.assertEqual(forwarded,raw)
        self.assertNotEqual(forwarded[-2:],bytes.fromhex('a17e'))
        self.assertEqual(after[2],bytes.fromhex('0730cafe00000800'))
        self.assertEqual(after[4],bytes.fromhex('0800'))
        self.assertEqual(after[5],bytes([15]))
        self.assertEqual(expected[0],0xA5A50730)
        self.assertEqual(expected[9],before[9])
        self.assertEqual(expected[15],before[15])
        self.assertEqual(stop,0x139A)
        self.assertNotIn(0x139A,pcs)

    def test_nested_return_address_and_saved_registers_are_distinct(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0xA0,0x80,7,0xFF,0x7FF,240,1)
        self.assertEqual(after[7][:8],bytes.fromhex('a5a50770')+before[9].to_bytes(4,'big'))
        self.assertEqual(after[7][8:12],(0x131E).to_bytes(4,'big'))
        self.assertEqual(expected[15],p.leaf.SP-4)
        self.assertEqual(expected[17],0x2014)  # final forward cursor0: Z and X

    def test_complete_empty_scan_and_handshake_clear(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0x80,0xFF,-1,0,0x7FF,255,0)
        self.assertEqual(outcome,'empty-return')
        self.assertEqual(expected[0],0xA5A50780)
        self.assertEqual(expected[8],0x770)
        self.assertEqual(after[0],bytes.fromhex('7f80'))
        self.assertEqual(expected[17],0x2700)
        self.assertEqual(expected[15],p.leaf.SP+4)
        self.assertEqual(sum(e[1] in range(0x700,0x780) for e in events),8)
        self.assertEqual(events[-1],[1,p.leaf.SP,4,p.leaf.STOP])

    def test_unready_handshake_avoids_command_source(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0xA0,0,7,0xFF,0x7FF,255,0)
        self.assertEqual(outcome,'unready-return')
        self.assertEqual(expected[17],0x2714)
        self.assertEqual(expected[7],before[7])
        self.assertEqual(len(events),3)
        self.assertEqual(after,[r[1] for r in regions])

    def test_no_forward_branch_keeps_output_cursor_and_canaries(self):
        before,expected,regions,after,events,pcs,stop,outcome=p.contract(0x40,0x80,0,1,0xF00F,255,0)
        self.assertEqual(after[5:7],[r[1] for r in regions[5:7]])
        self.assertEqual(expected[1],before[1])
        self.assertEqual(expected[10:12],before[10:12])
        self.assertEqual(expected[17],0x2717)  # gate40 doubled twice: X,C,V,Z

    def test_failure_report_never_overwritten(self):
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
