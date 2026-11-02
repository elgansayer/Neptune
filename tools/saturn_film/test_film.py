"""Owned synthetic packets exercise rejection and exact channel/sample recovery."""

from __future__ import annotations

from fractions import Fraction
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.saturn_film.cli import main
from tools.saturn_film.film import FilmError, extract, load, parse, rational
from tools.saturn_film.validate_real import packet_timing_matches, parser_controls, validate


def fixture(channels: int = 2) -> bytes:
    # Synthetic Cinepak-labelled packet bytes are deliberately not a video codec fixture.
    packets = [(b"\x00\x7f\x80\xff\x01\x02\x03\x04", 0xFFFFFFFF, 1),
               (b"OWN1", 0, 24), (b"OWN2", 0x80000018, 24),
               (b"\x10\x20\x30\x40", 0xFFFFFFFF, 1)]
    rows = []
    offset = 0
    for data, pts, duration in packets:
        rows.append(struct.pack(">4I", offset, len(data), pts, duration))
        offset += len(data)
    fdsc = b"FDSC" + struct.pack(">I4sIIBBBB H6s", 32, b"cvid", 2, 2,
                                 24, channels, 8, 0, 22050, bytes(6))
    stab = b"STAB" + struct.pack(">3I", 16 + len(rows) * 16, 600, len(rows)) + b"".join(rows)
    return b"FILM" + struct.pack(">I", 16 + len(fdsc) + len(stab)) + b"1.04" + bytes(4) + fdsc + stab + b"".join(p[0] for p in packets)


