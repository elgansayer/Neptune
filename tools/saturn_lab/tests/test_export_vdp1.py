"""Synthetic hand-calculated format cases; no original-game graphics or bytes."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export_vdp1 as tool


def fixture(mode=1, texture=None, pmod=0x80, ctrl=0, size=0x0101, colr=None):
    ram = bytearray(tool.VRAM_SIZE)
    bank = 0x1200 if colr is None else colr
    command = [ctrl, 0, (mode << 3) | pmod, 0x80 if mode == 1 else bank,
               0x40, size] + [0] * 10
    ram[:32] = struct.pack(">16H", *command)
    if mode == 1:
        ram[0x400:0x420] = struct.pack(">16H", 0, 0x801F, 0x83E0, 0xFC00, *([0xFFFF] * 12))
    if texture is None:
        texture = b"\x01\x23\x10\x32" if mode < 2 else bytes(range(8))
    ram[0x200:0x200 + len(texture)] = texture
    return bytes(ram)


def values(raw):
    return list(struct.unpack(">" + "H" * (len(raw) // 2), raw))


def png_pixels(raw):
    """Independent PNG reader verifies lengths, CRCs, dimensions and scanlines."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Bad PNG signature")
    position, compressed, kinds = 8, b"", []
    while position < len(raw):
        length, = struct.unpack(">I", raw[position:position + 4])
        kind = raw[position + 4:position + 8]
        data = raw[position + 8:position + 8 + length]
        crc, = struct.unpack(">I", raw[position + 8 + length:position + 12 + length])
        if crc != zlib.crc32(kind + data) & 0xFFFFFFFF:
            raise AssertionError("Bad PNG CRC")
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if (depth, colour, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise AssertionError("Unexpected PNG format")
        elif kind == b"IDAT":
            compressed += data
        position += 12 + length
    if kinds != [b"IHDR", b"IDAT", b"IEND"] or position != len(raw):
        raise AssertionError("Bad PNG structure")
    scan = zlib.decompress(compressed)
    if len(scan) != height * (width * 4 + 1):
        raise AssertionError("Bad scanline size")
    result = []
    for y in range(height):
        row = scan[y * (width * 4 + 1):(y + 1) * (width * 4 + 1)]
        if row[0] != 0:
            raise AssertionError("Unexpected filter")
        result.extend(tuple(row[x:x + 4]) for x in range(1, len(row), 4))
    return width, height, result


def meta(ram):
    return {"schema": "neptune.vdp1-capture.v1", "game": "synthetic fixture",
            "build": "hand-calculated-v1", "capture_id": "test", "frame": 0,
            "input_lock_sha256": "1" * 64, "core_sha256": "2" * 64,
            "vdp2_state_sha256": "3" * 64, "vram_sha256": tool.sha(ram),
            "synthetic": True, "byte_order": "big"}


class TextureTests(unittest.TestCase):
    def test_high_nibble_first_and_rgb_lookup(self):
        report, files = tool.decode(fixture(), 0)
        self.assertEqual(values(files["texels.u16be"]), [0, 1, 2, 3, 1, 0, 3, 2])
        self.assertEqual(values(files["colour-words.u16be"]),
                         [0, 0x801F, 0x83E0, 0xFC00, 0x801F, 0, 0xFC00, 0x83E0])
        width, height, pixels = png_pixels(files["source-pattern.png"])
        self.assertEqual((width, height), (8, 1))
        self.assertEqual(pixels[:4], [(0, 0, 0, 0), (255, 0, 0, 255),
                                      (0, 255, 0, 255), (0, 0, 255, 255)])
        self.assertEqual(report["source_offset"], 0x200)
        self.assertEqual(report["source_length"], 4)

    def test_all_bank_masks_and_full_native_samples(self):
        for mode, expected in [(0, [0xFFF0, 0xFFF1, 0xFFF2, 0xFFF3]),
                               (2, [0xFFC0, 0xFFC1, 0xFFFF, 0xFFFF]),
                               (3, [0xFF80, 0xFF81, 0xFFBF, 0xFFFF]),
                               (4, [0xFF00, 0xFF01, 0xFF3F, 0xFFFF])]:
            packed = b"\x01\x23\x45\x67" if mode == 0 else bytes([0, 1, 63, 255, 0, 0, 0, 0])
            with self.subTest(mode=mode):
                report, files = tool.decode(fixture(mode, packed, colr=0xFFF0), 0)
                self.assertEqual(values(files["colour-words.u16be"])[:4], expected)
                if mode != 0:
                    self.assertEqual(values(files["texels.u16be"])[3], 255)
                self.assertIsNone(report["preview"])
                self.assertNotIn("source-pattern.png", files)

    def test_rgb_big_endian_and_native_flip_metadata(self):
        packed = struct.pack(">8H", 0, 0x801F, 0x83E0, 0xFC00, 0xFFFF, 0x8000, 0x8210, 0x801F)
        report, files = tool.decode(fixture(5, packed, ctrl=0x30), 0)
        self.assertTrue(report["flip_x"] and report["flip_y"])
        self.assertEqual(files["texture.bin"], packed)
        self.assertEqual(png_pixels(files["source-pattern.png"])[2][:2],
                         [(0, 0, 0, 0), (255, 0, 0, 255)])

    def test_spd_does_not_silently_hide_zero_sample(self):
        # Lookup index zero is visible under SPD=1 and must use the actual LUT.
        ram = bytearray(fixture(pmod=0xC0))
        ram[0x400:0x402] = struct.pack(">H", 0xFFFF)
        _, files = tool.decode(bytes(ram), 0)
        self.assertEqual(png_pixels(files["source-pattern.png"])[2][0], (255, 255, 255, 255))

    def test_unresolved_lookup_or_direct_non_rgb_word_no_fake_preview(self):
        for ram in (fixture(pmod=0xC0), fixture(5, struct.pack(">8H", *([1] * 8)))):
            report, files = tool.decode(ram, 0)
            self.assertIsNone(report["preview"])
            self.assertNotIn("source-pattern.png", files)
            self.assertIn("Visible non-RGB word requires VDP2 interpretation", report["preview_unavailable_reasons"])

    def test_end_codes_preserved_and_not_guessed(self):
        for mode, packed, end in [(1, b"\xFF" * 4, 15), (2, b"\xFF" * 8, 255),
                                  (5, struct.pack(">8H", *([0x7FFF] * 8)), 0x7FFF)]:
            report, files = tool.decode(fixture(mode, packed, pmod=0), 0)
            self.assertEqual(values(files["texels.u16be"]), [end] * 8)
            self.assertIsNone(report["preview"])
            self.assertTrue(any("End-code" in reason for reason in report["preview_unavailable_reasons"]))

    def test_dimensions_and_row_order(self):
        report, files = tool.decode(fixture(1, b"\x11" * 4 + b"\x22" * 4, size=0x0102), 0)
        self.assertEqual((report["width"], report["height"]), (8, 2))
        self.assertEqual(values(files["texels.u16be"]), [1] * 8 + [2] * 8)

    def test_illegal_modes_commands_sizes_offsets(self):
        for mode in (6, 7):
            with self.assertRaisesRegex(ValueError, "Prohibited"):
                tool.decode(fixture(mode), 0)
        for ctrl in (0x8000, 0x4000, 4, 8, 15):
            with self.subTest(ctrl=ctrl), self.assertRaises(ValueError):
                tool.decode(fixture(ctrl=ctrl), 0)
        for size in (0, 0x0100, 0x0001, 0x4101):
            with self.subTest(size=size), self.assertRaises(ValueError):
                tool.decode(fixture(size=size), 0)
        for offset in (-32, 1, 8, tool.VRAM_SIZE):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                tool.decode(fixture(), offset)

    def test_short_oversized_or_wrapping_vram(self):
        for size in (0, tool.VRAM_SIZE - 1, tool.VRAM_SIZE + 1):
            with self.assertRaises(ValueError):
                tool.decode(bytes(size), 0)
        ram = bytearray(fixture(5, size=0x3FFF))
        ram[8:10] = struct.pack(">H", 0xFFFC)
        with self.assertRaisesRegex(ValueError, "span out of range"):
            tool.decode(bytes(ram), 0)
        ram = bytearray(fixture())
        ram[8:10] = struct.pack(">H", 0x41)
        with self.assertRaisesRegex(ValueError, "32-byte"):
            tool.decode(bytes(ram), 0)

    def test_bad_bank_and_lookup_alignment_rejected(self):
        with self.assertRaisesRegex(ValueError, "colour-bank"):
            tool.decode(fixture(0, colr=0x1201), 0)
        ram = bytearray(fixture())
        ram[6:8] = struct.pack(">H", 0x81)
        with self.assertRaisesRegex(ValueError, "Lookup table"):
            tool.decode(bytes(ram), 0)

    def test_provenance_controls(self):
        ram = fixture()
        valid = meta(ram)
        self.assertEqual(tool.provenance(json.dumps(valid).encode(), ram), valid)
        for field, value in [("frame", True), ("frame", -1), ("synthetic", "false"),
                             ("byte_order", "little"), ("game", ""), ("vram_sha256", "0" * 64),
                             ("core_sha256", "missing"), ("vdp2_state_sha256", None)]:
            changed = dict(valid, **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                tool.provenance(json.dumps(changed).encode(), ram)
        with self.assertRaises(ValueError):
            tool.provenance(b'{"schema":"bad","schema":"neptune.vdp1-capture.v1"}', ram)

    def test_repeatable_export_hashes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ram, capture = root / "vram", root / "capture.json"
            ram.write_bytes(fixture())
            capture.write_text(json.dumps(meta(ram.read_bytes())))
            first, second = root / "first", root / "second"
            report = tool.export(ram, capture, 0, first)
            tool.export(ram, capture, 0, second)
            for path in first.iterdir():
                self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
            for name, identity in report["outputs"].items():
                self.assertEqual(identity["sha256"], tool.sha((first / name).read_bytes()))
            before = (first / "manifest.json").read_bytes()
            with self.assertRaises(FileExistsError):
                tool.export(ram, capture, 0, first)
            self.assertEqual(before, (first / "manifest.json").read_bytes())

    def test_cli_failure_creates_no_success_output(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp)
            output = root / "result"
            self.assertEqual(tool.main(["--vram", str(root / "missing"), "--capture",
                                       str(root / "missing.json"), "--command-offset", "0",
                                       "--output", str(output)]), 1)
            self.assertFalse(output.exists())

    def test_write_failure_removes_only_own_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ram, capture = root / "vram", root / "capture.json"
            ram.write_bytes(fixture())
            capture.write_text(json.dumps(meta(ram.read_bytes())))
            output = root / "result"
            with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    tool.export(ram, capture, 0, output)
            self.assertFalse(output.exists())
            self.assertTrue(ram.exists() and capture.exists())


if __name__ == "__main__":
    unittest.main()
