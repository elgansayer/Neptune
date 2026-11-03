"""Separate ABI6 construction/layout tests; native/original execution is separate."""
from pathlib import Path
import ctypes
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_reset_capacity as m


class ResetCapacityTests(unittest.TestCase):
    def test_only_trace_storage_and_abi_change_from_accepted_state_backend(self):
        before=m.state.generated_source()
        expected=before.replace(b'#define MAX_STEPS 2048',b'#define MAX_STEPS 8192').replace(
            b'#define MAX_EVENTS 1024',b'#define MAX_EVENTS 4096').replace(
            b'uint32_t neptune_m68k_abi(void) { return 5; }',b'uint32_t neptune_m68k_abi(void) { return 6; }')
        self.assertEqual(m.generated_source(),expected)
        self.assertEqual((m.state.ABI,m.state.MAX_STEPS,m.state.MAX_EVENTS),(5,2048,1024))
        self.assertEqual((m.short.MAX_STEPS,m.short.MAX_EVENTS),(256,128))
        self.assertIn(b'#define MAX_RANGES 16',expected)
        self.assertIn(b'#define MAX_REGIONS 16',expected)

    def test_ambiguous_or_changed_accepted_generation_fails_before_compile(self):
        with patch.object(m.state,'MAX_EVENTS',1023),self.assertRaises(ValueError):m.generated_source()
        with patch.object(m.state,'generated_source',return_value=b'changed'),self.assertRaises(ValueError):m.generated_source()
        source=m.state.generated_source()
        with patch.object(m.state,'generated_source',return_value=source+source),self.assertRaises(ValueError):m.generated_source()

    def test_native_result_layout_has_distinct_full_bounded_arrays(self):
        self.assertEqual(m.Result.pcs.offset,20)
        self.assertEqual(m.Result.after.offset,20+8192*4)
        self.assertEqual(m.Result.events.offset,20+8192*4+18*4+4)
        self.assertEqual(ctypes.sizeof(m.Result),20+8192*4+18*4+4+4096*ctypes.sizeof(m.short.Event))
        self.assertGreater(ctypes.sizeof(m.Result),ctypes.sizeof(m.state.capacity.Result))

    def test_identity_binds_new_preparer_and_unchanged_state_lineage(self):
        identity=m.identity()
        self.assertEqual(identity['accepted_state_identity'],m.state.identity())
        self.assertEqual(identity['abi'],6)
        self.assertEqual(identity['preparation_module_sha256'],m.pinned.digest(Path(m.__file__).read_bytes()))
        self.assertEqual((identity['max_steps'],identity['max_events']),(8192,4096))

    def test_unneeded_range_region_or_instruction_expansion_is_rejected_before_dispatch(self):
        library=m.Library.__new__(m.Library)
        for ranges,regions in ((17,16),(16,17)):
            code,regs,ram,spans,*_=m.owned_case(ranges,regions)
            with patch.object(library,'configure',side_effect=AssertionError('must not configure')):
                with self.assertRaises(ValueError):library.run(code,0x100,0xFFF000,spans,ram,regs)
        code,regs,ram,spans,*_=m.owned_case()
        with patch.object(library,'configure',side_effect=AssertionError('must not configure')):
            with self.assertRaises(ValueError):library.run(code,0x100,0xFFF000,spans,ram,regs,budget=8193)


if __name__=='__main__':unittest.main()
