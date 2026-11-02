"""Owned scalar/path boundary examples, not original execution evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_record_transition as p


class RecordTransitionTests(unittest.TestCase):
    def test_selection_has_all_flags_categories_positions_and_signed_boundaries(self):
        cases=p.cases();self.assertEqual(len(cases),8256);self.assertEqual(len(set(cases)),8256)
        self.assertEqual({c[2] for c in cases if c[0]=='flags'},set(range(256)))
        self.assertEqual({c[3] for c in cases if c[0]=='categories'},set(range(256)))
        self.assertTrue(set(range(20))|{0x7FFFFFFF,0x80000000,0xFFFF8000,0xFFFFFFFF}<=
                        {c[1] for c in cases if c[0]=='indices'})

    def test_signed_bound_precedes_record_address_calculation(self):
        m=p.contract(('indices',18,1,255,0))
        self.assertEqual(m.reg['r0'],p.MASK);self.assertEqual(m.reg['r4'],18)
        self.assertEqual(len(m.trace),7);self.assertEqual(len(m.events),2)
        self.assertEqual(len(m.regions),1)
        self.assertEqual(m.trace[-1],[0x06006DFC,True])
        self.assertEqual(m.reg['sr'],0x3F3)
        self.assertFalse(p.accepted(0x10000));self.assertTrue(p.accepted(0x80000000))

    def test_negative_low_word_product_truncation_and_successful_byte_writes(self):
        self.assertEqual(p.pointer(0xFFFFFFFF),p.TABLE-88)
        self.assertEqual(p.pointer(0xFFFF8000),p.TABLE)
        self.assertEqual(p.pointer(0x80000000),p.TABLE)
        m=p.contract(('indices',0xFFFFFFFF,1,255,1));address=p.TABLE-88
        self.assertEqual(m.reg['r4'],address);self.assertEqual(m.reg['r0'],0)
        self.assertEqual(m.reg['sr'],1);self.assertEqual(m.reg['r1'],88)
        self.assertEqual(m.reg['r2'],2);self.assertEqual(m.reg['r3'],0)
        self.assertEqual(m.buffers[1][80:82],bytes([2,0]))
        self.assertEqual(m.buffers[1][:80],m.regions[1][1][:80])
        self.assertEqual(m.buffers[1][82:],m.regions[1][1][82:])
        self.assertEqual(len(m.trace),24);self.assertEqual(len(m.events),6)
        self.assertEqual(m.trace[-1],[0x06006DF6,True])

    def test_non_one_flag_is_unsigned_unchanged_and_restores_saved_MACL(self):
        for flag in (0,2,127,128,255):
            m=p.contract(('flags',17,flag,128,0))
            self.assertEqual(m.reg['r0'],p.MASK);self.assertEqual(m.reg['sr'],0x3F2)
            self.assertEqual(m.buffers[1],m.regions[1][1])
            self.assertEqual(m.reg['macl'],m.before['macl']);self.assertEqual(m.reg['r15'],m.before['r15'])
            self.assertEqual(len(m.trace),18);self.assertEqual(len(m.events),4)

    def test_all_selected_contracts_agree_with_scalar_outputs(self):
        for case in p.cases():
            m=p.contract(case)
            self.assertEqual(m.reg['macl'],m.before['macl']);self.assertEqual(m.reg['r15'],m.before['r15'])
            self.assertTrue(all(m.reg[n]==m.before[n] for n in ('pr','mach','gbr','vbr')))

    def test_report_is_private_exclusive_and_missing_input_is_not_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);report=root/'failed.json'
            args=['--kernel',str(root/'missing'),'--saturn-recomp',str(root),'--family','flags','--report',str(report)]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            raw=report.read_bytes();d=json.loads(raw)
            self.assertEqual(d['error']['phase'],'source_identity');self.assertIs(d['original_game_bytes_executed'],False)
            self.assertEqual(report.stat().st_mode&0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(p.main(args),1)
            self.assertEqual(report.read_bytes(),raw)


if __name__=='__main__':unittest.main()
