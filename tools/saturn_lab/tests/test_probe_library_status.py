"""Owned contract fixtures only; these tests do not execute original game code."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_status as p


def owned_literals():
    data = bytearray(p.pinned.SIZE)
    for address,value in p.HALFWORDS.items():
        data[address-p.pinned.BASE:address-p.pinned.BASE+2] = value.to_bytes(2,'big')
    return bytes(data)


class LibraryStatusContracts(unittest.TestCase):
    def test_status_classes_and_setter_cover_signed_status_bytes_zero_and_callback_cases(self):
        selected = p.cases('status')
        self.assertEqual(len(selected),4256)
        self.assertTrue({n&p.MASK for n in range(-128,128)} <= {case[3] for case in selected})
        for status in (0,(-16)&p.MASK,(-14)&p.MASK,(-13)&p.MASK,0x80000000,0x7FFFFFFF):
            for callback in (0,p.CALLBACK):
                self.assertTrue(any(case[3:5]==(status,callback) and case[5]==0 for case in selected))
        self.assertEqual(len(p.cases('setter')),256)
        with self.assertRaises(ValueError): p.cases('unknown')

    def test_all_owned_models_preserve_source_canaries_and_restore_visible_linkage(self):
        data = owned_literals()
        for family in p.FAMILIES:
            for case in p.cases(family):
                entry,model,regions = p.contract(data,case)
                self.assertEqual(model.reg['pc'],model.before['pr'])
                for name in ('r13','r14','r15','pr','mach','macl','gbr','vbr'):
                    self.assertEqual(model.reg[name],model.before[name])
                self.assertLessEqual(len(model.trace),128)
                for (_,buf,writable),after in zip(regions,model.buffers):
                    if not writable: self.assertEqual(bytes(after),buf)
                for i,(address,buf,_) in enumerate(regions):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    self.assertTrue(all(address+len(buf)<=other or other+len(value)<=address
                                        for other,value,_ in regions[i+1:]))
        self.assertEqual(data,owned_literals())

    def test_real_callback_boundary_only_runs_for_nonzero_effective_error(self):
        for status,argument,expected in ((0,0,0),(0,1,1),((-16)&p.MASK,0,(-25)&p.MASK),
                                         ((-14)&p.MASK,7,(-2)&p.MASK),((-13)&p.MASK,8,(-23)&p.MASK)):
            for callback in (0,p.CALLBACK):
                case=('status',0,37,status,callback,argument,0x12345678)
                _,model,regions=p.contract(owned_literals(),case)
                self.assertEqual(model.reg['r0'],expected)
                calls=[row for row in model.trace if row[0] in (p.CALLBACK,p.CALLBACK+2)]
                self.assertEqual(calls,[[p.CALLBACK,False],[p.CALLBACK+2,True]] if expected and callback else [])
                if calls:
                    self.assertEqual(model.reg['r4'],0x12345678)
                    self.assertEqual(model.reg['r5'],expected)
                    self.assertEqual(model.reg['sr']&1,0)
                else:self.assertEqual(model.reg['sr']&1,1)

    def test_setter_tail_clears_argument_and_uses_original_callback_for_mapped_error(self):
        for status in (0,(-16)&p.MASK):
            _,model,regions=p.contract(owned_literals(),('setter',1,255,status,p.CALLBACK,0,0xFEDCBA98))
            self.assertEqual(model.buffers[7],p.CALLBACK.to_bytes(4,'big'))
            self.assertEqual(model.buffers[8],bytes.fromhex('fedcba98'))
            self.assertIn([p.SETTER+16,True],model.trace)
            self.assertEqual(model.reg['r0'],p.effective(status,0))
            self.assertEqual(model.reg['r4'],0xFEDCBA98 if status else 0)

    def test_unknown_callbacks_bad_scalars_and_changed_original_literals_are_refused(self):
        data=owned_literals(); case=list(p.cases('status')[0])
        for index,value in ((4,p.CALLBACK+4),(3,-1),(5,1<<32),(6,True)):
            changed=case[:];changed[index]=value
            with self.assertRaises(ValueError):p.contract(data,changed)
        changed=bytearray(data);changed[0x06096CE4-p.pinned.BASE] ^= 1
        with self.assertRaisesRegex(ValueError,'literal'):p.contract(changed,case)

    def test_observer_requires_real_callback_range_without_weakening_original128_guard(self):
        before={'pc':p.STATUS,'pr':0xFFFFFFF0}
        with patch.object(p.guard,'observe',return_value={'owned':True}) as observed:
            self.assertEqual(p.observe(owned_literals(),None,'status',before,[]),{'owned':True})
        args=observed.call_args.kwargs
        self.assertEqual(args['budget'],128)
        self.assertEqual(args['aliases'],())
        self.assertEqual(args['ranges'],((p.STATUS,0x06096CB0),(p.CALLBACK,p.CALLBACK+4)))
        self.assertEqual(p.guard.MAX_STEPS,128)


if __name__=='__main__':unittest.main()
