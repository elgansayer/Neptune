"""Owned scalar/guard tests; no original opcode data or CPU execution here."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_dispatch as probe
import probe_netlink_pointer as leaf


class NetlinkDispatchTests(unittest.TestCase):
    def test_constructed_product_and_control_selection(self):
        rows=probe.cases()
        self.assertEqual(len(rows),2560)
        self.assertEqual(len(set(rows)),2560)
        controls=rows[::8]
        self.assertEqual(len(controls),320)
        self.assertEqual(len({r[:3] for r in controls}),320)

    def test_fixed_target_register_narrowing_and_ccr_contract(self):
        before,after,tag,address,target=probe.contract(0x40C8,7,5,0xFFFFFF00,0x201F,0x8000)
        self.assertEqual(target,0x4138)
        self.assertEqual(address,0xA3A2)
        self.assertEqual(tag,0x85)
        self.assertEqual(after[0],0xFFFF0007)
        self.assertEqual(after[7],20)
        self.assertEqual(after[10],0x4138)
        self.assertEqual(after[12:15],[0xA000,0xA400,0xA3A0])
        self.assertEqual(after[15],leaf.SP)
        self.assertEqual(after[17],0x2000)
        self.assertEqual(after[1:7],before[1:7])

    def test_zero_selector_sets_zero_and_clears_extend(self):
        for entry,base in probe.WRAPPERS.items():
            _,after,_,_,target=probe.contract(entry,0,0,0,0x271F,0x10000)
            self.assertEqual(target,base)
            self.assertEqual(after[17],0x2704)

    def test_unexpected_native_guard_cannot_be_success(self):
        class Failing:
            def run(self,*args,**kwargs):return {'status_code':3,'status':'instruction-access'}
        with self.assertRaisesRegex(ValueError,'Native guard'):
            probe.run_case(bytes(23920),Failing(),0x40C8,0,0,0,0x2700,0x8000)


if __name__=='__main__':unittest.main()
