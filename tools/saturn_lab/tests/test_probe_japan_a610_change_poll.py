import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probe_japan_a610_change_poll as probe

class JapanA610ChangePollTests(unittest.TestCase):
    def test_original_bounds_and_poll_word(self):
        self.assertEqual((probe.ENTRY,probe.RETURN),(0x0600A610,0xFFFFFE00))
        self.assertEqual((probe.LITERAL,probe.POLL_WORD),(0x0600A62C,0x060B3D40))
        self.assertEqual(probe.LIMIT,128)

    def test_explicit_samples_repeat_until_first_change(self):
        self.assertEqual(len(probe.cases()),8)
        for initial,polls in probe.SAMPLES:
            self.assertTrue(polls)
            self.assertNotEqual(polls[-1],initial)
            self.assertTrue(all(value==initial for value in polls[:-1]))

    def test_signed_halfword_boundaries_are_preserved(self):
        self.assertEqual([probe.signed_word(x) for x in (0,0x7fff,0x8000,0xffff)],[0,32767,-32768,-1])

if __name__=="__main__": unittest.main()
