"""Owned packet/frame expectations; no original bytes or CPU execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_cd_command_packing as p


class CommandPackingContracts(unittest.TestCase):
    def test_all_selected_models_fit_original_guard_and_preserve_readonly_bytes(self):
        for family in p.FAMILIES:
            cases=p.cases(family);self.assertTrue(cases);self.assertEqual(len(cases),len(set(cases)))
            for c in cases:
                m,r=p.contract(c);self.assertLessEqual(len(m.trace),64)
                for key in ('sr','mach','macl','gbr','vbr','r1','r2','r8','r9','r10','r11','r12'):self.assertEqual(m.reg[key],m.before[key])
                for i,(a,b,w) in enumerate(r):
                    self.assertTrue(0x06000000<=a<a+len(b)<=0x06100000)
                    if not w:self.assertEqual(m.buffers[i],b)
                    for a2,b2,_ in r[i+1:]:self.assertTrue(a+len(b)<=a2 or a2+len(b2)<=a)

    def test_48_packet_uses_only_low_bytes_and_zeroes_every_unused_byte(self):
        m,_=p.contract(('pack48',0,37,0xAABBCCDD,0x12345678,p.MASK))
        self.assertEqual(m.buffers[1][:8],bytes.fromhex('48dd000078000000'))
        self.assertEqual(m.reg['r0'],0x12345678);self.assertEqual(m.reg['r6'],0)
        self.assertEqual(m.reg['r4'],64)

    def test_62_packet_distinguishes_byte_and_big_endian_word_truncation(self):
        m,_=p.contract(('pack62',1,255,0xAABBCCDD,0x11223344,0x55667788))
        self.assertEqual(m.buffers[1][:8],bytes.fromhex('62003344dd007788'))
        self.assertEqual(m.reg['r0'],0x55667788);self.assertEqual(m.reg['r6'],0x55667788)
        self.assertEqual(m.reg['r4'],128);self.assertEqual(m.reg['r7'],0)

    def test_direct_service_entry_keeps_actual_root_frame_and_delay_arguments(self):
        for f,link in (('pack48',0x060AE698),('pack62',0x060AE92E)):
            m,_=p.contract((f,0,37,1,2,3));sp=m.before['r15']
            self.assertEqual(m.reg['r15'],sp-16);self.assertEqual(m.reg['pr'],link);self.assertEqual(m.reg['pc'],p.SERVICE)
            self.assertEqual(m.reg['r5'],sp-16);self.assertEqual(m.buffers[1][-8:-4],m.before['pr'].to_bytes(4,'big'))
            self.assertEqual(m.buffers[1][-4:],m.before['r14'].to_bytes(4,'big'))
            self.assertNotIn(p.SERVICE,[pc for pc,_ in m.trace]);self.assertTrue(m.trace[-1][1])

    def test_composed_entry_retains_uninitialised_response_and_local_canaries(self):
        for f in ('service48','service62'):
            m,r=p.contract((f,1,255,0x11223344,0x55667788,0xDEADBEEF));sp=m.before['r15']
            self.assertEqual(m.reg['pc'],p.TARGET);self.assertEqual(m.reg['pr'],0x060A4FD0)
            self.assertEqual(m.reg['r15'],sp-48);self.assertEqual(m.reg['r6'],sp-28);self.assertEqual(m.reg['r7'],1)
            self.assertEqual(m.buffers[1][20:28],r[1][1][20:28]);self.assertEqual(m.buffers[1][4:8],r[1][1][4:8])
            self.assertEqual(m.buffers[1][:4],bytes.fromhex('00000001'));self.assertIn(p.SERVICE,[pc for pc,_ in m.trace])
            self.assertNotIn(p.TARGET,[pc for pc,_ in m.trace])

    def test_guards_exclude_return_code_literals_and_pending_service_bodies(self):
        for family,target in (('pack48',p.SERVICE),('service62',p.TARGET)):
            m,r=p.contract((family,0,37,1,2,3))
            with patch.object(p.guard,'observe',return_value={}) as seen:p.observe(b'',None,m.before,r,family.startswith('service'))
            kw=seen.call_args.kwargs;self.assertEqual(kw['terminals'],{target:'handoff'})
            self.assertEqual(kw['budget'],64);self.assertEqual(kw['aliases'],());self.assertEqual(p.guard.MAX_STEPS,128)
            for a in (target,0x060AE698,0x060AE92E,0x060AEA30,0x060A4FD0):self.assertFalse(any(lo<=a<hi for lo,hi in kw['ranges']))

    def test_input_domains_and_root_arguments_are_explicit(self):
        for f in p.FAMILIES:
            m,_=p.contract((f,1,37,p.MASK,0x80000000,0x7FFFFFFF))
            self.assertEqual(m.before['r4'],p.MASK);self.assertEqual(m.before['r5'],0x80000000);self.assertEqual(m.before['r6'],0x7FFFFFFF)
        for c in (('pack48',2,37,0,0,0),('pack62',0,37,-1,0,0),('pack48',0,37,0x100000000,0,0)):
            with self.assertRaises(ValueError):p.contract(c)


if __name__=='__main__':unittest.main()
