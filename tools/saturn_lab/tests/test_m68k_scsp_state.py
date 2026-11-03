"""Recipe, layout and fail-closed construction; native acceptance is separate."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_scsp_state as m


class StateNativeTests(unittest.TestCase):
    def test_source_changes_only_bounded_capacity_and_version(self):
        source=m.generated_source()
        for text in (b'#define MAX_STEPS 2048',b'#define MAX_EVENTS 1024',
                     b'#define MAX_REGIONS 16',b'#define MAX_RANGES 16',
                     b'uint32_t neptune_m68k_abi(void) { return 5; }'):
            self.assertEqual(source.count(text),1)
        self.assertIn(b'if (size > 1 && address & 1) fail(3, address, size);',source)
        self.assertIn(b'(uint64_t)a->lo + a->size > 0x80000',source)
        self.assertIn(b'A controlled data overlay must not replace executable instruction bytes',source)
        self.assertIn(b'neptune_dsp_access(1,address,size,&bus)',source)
        self.assertIn(b'uint32_t neptune_m68k_abi(void) { return 4; }',m.device.generated_source())
        self.assertEqual((m.short.MAX_STEPS,m.short.MAX_EVENTS),(256,128))

    def test_changed_layout_or_ambiguous_base_rejects_before_compilation(self):
        with patch.object(m.capacity,'MAX_EVENTS',1023),self.assertRaises(ValueError):m.generated_source()
        with patch.object(m.device,'generated_source',return_value=b'changed'),self.assertRaises(ValueError):m.generated_source()
        source=m.device.generated_source()
        with patch.object(m.device,'generated_source',return_value=source+source),self.assertRaises(ValueError):m.generated_source()

    def test_identity_binds_state_verifier_device_and_trace_layout(self):
        identity=m.identity()
        self.assertEqual(identity['device_identity'],m.device.identity())
        self.assertEqual(identity['preparation_module_sha256'],m.pinned.digest(Path(m.__file__).read_bytes()))
        self.assertEqual(identity['capacity_adapter_sha256'],m.pinned.digest(Path(m.capacity.__file__).read_bytes()))

    def test_owned_fixture_reads_every_region_and_balances_disjoint_calls(self):
        code,regs,regions,ranges,expected,after,events,pcs=m.owned_case()
        self.assertEqual((len(regions),len(ranges),len(pcs),len(events)),(16,16,47,47))
        self.assertEqual({e[1] for e in events if e[0]==1 and e[2]==2},{r[0] for r in regions})
        self.assertEqual(expected[15:18],[0x70004,0xFFF000,0x2710])
        self.assertEqual(expected[0]&0xFFFF,562)
        self.assertEqual(after[1:],[r[1] for r in regions[1:]])
        self.assertEqual(after[0][:68],regions[0][1][:68])
        self.assertEqual(events[-1],[1,0x70000,4,0xFFF000])
        self.assertEqual(pcs[-1],0x10C)
        self.assertEqual(len(code),0x500)

    def test_python_overflow_rejects_before_device_or_native_calls(self):
        library=m.Library.__new__(m.Library)
        for ranges,regions in ((17,16),(16,17)):
            code,regs,ram,spans,*_=m.owned_case(ranges,regions)
            with patch.object(library,'configure',side_effect=AssertionError('must not configure')):
                with self.assertRaises(ValueError):library.run(code,0x100,0xFFF000,spans,ram,regs)


if __name__=='__main__':unittest.main()
