"""Fail-closed preparation and independent FIFO transition examples."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_scsp_fifo as m


class FifoNativeTests(unittest.TestCase):
    def test_definition_extraction_excludes_prototypes_and_comment_braces(self):
        source='static void example(int a);\nstatic void example(int a) // function\n{\n /* } */ if(a) { a++; } // }\n}\n'
        self.assertEqual(m.function(source,'example'),source[source.index('static void example(int a) //'):])
        with self.assertRaises(ValueError):m.function(source+source,'example')
        with self.assertRaises(ValueError):m.function('static void example(int a);','example')

    def test_only_selected_byte_device_lanes_bypass_ram_guards(self):
        source=m.generated_source()
        self.assertIn(b'address==0x100404 && size==1',source)
        self.assertIn(b'address==0x100407 && size==1',source)
        self.assertIn(b'SS_SCSP_MIDI_WriteOutput(&fifo,value&255)',source)
        self.assertIn(b'if (size > 1 && address & 1) fail(3, address, size);',source)
        self.assertIn(b'uint32_t neptune_m68k_abi(void) { return 3; }',source)
        self.assertEqual(m.short.MAX_STEPS,256)
        self.assertEqual(m.short.MAX_EVENTS,128)

    def test_changed_backend_or_reference_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);changed=root/'changed.c';changed.write_text('changed')
            with patch.object(m.short,'BACKEND',changed),self.assertRaises(ValueError):m.generated_source()
            (root/'COPYING').write_text('changed')
            with self.assertRaises(ValueError):m.extract_component(root)

    def test_reset_ring_wrap_full_and_pending_contract(self):
        reset=m.fifo_contract()
        self.assertEqual(reset['flags'],9)
        self.assertEqual(reset['count'],0)
        seeded=m.fifo_contract(3,3,0x12345678,0x200,push=0xE7)
        self.assertEqual([seeded[f'output{i}'] for i in range(4)],[0x34,0x56,0xE7,0x12])
        self.assertEqual((seeded['rp'],seeded['wp'],seeded['count'],seeded['flags']),(3,3,4,0x11))
        self.assertEqual((seeded['scipd'],seeded['mcipd']),(0,0))
        full=m.fifo_contract(4,3,0x12345678,0x200)
        self.assertEqual(m.fifo_contract(4,3,0x12345678,0x200,push=0xE7),full)


if __name__=='__main__':unittest.main()
