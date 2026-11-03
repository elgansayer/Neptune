"""Owned request-state models; no original kernel or CPU execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_request_state as p


class RequestStateContracts(unittest.TestCase):
    def test_whole_selected_corpus_preserves_declared_bytes_and_bounds(self):
        for f in p.FAMILIES:
            cases=p.cases(f);self.assertTrue(cases);self.assertEqual(len(cases),len(set(cases)))
            for c in cases:
                m,r=p.contract(c);self.assertLessEqual(len(m.trace),64)
                for key in ('mach','macl','gbr','vbr','r8','r9','r10','r11','r12','r13','r14'):self.assertEqual(m.reg[key],m.before[key])
                for i,(a,b,w) in enumerate(r):
                    self.assertTrue(0x06000000<=a<a+len(b)<=0x06100000)
                    if not w:self.assertEqual(m.buffers[i],b)
                    for a2,b2,_ in r[i+1:]:self.assertTrue(a+len(b)<=a2 or a2+len(b2)<=a)

    def test_store_changes_only_field60_and_preserves_result_sr_and_link(self):
        for value in (0,0x30000,p.MASK,0x80000000):
            m,r=p.contract(('store',0,37,value,0,0,0,0));expected=bytearray(r[1][1]);expected[60:64]=value.to_bytes(4,'big')
            self.assertEqual(m.buffers[1],expected)
            for key in ('r0','sr','pr','r15'):self.assertEqual(m.reg[key],m.before[key])
            self.assertEqual(m.trace[-1],[p.STORE+6,True])

    def test_poll_tests_any_nonzero_flag_and_exact_requested_index(self):
        for flag,index,want in ((0,23,1),(1,23,0),(2,23,0),(p.MASK,23,0),(1,24,1)):
            m,_=p.contract(('poll',0,37,flag,23,index,0,0));self.assertEqual(m.reg['r0'],want)
            self.assertFalse(any(e[0]==2 for e in m.events));self.assertEqual(m.reg['pc'],m.before['pr'])

    def test_busy_request_precedes_same_index_check_and_preserves_all_fields(self):
        m,r=p.contract(('request',0,37,1,23,23,p.MASK,0));self.assertEqual(m.reg['r0'],p.MASK)
        self.assertEqual(m.buffers[1],r[1][1]);self.assertNotIn(0x060A7BC8,[a for a,_ in m.trace])
        self.assertEqual(m.reg['r15'],m.before['r15']);self.assertEqual(m.reg['pr'],m.before['pr'])

    def test_same_index_returns_minus5_without_queuing(self):
        m,r=p.contract(('request',1,255,0,23,23,0,p.MASK));self.assertEqual(m.reg['r0'],(-5)&p.MASK)
        self.assertEqual(m.buffers[1],r[1][1]);self.assertEqual(m.reg['pc'],m.before['pr'])

    def test_queued_request_keeps_actual_arguments_and_pending_original_frame(self):
        m,r=p.contract(('request',1,255,0,23,24,p.MASK,0x80000000))
        self.assertEqual(m.buffers[1][0x338:0x348],b''.join(v.to_bytes(4,'big') for v in (1,23,p.MASK,0x80000000)))
        self.assertEqual(m.reg['pc'],p.TARGET);self.assertNotIn(p.TARGET,[a for a,_ in m.trace])
        self.assertEqual(m.reg['pr'],0x060A7C16);self.assertEqual(m.reg['r15'],m.before['r15']-8)
        self.assertEqual(m.reg['r4'],m.reg['r15']);self.assertEqual(m.buffers[7][:4],r[7][1][:4])

    def test_original_guard_and_nonexecutable_service_boundary_stay_explicit(self):
        m,r=p.contract(('request',0,37,0,23,24,0,p.MASK))
        with patch.object(p.guard,'observe',return_value={}) as seen:p.observe(b'',None,m.before,r)
        kw=seen.call_args.kwargs;self.assertEqual(kw['budget'],64);self.assertEqual(kw['aliases'],())
        self.assertEqual(kw['terminals'][p.TARGET],'handoff');self.assertEqual(p.guard.MAX_STEPS,128)
        for a in (p.TARGET,0x060A7BDC,0x060A7BEC,0x060A7C16):self.assertFalse(any(lo<=a<hi for lo,hi in kw['ranges']))
        for c in (('request',0,37,-1,0,0,0,0),('store',2,37,0,0,0,0,0)):
            with self.assertRaises(ValueError):p.contract(c)


if __name__=='__main__':unittest.main()
