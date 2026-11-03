"""Independent complete helper contracts; actual original execution is separate."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_netlink_slot_effects as p


class SlotResetHelpers(unittest.TestCase):
    def before(self):
        return {'slot_values':[0]*p.native.VALUES,'slot_unrelated_sha256':'slot-sentinel','unrelated_sha256':'dsp-sentinel','coef':[9]}

    def test_release_complete_loop_register_flags_transactions_and_device(self):
        _,_,regs,regions=p.helper_inputs('release',0,0x271F,1,16)
        result=p.helper_contract('release',regs,regions,self.before())
        self.assertEqual(len(result['pcs']),100)
        self.assertEqual(len(result['events']),65)
        self.assertEqual(result['events'][:2],[[1,0x10000B,1,0],[2,0x10000B,1,31]])
        self.assertEqual(result['registers'][7],65535)
        self.assertEqual(result['registers'][9],0x10040B)
        self.assertEqual(result['registers'][13],0x100000)
        self.assertEqual(result['registers'][17],0x2710)
        self.assertEqual(result['device_after']['slot_values'][5],31)
        self.assertEqual(result['regions_after'],[d for _,d,_ in regions])

    def test_send_complete_shifted_window_and_x_flag_preservation(self):
        _,_,regs,regions=p.helper_inputs('send',0,0x2015,0,16)
        result=p.helper_contract('send',regs,regions,self.before())
        self.assertEqual(len(result['pcs']),52)
        self.assertEqual(len(result['events']),17)
        self.assertEqual(result['events'][0],[2,0x100215,1,0])
        self.assertEqual(result['events'][-2],[2,0x1003F5,1,0])
        self.assertEqual(result['registers'][0],0)
        self.assertEqual(result['registers'][17],0x2014)
        self.assertEqual(result['registers'][9],0x100415)

    def test_volume_clears_exact16bytes_in_order_and_preserves_neighbors(self):
        _,_,regs,regions=p.helper_inputs('volume',0,0x271F,1,1)
        result=p.helper_contract('volume',regs,regions,self.before())
        self.assertEqual(len(result['pcs']),56)
        self.assertEqual(len(result['events']),21)
        self.assertEqual(result['regions_after'][0][0x187E:0x188E],bytes(16))
        self.assertEqual(result['regions_after'][0][:0x187E],regions[0][1][:0x187E])
        self.assertEqual(result['regions_after'][0][0x188E:],regions[0][1][0x188E:])
        self.assertEqual(result['events'][-5:-1],[[2,regs[14]+offset,4,0] for offset in (0x187E,0x1882,0x1886,0x188A)])

    def test_each_required_field_and_terminal_status_is_enforced(self):
        _,_,regs,regions=p.helper_inputs('volume',0,0x271F,0,0)
        expected=p.helper_contract('volume',regs,regions,self.before())
        actual={'status_code':1,'code_unchanged':True,**expected};p.compare(actual,expected)
        for field in expected:
            changed=deepcopy(actual)
            if field=='device_after':changed[field]['slot_unrelated_sha256']='wrong'
            elif field=='regions_after':changed[field][0]=b'wrong'
            elif field=='events':changed[field][0][3]^=1
            else:changed[field][0]^=1
            with self.subTest(field=field),self.assertRaises(ValueError):p.compare(changed,expected)
        for key,value in (('status_code',5),('code_unchanged',False)):
            with self.assertRaises(ValueError):p.compare({**actual,key:value},expected)

    def test_selection_covers_all_release_bytes_sr_variants_and_valid_windows(self):
        cases=p.selection();self.assertEqual(len(cases),len(set(cases)))
        self.assertEqual({s for mode,s,*_ in cases if mode=='release' and 0<=s<256},set(range(256)))
        self.assertEqual({sr for _,_,sr,_,_ in cases},set(p.SR_VALUES))
        for mode in ('send','volume'):
            self.assertEqual({base for m,_,_,_,base in cases if m==mode},set(range(17)))


if __name__=='__main__':unittest.main()
