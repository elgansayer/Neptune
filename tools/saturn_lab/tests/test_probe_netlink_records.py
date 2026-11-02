"""Owned byte/register/path contracts; original CPU execution stays separate."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_records as probe
import probe_netlink_pointer as leaf


class NetlinkRecordTests(unittest.TestCase):
    def test_selections_cover_every_index_free_position_and_full_case(self):
        self.assertEqual(len(probe.copy_cases()),8192)
        self.assertEqual({c[0] for c in probe.copy_cases()[::32]},set(range(256)))
        self.assertEqual(len(probe.scan_cases()),264)
        self.assertEqual({c[0] for c in probe.scan_cases()},set(range(-1,32)))

    def test_copy_high_index_width_and_signed_byte_flags(self):
        before,after,regions,expected,events,destination=probe.copy_contract(255,(1,128),0x271F,0x30000)
        self.assertEqual(destination,0x3027E)
        self.assertEqual(expected[2],b'\x01\x80')
        self.assertEqual(after[17],0x2708)
        self.assertEqual(after[:15],before[:15])
        self.assertEqual(after[15:17],[leaf.SP+4,leaf.STOP])
        self.assertEqual(len(events),19)
        self.assertEqual(events[:2],[[2,leaf.SP-2,2,before[8]&0xFFFF],
                                     [2,leaf.SP-4,2,before[8]>>16]])
        self.assertNotEqual(before[8]&0xFFFF,before[8]>>16)

    def test_scan_first_free_changes_one_record_and_returns_original_sr2700(self):
        before,after,regions,expected,events,pcs=probe.scan_contract(31,0x201F,0)
        self.assertEqual(expected[0][:31*12],regions[0][1][:31*12])
        self.assertEqual(expected[0][31*12:32*12],bytes.fromhex('81007f80deadbeef00018000'))
        self.assertEqual(after[17],0x2700)
        self.assertEqual(after[:15],before[:15])
        self.assertEqual(len(pcs),173)
        self.assertEqual(sum(1 for kind,_,_,_ in events if kind==2),12)

    def test_full_scan_preserves_all_records_and_discards_carry_on_sr_restore(self):
        _,after,regions,expected,events,pcs=probe.scan_contract(-1,0x271F,1)
        self.assertEqual(regions[0][1],expected[0])
        self.assertEqual(after[17],0x2700)
        self.assertEqual(len(pcs),168)
        self.assertIn(0x4BFE,pcs)
        self.assertEqual(sum(1 for kind,_,_,_ in events if kind==2),5)

    def test_native_guard_memory_abi_and_instruction_failures_are_rejected(self):
        valid={'status_code':1,'status':'stop-reached','registers':[1],
               'regions_after':[b'a'],'code_unchanged':True,'events':[[1,2,1,3]],'pcs':[4],'steps':1}
        probe.check(valid,[1],[b'a'],[[1,2,1,3]],[4])
        for field,value in (('status_code',4),('registers',[2]),('regions_after',[b'b']),
                            ('code_unchanged',False),('events',[]),('pcs',[]),('steps',0)):
            with self.subTest(field=field),self.assertRaises(ValueError):
                probe.check({**valid,field:value},[1],[b'a'],[[1,2,1,3]],[4])


if __name__=='__main__':unittest.main()
