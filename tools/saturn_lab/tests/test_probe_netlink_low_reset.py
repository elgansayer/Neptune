"""Owned contract and failure fixtures; real originals run separately."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_low_reset as p


class LowResetTests(unittest.TestCase):
    def test_complete_fixed_data_clear_preserves_neighbors_stack_and_other_registers(self):
        device={'unchanged':'sentinel'}
        before,regions,expected=p.contract(0x12345678,0x271F,1,device)
        self.assertEqual(expected['registers'][0],0)
        self.assertEqual(expected['registers'][8],0x790)
        self.assertEqual(expected['registers'][15:],[p.leaf.SP+4,p.leaf.STOP,0x2714])
        for i in range(15):
            if i not in (0,8):self.assertEqual(expected['registers'][i],before[i])
        self.assertEqual(expected['regions_after'][0][16:32],bytes(16))
        self.assertEqual(expected['regions_after'][0][:16],regions[0][1][:16])
        self.assertEqual(expected['regions_after'][0][32:],regions[0][1][32:])
        self.assertEqual(expected['regions_after'][1],regions[1][1])
        self.assertFalse(regions[1][2])
        self.assertEqual(expected['device_after'],device)
        self.assertEqual(expected['pcs'],[0x3530,0x3532,0x3536,0x3538,0x353A,0x353C,0x353E])
        self.assertEqual(expected['events'],[[2,0x780,4,0],[2,0x784,4,0],[2,0x788,4,0],[2,0x78C,4,0],[1,p.leaf.SP,4,p.leaf.STOP]])

    def test_zero_result_preserves_x_and_supervisor_mask_with_other_flags_cleared(self):
        for sr in p.effects.SR_VALUES:
            expected=p.contract(0,sr,0,{})[2]
            self.assertEqual(expected['registers'][17],(sr&~31)|(sr&16)|4)

    def test_comparison_rejects_every_required_observable(self):
        expected=p.contract(1,0x271F,0,{'sentinel':1})[2]
        actual={'status_code':1,'status':'stop-reached','code_unchanged':True,**deepcopy(expected)}
        p.effects.compare(actual,expected)
        for field in expected:
            changed=deepcopy(actual)
            if field=='regions_after':changed[field][0]=b'wrong'
            elif field=='device_after':changed[field]['sentinel']=2
            elif field=='events':changed[field][0][3]=1
            elif field=='steps':changed[field]+=1
            else:changed[field][0]^=1
            with self.subTest(field=field),self.assertRaises(ValueError):p.effects.compare(changed,expected)
        for key,value in (('status_code',5),('code_unchanged',False)):
            with self.assertRaises(ValueError):p.effects.compare({**actual,key:value},expected)

    def test_selection_covers_each_seed_byte_flags_and_register_variant(self):
        rows=p.selection();self.assertEqual(len(rows),len(set(rows)))
        self.assertEqual({seed for seed,sr,variant in rows if sr==0x271F and variant==0 and seed<256},set(range(256)))
        self.assertEqual({sr for _,sr,_ in rows},set(p.effects.SR_VALUES))
        self.assertEqual({variant for _,_,variant in rows},{0,1})

    def test_undeclared_case_is_rejected(self):
        case=[0,0x271F,0]
        for index,value in ((0,True),(0,-1),(0,2**32),(1,0),(2,True),(2,2)):
            changed=list(case);changed[index]=value
            with self.subTest(index=index,value=value),self.assertRaises(ValueError):p.contract(*changed,{})

    def test_guard_exit_never_passes_as_terminal_semantic_control(self):
        class Incomplete:
            def run(self,*args,**kwargs):return {'status_code':2}
        with self.assertRaisesRegex(ValueError,'terminal semantics'):
            p.semantic_controls(bytes(23920),Incomplete())

    def test_shared_command10_inputs_cover_both_modes_variants_all_masks_without_mmio_ram(self):
        rows=list(p.effects.command10_inputs())
        self.assertEqual(len(rows),128)
        self.assertEqual({(mode,variant,mask) for mode,variant,mask,*_ in rows},
                         {(mode,v,m) for mode in ('handler','dispatcher') for v in (0,1) for m in range(32)})
        for mode,variant,mask,ranges,entry,regs,regions in rows:
            self.assertEqual(entry,0x1E68 if mode=='handler' else 0x17F2)
            self.assertEqual(regs[7]&0xFFFF,16)
            self.assertEqual(regions[5][1],bytes(1 if mask&(1<<i) else 0 for i in range(5)))
            self.assertTrue(all(lo+len(data)<=0x100000 for lo,data,_ in regions))
            self.assertFalse(any(lo<=0x780<lo+len(data) for lo,data,_ in regions))

    def test_failed_source_creates_private_exclusive_failure_before_library_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'result.json'
            args=['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(report)]
            with patch.object(p.native,'Library') as library,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args),1);library.assert_not_called()
            data=report.read_bytes();result=json.loads(data)
            self.assertEqual(result['error']['phase'],'source_identity')
            self.assertFalse(result['original_game_bytes_executed'])
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),data)


if __name__=='__main__':unittest.main()
