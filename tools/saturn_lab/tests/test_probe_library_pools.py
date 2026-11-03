"""Owned pool/copy/context expectations only; zero original instruction execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_pools as p


class PoolContracts(unittest.TestCase):
    def test_corpus_distinct_and_every_owned_model_obeys_boundaries_and_preservation(self):
        for family in p.FAMILIES:
            cases=p.cases(family);self.assertTrue(cases);self.assertEqual(len(cases),len(set(cases)))
            for case in cases:
                m,regions=p.contract(case)
                self.assertLessEqual(len(m.trace),512 if family.startswith('context') else 256)
                for name in ('pr','r15','r13','r14'):
                    if family!='context-prefix':self.assertEqual(m.reg[name],m.before[name])
                for name in ('macl','mach','gbr','vbr'):self.assertEqual(m.reg[name],m.before[name])
                for i,(address,buf,write) in enumerate(regions):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not write:self.assertEqual(m.buffers[i],buf)
                    for other,value,_ in regions[i+1:]:self.assertTrue(address+len(buf)<=other or other+len(value)<=address)

    def test_forward_copy_handles_overlap_and_four_byte_pointer_advance(self):
        for length in range(33):
            for delta in (-16,-3,-1,0,1,3,16,64):
                m,r=p.contract(('copy',0,37,length,delta));want=bytearray(r[1][1])
                for i in range(length):want[32+delta+i]=want[32+i]
                self.assertEqual(m.buffers[1],want)
                self.assertEqual(m.reg['r1'],m.before['r1']+length//4*4)
                for name in ('r2','r3','r4'):self.assertEqual(m.reg[name],m.before[name])
                self.assertEqual(m.reg['sr'],(m.before['sr']&~1)|int(length==0))
        m,r=p.contract(('copy',0,37,8,1))
        self.assertEqual(m.buffers[1][33:41],bytes([r[1][1][32]])*8)
        for length in (p.MASK,p.MASK-1,p.MASK-31):
            m,_=p.contract(('copy',1,255,length,64))
            self.assertEqual(sum(e[0]==2 and e[2]==1 for e in m.events),1)

    def test_copy_original_saved_frame_is_independently_checked(self):
        for n in (0,1,4,6,8,32,p.MASK):
            m,_=p.contract(('copy',1,37,n,3))
            self.assertEqual(m.buffers[10],b''.join(m.before[x].to_bytes(4,'big') for x in ('r4','r3','r2')))
            self.assertEqual(m.trace[-2:],[[0x060945E8,False],[0x060945EA,True]])

    def test_allocators_first_zero_full_return_codes_and_other_pool_preserved(self):
        for family,offset,full in (('alloc0',0,-4),('alloc24',24,-3)):
            for seed in (0,37,255):
                for free in range(25):
                    mask=(1<<free)-1;m,r=p.contract((family,1,seed,mask,p.MASK))
                    self.assertEqual(m.reg['r0'],0 if free<24 else full&p.MASK)
                    self.assertEqual(int.from_bytes(m.buffers[1],'big'),free if free<24 else p.MASK)
                    self.assertEqual(m.buffers[4][24-offset:48-offset],r[4][1][24-offset:48-offset])
                    if free<24:self.assertEqual(m.buffers[4][offset+free],1)

    def test_release_requires_exact_marker_one_for_every_byte_and_all_indices(self):
        for index in range(24):
            for marker in range(256):
                m,r=p.contract(('release24',0,37,index,marker))
                self.assertEqual(m.reg['r0'],0 if marker==1 else (-7)&p.MASK)
                self.assertEqual(m.buffers[4][24+index],0 if marker==1 else marker)
                self.assertEqual(m.buffers[4][:24],r[4][1][:24])
        for index in (24,25,0x7FFFFFFF,0x80000000,p.MASK):
            m,r=p.contract(('release24',1,255,index,1))
            self.assertEqual(m.reg['r0'],(-6)&p.MASK)
            self.assertFalse(m.events)

    def test_context_full_failure_and_actual_pending_prefix_have_precise_layout(self):
        for family,mask in (('context-failure',0xFFFFFF),('context-prefix',7)):
            m,r=p.contract((family,1,255,128,mask));base=m.before['r4'];sp=m.before['r15']
            self.assertEqual(m.buffers[1][44:50],bytes([128,0,0,0,0,0]))
            for pos,value in ((28,0),(52,1),(56,p.MASK),(60,0),(64,0),(68,0),(72,0)):
                self.assertEqual(int.from_bytes(m.buffers[1][pos:pos+4],'big'),value)
            self.assertEqual(m.buffers[1][14],128)
            self.assertEqual(m.buffers[1][76:],r[1][1][76:])
            self.assertEqual(m.reg['r0'],0)
            self.assertEqual(m.buffers[10][:12],b''.join(x.to_bytes(4,'big') for x in (base,0x060945B4,sp-20)))
            self.assertEqual(m.buffers[10][-12:],b''.join(m.before[x].to_bytes(4,'big') for x in ('pr','r13','r14')))
            if family=='context-prefix':
                self.assertEqual(m.reg['pc'],p.ALLOC24);self.assertEqual(m.reg['pr'],0x060A7054)
                self.assertEqual(m.reg['r4'],sp-28);self.assertEqual(m.reg['r15'],sp-28)
                self.assertEqual(m.reg['r14'],base+28)
                self.assertEqual(int.from_bytes(m.buffers[1][32:36],'big'),3)
                self.assertFalse(any(pc==p.ALLOC24 for pc,_ in m.trace))
            else:self.assertEqual(m.reg['pc'],m.before['pr'])

    def test_guards_preserve_old128_and_separate_accepted_cap_with_no_aliases(self):
        for family,case,budget in (('alloc24',('alloc24',0,37,0xFFFFFF,0),256),
                                  ('context-prefix',('context-prefix',0,37,128,7),512)):
            m,r=p.contract(case)
            with patch.object(p.longer,'observe',return_value={}) as observed:
                p.observe(b'',None,family,m.before,r)
            self.assertEqual(observed.call_args.kwargs['budget'],budget)
            self.assertEqual(observed.call_args.kwargs['aliases'],())
            if family=='context-prefix':
                kw=observed.call_args.kwargs;self.assertEqual(kw['terminals'][p.ALLOC24],'handoff')
                self.assertFalse(any(lo<=p.ALLOC24<hi for lo,hi in kw['ranges']))
        self.assertEqual(p.short.MAX_STEPS,128);self.assertEqual(p.longer.MAX_STEPS,1024)

    def test_outside_contracts_refuse_before_execution(self):
        for c in (('copy',0,0,33,64),('copy',0,0,1,65),('alloc0',0,1,0,0),
                  ('alloc24',0,37,1<<24,0),('release24',0,37,-1,1),
                  ('context-failure',0,37,1,0),('context-prefix',0,37,1,0xFFFFFF)):
            with self.subTest(case=c),self.assertRaises(ValueError):p.contract(c)


if __name__=='__main__':unittest.main()
