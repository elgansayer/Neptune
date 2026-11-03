"""Owned contract examples only; these do not execute Saturn instructions."""
from pathlib import Path
from contextlib import redirect_stdout
import io
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_state as p


def device():
    return dict(coef=[0]*64,madrs=list(range(32)),mprog=[0]*128,dirty=0,unrelated_sha256='owned')


def code():
    data=bytearray(0x5D70)
    for i in range(128):data[0x5414+i]=127-i
    for i in range(72):data[0x54B6+i]=(i*3)&255
    for i in range(1089):data[0x5586+i]=i&255
    for i in range(33):data[0x59C8+i]=128
    for table in (0x5A1A,0x5AC4,0x5B6E,0x5C18):
        for i in range(136):data[table+i]=i//2
    for i in range(140):data[0x5CE4+i]=i
    return bytes(data)


class StateContractTests(unittest.TestCase):
    def test_original_dispatch_prefix_clears_extend_before_disabled_handler(self):
        case=p.base_case('dispatcher');case.update(gate=0,alias=False)
        regs,*_=p.Contract(code(),case,device()).run()
        # Original diagnostic002 reaches186C with SR2700. The two ADD.W index
        # doublings clear X before the disabled handler's final OR.W.
        self.assertEqual(regs[17],0x2700)

    def test_effects_use_independent_tables_registers_and_ordered_device_accesses(self):
        case=p.base_case('effects');case.update(flags=255,current=(10,20,30),target=(10,20,30))
        model=p.Contract(code(),case,device());regs,after,events,pcs,result=model.run()
        self.assertEqual(regs[0],108<<8);self.assertEqual(regs[1],108)
        self.assertEqual(regs[3:5],[128,30]);self.assertEqual(regs[8],108)
        self.assertEqual(regs[15:18],[p.leaf.SP+4,p.leaf.STOP,0x2700])
        self.assertEqual(result['coef'][45],117*32)
        self.assertEqual(result['coef'][38],90*32)
        self.assertEqual(result['coef'][43],108*32)
        self.assertEqual(result['madrs'][4:6],[0,179])
        mmio=[e for e in events if e[1]>=0x100700]
        self.assertEqual(mmio[2:6],[[1,0x100782,2,1],[1,0x100780,2,0],
                                   [2,0x100788,2,0],[2,0x10078A,2,179]])
        self.assertEqual(after[1][8+0x28+0x2C],254)
        self.assertEqual(after[2],model.regions[2][1])
        self.assertIn(0x5574,pcs);self.assertNotIn(0x5562,pcs)

    def test_inactive_state_restores_all_saved_registers_and_preserves_extend(self):
        case=p.base_case();model=p.Contract(code(),case,device())
        regs,after,events,pcs,result=model.run()
        self.assertEqual(regs[1:15],model.before[1:15])
        self.assertEqual(regs[0],0);self.assertEqual(regs[17],0x2714)
        self.assertEqual(len(pcs),31);self.assertNotIn(p.EFFECT,pcs)
        self.assertEqual(result,device())
        self.assertFalse(any(e[1]>=0x100700 for e in events))
        self.assertEqual(after[1][:8],model.regions[1][1][:8])
        self.assertEqual(after[2][:128],model.regions[2][1][:128])

    def test_return_status_uses_restored_caller_context(self):
        case=p.base_case();case.update(flags=0,alias=False)
        regs,*_=p.Contract(code(),case,device()).run()
        self.assertEqual(regs[0],2)
        self.assertEqual(regs[14],0x18000)

    def test_active_countdown_handles_exact_boundary_underflow_and_zero_step(self):
        case=p.base_case('effects');case.update(flags=1,current=(10,20,30),target=(12,25,35),
             steps=(0,3,7),magnitude=(0,3,7),remaining=(1,3,1))
        model=p.Contract(code(),case,device());regs,after,events,pcs,result=model.run()
        self.assertEqual([regs[i]&255 for i in (5,6,7)],[10,25,35])
        self.assertEqual([after[1][8+0x28+0x20+i*2] for i in range(3)],[1,0,250])
        self.assertEqual(after[1][8+0x28+0x2C],1)
        self.assertNotIn(0x53A2,pcs);self.assertIn(0x53C6,pcs);self.assertIn(0x53EA,pcs)

    def test_pending_state_reuses_ramp_and_normalises_zero_step(self):
        case=p.base_case();case.update(pending=True,steps=(0,128,0))
        model=p.Contract(code(),case,device());_,after,_,pcs,_=model.run()
        self.assertIn(0x5290,pcs);self.assertIn(p.EFFECT,pcs)
        self.assertEqual([after[1][8+0x28+0x1A+2*i] for i in range(3)],[1,1,1])
        self.assertEqual(after[1][8+11],0)

    def test_disabled_command_and_dispatcher_preserve_word_result_and_stack(self):
        for mode in ('helper','handler','dispatcher'):
            case=p.base_case(mode);case.update(variant=1,gate=63,alias=False)
            model=p.Contract(code(),case,device());regs,after,events,pcs,result=model.run()
            self.assertNotIn(p.STATE,pcs)
            self.assertEqual(regs[0],model.before[0])
            self.assertEqual(regs[17],0x2708 if mode=='dispatcher' else 0x2718)
            self.assertEqual(regs[15:17],[p.leaf.SP+4,p.leaf.STOP])
            self.assertEqual(regs[8],model.base)
            self.assertEqual(result,device())
            if mode=='dispatcher':
                self.assertEqual(regs[7]&65535,0x44)
                self.assertEqual(regs[12],model.before[14])
                self.assertEqual(regs[13:15],model.before[13:15])

    def test_selection_has_all_entries_and_declared_byte_domains(self):
        selected=p.cases()
        self.assertEqual(len(selected),len({json.dumps(c,sort_keys=True) for c in selected}))
        self.assertEqual({c['mode'] for c in selected},set(p.MODES))
        for mode in p.MODES:
            group=[c for c in selected if c['mode']==mode]
            self.assertEqual({c['flags'] for c in group},set(range(256)))
            for field,limit in [('current',128),('target',128),('steps',256),('magnitude',256),('remaining',256)]:
                for axis in range(3):self.assertEqual({c[field][axis] for c in group},set(range(limit)))
            if mode in ('helper','handler','dispatcher'):
                self.assertEqual({c['gate'] for c in group},set(range(256)))

    def test_undeclared_or_mistyped_case_stops_before_execution(self):
        for field,value in [('gate',True),('gate',256),('current',(128,0,0)),
                            ('offsets',(False,0)),('pending',1),('mode','other')]:
            case=p.base_case();case[field]=value
            with self.assertRaises(ValueError):p.Contract(code(),case,device())

    def test_missing_input_is_failed_and_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'report.json'
            args=['--source-file',str(root/'missing'),'--prepared',str(root/'missing-native'),'--report',str(report)]
            with redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            before=report.read_bytes();value=json.loads(before)
            self.assertEqual(value['status'],'failure');self.assertEqual(value['error']['phase'],'identity')
            self.assertFalse(value.get('original_game_bytes_executed',False))
            with self.assertRaises(FileExistsError):p.main(args)
            self.assertEqual(report.read_bytes(),before)


if __name__=='__main__':unittest.main()
