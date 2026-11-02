"""Static-analysis wrapper tests with owned synthetic inputs only."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_sound_driver as sound


class SoundDiscoveryTests(unittest.TestCase):
    def vectors(self):
        data = bytearray(0x420)
        data[:4] = (0x10000).to_bytes(4, 'big')
        data[4:8] = (0x400).to_bytes(4, 'big')
        data[8:12] = (0x410).to_bytes(4, 'big')
        return data

    def test_vector_identity_has_no_execution_claim(self):
        result = sound.vector_summary(self.vectors())
        self.assertEqual(result['reset_pc'], '0x400')
        self.assertEqual(result['vector_entries'], ['0x400', '0x410'])
        self.assertEqual(result['vector_target_counts']['0x0'], 253)

    def test_rejects_odd_outside_and_vector_table_reset_targets(self):
        for pc in (0x401, 0x420, 0, 0x3FE):
            data = self.vectors()
            data[4:8] = pc.to_bytes(4, 'big')
            with self.assertRaises(ValueError): sound.vector_summary(data)
        with self.assertRaises(ValueError): sound.vector_summary(bytes(1023))

    def test_sound_lifetimes_remain_separate(self):
        self.assertEqual(set(sound.SOURCES), {'SND', 'XBSND', 'NLSND'})
        self.assertEqual(len({row[1] for row in sound.SOURCES.values()}), 3)

    def test_source_container_identity_precedes_slice(self):
        owned = bytes(range(32))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'owned'
            path.write_bytes(owned)
            identity = (32, sound.pinned.digest(owned), 4, 8)
            with patch.dict(sound.SOURCES, {'OWNED': identity}):
                self.assertEqual(sound.source_bytes(path, 'OWNED'), owned[4:12])
                path.write_bytes(owned[:-1] + b'\xFF')
                with self.assertRaises(ValueError): sound.source_bytes(path, 'OWNED')

    def test_changed_decoder_source_fails_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'src/saturnrecomp/m68k.py'
            path.parent.mkdir(parents=True)
            path.write_text('raise AssertionError("must never execute")')
            with self.assertRaises(ValueError): sound.decoder(root)

    def test_missing_source_report_is_private_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'failed.json'
            args = ['--source-file', str(root/'missing'), '--module', 'SND',
                    '--saturn-recomp', str(root), '--cache', str(root/'cache'), '--report', str(report)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sound.main(args), 1)
            original = report.read_bytes()
            self.assertEqual(json.loads(original)['error']['phase'], 'source_identity')
            self.assertNotIn(str(root), original.decode())
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sound.main(args), 1)
            self.assertEqual(report.read_bytes(), original)


if __name__ == '__main__': unittest.main()
