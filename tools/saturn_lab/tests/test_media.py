"""Synthetic headers/firmware exercise parsers only, never original-game evidence."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import media


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "disc").mkdir()
        self.header = bytearray(b" " * 2048)
        self.header[:16] = b"SEGA SEGASATURN "
        self.header[0x20:0x30] = b"TEST-0001 V1.000"
        self.header[0x40] = ord("U")
        title = b"SYNTHETIC TOOL FIXTURE"
        self.header[0x60:0x60 + len(title)] = title
        self.write_disc()
        self.bios = b"synthetic-only".ljust(524288, b"\0")
        (self.root / "bios.bin").write_bytes(self.bios)
        self.catalog = {"filename": "mpr-17933.bin", "md5": hashlib.md5(self.bios, usedforsecurity=False).hexdigest()}
        self.patch = patch.dict(media.FIRMWARE, {"usa": self.catalog})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_disc(self, mode="MODE1/2352", index="00:00:00", leading=0):
        sector = (b"\0" + b"\xff" * 10 + b"\0" + b"\0\x02\0\x01" + bytes(self.header) + b"\0" * 288) if mode.endswith("2352") else bytes(self.header)
        (self.root / "disc/data.bin").write_bytes(b"\0" * leading + sector)
        (self.root / "disc/audio.bin").write_bytes(b"synthetic audio")
        (self.root / "disc/game.cue").write_text(f'FILE "data.bin" BINARY\n TRACK 01 {mode}\n INDEX 01 {index}\nFILE "audio.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')

    def inspect(self):
        return media.inspect_media(self.root, "disc/game.cue", "usa")

    def test_real_file_dependency_parser_keeps_first_data_file(self):
        result = self.inspect()
        self.assertEqual(result["header"]["source"]["path"], "disc/data.bin")
        self.assertEqual(result["header"]["product"], "TEST-0001")
        self.assertEqual(result["header"]["revision"], "V1.000")
        self.assertEqual(result["header"]["title"], "SYNTHETIC TOOL FIXTURE")
        self.assertEqual(result["track_file_count"], 2)
        self.assertEqual(len(result["files"]), 4)

    def test_cooked_mode_and_nonzero_raw_index(self):
        self.write_disc(mode="MODE1/2048")
        self.assertEqual(self.inspect()["header"]["area_symbols"], "U")
        self.write_disc(index="00:00:01", leading=2352)
        self.assertEqual(self.inspect()["header"]["source"]["index_sector"], 1)

    def test_missing_audio_dependency_is_not_silently_skipped(self):
        (self.root / "disc/audio.bin").unlink()
        with self.assertRaisesRegex(media.LabError, "Missing"):
            self.inspect()

    def test_wrong_signature_mode_truncation_and_encoding_fail(self):
        for position in [0, 15, 16, 16 + 0x20]:
            self.write_disc()
            path = self.root / "disc/data.bin"
            data = bytearray(path.read_bytes())
            data[position] = 255
            path.write_bytes(data)
            with self.assertRaises(media.LabError): self.inspect()
        (self.root / "disc/data.bin").write_bytes(b"short")
        with self.assertRaisesRegex(media.LabError, "Truncated"):
            self.inspect()

    def test_bad_index_and_unsupported_track_reject(self):
        for index in ["00:00:75", "00:60:00", "-1:00:00", "00:00:99"]:
            self.write_disc(index=index)
            with self.assertRaises(media.LabError): self.inspect()
        self.write_disc(mode="MODE2/2352")
        with self.assertRaisesRegex(media.LabError, "MODE1"):
            self.inspect()

    def test_region_and_firmware_bytes_are_independent_of_filename(self):
        (self.root / "bios.bin").rename(self.root / "arbitrary.rom")
        result = self.inspect()
        self.assertEqual(result["bios"], "arbitrary.rom")
        self.assertEqual(result["firmware"]["filename"], "mpr-17933.bin")
        self.header[0x40] = ord("J")
        self.write_disc()
        with self.assertRaisesRegex(media.LabError, "region"):
            self.inspect()

    def test_duplicate_firmware_aliases_preserve_identity(self):
        (self.root / "alias.bin").write_bytes(self.bios)
        result = self.inspect()
        self.assertEqual(result["matching_bios_paths"], ["alias.bin", "bios.bin"])
        self.assertEqual(result["bios"], "alias.bin")

    def test_inconsistent_lookup_aliases_fail_even_with_explicit_selection(self):
        # Controlled lookup collision exercises policy, not a real MD5 collision
        # claim. SHA-256 is still computed from the two different fixture files.
        (self.root / "alias.bin").write_bytes(b"different synthetic bytes".ljust(524288, b"\0"))
        with patch.object(media.hashlib, "md5") as lookup:
            lookup.return_value.hexdigest.return_value = self.catalog["md5"]
            for selected in [None, "bios.bin"]:
                with self.assertRaisesRegex(media.LabError, "Ambiguous"):
                    media.inspect_media(self.root, "disc/game.cue", "usa", selected)

    def test_wrong_size_explicit_bios_and_no_match_fail(self):
        (self.root / "wrong.bin").write_bytes(b"wrong")
        with self.assertRaisesRegex(media.LabError, "Explicit BIOS"):
            media.inspect_media(self.root, "disc/game.cue", "usa", "wrong.bin")
        (self.root / "bios.bin").unlink()
        with self.assertRaisesRegex(media.LabError, "No checksum"):
            self.inspect()

    def test_report_repeatability_and_tamper_detection(self):
        result = self.inspect()
        self.assertEqual(result, self.inspect())
        self.assertEqual(media.verify_media(self.root, result), 4)
        (self.root / "disc/audio.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(media.LabError, "differs"):
            media.verify_media(self.root, result)

    def test_report_fields_and_catalogue_do_not_alias(self):
        result = self.inspect()
        result["firmware"]["md5"] = "0" * 32
        self.assertEqual(media.FIRMWARE["usa"], self.catalog)
        with self.assertRaisesRegex(media.LabError, "differs"):
            media.verify_media(self.root, result)
        for bad in [None, {}, {"schema": media.SCHEMA}, {"schema": "future"}]:
            with self.assertRaises(media.LabError): media.verify_media(self.root, bad)

    def test_symlinks_and_unsafe_cue_paths_fail(self):
        (self.root / "disc/game.cue").write_text('FILE "../bios.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n')
        with self.assertRaises(media.LabError): self.inspect()
        self.write_disc()
        (self.root / "alias.bin").symlink_to(self.root / "bios.bin")
        with self.assertRaisesRegex(media.LabError, "Symlink"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
