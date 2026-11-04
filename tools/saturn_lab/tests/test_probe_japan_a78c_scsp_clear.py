import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_japan_a78c_scsp_clear as probe

class JapanA78cScspClearTests(unittest.TestCase):
    def test_original_entry_helper_and_scsp_range(self):
        self.assertEqual((probe.ENTRY,probe.RETURN),(0x0600A78C,0xFFFFFE00))
        self.assertEqual((probe.SCSP_RAM,probe.SIZE),(0x25B00800,0x400))
        self.assertEqual(probe.LIMIT,8192)

    def test_original_literals_and_full_word_extent(self):
        self.assertEqual(probe.LITERALS[0x0600A794],(2,0x0400))
        self.assertEqual(probe.LITERALS[0x0600A798],(4,probe.SCSP_RAM))
        self.assertEqual(probe.SIZE//2,512)
        self.assertEqual(probe.SCSP_RAM+probe.SIZE-2,0x25B00BFE)

    def test_direct_corpus_has_only_register_seeds(self):
        self.assertEqual(probe.SEEDS,(0,1))

if __name__=="__main__": unittest.main()
