"""Owned record-access expectations; no original bytes or interpreter execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_record_access as p


class RecordAccessContracts(unittest.TestCase):
    def test_all_cases_restore_root_fit_budget_and_preserve_readonly_bytes(self):
        for f in p.FAMILIES:
            cases=p.cases(f);self.assertTrue(cases);self.assertEqual(len(cases),len(set(cases)))
            for c in cases:
                m,r=p.contract(c);self.assertLessEqual(len(m.trace),512)
                for key in ('r14','r15','pr','mach','macl','gbr','vbr'):self.assertEqual(m.reg[key],m.before[key])
                self.assertEqual(m.reg['pc'],m.before['pr'])
                for i,(a,b,w) in enumerate(r):
                    self.assertTrue(0x06000000<=a<a+len(b)<=0x06100000)
                    if not w:self.assertEqual(m.buffers[i],b)
                    for a2,b2,_ in r[i+1:]:self.assertTrue(a+len(b)<=a2 or a2+len(b2)<=a)

    def test_move_matches_snapshot_copy_in_both_overlap_directions_and_identity(self):
        for n,source,dest in ((0,64,65),(32,64,65),(32,65,64),(48,64,80),(48,80,64),(48,64,64)):
            m,r=p.contract(('move',0,37,n,source,dest));expected=bytearray(r[1][1]);expected[dest:dest+n]=r[1][1][source:source+n]
            self.assertEqual(m.buffers[1],expected);self.assertEqual(m.reg['r0'],m.before['r4'])
            self.assertEqual(sum(e[0]==2 for e in m.events),n if source!=dest else 0)

    def test_pointer_uses_populated_count_and_only_mode_one(self):
        m,_=p.contract(('name-pointer',0,37,26,25,1,0,1000));self.assertEqual(m.reg['r0'],0x060D4010+25*24+12)
        m,_=p.contract(('name-pointer',0,37,26,26,1,0,1000));self.assertEqual(m.reg['r0'],0)
        for mode in (0,2,p.MASK,-1):
            m,_=p.contract(('name-pointer',0,37,26,25,mode,0,1000));self.assertEqual(m.reg['r0'],0)
            self.assertEqual(int.from_bytes(m.buffers[7][0xC0:0xC4],'big'),(-8)&p.MASK)

    def test_descriptor_mode_one_uses24_other_modes_use12(self):
        for mode in (0,1,2,p.MASK):
            m,r=p.contract(('descriptor-copy',0,37,26,25,mode,0,1000));stride=24 if mode==1 else 12;start=16+25*stride
            self.assertEqual(m.buffers[4][:12],r[1][1][start:start+12]);self.assertEqual(m.reg['r0'],0)
            pcs=[pc for pc,_ in m.trace]
            self.assertIn(p.setup.INDEX24 if mode==1 else p.setup.INDEX12,pcs)
            self.assertIn(p.MOVE,pcs)

    def test_descriptor_overlap_copies12_before_reporting_effective_status(self):
        for delta in (-4,0,4,12):
            m,r=p.contract(('descriptor-copy',1,255,26,25,1,(-16)&p.MASK,delta))
            source=16+25*24;expected=bytearray(r[1][1]);expected[source+delta:source+delta+12]=r[1][1][source:source+12]
            self.assertEqual(m.buffers[1],expected);self.assertEqual(m.reg['r0'],(-25)&p.MASK)
            m,_=p.contract(('name-pointer',0,37,26,25,1,(-16)&p.MASK,1000));self.assertEqual(m.reg['r0'],0)

    def test_invalid_index_or_null_table_stores_error_without_copy(self):
        for count,index,mode in ((26,p.MASK,1),(26,26,1),(0,0,1),(p.MASK,0,1),(26,25,-1)):
            m,r=p.contract(('descriptor-copy',0,37,count,index,mode,0,1000))
            self.assertEqual(m.reg['r0'],(-10)&p.MASK);self.assertEqual(m.buffers[4],r[4][1])
            self.assertNotIn(p.MOVE,[pc for pc,_ in m.trace])

    def test_guards_exclude_literals_and_callbacks_and_refuse_outside_inputs(self):
        m,r=p.contract(('descriptor-copy',0,37,26,25,1,0,1000))
        with patch.object(p.longer,'observe',return_value={}) as seen:p.observe(b'',None,m.before,r)
        kw=seen.call_args.kwargs;self.assertEqual(kw['budget'],512);self.assertEqual(kw['aliases'],())
        for a in (0x06094A22,0x06095DF0,0x06095E08,p.name.status.CALLBACK):self.assertFalse(any(lo<=a<hi for lo,hi in kw['ranges']))
        self.assertEqual(p.name.status.guard.MAX_STEPS,128);self.assertEqual(p.longer.MAX_STEPS,1024)
        for c in (('move',0,37,49,64,65),('descriptor-copy',0,37,27,25,1,0,1000),('descriptor-copy',0,37,26,p.MASK,1,0,4)):
            with self.assertRaises(ValueError):p.contract(c)


if __name__=='__main__':unittest.main()
