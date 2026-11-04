import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_japan_a680_vdp2_clear as probe

class JapanA680Vdp2ClearTests(unittest.TestCase):
    def test_original_function_helper_and_captured_pointer(self):
        self.assertEqual((probe.ENTRY,probe.RETURN),(0x0600A680,0xFFFFFE00))
        self.assertEqual((probe.POINTER_WORD,probe.POINTER_VALUE),(0x060B3D48,0x25F00800))
        self.assertEqual((probe.VDP2_START,probe.SIZE),(0x25F00800,0x200))

    def test_original_size_and_memory_intent_extent(self):
        self.assertEqual(probe.LITERALS[0x0600A742],(2,0x01FE))
        self.assertEqual(probe.SIZE//2,256)
        self.assertEqual(probe.VDP2_START+probe.SIZE-2,0x25F009FE)
        self.assertEqual(probe.LIMIT,2048)

    def test_seed_corpus(self):
        self.assertEqual(probe.SEEDS,(0,1))

if __name__=="__main__":unittest.main()
