"""Owned slot-contract fixtures; no original-game instructions execute here."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_slots as p


def owned_literals():
    data=bytearray(p.pinned.SIZE)
    for address,value in p.HALFWORDS.items():
        data[address-p.pinned.BASE:address-p.pinned.BASE+2]=value.to_bytes(2,'big')
    return bytes(data)


class SlotContracts(unittest.TestCase):
    def test_corpus_has_distinct_cases_every_first_free_full_and_all_eight_bit_masks(self):
        selected=p.cases('select');self.assertEqual(len(selected),len(set(selected)))
        self.assertEqual(len(selected),3486)
        for count in range(25):
            for free in range(count+1):
                self.assertTrue(any(case[3]==count and
                    next((i for i in range(count) if not case[4]>>i&1),count)==free for case in selected))
        self.assertEqual({case[4]&255 for case in selected if case[3]==8},set(range(256)))
        self.assertEqual(len(p.cases('release')),432)
        with self.assertRaises(ValueError):p.cases('unknown')

    def test_all_owned_models_preserve_stack_linkage_other_memory_and_bounded_addresses(self):
        data=owned_literals();colors=set()
        for family in p.FAMILIES:
            for case in p.cases(family):
                model,regions=p.contract(data,case)
                self.assertEqual(model.reg['pc'],model.before['pr'])
                for name in ('pr','r15','macl','mach','gbr','vbr'):
                    self.assertEqual(model.reg[name],model.before[name])
                self.assertLessEqual(len(model.trace),256 if family=='select' else 128)
                for index,(address,buf,writable) in enumerate(regions):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not writable:self.assertEqual(bytes(model.buffers[index]),buf)
                    for other,value,_ in regions[index+1:]:
                        self.assertTrue(address+len(buf)<=other or other+len(value)<=address)
                if family=='select':
                    colors.update(int.from_bytes(regions[4][1][p.OFFSET+i*p.STRIDE:p.OFFSET+i*p.STRIDE+4],'big')
                                  for i in range(24))
        self.assertEqual(colors,{0,1,0x80000000,p.MASK})

    def test_signed_negative_count_and_zero_have_different_declared_contracts(self):
        data=owned_literals()
        for count in (p.MASK,p.MASK-1,0x80000000):
            model,regions=p.contract(data,('select',0,255,count,0xFFFFFF))
            block=p.tables.BLOCK
            self.assertEqual(model.reg['r0'],block+p.OFFSET)
            self.assertEqual(model.buffers[4][p.OFFSET:p.OFFSET+4],bytes.fromhex('00000001'))
            self.assertEqual(model.reg['r5'],0)
        model,regions=p.contract(data,('select',0,255,0,0xFFFFFF))
        self.assertEqual(model.reg['r0'],0)
        self.assertEqual(bytes(model.buffers[4]),regions[4][1])

    def test_long_loop_requires_separate_profile_and_keeps_original128_guard(self):
        case=('select',0,0,24,0xFFFFFF);model,regions=p.contract(owned_literals(),case)
        self.assertGreater(len(model.trace),128)
        self.assertLessEqual(len(model.trace),256)
        with patch.object(p.longer,'observe',return_value={'owned':True}) as observed:
            p.observe(owned_literals(),None,'select',model.before,regions)
        self.assertEqual(observed.call_args.kwargs['budget'],256)
        with patch.object(p.short,'observe',return_value={'owned':True}) as observed:
            p.observe(owned_literals(),None,'select',model.before,regions,short_refusal=True)
        self.assertEqual(observed.call_args.kwargs['budget'],128)
        self.assertEqual(p.short.MAX_STEPS,128)
        self.assertEqual(p.longer.MAX_STEPS,1024)

    def test_release_has_actual_store_delay_and_only_one_word_changes(self):
        model,regions=p.contract(owned_literals(),('release',1,37,23,p.MASK))
        self.assertEqual(model.trace,[[p.RELEASE,False],[p.RELEASE+2,False],[p.RELEASE+4,True]])
        self.assertEqual(model.events,[[2,model.before['r4'],4,0]])
        self.assertEqual(model.reg['r0'],model.before['r0'])
        self.assertEqual(model.reg['r3'],0)

    def test_out_of_domain_counts_masks_indices_scalars_and_changed_literals_refuse(self):
        data=owned_literals()
        for case in (('select',0,0,25,0),('select',0,0,24,1<<24),('release',0,0,24,0),
                     ('release',0,0,-1,0),('release',0,0,0,True),('select',2,0,1,0),('select',0,1,1,0)):
            with self.subTest(case=case),self.assertRaises(ValueError):p.contract(data,case)
        changed=bytearray(data);changed[0x06096BD8-p.pinned.BASE] ^= 1
        with self.assertRaisesRegex(ValueError,'literal'):p.contract(changed,('select',0,0,1,0))


if __name__=='__main__':unittest.main()
