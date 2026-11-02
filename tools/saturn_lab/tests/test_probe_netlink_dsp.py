"""Constructed contract boundaries; no original media or native execution here."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_dsp as p


class DspContractTests(unittest.TestCase):
    def setUp(self):
        self.code=bytes(0x5000)

    def test_selection_is_unique_and_sweeps_each_complete_byte_domain(self):
        cases=p.cases()
        self.assertEqual(len(cases),27195)
        self.assertEqual(len(cases),len(set(cases)))
        for mode in p.MODES:
            for field in (3,4,5,6):
                self.assertEqual({case[field] for case in cases if case[0]==mode},set(range(256)))

    def test_active_mask_lanes_and_caller_stack_balance(self):
        for mode in p.MODES:
            for flags,mask in ((0x10,3),(0x20,7),(0x30,3)):
                before,expected,regions,after,events,pcs,writes,dest=p.contract(self.code,mode,0x271F,0,flags,7,255,0xFE)
                self.assertEqual(dest,0x100700+0xFE+mask*8)
                self.assertEqual(writes,[(dest+i*2,0) for i in range(4)])
                self.assertEqual(expected[0:2],[mask*8,31*8])
                self.assertEqual(expected[8:11],[0x8000,dest+8,p.TABLE+31*8+8])
                self.assertEqual(expected[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2700])
                self.assertEqual(events[-1],[1,p.leaf.SP,4,p.leaf.STOP])
                self.assertEqual([e for e in events if e[0]==2 and e[1]>=0x100000],[[2,a,2,v] for a,v in writes])
                self.assertNotIn(p.TABLE,pcs)
                self.assertEqual(len(regions),5)
                self.assertEqual(len(after),5)
                if mode=='dispatcher':self.assertEqual(expected[12:15],[before[14],before[13],before[14]])

    def test_inactive_preserves_extend_and_other_registers_without_device_writes(self):
        for mode in p.MODES:
            before,expected,_,_,events,pcs,writes,dest=p.contract(self.code,mode,0x271F,1,0xCF,255,255,255)
            self.assertEqual((writes,dest),([],None))
            self.assertEqual(expected[0:2],before[0:2])
            self.assertEqual(expected[9:11],before[9:11])
            self.assertEqual(expected[17],0x2708 if mode=='dispatcher' else 0x2718)
            self.assertFalse(any(e[0]==2 and e[1]>=0x100000 for e in events))
            self.assertNotIn(0x41C8,pcs)

    def test_out_of_range_constructed_fields_fail_closed(self):
        for case in (('other',0x2700,0,0,0,0,0),('helper',0,0,0,0,0,0),
                     ('helper',0x2700,0,256,0,0,0),('helper',0x2700,0,0,True,0,0)):
            with self.assertRaises(ValueError):p.contract(self.code,*case)


if __name__=='__main__':unittest.main()
