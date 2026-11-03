"""Owned independent ramp boundary examples; no emulator or original media."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_ramp as p


class RampContractTests(unittest.TestCase):
    def test_selection_sweeps_all_bytes_in_each_declared_field(self):
        selected=p.cases()
        self.assertEqual(len(selected),len(set(selected)))
        for group in (3,4,5):
            for axis in range(3):
                self.assertEqual({c[group][axis] for c in selected},set(range(256)))
        self.assertEqual({c[0] for c in selected},set(p.records.SR_VALUES))
        self.assertEqual({c[2] for c in selected},set(range(256)))

    def test_linear_direction_circular_wrap_and_preserved_canaries(self):
        before,expected,regions,after,events,pcs=p.contract(0x271F,1,0x80,(100,120,10),(20,5,120),(130,2,254))
        memory=after[0];origin=8
        for offset,value in ((0x2C,129),(0x20,80),(6,254),(0x26,2),
                             (0x22,13),(8,2),(0x28,2),(0x24,18),(10,254),(0x2A,2),
                             (0xC,20),(0xE,5),(0x10,120)):
            self.assertEqual(memory[origin+offset],value)
        self.assertEqual(memory[:8],regions[0][1][:8])
        self.assertEqual(memory[-8:],regions[0][1][-8:])
        self.assertEqual(after[1],regions[1][1])
        self.assertEqual(expected[0],18)
        self.assertEqual(expected[1],(before[1]&0xFFFFFF00)|2)
        self.assertEqual(expected[5:15],before[5:15])
        self.assertEqual(expected[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2710])
        self.assertEqual(events[-1],[1,p.leaf.SP,4,p.leaf.STOP])
        self.assertIn(0x52C6,pcs);self.assertIn(0x530A,pcs);self.assertIn(0x5332,pcs)

    def test_zero_step_and_full_byte_wrap_keep_actual_byte_arithmetic(self):
        _,expected,_,after,_,_=p.contract(0x200A,0,255,(0,255,255),(0,0,0),(128,128,1))
        self.assertEqual(after[0][8+0x26],0)
        self.assertEqual(after[0][8+0x28],128)
        self.assertEqual(expected[0],129)
        # -255 wraps to1, then+128 has no carry: final MOVE sets Z only.
        self.assertEqual(expected[17],0x2004)

    def test_undeclared_inputs_fail_closed(self):
        base=(0x2700,0,0,(1,2,3),(4,5,6),(7,8,9))
        for index,value in ((0,0),(1,True),(2,256),(3,[1,2,3]),(4,(1,2)),(5,(1,True,3))):
            case=list(base);case[index]=value
            with self.assertRaises(ValueError):p.contract(*case)


if __name__=='__main__':unittest.main()
