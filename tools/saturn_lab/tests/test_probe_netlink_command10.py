"""Independent constructed contracts; original execution is a separate private job."""
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
import probe_netlink_command10 as p


class Command10Contracts(unittest.TestCase):
    def device(self):
        return {'slot_values':[0]*p.native.slots.VALUES,'slot_unrelated_sha256':'slot-canary',
                'unrelated_sha256':'dsp-canary','coef':[7]*64,'madrs':[9]*32,
                'mprog':[0x123456789ABCDEF0]*128,'dirty':0,'temp':[0x123456]*128}

    def model(self,controls,profile=0,mode='handler',location=0,sr=0x271F):
        contract=p.Contract((mode,controls,profile,sr,location,0x8000),self.device())
        return contract,contract.run()

    def test_controls_require_exactly_one_and_restore_sr_stack_and_neighbors(self):
        for controls in ((0,0,0,0,0),(2,127,128,255,2)):
            contract,result=self.model(controls)
            self.assertEqual(result['registers'][8],0x40005)
            self.assertEqual(result['registers'][13:15],[0x100000,0x7000])
            self.assertEqual(result['registers'][15:18],[p.leaf.SP+4,p.leaf.STOP,0x271F])
            self.assertEqual(result['device_after'],self.device())
            for index in (0,1,2,3,5):self.assertEqual(result['regions_after'][index],contract.regions[index][1])
            self.assertEqual(result['regions_after'][4][:510],contract.regions[4][1][:510])
            self.assertEqual(result['regions_after'][4][512:],contract.regions[4][1][512:])
            self.assertEqual(result['pcs'][-2:],[0x1EEA,0x1EEC])

    def test_fourth_control_redirects_final_read_and_four_payload_bytes_suffice(self):
        for payload in ((0,0,0,1),(0,0,0,1,1)):
            contract,result=self.model(payload)
            self.assertEqual(result['registers'][8],0x888F)
            self.assertEqual(result['registers'][0],255)
            self.assertEqual(result['device_after']['temp'],[0]*128)
            self.assertEqual(result['device_after']['mprog'],[0]*128)
            self.assertEqual(result['reference_bus_events'][0],[2,0x100800,2,0])
            self.assertIn([1,0x888E,1,0],result['events'])
        _,result=self.model((0,0,0,1,1),profile=1)
        self.assertEqual(result['registers'][8],0x40005)
        self.assertIn([1,0x40004,1,1],result['events'])
        self.assertNotIn(0x1646,result['pcs'])

    def test_slot_helper_moveq_clears_d7_upper_bits_in_complete_composition(self):
        for profile in (0,1):
            for controls in ((1,0,0,0,0),(0,0,0,0,1)):
                contract,result=self.model(controls,profile=profile)
                self.assertNotEqual(contract.before[7]&0xFFFF0000,0)
                self.assertEqual(result['registers'][7],65535)

    def test_alias_is_read_after_prior_clear_and_first_control_restores_its_pointer(self):
        contract,result=self.model((1,1,1,1,1),location=5)
        self.assertEqual(result['registers'][8],0x785)
        self.assertEqual(contract.peek(0x780,16),0)
        self.assertNotIn(0x1E96,result['pcs'])
        self.assertNotIn(0x1EC4,result['pcs'])
        self.assertEqual(result['device_after']['mprog'],self.device()['mprog'])
        self.assertIn([1,0x781,1,0],result['events'])

    def test_descriptor_scan_emits32_records_wraps_and_clears_only_matching_flags(self):
        contract,result=self.model((1,0,0,0,0),profile=1)
        self.assertEqual(contract.emitted,32)
        self.assertEqual(contract.peek(p.POOL+0x1840,1),26)
        for i in range(32):self.assertEqual(contract.peek(p.POOL+0x2400+i*12,1),i&1)
        for i in range(8):self.assertEqual(contract.peek(p.POOL+0x2100+i*96+2,2),0)
        self.assertEqual(result['device_after']['unrelated_sha256'],'dsp-canary')
        contract,_=self.model((1,0,0,0,0),profile=4)
        self.assertEqual(contract.emitted,0)
        for i in range(32):self.assertEqual(contract.peek(p.POOL+0x2400+i*12,1),128|(i&1))

    def test_paired_channel_flags_and_dispatcher_outer_state_are_explicit(self):
        contract,result=self.model((0,1,0,0,0),profile=2,mode='dispatcher')
        for i in range(16):self.assertEqual(contract.peek(p.RAM+0x1890+i,1),(i*3)&31)
        self.assertEqual(result['registers'][13:15],contract.before[13:15])
        self.assertEqual(result['registers'][17],0x2700)
        self.assertEqual(result['registers'][15:17],[p.leaf.SP+4,p.leaf.STOP])
        self.assertEqual(result['pcs'][-2:],[0x1868,0x186C])
        self.assertIn([2,p.leaf.SP-2,2,contract.before[14]&65535],result['events'])

    def test_all_required_observables_terminal_status_and_immutable_code_are_enforced(self):
        _,expected=self.model((0,0,0,1,1))
        actual={'status_code':1,'status':'stop-reached','code_unchanged':True,**deepcopy(expected)}
        p.compare(actual,expected)
        for key in expected:
            changed=deepcopy(actual)
            if key=='steps':changed[key]+=1
            elif key=='device_after':changed[key]['temp'][0]=1
            elif key=='regions_after':changed[key][0]=b'wrong'
            elif key in ('events','reference_bus_events'):changed[key][0][3]^=1
            else:changed[key][0]^=1
            with self.subTest(key=key),self.assertRaises(ValueError):p.compare(changed,expected)
        for key,value in (('status_code',5),('code_unchanged',False)):
            with self.assertRaises(ValueError):p.compare({**actual,key:value},expected)
        class Guard:
            def configure(self,*a):pass
            def snapshot(self):return self_device
            def run(self,*a,**k):return {'status_code':2}
        self_device=self.device()
        with self.assertRaisesRegex(ValueError,'terminal command10 semantics'):p.controls(bytes(23920),Guard())

    def test_declared_selection_covers_masks_byte_values_aliases_and_four_byte_payload(self):
        rows=p.selection();self.assertEqual(len(rows),9476);self.assertEqual(len(rows),len(set(rows)))
        for mode in ('handler','dispatcher'):
            self.assertEqual({tuple((mask>>i)&1 for i in range(5)) for mask in range(32)},
                             {c for m,c,profile,sr,location,word in rows if m==mode and profile==0 and sr==0x271F and location==0 and word==0 and len(c)==5 and set(c)<={0,1}})
            for index in range(5):self.assertEqual({c[index] for m,c,*_ in rows if m==mode and len(c)==5},set(range(256)))
            self.assertTrue(any(m==mode and len(c)==4 for m,c,*_ in rows))
        self.assertEqual({r[4] for r in rows},set(range(6)))
        for case in [('bad',(0,)*5,0,0x271F,0,0),('handler',(0,)*4,0,0x271F,0,0),
                     ('handler',(0,)*4,1,0x271F,0,0),('handler',(0,)*5,True,0x271F,0,0)]:
            with self.assertRaises(ValueError):p.Contract(case,self.device())

    def test_missing_source_records_private_failure_and_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'report.json';args=['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(out)]
            with patch.object(p.native,'Library') as library,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args),1);library.assert_not_called()
            data=out.read_bytes();self.assertEqual(json.loads(data)['error']['phase'],'source_identity')
            self.assertFalse(json.loads(data)['original_game_bytes_executed']);self.assertEqual(out.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(out.read_bytes(),data)


if __name__=='__main__':unittest.main()
