"""Owned full-scan boundary examples, separate from original CPU evidence."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_active_scan as p


class ActiveScanTests(unittest.TestCase):
    def test_declared_domains_and_unresolved_handler_exclusion(self):
        rows=p.cases()
        self.assertEqual(len(rows),3196)
        self.assertEqual(len(set(rows)),len(rows))
        self.assertEqual(len(p.RETURNING),223)
        self.assertEqual({r[0] for r in rows},set(range(256)))
        self.assertEqual({r[1] for r in rows if r[1]!=0x100},set(p.RETURNING))
        self.assertEqual({r[5] for r in rows},set(range(256)))
        self.assertEqual({r[4]&0x7F0 for r in rows},set(range(0,0x800,16)))
        for command in (1,0x80,0x8C,0x8F,0x90):
            with self.assertRaises(ValueError):p.contract(255,command,0xA0,0xFF,0x7FF,255,0)

    def test_all_eight_headers_clear_and_timestamped_log_differs_from_raw_forwarding(self):
        before,after,regions,changed,events,pcs,processed=p.contract(255,0x100,0xA0,0xFF,0x7FF,255,0)
        source=regions[1][1]
        self.assertEqual(processed,list(range(8)))
        self.assertTrue(all(changed[1][i*16:i*16+2]==b'\0\0' for i in range(8)))
        self.assertEqual(changed[3][-16:],source[:14]+bytes.fromhex('a17e'))
        self.assertEqual(changed[3][:16],source[16:30]+b'\0\0')
        self.assertEqual(changed[3][0x60:0x70],source[112:126]+b'\0\0')
        self.assertEqual(bytes(changed[6][(255+i)&255] for i in range(128)),source)
        self.assertEqual(changed[2],bytes.fromhex('0770cafe00000070'))
        self.assertEqual(changed[4],bytes.fromhex('0070'))
        self.assertEqual(changed[5],bytes([127]))
        self.assertEqual(after[0],0xA5A50780)
        self.assertEqual(after[1],0xFFFF)
        self.assertEqual(after[7],0xA5A500FF)
        self.assertEqual(after[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2700])
        self.assertEqual(pcs.count(0x139A),8)
        self.assertEqual(pcs.count(0x13A4),8)

    def test_original_middle_ori_returns_and_slot_is_reloaded_before_word_clear(self):
        before,after,regions,changed,events,pcs,processed=p.contract(128,0x8D,0xA0,0x80,0xFFFF,255,1)
        self.assertEqual(processed,[7])
        self.assertEqual(after[7],0xA5A50034)
        self.assertEqual(after[12],before[12])
        self.assertEqual(after[17],0x2004)
        self.assertIn(0x1842,pcs)
        self.assertIn([2,0x770,2,0],events)
        self.assertEqual(after[8],0x770)
        self.assertEqual(after[0],0xA5A50780)
        self.assertEqual(changed[1][112:114],b'\0\0')

    def test_unready_does_not_mutate_packets_or_ack(self):
        before,after,regions,changed,events,pcs,processed=p.contract(255,0x100,0x80,0,0x7FF,255,0)
        self.assertEqual(changed,[r[1] for r in regions])
        self.assertEqual(processed,[])
        self.assertEqual(after[7],before[7])
        self.assertEqual(after[17],0x2714)
        self.assertEqual(len(events),3)
        self.assertEqual(pcs,[0x130E,0x1312,0x1314,0x1318,0x1324])

    def test_direct_scan_retains_empty_slots_and_returns_real_final_add_flags(self):
        _,after,regions,changed,events,pcs,processed=p.contract(1,0x1F,0,0xFF,0x7FF,255,0)
        self.assertEqual(processed,[0])
        self.assertEqual(changed[1][2:],regions[1][1][2:])
        self.assertEqual(changed[5:7],[r[1] for r in regions[5:7]])
        self.assertEqual(changed[0],regions[0][1])
        self.assertEqual(after[17],0x270A)
        self.assertEqual(after[7],0xA5A50000)
        self.assertEqual(after[12],0x8000)


if __name__=='__main__':unittest.main()
