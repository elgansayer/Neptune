"""Owned full-consumer oracle/selection checks; original execution is separate."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_consumer as p


class ConsumerTests(unittest.TestCase):
    def test_full_declared_selection_includes_every_position_and_dense_states(self):
        rows=p.cases()
        self.assertEqual(len(rows),1476)
        self.assertEqual(len(set(rows)),1476)
        self.assertTrue(all(any(r[0]==1<<i for r in rows) for i in range(32)))
        self.assertIn((p.ALL,p.ALL,1,250,9),rows)
        self.assertIn((p.ALL,0,0x100,255,255),rows)

    def test_all32_matching_records_clear_and_wrap_in_order(self):
        before,after,regions,expected,events,pcs,emitted=p.contract(p.ALL,p.ALL,1,250,9)
        self.assertEqual(len(emitted),32)
        self.assertEqual([e['record_index'] for e in emitted],list(range(32)))
        self.assertEqual([e['counter'] for e in emitted],[(250+i)&255 for i in range(32)])
        self.assertEqual(expected[3],bytes([26]))
        self.assertEqual(len(pcs),1572)
        self.assertEqual(len(events),967)
        self.assertTrue(all(expected[2][i*12]&128==0 for i in range(32)))
        self.assertEqual(after[6],before[6])
        self.assertEqual(after[13],before[13])
        self.assertEqual(after[17],0x2714)

    def test_clear_only_tests_low_byte_and_preserves_records_when_it_is_zero(self):
        _,_,regions,expected,_,pcs,emitted=p.contract(p.ALL,p.ALL,0x100,0,0)
        self.assertEqual(regions[2][1],expected[2])
        self.assertEqual(len(emitted),32)
        self.assertEqual(len(pcs),1540)

    def test_inactive_records_and_mismatched_pointers_never_emit(self):
        for active,matching,steps,sr in ((0,p.ALL,132,0x2004),(p.ALL,0,196,0x2009)):
            before,after,regions,expected,events,pcs,emitted=p.contract(active,matching,1,255,255)
            self.assertEqual(emitted,[])
            self.assertEqual(expected[2],regions[2][1])
            self.assertEqual(expected[4],regions[4][1])
            self.assertEqual(expected[3],b'\xFF')
            self.assertEqual(len(pcs),steps)
            self.assertEqual(after[17],sr)
            self.assertEqual(after[:6],before[:6])

    def test_short_profile_rejection_does_not_claim_complete_call(self):
        class Rejected:
            def run(self,*args,**kwargs):
                return {'status_code':6,'status':'event-budget','steps':200,'events':[None]*128,
                        'error_address':1,'code_unchanged':True}
        result=p.short_proof(bytes(23920),Rejected())
        self.assertFalse(result['completed_original_call'])
        self.assertEqual(result['expected_full_instructions'],1572)
        self.assertEqual(result['expected_full_events'],967)


if __name__=='__main__':unittest.main()
