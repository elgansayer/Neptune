"""Independent word semantics and fail-closed adapter construction."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_scsp_dsp as m


class DspTests(unittest.TestCase):
    def state(self):
        return {'coef':[0x1234]*64,'madrs':[0xABCD]*32,'mprog':[0x0123456789ABCDEF]*128,
                'dirty':0,'unrelated_sha256':'preserved'}

    def test_coefficient_truncation_address_endpoints_and_gap_noop(self):
        before=self.state()
        for address,index in ((0x100700,0),(0x10077E,63)):
            expected=self.state(); expected['coef'][index]=0x1FFF
            self.assertEqual(m.transition(before,address,0xFFFF),expected)
        for address in (0x1007C0,0x1007FE):
            self.assertEqual(m.transition(before,address,0xFFFF),before)
        self.assertEqual(before,self.state())

    def test_madrs_endpoints_and_all_four_big_endian_program_lanes(self):
        before=self.state()
        for address,index in ((0x100780,0),(0x1007BE,31)):
            expected=self.state(); expected['madrs'][index]=0xFFFF
            self.assertEqual(m.transition(before,address,0xFFFF),expected)
        for base,index in ((0x100800,0),(0x100BF8,127)):
            for lane in range(4):
                expected=self.state(); shift=(3-lane)*16
                expected['mprog'][index]=(before['mprog'][index]&~(0xFFFF<<shift))|(0xF00D<<shift)
                expected['dirty']=1
                self.assertEqual(m.transition(before,base+2*lane,0xF00D),expected)
        # Identical writes still invalidate the decoded program.
        self.assertEqual(m.transition(before,0x100800,0x0123)['dirty'],1)

    def test_unsupported_addresses_and_values_never_get_a_ram_transition(self):
        for address in (0x1006FE,0x100701,0x1007FF,0x100C00,-1,True):
            with self.subTest(address=address),self.assertRaises(ValueError):
                m.transition(self.state(),address,0)
        for value in (-1,65536,True):
            with self.assertRaises(ValueError):m.transition(self.state(),0x100700,value)

    def test_profile_does_not_remove_alignment_region_or_execution_guards(self):
        source=m.generated_source()
        self.assertIn(b'uint32_t neptune_m68k_abi(void) { return 4; }',source)
        self.assertEqual(source.count(b'if (size > 1 && address & 1) fail(3, address, size);'),2)
        self.assertIn(b'(uint64_t)a->lo + a->size > 0x80000',source)
        self.assertIn(b'neptune_dsp_access(0,address,size,&bus)',source)
        self.assertIn(b'neptune_dsp_access(1,address,size,&bus)',source)
        self.assertEqual((m.short.MAX_STEPS,m.short.MAX_EVENTS),(256,128))

    def test_preparation_identity_includes_the_executable_verifier(self):
        expected=m.pinned.digest(Path(m.__file__).read_bytes())
        self.assertEqual(m.identity()['preparation_module_sha256'],expected)

    def test_changed_base_and_missing_or_changed_reference_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); changed=root/'base.c'; changed.write_bytes(b'changed')
            with patch.object(m.short,'BACKEND',changed),self.assertRaises(ValueError):m.generated_source()
            with self.assertRaises(OSError):m.extract_component(root)
            (root/'COPYING').write_bytes(b'changed')
            with self.assertRaises(ValueError):m.extract_component(root)


if __name__=='__main__':unittest.main()
