"""Independent gate contracts; actual original instructions run separately."""
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
import probe_netlink_boot_gate as p


class BootGateContracts(unittest.TestCase):
    def test_valid_gate_clobbers_all_registers_and_transfers_without_stack_or_device_access(self):
        before,regions,expected,outcome=p.contract(p.SIGNATURE,0x271F,1)
        self.assertEqual(outcome,'gate-transfer');self.assertEqual(expected['status_code'],1)
        self.assertEqual(expected['registers'],[0]*13+[0x100000,0x7000,0xA000,0x1080,0x2704])
        self.assertEqual(expected['events'],[[1,p.TAG,4,p.SIGNATURE]])
        self.assertEqual(expected['steps'],22)
        self.assertEqual(expected['regions_after'],[b for _,b,_ in regions]);self.assertTrue(all(not w for _,_,w in regions))
        self.assertNotEqual(before[15],expected['registers'][15])
        self.assertFalse(any(0x1020<=pc<0x1060 for pc in expected['pcs']))

    def test_wrong_tags_retain_poison_registers_and_compare_exact_bounded_loops_and_flags(self):
        for tag,flags in ((0,9),(0xFFFFFFFF,8),(0x80000000,2),(0x7FFFFFFF,0),(p.SIGNATURE-1,9),(p.SIGNATURE+1,0)):
            before,_,expected,outcome=p.contract(tag,0x2015,0)
            self.assertEqual(outcome,'bounded-wait-not-completed-boot')
            self.assertEqual(expected['status_code'],2);self.assertEqual(expected['steps'],63)
            self.assertEqual(expected['registers'][:16],before[:16])
            self.assertEqual(expected['registers'][16:],[0x1000,0x2700|flags])
            self.assertEqual(expected['pcs'],[0x1000,0x1004,0x100E]*21)
            self.assertEqual(expected['events'],[[1,p.TAG,4,tag]]*21)

    def test_declared_union_covers_each_tag_byte_and_retains_completion_partition(self):
        cases=p.selection();self.assertEqual(len(cases),8200);self.assertEqual(len(cases),len(set(cases)))
        for index in range(4):self.assertEqual({(tag>>(index*8))&255 for tag,_,_ in cases},set(range(256)))
        self.assertEqual(sum(tag==p.SIGNATURE for tag,_,_ in cases),8)
        for case in ((True,0x2700,0),(0,0,0),(0,0x2700,True)):
            with self.assertRaises(ValueError):p.contract(*case)

    def test_every_observable_code_and_untouched_device_is_enforced(self):
        expected=p.contract(p.SIGNATURE,0x2700,0)[2]
        actual={**deepcopy(expected),'code_unchanged':True,'device_before':{'sentinel':1},'device_after':{'sentinel':1}}
        p.compare(actual,expected)
        for key in expected:
            changed=deepcopy(actual)
            if key in ('steps','status_code','error_address','error_size'):changed[key]+=1
            elif key=='regions_after':changed[key][0]=b'wrong'
            elif key=='events':changed[key][0][3]^=1
            elif key=='reference_bus_events':changed[key].append([2,0x100800,2,0])
            else:changed[key][0]^=1
            with self.subTest(key=key),self.assertRaises(ValueError):p.compare(changed,expected)
        for changes in ({'code_unchanged':False},{'device_after':{'sentinel':2}}):
            with self.assertRaises(ValueError):p.compare({**actual,**changes},expected)

    def test_controls_reject_guards_as_terminal_semantic_evidence(self):
        class Guard:
            def run(self,*a,**k):return {'status_code':2}
        with self.assertRaisesRegex(ValueError,'normal gate handoff'):p.controls(bytes(23920),Guard())

    def test_missing_source_retains_private_exclusive_failure_without_loading_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'report.json';args=['--source-file',str(root/'missing'),'--prepared',str(root),'--report',str(out)]
            with patch.object(p.native,'Library') as library,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args),1);library.assert_not_called()
            data=out.read_bytes();report=json.loads(data);self.assertFalse(report['original_game_bytes_executed']);self.assertEqual(report['error']['phase'],'source_identity')
            self.assertEqual(out.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(out.read_bytes(),data)


if __name__=='__main__':unittest.main()
