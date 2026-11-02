"""Owned contract/selection examples only; original execution is private."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_record_delta as p


class RecordDeltaTests(unittest.TestCase):
    def test_selection_has_all_flags_all_positions_and_unsigned_boundaries(self):
        rows=p.cases()
        self.assertEqual(len(rows),7568)
        self.assertEqual(len(set(rows)),len(rows))
        self.assertEqual({c[5] for c in rows if c[0]=='flags'},set(range(256)))
        self.assertEqual({c[3] for c in rows if c[0]=='records'},set((0,p.ALL,*[1<<i for i in range(18)])))
        self.assertEqual({(c[1]-c[2])&p.MASK for c in rows if c[0]=='records'},
                         {0,1,2,0x7FFFFFFF,0x80000000,p.MASK})

    def test_equal_samples_skip_all_record_access_and_restore_delay_register(self):
        m=p.contract(('boundary',p.MASK,p.MASK,p.ALL,5,255,1))
        self.assertEqual(len(m.trace),9)
        self.assertEqual(len(m.events),6)
        self.assertFalse(any(p.TABLE<=event[1]<p.TABLE+18*88 for event in m.events))
        self.assertEqual(m.reg['r14'],m.before['r14'])
        self.assertEqual(m.reg['r15'],p.records.SP)
        self.assertEqual(m.trace[-1],[0x06006BE2,True])
        self.assertEqual(m.reg['r4'],p.MASK)

    def test_unsigned_high_word_decrements_and_wrap_delta_is_two(self):
        m=p.contract(('flags',1,p.MASK,p.ALL,5,128,0))
        self.assertEqual(m.reg['r7'],2)
        self.assertEqual(m.buffers[1],bytes.fromhex('00000001'))
        self.assertTrue(all(m.buffers[2][i*88:i*88+4]==bytes.fromhex('7ffffffe') for i in range(18)))
        self.assertEqual(sum(pc==0x06006BB6 for pc,_ in m.trace),18)
        self.assertEqual(sum(event[0]==1 and event[1]==p.RAW_SAMPLE for event in m.events),1)
        self.assertEqual(len(m.trace),343)
        self.assertEqual(len(m.events),99)

    def test_saturation_preserves_zero_one_inactive_and_canaries(self):
        m=p.contract(('records',0,p.MASK,p.ALL,8,255,1))
        for i,old in enumerate(p.timers(8)):
            self.assertEqual(int.from_bytes(m.buffers[2][i*88:i*88+4],'big'),old if old<=1 else max(1,old-1))
            self.assertEqual(m.buffers[2][i*88+4:(i+1)*88],m.regions[2][1][i*88+4:(i+1)*88])
        high=p.contract(('records',0x80000000,0,p.ALL,5,1,0))
        self.assertTrue(all(high.buffers[2][i*88:i*88+4]==bytes.fromhex('00000001') for i in range(18)))
        inactive=p.contract(('records',1,0,0,5,1,1))
        self.assertEqual(inactive.buffers[2],inactive.regions[2][1])
        self.assertEqual(inactive.buffers[1],bytes.fromhex('00000001'))

    def test_all_cases_have_consistent_independent_scalar_and_path_contracts(self):
        for case in p.cases():
            m=p.contract(case)
            self.assertEqual(m.reg['r14'],m.before['r14'])
            self.assertEqual(m.reg['r15'],m.before['r15'])
            self.assertEqual(m.buffers[0],m.regions[0][1])
            self.assertTrue(all(m.reg[name]==m.before[name] for name in ('pr','macl','mach','gbr','vbr')))

    def test_report_is_private_exclusive_and_failed_identity_is_not_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--family','boundary','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            raw=report.read_bytes();d=json.loads(raw)
            self.assertEqual(d['error']['phase'],'source_identity')
            self.assertIs(d['original_game_bytes_executed'],False)
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),raw)


if __name__=='__main__':unittest.main()
