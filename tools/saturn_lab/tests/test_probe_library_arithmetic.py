"""Owned manual/math models only; no original instructions execute in these tests."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_arithmetic as p


def owned_literals():
    data=bytearray(p.pinned.SIZE)
    for address,value in p.SHORTS.items():
        data[address-p.pinned.BASE:address-p.pinned.BASE+2]=value.to_bytes(2,'big')
    return bytes(data)


class ArithmeticContracts(unittest.TestCase):
    def test_distinct_corpus_covers_signed_bytes_wide_inputs_and_all_initial_flags(self):
        for family in p.FAMILIES:
            rows=p.cases(family);self.assertEqual(len(rows),len(set(rows)))
            self.assertEqual({case[1] for case in rows},{0,1})
            if family=='format':
                self.assertEqual({case[3]&255 for case in rows},set(range(256)))
                self.assertEqual(len(rows),3072)
            else:
                self.assertTrue({n&p.MASK for n in range(-128,128)}<={case[3] for case in rows})
                self.assertEqual({case[5] for case in rows if case[4]==0},set(range(8)))
                self.assertTrue(any(case[3:5]==(0x80000000,p.MASK) for case in rows))
        with self.assertRaises(ValueError):p.cases('unknown')

    def test_all_owned_models_agree_with_independent_math_restore_frames_and_preserve_canaries(self):
        data=owned_literals()
        for family in p.FAMILIES:
            for case in p.cases(family):
                model,regions=p.contract(data,case);before=model.before
                self.assertEqual(model.reg['pc'],before['pr'])
                self.assertLessEqual(len(model.trace),128)
                for name in ('r15','pr','macl','mach','gbr','vbr'):
                    self.assertEqual(model.reg[name],before[name])
                if family!='format':
                    for name in ('r2','r3','r4'):self.assertEqual(model.reg[name],before[name])
                    q,r=p.scalar(case[3],case[4]);self.assertEqual(model.reg['r0'],q if family=='quotient' else r)
                for i,(address,buf,write) in enumerate(regions):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not write:self.assertEqual(bytes(model.buffers[i]),buf)
                    for other,value,_ in regions[i+1:]:
                        self.assertTrue(address+len(buf)<=other or other+len(value)<=address)
        self.assertEqual(data,owned_literals())

    def test_signed_scalar_uses_truncation_zero_and_machine_overflow_representation(self):
        self.assertEqual(p.scalar((-7)&p.MASK,3),((-2)&p.MASK,(-1)&p.MASK))
        self.assertEqual(p.scalar(7,(-3)&p.MASK),((-2)&p.MASK,1))
        self.assertEqual(p.scalar(0x80000000,p.MASK),(0x80000000,0))
        self.assertEqual(p.scalar(1,0),(0,0))

    def test_quotient_flags_have_independent_closed_formula(self):
        for n,d in ((0,p.MASK),(1,(-2)&p.MASK),((-1)&p.MASK,2),(0x80000000,p.MASK),
                    (0x7FFFFFFF,1),(0x80000000,0x80000000)):
            model,_=p.contract(owned_literals(),('quotient',0,37,n,d,7))
            q,_=p.scalar(n,d);adjust=(n^d)>>31;pre=(q-adjust)&p.MASK
            self.assertEqual((model.reg['sr']>>9)&1,d>>31)
            self.assertEqual((model.reg['sr']>>8)&1,(d>>31)^int(not(pre&1)))
            self.assertEqual(model.reg['sr']&1,int(q==0 and bool(adjust)))

    def test_zero_divisor_writes_error_and_preserves_all_MQ_inputs(self):
        for family in ('quotient','remainder'):
            for flags in range(8):
                model,regions=p.contract(owned_literals(),(family,0,37,0x80000000,0,flags))
                self.assertEqual(model.reg['r0'],0)
                self.assertEqual(model.reg['r1'],p.ERROR_CELL)
                self.assertEqual(model.reg['sr'],model.before['sr']|1)
                self.assertEqual(model.buffers[1],bytes.fromhex('0000044e'))
                self.assertEqual(len(model.trace),9)
                self.assertEqual(sum(event[0]==2 and event[1]==p.ERROR_CELL for event in model.events),1)

    def test_remainder_correction_paths_and_exact_full_flags_are_part_of_model(self):
        seen=set()
        for n in range(-16,17):
            for d in (-8,-3,-1,1,2,7):
                model,_=p.contract(owned_literals(),('remainder',1,0,n&p.MASK,d&p.MASK,0))
                seen.add(any(pc==0x06094308 for pc,_ in model.trace))
                self.assertEqual(model.reg['sr']&~0x301,model.before['sr']&~0x301)
        self.assertEqual(seen,{False,True})

    def test_format_mapping_and_upper_bits_do_not_change_result(self):
        data=owned_literals()
        for low in range(256):
            index=(int(bool(low&64))<<2)|(int(bool(low&16))<<1)|int(bool(low&8))
            expected=(2048,2048,2324,0,2352,2352,2352,2352)[index]
            for high in (0,0x80000000,0xFFFFFF00):
                model,_=p.contract(data,('format',0,37,high|low,0,7))
                self.assertEqual(model.reg['r0'],expected)
                self.assertEqual(model.reg['sr']&~1,model.before['sr']&~1)
                self.assertFalse(any(event[0]==2 for event in model.events))

    def test_old_guard_stays128_and_literal_island_is_not_executable(self):
        model,regions=p.contract(owned_literals(),('format',0,0,64,0,7))
        with patch.object(p.guard,'observe',return_value={'owned':True}) as observed:
            p.observe(owned_literals(),None,'format',model.before,regions)
        args=observed.call_args.kwargs
        self.assertEqual(args['budget'],128);self.assertEqual(p.guard.MAX_STEPS,128)
        self.assertFalse(any(lo<=0x060A6DB2<hi for lo,hi in args['ranges']))
        self.assertEqual(args['aliases'],())

    def test_invalid_flags_scalars_and_changed_format_literals_refuse(self):
        data=owned_literals()
        for case in (('unknown',0,0,0,0,0),('quotient',2,0,0,1,0),('quotient',0,0,-1,1,0),
                     ('remainder',0,0,1,True,0),('format',0,0,0,0,8)):
            with self.subTest(case=case),self.assertRaises(ValueError):p.contract(data,case)
        changed=bytearray(data);changed[0x060A6E90-p.pinned.BASE] ^= 1
        with self.assertRaisesRegex(ValueError,'literal'):p.contract(changed,('format',0,0,0,0,0))


if __name__=='__main__':unittest.main()
