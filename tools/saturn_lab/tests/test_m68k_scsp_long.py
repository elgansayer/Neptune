"""Independent logical/layout/identity guards; actual native preparation is separate."""
import ctypes
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_scsp_long as m


class LongContracts(unittest.TestCase):
    def fixture(self):
        return {'coef':[0]*64,'madrs':[0]*32,'mprog':[0]*128,'dirty':0,'temp':[0]*128,
                'slot_values':[123],'slot_unrelated_sha256':'slot','unrelated_sha256':'dsp'}

    def test_coef_and_madrs_word_lanes_and_normal_longword_order(self):
        before=self.fixture();after=m.transition(before,0x100700,0x1234ABCD,4)
        self.assertEqual(after['coef'][:3],[0x246,0x1579,0])
        after=m.transition(before,0x100780,0x1234ABCD,4)
        self.assertEqual(after['madrs'][:3],[0x1234,0xABCD,0])
        self.assertEqual(before,self.fixture())
        self.assertEqual(after['slot_values'],[123])
        self.assertEqual(after['unrelated_sha256'],'dsp')

    def test_program_words_pack_all_four_lanes_and_invalidate_identical_writes(self):
        before=self.fixture();before['mprog'][0]=0x1122334455667788
        after=m.transition(before,0x100800,0x1234ABCD,4)
        self.assertEqual(after['mprog'][0],0x1234ABCD55667788)
        self.assertEqual(after['dirty'],1)
        after=m.transition(before,0x100804,0x1234ABCD,4)
        self.assertEqual(after['mprog'][0],0x112233441234ABCD)
        after=m.transition(before,0x100800,0x1122,2)
        self.assertEqual(after['mprog'],before['mprog']);self.assertEqual(after['dirty'],1)
        self.assertEqual(after['temp'],before['temp'])

    def test_temp_longword_packing_and_sign_are_not_big_endian_flat_ram(self):
        after=m.transition(self.fixture(),0x100C00,0x12345678,4)
        self.assertEqual(after['temp'][:2],[0x567834,0])
        after=m.transition(self.fixture(),0x100C00,0x12FFFF80,4)
        self.assertEqual(after['temp'][0],0xFFFF80FF)
        after=m.transition(self.fixture(),0x100DFC,0xFFFFFFFF,4)
        self.assertEqual(after['temp'][-1],0xFFFFFFFF)
        self.assertEqual(after['temp'][:-1],[0]*127)
        self.assertEqual(after['dirty'],0)

    def test_temp_word_masks_lanes_and_sign_extension_preserving_the_other_bits(self):
        before=self.fixture();before['temp'][0]=0x123456
        self.assertEqual(m.transition(before,0x100C00,0xABCD,2)['temp'][0],0x1234CD)
        self.assertEqual(m.transition(before,0x100C02,0x8000,2)['temp'][0],0xFF800056)
        self.assertEqual(m.transition(before,0x100C02,0x7FFF,2)['temp'][0],0x7FFF56)
        before['temp'][0]=0xFF800056
        self.assertEqual(m.read_word(before,0x100C00),0x56)
        self.assertEqual(m.read_word(before,0x100C02),0x8000)

    def test_gap_writes_have_no_register_effect_and_reads_are_undefined(self):
        before=self.fixture()
        for address in (0x1007C0,0x1007FC):self.assertEqual(m.transition(before,address,0xFFFFFFFF,4),before)
        with self.assertRaises(ValueError):m.read_word(before,0x1007C0)

    def test_unsupported_width_value_alignment_and_cross_boundary_fail(self):
        for address in (0x1006FC,0x100701,0x100702,0x100DFE,0x100E00,True):
            with self.subTest(address=address),self.assertRaises(ValueError):m.transition(self.fixture(),address,0,4)
        for size in (0,1,3,True):
            with self.assertRaises(ValueError):m.transition(self.fixture(),0x100700,0,size)
        for value in (-1,2**32,True):
            with self.assertRaises(ValueError):m.transition(self.fixture(),0x100700,value,4)
        with self.assertRaises(ValueError):m.transition(self.fixture(),0x100700,65536,2)

    def test_abi8_result_capacity_parent_generations_and_mode_guard(self):
        self.assertEqual(ctypes.sizeof(m.Result),98400)
        self.assertIsNot(m.Result,m.slots.Result)
        self.assertEqual(m.slots.ABI,7);self.assertEqual(m.slots.capacity.ABI,6)
        parent=m.slots.generated_source();self.assertIn(b'return 7;',parent)
        source=m.generated_source();self.assertIn(b'return 8;',source)
        self.assertIn(b'((opcode>>6)&7)==4',source)
        self.assertEqual(m.VALUES,225+128)
        with patch.object(m.slots,'generated_source',return_value=b'changed'),self.assertRaises(ValueError):m.generated_source()
        with patch.object(m.slots,'generated_source',return_value=parent+parent),self.assertRaises(ValueError):m.generated_source()

    def test_source_tampering_fails_before_extraction_or_native_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'COPYING').write_text('wrong')
            with self.assertRaisesRegex(ValueError,'Pinned longword source changed'):
                m.extract_component(root)
            with patch.object(m.c,'CDLL') as load,self.assertRaises((OSError,ValueError)):
                m.Library(root)
            load.assert_not_called()

    def test_bus_count_is_checked_before_copying_native_buffer(self):
        class Fake:
            def neptune_dsp_bus_count(self):return m.BUS_LIMIT+1
            def neptune_dsp_bus_snapshot(self,*args):raise AssertionError('must not copy')
        library=object.__new__(m.Library);library.library=Fake()
        with self.assertRaisesRegex(ValueError,'bus trace count'):library.bus_trace()


if __name__=='__main__':unittest.main()
