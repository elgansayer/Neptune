"""Independent slot contracts/layout/source guard tests; native runs separate."""
import ctypes
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_scsp_slots as s


class SlotContracts(unittest.TestCase):
    def fixture(self):
        values=[0]*(s.VALUES);values[0]=0xFFFF;values[16]=0xABCDEF;values[10]=0xFFAA
        return {'slot_values':values,'slot_unrelated_sha256':'sentinel','coef':[7],'unrelated_sha256':'dsp'}

    def test_key_execute_latches_and_decodes_control_without_changing_start_low_word(self):
        before=self.fixture();after=s.transition(before,0x100000,0x1F)
        self.assertEqual(after['slot_values'][0],0x0FFF)
        self.assertEqual(after['slot_values'][-1],1)
        self.assertEqual(after['slot_values'][16],0xFCDEF)
        self.assertEqual(after['slot_values'][17:22],[1,1,3,3,0xFFFF])
        again=s.transition(after,0x100000,0)
        self.assertEqual(again['slot_values'][-1],1)
        self.assertEqual(before['slot_values'][0],0xFFFF)

    def test_release_lane_preserves_high_byte_and_updates_all_decoded_fields(self):
        before=self.fixture();before['slot_values'][5]=0xD500
        after=s.transition(before,0x10000B,0xBF)
        self.assertEqual(after['slot_values'][5],0xD5BF)
        self.assertEqual(after['slot_values'][22:27],[31,13,5,1,1])

    def test_send_masks_upper_word_and_ignores_reserved_select_bit_without_touching_other_slot(self):
        before=self.fixture();after=s.transition(before,0x100015,0xFF)
        self.assertEqual(after['slot_values'][10],255)
        self.assertEqual(after['slot_values'][27:29],[15,7])
        self.assertEqual(after['slot_values'][s.STRIDE:],before['slot_values'][s.STRIDE:])
        self.assertEqual(after['slot_unrelated_sha256'],'sentinel')

    def test_volume_zero_hard_pan_and_fractional_attenuation(self):
        self.assertEqual(s.pan_volume(0,0),[0,0])
        self.assertEqual(s.pan_volume(7,0),[16384,16384])
        self.assertEqual(s.pan_volume(7,1),[12288,16384])
        self.assertEqual(s.pan_volume(7,15),[0,16384])
        self.assertEqual(s.pan_volume(7,31),[16384,0])
        before=self.fixture();before['slot_values'][11]=0xE000
        after=s.transition(before,0x100017,0xFF)
        self.assertEqual(after['slot_values'][29:33],[16384,16384,16384,0])

    def test_unsupported_addresses_and_values_fail_closed(self):
        for address in (0xFFFFF,0x100001,0x100400,True):
            with self.subTest(address=address),self.assertRaises(ValueError):s.transition(self.fixture(),address,0)
        for value in (-1,256,True):
            with self.assertRaises(ValueError):s.transition(self.fixture(),0x100000,value)

    def test_layout_and_immutable_parent_generations(self):
        self.assertEqual(ctypes.sizeof(s.Result),98400)
        self.assertIsNot(s.Result,s.capacity.Result)
        self.assertEqual(s.Result.events.offset,s.capacity.Result.events.offset)
        self.assertEqual(s.capacity.ABI,6);self.assertEqual(s.device.ABI,4)
        source=s.generated_source()
        self.assertIn(b'uint32_t neptune_m68k_abi(void) { return 7; }',source)
        self.assertIn(b'value&0xFF',source)
        with patch.object(s.capacity,'generated_source',return_value=b'changed'),self.assertRaises(ValueError):s.generated_source()
        parent=s.capacity.generated_source()
        with patch.object(s.capacity,'generated_source',return_value=parent+parent),self.assertRaises(ValueError):s.generated_source()
        with self.assertRaises(ValueError):s.between('xSTARTySTARTzEND','START','END')


if __name__=='__main__':unittest.main()