class FilmTests(unittest.TestCase):
    def test_exact_planar_stereo_signed_extremes_and_packet_boundary(self):
        film = parse(fixture())
        self.assertEqual(film.pcm_s8(), bytes([0, 1, 127, 2, 128, 3, 255, 4, 16, 48, 32, 64]))
        table = film.sample_table()
        self.assertEqual(table[0]["start_sample_frame"], 0)
        self.assertEqual(table[3]["start_sample_frame"], 4)
        self.assertEqual(table[2]["pts_ticks"], 24)
        self.assertFalse(table[2]["keyframe"])
        self.assertEqual(table[0]["source_offset"], 128)

    def test_mono_and_exact_rational_time(self):
        film = parse(fixture(channels=1))
        self.assertEqual(film.pcm_s8(), bytes([0, 127, 128, 255, 1, 2, 3, 4, 16, 32, 48, 64]))
        report = film.report()
        self.assertEqual(report["video"]["duration_seconds"], rational(Fraction(2, 25)))
        self.assertEqual(report["video"]["average_frames_per_second"], rational(Fraction(25)))
        self.assertEqual(report["audio"]["duration_seconds"], rational(Fraction(12, 22050)))
        self.assertEqual(report["source"]["lineage"], "prior-assets-unresolved-release")
        self.assertFalse(report["source"]["pinned_usa_or_japan_original"])

    def test_deterministic_artifacts_wave_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            film = parse(fixture())
            extract(film, root / "one")
            extract(film, root / "two")
            for path in (root / "one").iterdir():
                self.assertEqual(path.read_bytes(), (root / "two" / path.name).read_bytes())
            with wave.open(str(root / "one/audio.wav"), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 2)
                self.assertEqual(stream.getsampwidth(), 1)
                self.assertEqual(stream.getnframes(), 6)
                self.assertEqual(stream.getframerate(), 22050)
                self.assertEqual(bytes(x ^ 128 for x in stream.readframes(6)), film.pcm_s8())
            with self.assertRaises(FileExistsError):
                extract(film, root / "one")
            self.assertTrue((root / "one/audio.wav").is_file())

    def test_header_versions_extensions_and_unsupported_formats_rejected(self):
        cases = [(0, b"NOPE"), (8, b"1.09"), (12, b"\0\0\0\1"),
                 (16, b"OTHER"), (20, struct.pack(">I", 40)), (24, b"mpeg"),
                 (28, struct.pack(">I", 0)), (32, struct.pack(">I", 5000)),
                 (36, bytes([16])), (37, bytes([3])), (38, bytes([16])),
                 (39, bytes([1])), (40, bytes(2)), (42, bytes([1])),
                 (48, b"STUB")]
        for offset, replacement in cases:
            with self.subTest(offset=offset):
                data = bytearray(fixture())
                data[offset:offset + len(replacement)] = replacement
                with self.assertRaises(FilmError):
                    parse(bytes(data))

    def test_table_ranges_counts_payload_truncation_and_trailer_rejected(self):
        cases = [(4, 64), (52, 64), (56, 0), (60, 100001), (64, 1),
                 (68, 0), (80, 0), (84, 10000)]
        for offset, replacement in cases:
            with self.subTest(offset=offset):
                data = bytearray(fixture())
                struct.pack_into(">I", data, offset, replacement)
                with self.assertRaises(FilmError):
                    parse(bytes(data))
        for data in (fixture()[:20], fixture()[:-1], fixture() + b"\0"):
            with self.assertRaises(FilmError):
                parse(data)

    def test_audio_tags_partial_frames_and_video_timing_rejected(self):
        cases = [(76, 0), (68, 7), (88, 1), (88, 0x80000000),
                 (92, 0), (104, 23), (104, 25)]
        for offset, replacement in cases:
            with self.subTest(offset=offset):
                data = bytearray(fixture())
                struct.pack_into(">I", data, offset, replacement)
                with self.assertRaises(FilmError):
                    parse(bytes(data))

    def test_budgets_enforced(self):
        for name, maximum in [("MAX_FILE_BYTES", 64), ("MAX_HEADER_BYTES", 64),
                              ("MAX_SAMPLES", 2), ("MAX_PACKET_BYTES", 4),
                              ("MAX_AUDIO_BYTES", 8)]:
            with self.subTest(name=name), patch(f"tools.saturn_film.film.{name}", maximum):
                with self.assertRaises(FilmError):
                    parse(fixture())

    def test_symlinks_and_missing_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").write_bytes(fixture())
            (root / "link").symlink_to(root / "source")
            (root / "linked-directory").symlink_to(root, target_is_directory=True)
            for path in (root / "link", root / "linked-directory/source", root / "missing"):
                with self.assertRaises(FilmError):
                    load(path)
            with self.assertRaises(FilmError):
                extract(parse(fixture()), root / "linked-directory/out")

    def test_failed_write_cleans_only_own_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(Path, "write_bytes", side_effect=OSError("injected failure")):
                with self.assertRaises(OSError):
                    extract(parse(fixture()), output)
            self.assertFalse(output.exists())

    def test_private_output_even_with_permissive_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "private"
            previous = os.umask(0)
            try:
                extract(parse(fixture()), output)
            finally:
                os.umask(previous)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)

    def test_cli_fails_closed_and_does_not_write_on_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.cpk"
            source.write_bytes(fixture()[:-1])
            output = Path(directory) / "output"
            self.assertEqual(main(["extract", "--input", str(source), "--output", str(output)]), 1)
            self.assertFalse(output.exists())

    def test_independent_packet_comparison_rejects_tick_and_keyframe_changes(self):
        film = parse(fixture())
        packets = [{"pts": 0, "duration": 24, "flags": "K_"},
                   {"pts": 24, "duration": 24, "flags": "__"}]
        self.assertTrue(packet_timing_matches(film, packets))
        packets[1]["duration"] = 25
        self.assertFalse(packet_timing_matches(film, packets))
        packets[1]["duration"] = 24
        packets[1]["flags"] = "K_"
        self.assertFalse(packet_timing_matches(film, packets))
        self.assertTrue(all(parser_controls(film).values()))

    def test_optional_validation_missing_tool_fails_without_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch("tools.saturn_film.validate_real.shutil.which", return_value=None):
                with self.assertRaises(FilmError):
                    validate([Path(directory) / "missing.cpk"], output)
            self.assertFalse(output.exists())

    def test_optional_validation_timeout_is_incomplete_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "owned.cpk"
            source.write_bytes(fixture())
            output = root / "new"
            previous = os.umask(0)
            try:
                with patch("tools.saturn_film.validate_real.shutil.which", return_value="/bin/true"), \
                     patch("tools.saturn_film.validate_real.subprocess.run", side_effect=subprocess.TimeoutExpired("owned", 1)):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        validate([source], output, timeout=1)
            finally:
                os.umask(previous)
            self.assertTrue((output / "INCOMPLETE.txt").is_file())
            self.assertFalse((output / "receipt.json").exists())
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
