"""Owned parser/dispatch contract checks; no original instruction execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_parser as p


class ParserTests(unittest.TestCase):
    def test_selection_domains_and_separate_complete_paths(self):
        rows=p.cases()
        self.assertEqual(len(rows),13690)
        self.assertEqual(len(set(rows)),13690)
        self.assertEqual(sum(r[-1] for r in rows),3711)
        self.assertEqual({r[0] for r in rows},set(range(256)))
        for group in range(8):
            selected=[r for r in rows if r[0]==group and not r[-1]]
            self.assertEqual({r[1] for r in selected},set(range(256)))
            self.assertEqual({r[2] for r in selected},set(range(256)))
            self.assertEqual({r[3] for r in selected},set(range(256)))
        self.assertEqual({r[4] for r in rows if r[0]==7 and r[-1]},set(range(256)))

    def test_two_byte_wrap_field_decode_and_flag_return(self):
        before,after,regions,expected,events,pcs,formatted=p.contract(0xFD,255,255,255,0x40,1,True)
        self.assertEqual(formatted,[0xDF,0x80])
        self.assertEqual(expected[0][0x41:0x43],b'\x01\x00')
        self.assertEqual(expected[3][255],0xDF)
        self.assertEqual(expected[3][0],0x80)
        self.assertEqual(expected[0][:4],bytes.fromhex('0e00001f'))
        self.assertEqual(expected[0][10:12],bytes.fromhex('0ff0'))
        self.assertEqual(after[0],20)
        self.assertEqual(after[1],0xA5A5001F)
        self.assertEqual(after[2],0xA5A50F80)
        self.assertEqual(after[9],0x11DFF)
        self.assertEqual(after[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2000])
        self.assertEqual(after[8],before[8])

    def test_length_classes_and_bit6_gate_are_distinct(self):
        for group in range(8):
            _,_,_,_,_,_,formatted=p.contract(group,0,0,254,0x40,0,False)
            self.assertEqual(len(formatted),2 if group in (4,5) else 3)
        for gate,enabled in ((0,False),(0x80,False),(0x40,True),(0xFF,True)):
            _,_,regions,after,_,_,formatted=p.contract(1,0,0,255,gate,0,False)
            self.assertEqual(bool(formatted),enabled)
            if not enabled:self.assertEqual(after[3],regions[3][1])

    def test_all_transfer_targets_and_full_path_restriction(self):
        for group,target in enumerate(p.TARGETS):
            _,after,_,_,_,pcs,_=p.contract(group,0,0,0,0,0,False)
            self.assertEqual(after[16],target)
            self.assertEqual(after[15],p.leaf.SP)
            self.assertEqual(pcs[-1],0x24B2+4*group)
            if group not in p.RETURNING:
                with self.assertRaises(ValueError):p.contract(group,0,0,0,0,0,True)

    def test_original_flag_bits_and_zero_reflect_old_bit(self):
        for group,(_,bit) in p.RETURNING.items():
            _,after,_,buffers,_,_,_=p.contract(group,0,0,0,0,0,True)
            self.assertEqual(buffers[4],bytes([1<<bit]))
            self.assertEqual(after[17]&31,4)

    def test_native_guard_failure_is_not_a_completed_path(self):
        class Failed:
            def run(self,*args,**kwargs):return {'status_code':3,'status':'instruction-access'}
        with self.assertRaisesRegex(ValueError,'Native guard'):
            p.run_case(bytes(23920),Failed(),0,0,0,0,0,0,False)


if __name__=='__main__':unittest.main()
