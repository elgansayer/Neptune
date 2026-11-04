import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_japan_a694_smpc_scsp as probe

class JapanA694SmpcScspTests(unittest.TestCase):
    def test_original_switch_and_return_ranges(self):
        self.assertEqual((probe.ENTRY,probe.RETURN),(0x0600A694,0xFFFFFE00))
        self.assertEqual(probe.MODES,(0,1,2,3))
        self.assertEqual(len(probe.cases()),8)
        self.assertEqual(probe.LIMIT,4096)

    def test_original_smpc_scsp_literals(self):
        self.assertEqual(probe.LITERALS[0x0600A764],(4,0x2010001F))
        self.assertEqual(probe.LITERALS[0x0600A768],(4,0x25B00400))
        self.assertEqual(probe.LITERALS[0x0600A76C],(4,0x25A00000))
        self.assertEqual(probe.LITERALS[0x0600A744],(2,0x03FC))
        self.assertEqual(probe.LITERALS[0x0600A778],(4,0x25A00400))

    def test_mode1_scsp_write_extent(self):
        self.assertEqual(0x03FC//4+1,256)
        self.assertEqual(probe.DSP_RAM-probe.SCSP_RAM,0x400)

if __name__=="__main__": unittest.main()
