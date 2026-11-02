"""Owned handoff/path examples; private original execution supplies the evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_context_handoff as p


def models(case):
    entry,before,regions=p.fixture(case);one=p.model(before,regions);one.outbound(entry)
    if one.reg['pc']==p.RETURN:return one,None
    inputs=[(lo,bytes(buf),write) for (lo,_,write),buf in zip(regions,one.buffers)]
    two=p.model({**one.reg,'r4':regions[-1][0]+32,'r5':case[6],'pc':p.RESTORE},inputs)
    two.restore();two.resume_tail();return one,two


class ContextHandoffTests(unittest.TestCase):
    def test_selection_has_both_cpu_slots_every_record_and_zero_nonzero_resume(self):
        rows=p.cases();self.assertEqual(len(rows),2400);self.assertEqual(len(set(rows)),2400)
        self.assertEqual({c[1] for c in rows},{0,1})
        self.assertEqual({c[2] for c in rows if c[0]=='records'},set(range(18)))
        self.assertEqual({c[3] for c in rows if c[0]=='yield'},set(p.WORDS))
        self.assertEqual({c[6] for c in rows if c[0]=='yield'},{0,1,0x80000000,p.MASK})

    def test_original_activation_model_saves_actual_resume_PC_and_live_stack(self):
        case=('yield',1,17,p.MASK,0x80000000,1,1,0);one,two=models(case)
        self.assertEqual(one.reg['pc'],p.OUTBOUND)
        self.assertEqual(len(one.trace),82);self.assertEqual(len(one.events),42)
        saved=one.buffers[-1][32:80]
        self.assertEqual(int.from_bytes(saved[36:40],'big'),0x06006D86)
        self.assertEqual(int.from_bytes(saved[32:36],'big'),p.records.SP-16)
        self.assertEqual(int.from_bytes(saved[24:28],'big'),p.RAW_CURRENT)
        self.assertEqual(saved[0:4],saved[4:8])
        self.assertEqual(two.reg['pc'],p.RETURN);self.assertEqual(two.reg['r15'],p.records.SP)
        self.assertEqual(two.reg['r14'],one.before['r14']);self.assertEqual(two.reg['r13'],one.before['r13'])
        self.assertEqual(two.reg['r4'],one.before['r8'])
        self.assertEqual(two.reg['sr'],0x3F2)
        self.assertEqual(len(two.trace),33);self.assertEqual(len(two.events),17)
        self.assertEqual(two.buffers[3],bytes(4));self.assertEqual(two.buffers[2],bytes.fromhex('facefeed'))
        self.assertEqual(two.trace[-1],[0x06006DAC,True])

    def test_zero_resume_is_second_handoff_and_preserves_pending_and_context(self):
        case=('yield',0,0,7,1,p.MASK,0,1);one,two=models(case)
        self.assertEqual(two.reg['pc'],p.OUTBOUND)
        self.assertEqual(two.reg['r0'],7)
        self.assertEqual(two.buffers[2],bytes.fromhex('ffffffff'))
        self.assertEqual(two.buffers[-1],one.buffers[-1])
        self.assertEqual(len(two.trace),43);self.assertEqual(len(two.events),27)
        self.assertNotIn([0x06006DA2,False],two.trace)

    def test_pending_wrapper_zero_returns_and_nonzero_tail_enters_with_one(self):
        zero,_=models(('wrapper',1,0,p.MASK,1,0,1,0))
        self.assertEqual(zero.reg['pc'],p.RETURN);self.assertEqual(zero.reg['r4'],p.MASK)
        self.assertEqual(len(zero.trace),11);self.assertEqual(len(zero.events),2)
        self.assertTrue(all(bytes(buf)==original for (_,original),buf in zip(zero.regions,zero.buffers)))
        active,resumed=models(('wrapper',1,0,p.MASK,1,1,1,0))
        self.assertEqual(active.buffers[-1][:8],bytes.fromhex('0000000100000001'))
        self.assertEqual(active.reg['r0'],1);self.assertEqual(len(active.trace),93)
        self.assertEqual(resumed.reg['pc'],p.RETURN)
        self.assertIn([0x06006DC2,True],active.trace)

    def test_all_paths_fit_existing_profile_and_keep_readonly_neighbors(self):
        for case in p.cases():
            one,two=models(case)
            for m in (one,two):
                if m is None:continue
                self.assertLessEqual(len(m.trace),p.profile.MAX_STEPS)
                self.assertEqual(m.buffers[1],m.regions[1][1])
                self.assertEqual(m.buffers[3-case[1]],m.regions[3-case[1]][1])
                self.assertEqual(m.buffers[4],m.regions[4][1])
                self.assertEqual(m.buffers[5],m.regions[5][1])

    def test_failed_identity_report_is_exclusive_private_and_no_game_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--family','yield','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            raw=report.read_bytes();d=json.loads(raw)
            self.assertEqual(d['error']['phase'],'source_identity');self.assertIs(d['original_game_bytes_executed'],False)
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),raw)


if __name__=='__main__':unittest.main()
