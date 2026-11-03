"""Owned name-contract expectations; no original bytes or CPU execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_name as p


class NameContracts(unittest.TestCase):
    def test_entire_selected_model_corpus_fits_guard_and_preserves_inputs(self):
        for family in p.FAMILIES:
            cases=p.cases(family);self.assertTrue(cases);self.assertEqual(len(cases),len(set(cases)))
            for c in cases:
                m,regions=p.contract(c);self.assertLessEqual(len(m.trace),1024)
                self.assertEqual(m.reg['pc'],m.before['pr'])
                for key in ('r15','pr','mach','macl','gbr','vbr'):self.assertEqual(m.reg[key],m.before[key])
                for key in range(10,15):self.assertEqual(m.reg['r'+str(key)],m.before['r'+str(key)])
                for i,(a,b,w) in enumerate(regions):
                    self.assertTrue(0x06000000<=a<a+len(b)<=0x06100000)
                    if not w:self.assertEqual(m.buffers[i],b)
                    for a2,b2,_ in regions[i+1:]:self.assertTrue(a+len(b)<=a2 or a2+len(b2)<=a)

    def test_compare_zero_length_and_early_nul_skip_later_bytes(self):
        m,_=p.contract(('compare',0,0,0,0,255,1,-1));self.assertEqual(m.reg['r0'],0);self.assertEqual(m.events,[])
        m,_=p.contract(('compare',1,37,12,11,128,127,0));self.assertEqual(m.reg['r0'],0)
        self.assertEqual(len([e for e in m.events if e[0]==1]),5)

    def test_compare_uses_unsigned_difference_in_both_directions(self):
        for a,b in ((128,127),(255,0),(0,255),(1,128),(127,128)):
            m,_=p.contract(('compare',0,37,12,0,a,b,-1));self.assertEqual(m.reg['r0'],(a-b)&p.MASK)

    def test_flag_stops_after_mismatch_but_matching_end_record_wins(self):
        for hit,stop,want in ((2,1,p.MASK),(2,2,2),(2,-1,2),(-1,0,p.MASK)):
            m,_=p.contract(('search',0,255,4,hit,stop,5,0,1));self.assertEqual(m.reg['r0'],want)
        m,_=p.contract(('search',1,255,4,3,-1,0,0,1));self.assertEqual(m.reg['r0'],3)

    def test_nonpositive_signed_capacity_skips_all_table_and_query_reads(self):
        for n in (0,p.MASK,0x80000000):
            m,_=p.contract(('search',0,0,n,-1,-1,0,0,1));self.assertEqual(m.reg['r0'],p.MASK)
            self.assertNotIn(p.COMPARE,[pc for pc,_ in m.trace])
            self.assertFalse(any(0x060D4000<=a<0x060D8010 for k,a,s,v in m.events if k==1))

    def test_lookup_keeps_distinct_invalid_notfound_and_success_status_paths(self):
        for g,want in ((0,2),((-16)&p.MASK,(-25)&p.MASK),((-14)&p.MASK,(-2)&p.MASK),((-13)&p.MASK,(-23)&p.MASK)):
            m,_=p.contract(('lookup',0,37,4,2,-1,0,g,1));self.assertEqual(m.reg['r0'],want)
        m,_=p.contract(('lookup',0,37,4,-1,-1,0,0,1));self.assertEqual(m.reg['r0'],(-9)&p.MASK)
        for mode in (0,2,p.MASK,-1):
            m,_=p.contract(('lookup-invalid',0,37,4,2,-1,0,0,mode))
            self.assertEqual(m.reg['r0'],(-8)&p.MASK);self.assertNotIn(p.SEARCH,[pc for pc,_ in m.trace])

    def test_guard_does_not_execute_literals_or_callbacks_and_refuses_bad_inputs(self):
        m,r=p.contract(('lookup',0,37,4,2,-1,0,0,1))
        with patch.object(p.longer,'observe',return_value={}) as seen:p.observe(b'',None,m.before,r)
        kw=seen.call_args.kwargs;self.assertEqual(kw['budget'],1024);self.assertEqual(kw['aliases'],())
        for a in (0x06095CE0,0x06095CE4,0x06095DF4,0x060A5824,p.status.CALLBACK):
            self.assertFalse(any(lo<=a<hi for lo,hi in kw['ranges']))
        self.assertEqual(p.status.guard.MAX_STEPS,128);self.assertEqual(p.longer.MAX_STEPS,1024)
        for c in (('compare',0,37,65,0,1,2,-1),('search',0,37,9,0,-1,0,0,1),('lookup',0,37,4,0,-1,0,0,2)):
            with self.assertRaises(ValueError):p.contract(c)


if __name__=='__main__':unittest.main()
