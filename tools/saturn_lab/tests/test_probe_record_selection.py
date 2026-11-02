"""Owned selection/search fixtures; original-byte evidence is private."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_record_selection as p


class RecordSelectionTests(unittest.TestCase):
    def test_case_denominators_cover_slots_positions_previous_indices_and_all_flags(self):
        rows=p.cases();self.assertEqual(len(rows),7736);self.assertEqual(len(set(rows)),7736)
        self.assertEqual({c[4] for c in rows if c[0]=='flag-bytes'},set(range(256)))
        self.assertEqual({c[2] for c in rows if c[0].startswith('positions')},{p.MASK,*range(18)})
        self.assertEqual({c[3] for c in rows if c[0].startswith('positions')},set(range(18)))
        self.assertEqual({c[1] for c in rows},{0,1})

    def test_ready_transfer_saves_actual_root_resume_and_does_not_return_normally(self):
        case=('positions0',0,p.MASK,0,1,1,0,0,7,0);m,_=p.expected(case)
        self.assertFalse(m.wait);self.assertEqual(m.reg['pc'],p.OUTBOUND)
        self.assertEqual(int.from_bytes(m.buffers[-2][36:40],'big'),0x06006C00)
        self.assertEqual(int.from_bytes(m.buffers[-2][32:36],'big'),p.records.SP-44)
        self.assertEqual(m.buffers[-2][:4],m.buffers[-2][4:8])
        self.assertEqual(m.reg['r0'],1);self.assertEqual(m.reg['r4'],0x33000000)
        self.assertEqual(m.reg['r15'],0x060E0000);self.assertEqual(m.reg['macl'],0xCC000000)
        self.assertEqual(m.reg['mach'],0xBB000000);self.assertEqual(m.reg['sr'],0x3F2)

    def test_flag_two_initializes_real_PR_argument_and_flag_then_reloads_interval(self):
        case=('fields',1,p.MASK,0,2,p.MASK,0,0,0x80000000,1);m,regions=p.expected(case)
        self.assertFalse(m.wait);self.assertEqual(m.reg['r0'],0x80000000)
        self.assertEqual(m.reg['r4'],0x80000000)
        self.assertEqual(int.from_bytes(regions[-1][1][68:72],'big'),0xDEAD0000)
        self.assertEqual(int.from_bytes(m.buffers[-1][68:72],'big'),p.OUTBOUND)
        self.assertEqual(m.buffers[-1][80],3)
        self.assertEqual(int.from_bytes(m.buffers[-1][:4],'big'),0x80000000)
        self.assertIn([2,p.ARRAY_B+4,4,0xB0B00101],m.events)
        self.assertEqual(m.buffers[3],regions[3][1])
        self.assertEqual(m.buffers[11],regions[11][1])

    def test_current_record_is_revisited_after_wrap_and_end_scan_polls(self):
        case=('positions0',0,0,0,1,1,0,0,7,0);m,_=p.expected(case)
        self.assertEqual(sum(pc==p.delta.ENTRY for pc,_ in m.trace),2)
        self.assertEqual(sum(pc==0x06006C70 for pc,_ in m.trace),18)
        self.assertEqual(m.reg['pc'],p.OUTBOUND)
        self.assertEqual(p.scalar(case)['polls'],2)

    def test_one_original_delta_poll_makes_last_record_ready_after_full_scan(self):
        case=('polls0',0,p.MASK,17,1,2,1,0,1,0);m,_=p.expected(case);logical=p.scalar(case)
        self.assertFalse(m.wait);self.assertEqual(logical['selected'],17)
        self.assertEqual(sum(pc==p.delta.ENTRY for pc,_ in m.trace),1)
        self.assertEqual(sum(pc==0x06006C70 for pc,_ in m.trace),36)
        self.assertGreater(len(m.trace),128);self.assertLessEqual(len(m.trace),1024)
        self.assertIn([1,p.RAW_SAMPLE,4,1],m.events)
        self.assertIn([2,p.PREVIOUS,4,1],m.events)
        short,_=p.expected(case,128);self.assertTrue(short.wait);self.assertEqual(len(short.trace),128)

    def test_static_sample_stable_no_eligible_state_is_bounded_incomplete(self):
        case=('waits',0,p.MASK,0,255,2,1,0,1,0);m,_=p.expected(case)
        self.assertTrue(m.wait);self.assertEqual(len(m.trace),1024)
        self.assertIsNone(p.scalar(case)['selected'])
        self.assertEqual(int.from_bytes(m.buffers[8],'big'),1)
        self.assertEqual(int.from_bytes(m.buffers[-2][36:40],'big'),0x06006C00)
        self.assertNotIn([p.handoff.RESTORE,False],m.trace)

    def test_all_case_scalar_and_path_models_agree_without_dropping_waits(self):
        ready=waits=0
        for case in p.cases():
            m,_=p.expected(case);logical=p.scalar(case)
            self.assertEqual(m.wait,logical['selected'] is None)
            if m.wait:waits+=1
            else:
                ready+=1;self.assertEqual(bytes(m.buffers[-1]),logical['table'])
                self.assertEqual(m.reg['r0'],logical['argument'])
        self.assertEqual((ready,waits),(5340,2396))

    def test_exclusive_private_report_fails_identity_before_CPU_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--family','waits','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            raw=report.read_bytes();d=json.loads(raw)
            self.assertEqual(d['error']['phase'],'source_identity');self.assertIs(d['original_game_bytes_executed'],False)
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),raw)


if __name__=='__main__':unittest.main()
