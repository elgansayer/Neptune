"""Owned full-library error expectations; zero original instruction execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_open_errors as p


def owned_literals():
    b=bytearray(p.pinned.SIZE)
    values={**p.record.SHORTS,**p.record.arithmetic.SHORTS,**p.status.HALFWORDS,**p.slots.HALFWORDS,**p.SHORTS}
    for a,v in values.items():b[a-p.pinned.BASE:a-p.pinned.BASE+2]=v.to_bytes(2,'big')
    return bytes(b)


class OpenErrorContracts(unittest.TestCase):
    def test_all_owned_models_fit_current_cap_and_restore_root_readonly_data(self):
        data=owned_literals()
        for family in p.FAMILIES:
            cases=p.cases(family);self.assertEqual(len(cases),len(set(cases)))
            for c in cases:
                m,r=p.contract(data,c)
                self.assertEqual(m.reg['r0'],0);self.assertEqual(m.reg['pc'],m.before['pr'])
                self.assertLessEqual(len(m.trace),1024)
                for name in ('r12','r13','r14','r15','pr','mach','gbr','vbr'):self.assertEqual(m.reg[name],m.before[name])
                for i,(address,buf,write) in enumerate(r):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not write:self.assertEqual(m.buffers[i],buf)
                    for other,value,_ in r[i+1:]:self.assertTrue(address+len(buf)<=other or other+len(value)<=address)

    def test_invalid_indices_report_before_any_selection_or_record_access(self):
        for index in (p.MASK,p.MASK-1,0x80000000,24,25,0x7FFFFFFF):
            m,r=p.contract(owned_literals(),('invalid-index',1,255,0,24,0,index,255,2049))
            pcs=[pc for pc,_ in m.trace]
            self.assertNotIn(p.slots.SELECT,pcs);self.assertNotIn(p.record.ENTRY,pcs)
            self.assertIn(p.status.STATUS,pcs)
            self.assertEqual(int.from_bytes(m.buffers[1][0xC0:0xC4],'big'),(-10)&p.MASK)
            self.assertEqual(m.buffers[1][p.slots.OFFSET:],r[1][1][p.slots.OFFSET:])

    def test_no_slots_report_distinct_code_with_unchanged_all_markers(self):
        for count in range(25):
            m,r=p.contract(owned_literals(),('no-slot',0,37,0,count,0xFFFFFF,0,255,2049))
            pcs=[pc for pc,_ in m.trace]
            self.assertIn(p.slots.SELECT,pcs);self.assertNotIn(p.record.setup.CALLER,pcs)
            self.assertEqual(int.from_bytes(m.buffers[1][0xC0:0xC4],'big'),(-19)&p.MASK)
            self.assertEqual(m.buffers[1][p.slots.OFFSET:],r[1][1][p.slots.OFFSET:])

    def test_full_failed_setup_keeps_allocated_marker_and_original_slot_header(self):
        for family in ('record12','record24'):
            m,r=p.contract(owned_literals(),(family,1,255,0,24,(1<<23)-1,23,255,2049))
            offset=p.slots.OFFSET+23*p.slots.STRIDE;body=m.buffers[1]
            self.assertEqual(int.from_bytes(body[offset:offset+4],'big'),1)
            self.assertEqual(body[offset+4:offset+12],r[1][1][offset+4:offset+12])
            self.assertEqual(body[offset+156:offset+160],r[1][1][offset+156:offset+160])
            self.assertEqual(int.from_bytes(body[offset+12:offset+16],'big'),23)
            self.assertEqual(int.from_bytes(body[offset+16:offset+20],'big'),(0xDEADBEEF^(23*0x01010101))&p.MASK)
            self.assertEqual(int.from_bytes(body[0xC0:0xC4],'big'),(-10)&p.MASK)
            pcs=[pc for pc,_ in m.trace]
            for entry in (p.slots.SELECT,p.record.setup.CALLER,p.record.ENTRY,p.record.pools.CONTEXT,p.status.STATUS):self.assertIn(entry,pcs)
            self.assertNotIn(p.record.pools.ALLOC24,pcs);self.assertNotIn(p.status.CALLBACK,pcs)

    def test_status_overrides_are_composed_in_all_error_branches(self):
        for family in p.FAMILIES:
            for source,want in p.status.MAPPINGS.items():
                c=(family,0,37,source,24,0xFFFFFF if family=='no-slot' else 0,p.MASK if family=='invalid-index' else 0,128,2049)
                m,_=p.contract(owned_literals(),c)
                self.assertEqual(int.from_bytes(m.buffers[1][0xC0:0xC4],'big'),want)
                self.assertEqual(m.reg['r0'],0)

    def test_record_strides_are_real_distinct_inputs_and_high_mode_words_work(self):
        for family,entry,stride in (('record12',p.record.setup.INDEX12,12),('record24',p.record.setup.INDEX24,24)):
            for seed in (0,37,255):
                m,r=p.contract(owned_literals(),(family,0,seed,0,24,0,23,24,2049));pcs=[pc for pc,_ in m.trace]
                self.assertIn(entry,pcs)
                ptr=0x060D4000+23*stride
                self.assertTrue(any(kind==1 and address==ptr and size==4 for kind,address,size,_ in m.events))
                self.assertNotEqual(r[4][1][:12],r[4][1][23*stride:23*stride+12])

    def test_negative_counts_keep_real_selection_behavior_in_full_caller(self):
        for count in (p.MASK,p.MASK-1,0x80000000):
            m,r=p.contract(owned_literals(),('record12',0,37,0,count,0xFFFFFF,19,128,2049))
            offset=p.slots.OFFSET
            self.assertEqual(int.from_bytes(m.buffers[1][offset:offset+4],'big'),1)
            self.assertEqual(m.buffers[1][offset+p.slots.STRIDE:],r[1][1][offset+p.slots.STRIDE:])

    def test_old_guard_and_literal_islands_stay_unchanged_with_strict_input_refusal(self):
        m,r=p.contract(owned_literals(),('record12',0,37,0,24,0,0,128,2049))
        with patch.object(p.longer,'observe',return_value={}) as seen:p.observe(b'',None,'record12',m.before,r)
        kw=seen.call_args.kwargs;self.assertEqual(kw['budget'],1024);self.assertEqual(kw['aliases'],())
        for address in (0x06095EEE,0x060A68A2,0x060A6DB2,p.record.pools.ALLOC24,p.status.CALLBACK):
            self.assertFalse(any(lo<=address<hi for lo,hi in kw['ranges']))
        self.assertEqual(p.slots.short.MAX_STEPS,128);self.assertEqual(p.longer.MAX_STEPS,1024)
        bad=[('record12',0,37,0,24,0,p.MASK,0,0),('record24',0,37,0,0,0,0,0,0),
             ('no-slot',0,37,0,24,0,0,0,0),('invalid-index',0,37,0,24,0,0,0,0),
             ('record12',0,37,0,25,0,0,0,0)]
        for c in bad:
            with self.assertRaises(ValueError):p.contract(owned_literals(),c)


if __name__=='__main__':unittest.main()
