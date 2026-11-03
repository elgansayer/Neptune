"""Owned models and fences only; these fixtures execute no original game code."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_library_setup as p


class SetupContracts(unittest.TestCase):
    def test_case_corpus_is_distinct_and_covers_ordinary_and_wide_values(self):
        for family in p.FAMILIES:
            selected=p.cases(family);self.assertEqual(len(selected),len(set(selected)))
            self.assertGreater(len(selected),200)
            self.assertEqual({row[1] for row in selected},{0,1})
            if family.startswith('index'):
                self.assertTrue(set(range(256))<={row[3] for row in selected})
                self.assertTrue({0,1,0x060BF198,0x80000000,p.MASK}<={row[4] for row in selected})
            elif not family.startswith('caller'):
                self.assertTrue(set(range(256))<={row[3] for row in selected})
        with self.assertRaises(ValueError):p.cases('unresolved')

    def test_all_models_keep_declared_bytes_and_source_stack_register_fences(self):
        for family in p.FAMILIES:
            for case in p.cases(family):
                model,regions=p.contract(case);before=model.before;handoff=family=='caller-prefix'
                self.assertEqual(model.reg['pc'],p.TARGET if handoff else before['pr'])
                for name in ('mach','macl','gbr','vbr'):
                    self.assertEqual(model.reg[name],before[name])
                if not handoff:
                    for name in ('r13','r14','r15','pr'):self.assertEqual(model.reg[name],before[name])
                self.assertLessEqual(len(model.trace),64)
                for i,(address,buf,write) in enumerate(regions):
                    self.assertTrue(0x06000000<=address<address+len(buf)<=0x06100000)
                    if not write:self.assertEqual(bytes(model.buffers[i]),buf)
                    for other,value,_ in regions[i+1:]:
                        self.assertTrue(address+len(buf)<=other or other+len(value)<=address)

    def test_index_equations_include_wrapping_and_instruction_T_effects(self):
        for family,stride in (('index12',12),('index24',24)):
            for case in p.cases(family):
                model,_=p.contract(case);a,b=case[3:]
                self.assertEqual(model.reg['r0'],(stride*a+b)&p.MASK)
                self.assertEqual(model.reg['r3'],a)
                t=(a>>31) if stride==12 else (((a*12)&p.MASK)>>31)
                self.assertEqual(model.reg['sr'],(model.before['sr']&~1)|t)
                self.assertEqual(model.events,[])
        low,_=p.contract(('index24',0,0,0x15555555,0))
        wrapped,_=p.contract(('index24',0,0,0x15555556,0))
        self.assertEqual(low.reg['sr']&1,1)
        self.assertEqual(wrapped.reg['sr']&1,0)

    def test_initializer_calls_real_setters_and_preserves_unwritten_field48(self):
        model,regions=p.contract(('init',0,37,0xDEADBEEF,0x80000000))
        self.assertEqual(model.buffers[1][48:52],regions[1][1][48:52])
        self.assertEqual([row for row in model.trace if p.FIELD56<=row[0]<0x060A5F32],
                         [[p.FIELD44,False],[p.FIELD44+2,True]]+
                         [[p.FIELD56+i,i==10] for i in range(0,12,2)])
        self.assertEqual(model.reg['r0'],model.before['r4'])
        self.assertEqual(model.reg['r5'],0)
        self.assertEqual(model.reg['sr'],model.before['sr'])

    def test_field_setters_return_the_declared_values_and_real_store_delays(self):
        for family in ('field56','field44'):
            model,regions=p.contract((family,1,255,0xDEADBEEF,0x12345678))
            self.assertTrue(model.trace[-1][1])
            self.assertEqual(model.reg['r0'],0x12345678 if family=='field56' else model.before['r0'])
            self.assertEqual(model.reg['r5'],0 if family=='field56' else 0xDEADBEEF)
            self.assertEqual(model.reg['sr'],model.before['sr'])

    def test_real_caller_prefix_retains_saved_frame_and_restores_next_call_arguments(self):
        model,regions=p.contract(('caller-prefix',1,37,0x060BF198,25));before=model.before
        self.assertEqual(model.reg['pc'],p.TARGET)
        self.assertEqual(model.reg['r4'],before['r4']+12)
        self.assertEqual(model.reg['r5'],before['r5'])
        self.assertEqual(model.reg['r6'],before['r6'])
        self.assertEqual(model.reg['r0'],before['r4']+108)
        self.assertEqual(model.reg['r15'],before['r15']-16)
        self.assertEqual(model.reg['pr'],0x06096DA2)
        self.assertEqual(bytes(model.buffers[1][:108]),regions[1][1][:108])
        self.assertEqual(model.reg['sr']&1,0)
        self.assertNotIn([p.TARGET,False],model.trace)
        self.assertEqual(model.trace[-1],[0x06096DA0,True])
        null,_=p.contract(('caller-null',1,255,0xDEADBEEF,0x80000000))
        self.assertEqual(null.reg['r0'],0);self.assertEqual(null.reg['sr']&1,1)
        self.assertFalse(any(p.INIT<=row[0]<0x060A5F32 for row in null.trace))

    def test_fences_keep_A681A_nonexecutable_and_original_guard_unchanged(self):
        model,regions=p.contract(('caller-prefix',0,0,1,25))
        with patch.object(p.guard,'observe',return_value={'owned':True}) as observed:
            p.observe(bytes(p.pinned.SIZE),None,'caller-prefix',model.before,regions)
        args=observed.call_args.kwargs
        self.assertEqual(args['budget'],64)
        self.assertEqual(args['terminals'][p.TARGET],'handoff')
        self.assertFalse(any(lo<=p.TARGET<hi for lo,hi in args['ranges']))
        self.assertEqual(args['aliases'],())
        self.assertEqual(p.guard.MAX_STEPS,128)

    def test_bad_family_variants_seeds_and_non_uint32_arguments_refuse(self):
        for case in (('unknown',0,0,0,0),('init',2,0,0,0),('init',0,1,0,0),
                     ('index12',0,0,True,0),('field56',0,0,-1,0),('caller-prefix',0,0,0,1<<32)):
            with self.subTest(case=case),self.assertRaises(ValueError):p.contract(case)

    def test_control_failure_keeps_completed_owned_records(self):
        case=('field44',0,0,1,0)
        row={'case':list(case),'status':'returned','owned_fixture':True}
        with patch.object(p,'cases',return_value=[case]),patch.object(p,'run_case',return_value=row):
            with self.assertRaises(p.EvidenceFailure) as caught:p.execute(bytes(p.pinned.SIZE),None,'field44')
        self.assertEqual(caught.exception.partial['results'],[row])
        self.assertEqual(caught.exception.partial['failed_control']['name'],'lost-store-delay')
        self.assertEqual(caught.exception.partial['complete_returns'],1)

    def test_later_case_failure_keeps_preceding_owned_results(self):
        case=('field44',0,0,1,0);row={'owned_fixture':True,'status':'returned'}
        error=p.task.CaseFailure('owned failure',case,{'regions_after':[],'owned_fixture':True})
        with patch.object(p,'cases',return_value=[case,case]),patch.object(p,'run_case',side_effect=[row,error]):
            with self.assertRaises(p.task.CaseFailure) as caught:p.execute(bytes(p.pinned.SIZE),None,'field44')
        self.assertEqual(caught.exception.completed_results,[row])


if __name__=='__main__':unittest.main()
