"""Independent reset contracts/failure examples; real originals run separately."""
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
import probe_netlink_dsp_reset as p


class DSPResetContracts(unittest.TestCase):
    def device(self):
        return {'coef':[7]*64,'madrs':[9]*32,'mprog':[0x123456789ABCDEF0]*128,'dirty':0,'temp':[0xFF123456]*128,'unrelated_sha256':'dsp','slot_unrelated_sha256':'slot','slot_values':[99]}

    def test_program_clears_all_words_invalidates_and_preserves_d7_upper_word(self):
        before,regions,expected=p.contract('program',0,0x271F,1,self.device())
        self.assertEqual(expected['device_after']['mprog'],[0]*128)
        self.assertEqual(expected['device_after']['dirty'],1)
        self.assertEqual(expected['device_after']['temp'],self.device()['temp'])
        self.assertEqual(expected['registers'][7],(before[7]&0xFFFF0000)|0xFFFF)
        self.assertEqual(expected['registers'][9],0x100C00)
        self.assertEqual(expected['steps'],517)
        self.assertEqual(len(expected['events']),257)
        self.assertEqual(len(expected['reference_bus_events']),512)
        self.assertEqual(expected['reference_bus_events'][-1],[2,0x100BFE,2,0])
        self.assertEqual(expected['regions_after'],[x[1] for x in regions])

    def test_madrs_clears32_words_but_traces_full_gap_writes_without_program_change(self):
        before,_,expected=p.contract('madrs',1,0x2015,0,self.device())
        self.assertEqual(expected['device_after']['madrs'],[0]*32)
        self.assertEqual(expected['device_after']['mprog'],self.device()['mprog'])
        self.assertEqual(expected['device_after']['dirty'],0)
        self.assertEqual(expected['registers'][7],0xFFFF)
        self.assertEqual(expected['registers'][9],0x100800)
        self.assertEqual(expected['registers'][17],0x2014)
        self.assertEqual(expected['steps'],69)
        self.assertEqual(expected['reference_bus_events'][32],[2,0x1007C0,2,0])
        self.assertEqual(expected['reference_bus_events'][-1],[2,0x1007FE,2,0])

    def test_coef_and_temp_preserve_all_other_fields_and_visible_registers(self):
        for mode,size,end,steps in [('coef',64,0x100780,69),('temp',128,0x100E00,260)]:
            before,_,expected=p.contract(mode,0x12345678,0x271F,0,self.device())
            self.assertEqual(expected['device_after'][mode],[0]*size)
            for key in self.device():
                if key!=mode:self.assertEqual(expected['device_after'][key],self.device()[key])
            self.assertEqual(expected['registers'][9],end)
            self.assertEqual(expected['steps'],steps)
            for index in range(15):
                if index not in (0,7,9):self.assertEqual(expected['registers'][index],before[index])

    def test_every_required_observable_terminal_status_and_code_are_enforced(self):
        expected=p.contract('temp',0,0x271F,0,self.device())[2]
        actual={'status_code':1,'status':'stop-reached','code_unchanged':True,**deepcopy(expected)}
        p.effects.compare(actual,expected)
        for key in expected:
            changed=deepcopy(actual)
            if key=='steps':changed[key]+=1
            elif key=='device_after':changed[key]['temp'][0]=1
            elif key=='regions_after':changed[key][0]=b'wrong'
            elif key in ('events','reference_bus_events'):changed[key][0][3]=1
            else:changed[key][0]^=1
            with self.subTest(key=key),self.assertRaises(ValueError):p.effects.compare(changed,expected)
        with self.assertRaises(ValueError):p.effects.compare({**actual,'status_code':5},expected)
        with self.assertRaises(ValueError):p.effects.compare({**actual,'code_unchanged':False},expected)

    def test_selection_and_input_guards(self):
        rows=p.selection();self.assertEqual(len(rows),414);self.assertEqual(len(rows),len(set(rows)))
        self.assertEqual({seed for mode,seed,sr,variant in rows if mode=='temp' and sr==0x271F and variant==0 and seed<256},set(range(256)))
        for case in [('bad',0,0x271F,0),('coef',True,0x271F,0),('coef',0,0,0),('coef',0,0x271F,True)]:
            with self.assertRaises(ValueError):p.contract(*case,{})
        class Guard:
            def run(self,*args,**kwargs):return {'status_code':2}
        with self.assertRaisesRegex(ValueError,'terminal reset semantics'):p.controls(bytes(23920),Guard())

    def test_missing_source_retains_exclusive_private_failure_before_loading_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'report.json'
            args=['--source-file',str(root/'missing'),'--prepared',str(root),'--previous-prepared',str(root),'--report',str(out)]
            with patch.object(p.native,'Library') as library,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(args),1);library.assert_not_called()
            data=out.read_bytes();self.assertEqual(json.loads(data)['error']['phase'],'source_identity')
            self.assertFalse(json.loads(data)['original_game_bytes_executed']);self.assertEqual(out.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(out.read_bytes(),data)


if __name__=='__main__':unittest.main()
