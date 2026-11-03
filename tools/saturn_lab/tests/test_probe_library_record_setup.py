"""Owned composed expectations only, without executing original game bytes."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_record_setup as p


def owned_literals():
    data=bytearray(p.pinned.SIZE)
    for address,value in {**p.SHORTS,**p.arithmetic.SHORTS}.items():
        data[address-p.pinned.BASE:address-p.pinned.BASE+2]=value.to_bytes(2,'big')
    return bytes(data)


class ComposedRecordContracts(unittest.TestCase):
    def test_every_owned_case_restores_root_and_keeps_explicit_readonly_regions(self):
        data=owned_literals()
        for f in p.FAMILIES:
            cases=p.cases(f);self.assertEqual(len(cases),len(set(cases)))
            self.assertEqual({c[3] for c in cases},set(range(256)))
            for case in cases:
                m,r=p.contract(data,case)
                self.assertEqual(m.reg['r0'],0);self.assertEqual(m.reg['pc'],m.before['pr'])
                for name in ('r9','r10','r11','r12','r13','r14','r15','pr','mach','gbr','vbr'):
                    self.assertEqual(m.reg[name],m.before[name])
                self.assertLessEqual(len(m.trace),768)
                self.assertEqual(m.reg['sr']&1,1)
                for i,(address,buf,write) in enumerate(r):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not write:self.assertEqual(m.buffers[i],buf)
                    for other,value,_ in r[i+1:]:self.assertTrue(address+len(buf)<=other or other+len(value)<=address)

    def test_real_nested_call_paths_are_present_and_service_targets_absent(self):
        data=owned_literals()
        for family in p.FAMILIES:
            m,_=p.contract(data,(family,0,37,128,2049,19));pcs=[pc for pc,_ in m.trace]
            for entry in (p.ENTRY,p.arithmetic.QUOTIENT,p.arithmetic.REMAINDER,p.arithmetic.FORMAT,
                          p.pools.CONTEXT,p.pools.COPY,p.pools.ALLOC0):self.assertIn(entry,pcs)
            for entry in (p.pools.ALLOC24,0x060A7F4E,0x060A4EA0):self.assertNotIn(entry,pcs)
            self.assertEqual(pcs.count(p.arithmetic.REMAINDER),2)
            if family=='caller-failure':
                for entry in (p.setup.CALLER,p.setup.INIT,p.setup.FIELD44,p.setup.FIELD56):self.assertIn(entry,pcs)

    def test_format_zero_skips_remainder_but_still_executes_real_context_failure(self):
        m,_=p.contract(owned_literals(),('record-failure',1,255,24,2049,0))
        pcs=[pc for pc,_ in m.trace];self.assertNotIn(p.arithmetic.REMAINDER,pcs)
        self.assertNotIn(p.arithmetic.QUOTIENT,pcs);self.assertIn(p.pools.CONTEXT,pcs)
        for offset,value in ((8,2049),(16,0),(20,2),(24,0)):
            self.assertEqual(int.from_bytes(m.buffers[1][offset:offset+4],'big'),value)

    def test_rounding_wrap_and_padding_use_separate_scalar_identities(self):
        for flag in (0,16,24,64,128,152,255):
            for n in (0,1,2047,2048,2049,0x7FFFFFFF,0x80000000,p.MASK):
                m,_=p.contract(owned_literals(),('record-failure',0,37,flag,n,p.MASK))
                effective=(p.arithmetic.scalar((n+2047)&p.MASK,2048)[0]*2048)&p.MASK if flag&128 else n
                self.assertEqual(int.from_bytes(m.buffers[1][8:12],'big'),effective)
                fmt=int.from_bytes(m.buffers[1][16:20],'big')
                self.assertEqual(int.from_bytes(m.buffers[1][24:28],'big'),(-effective)&2047 if fmt else 0)
                self.assertEqual(m.reg['macl'],effective if flag&128 else m.before['macl'])

    def test_caller_initialization_and_untouched_error_path_fields(self):
        m,r=p.contract(owned_literals(),('caller-failure',1,255,192,4095,19));buf=m.buffers[1]
        self.assertEqual(buf[:12],r[1][1][:12])
        for offset in (20,44):self.assertEqual(int.from_bytes(buf[108+offset:112+offset],'big'),1)
        self.assertEqual(int.from_bytes(buf[164:168],'big'),3)
        self.assertEqual(buf[156:160],r[1][1][156:160])
        self.assertEqual(buf[88:108],r[1][1][88:108])
        self.assertEqual(m.trace[-2:],[[0x06096DAE,False],[0x06096DB0,True]])

    def test_old_guard_is_unchanged_and_literal_islands_never_executable(self):
        m,r=p.contract(owned_literals(),('record-failure',0,37,0,0,0))
        with patch.object(p.longer,'observe',return_value={}) as seen:
            p.observe(b'',None,'record-failure',m.before,r)
        kw=seen.call_args.kwargs;self.assertEqual(kw['budget'],768);self.assertEqual(kw['aliases'],())
        for point in (0x060A689E,0x060A68A2,0x060A68A4,0x060A68B4,0x060A6DB2,p.pools.ALLOC24):
            self.assertFalse(any(lo<=point<hi for lo,hi in kw['ranges']))
        self.assertEqual(p.pools.short.MAX_STEPS,128);self.assertEqual(p.longer.MAX_STEPS,1024)

    def test_outside_input_and_changed_literals_refuse(self):
        data=owned_literals()
        for c in (('unknown',0,37,0,0,0),('record-failure',2,37,0,0,0),
                  ('record-failure',0,37,256,0,0),('caller-failure',0,37,0,-1,0)):
            with self.assertRaises(ValueError):p.contract(data,c)
        changed=bytearray(data);changed[0x060A68A2-p.pinned.BASE]^=1
        with self.assertRaisesRegex(ValueError,'literal'):p.contract(changed,('record-failure',0,37,0,0,0))


if __name__=='__main__':unittest.main()
