#!/usr/bin/env python3
"""Lossless unpacking of one captured VDP1 texture; not a scene renderer.

Only RGB textures with end codes disabled get an RGBA source-pattern preview.
Palette/VDP2 interpretation, effects and transformed drawing remain separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import zlib

VRAM_SIZE = 0x80000
MAX_METADATA = 16384
FIELDS = ("ctrl", "link", "pmod", "colr", "srca", "size", "xa", "ya",
          "xb", "yb", "xc", "yc", "xd", "yd", "grda", "reserved")
MODES = ("bank16", "lut16", "bank64", "bank128", "bank256", "rgb555")
LIMITATIONS = [
    "Input provenance is a declaration checked for byte identity, not authenticated execution.",
    "One explicit command; no command-list traversal, draw-order or source-bank correlation.",
    "Native source orientation; flips, scaling, distortion, clipping and placement are not applied.",
    "No mesh, shading, colour calculation, sprite priority or VDP2 composition.",
    "No animation duration, completeness or original-game fidelity established by this tool.",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Input exceeds size limit")
    return data


def provenance(raw: bytes, vram: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate provenance field")
            result[key] = value
        return result

    meta = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(meta, dict) or meta.get("schema") != "neptune.vdp1-capture.v1":
        raise ValueError("Unsupported capture schema")
    for field in ("game", "build", "capture_id"):
        value = meta.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("Missing/invalid capture field: " + field)
    for field in ("input_lock_sha256", "core_sha256", "vram_sha256", "vdp2_state_sha256"):
        value = meta.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Missing/invalid capture digest: " + field)
    if meta["vram_sha256"] != sha(vram):
        raise ValueError("VRAM digest differs from capture declaration")
    if type(meta.get("frame")) is not int or meta["frame"] < 0:
        raise ValueError("Frame must be a non-negative integer")
    if type(meta.get("synthetic")) is not bool or meta.get("byte_order") != "big":
        raise ValueError("Declare synthetic boolean and CPU-address-order big endian bytes")
    # Ignore arbitrary extra text rather than copying it into a published receipt.
    return {key: meta[key] for key in ("schema", "game", "build", "capture_id",
            "input_lock_sha256", "core_sha256", "vram_sha256", "vdp2_state_sha256",
            "frame", "synthetic", "byte_order")}


def span(data: bytes, offset: int, length: int) -> bytes:
    if offset < 0 or length < 0 or offset + length > len(data):
        raise ValueError("VRAM span out of range; wrapped textures are unsupported")
    return data[offset:offset + length]


def words(values) -> bytes:
    return b"".join(struct.pack(">H", value) for value in values)


def rgba_png(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("Invalid pixel buffer")

    def chunk(kind, content):
        return (struct.pack(">I", len(content)) + kind + content
                + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF))

    scan = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scan, 9)) + chunk(b"IEND", b""))


def decode(vram: bytes, offset: int) -> tuple[dict, dict[str, bytes]]:
    if len(vram) != VRAM_SIZE:
        raise ValueError("Expected exactly 512 KiB of VDP1 VRAM")
    if type(offset) is not int or offset % 32:
        raise ValueError("Command offset must be aligned to 32 bytes")
    command = span(vram, offset, 32)
    cmd = dict(zip(FIELDS, struct.unpack(">16H", command)))
    ctrl, pmod = cmd["ctrl"], cmd["pmod"]
    if ctrl & 0xC000 or (ctrl & 15) not in (0, 1, 2):
        raise ValueError("Expected a non-skipped normal/scaled/distorted sprite command")
    mode = (pmod >> 3) & 7
    if mode >= len(MODES):
        raise ValueError("Prohibited colour mode")
    if cmd["size"] & 0xC000:
        raise ValueError("Reserved character-size bits are nonzero")
    width, height = ((cmd["size"] >> 8) & 63) * 8, cmd["size"] & 255
    if not width or not height:
        raise ValueError("Zero-size texture")
    # A strict capture contract: reject unaligned/wrapping patterns, never repair.
    source = cmd["srca"] * 8
    if source % 32:
        raise ValueError("Character pattern must start on a 32-byte boundary")
    bpp = 4 if mode < 2 else 16 if mode == 5 else 8
    packed = span(vram, source, width * height * bpp // 8)
    if bpp == 4:
        texels = [value for byte in packed for value in (byte >> 4, byte & 15)]
    elif bpp == 8:
        texels = list(packed)
    else:
        texels = list(struct.unpack(">" + "H" * (len(packed) // 2), packed))
    # Keep unmasked native samples: FF is the end code even in 64/128-colour modes.
    mask = (15, 15, 63, 127, 255, 65535)[mode]
    palette = b""
    if mode == 1:
        if cmd["colr"] & 3:
            raise ValueError("Lookup table must start on a 32-byte boundary")
        palette = span(vram, cmd["colr"] * 8, 32)
        lut = struct.unpack(">16H", palette)
        colour_words = [lut[value] for value in texels]
    elif mode == 5:
        colour_words = texels[:]
    else:
        if cmd["colr"] & 15:
            raise ValueError("Reserved low colour-bank bits must be zero")
        # Low bank bits are ignored for the selected colour depth (manual 6.4).
        bank = cmd["colr"] & (0xFFFF ^ mask)
        colour_words = [bank | (value & mask) for value in texels]
    files = {"command.bin": command, "texture.bin": packed,
             "texels.u16be": words(texels), "colour-words.u16be": words(colour_words)}
    if palette:
        files["lookup-table.bin"] = palette
    reasons = []
    if mode not in (1, 5):
        reasons.append("VDP2 palette/priority interpretation required for bank-mode colour words")
    if not pmod & 0x80:
        reasons.append("End-code-enabled preview requires a draw-direction/clipping-aware adapter")
    spd = bool(pmod & 0x40)
    visible = [spd or sample != 0 for sample in texels]
    if mode in (1, 5) and any(show and not value & 0x8000
                              for show, value in zip(visible, colour_words)):
        reasons.append("Visible non-RGB word requires VDP2 interpretation")
    if not reasons:
        rgba = bytearray()
        for value, show in zip(colour_words, visible):
            channels = [(value >> shift) & 31 for shift in (0, 5, 10)]
            rgba.extend([(c << 3) | (c >> 2) for c in channels] + [255 if show else 0])
        files["source-pattern.png"] = rgba_png(width, height, bytes(rgba))
    report = {"command_offset": offset, "command_words": cmd,
              "source_offset": source, "source_length": len(packed),
              "width": width, "height": height, "bits_per_pixel": bpp,
              "mode": MODES[mode], "flip_x": bool(ctrl & 16), "flip_y": bool(ctrl & 32),
              "lookup_offset": cmd["colr"] * 8 if mode == 1 else None,
              "preview": "source-pattern.png" if not reasons else None,
              "preview_unavailable_reasons": reasons,
              "interpretation": "native source samples and pre-composition colour words; not a rendered draw"}
    return report, files


def export(vram_path: Path, metadata_path: Path, offset: int, output: Path) -> dict:
    vram = read_bounded(vram_path, VRAM_SIZE)
    raw_meta = read_bounded(metadata_path, MAX_METADATA)
    capture = provenance(raw_meta, vram)
    report, files = decode(vram, offset)
    report.update(schema="neptune.vdp1-texture.v1", capture=capture,
                  capture_metadata_sha256=sha(raw_meta),
                  exporter_sha256=sha(Path(__file__).read_bytes()),
                  runtime={"python": list(sys.version_info[:3]), "zlib": zlib.ZLIB_RUNTIME_VERSION},
                  limitations=LIMITATIONS,
                  outputs={name: {"bytes": len(data), "sha256": sha(data)}
                           for name, data in sorted(files.items())})
    # Reserve a fresh directory; never overwrite an accepted or concurrent run.
    output.mkdir(mode=0o700)
    try:
        for name, data in files.items():
            (output / name).write_bytes(data)
        (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except BaseException:
        shutil.rmtree(output)
        raise
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vram", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--command-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh private output directory")
    args = parser.parse_args(argv)
    try:
        report = export(args.vram, args.capture, args.command_offset, args.output)
    except (OSError, ValueError, TypeError, struct.error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "native-decoded", "synthetic": report["capture"]["synthetic"],
                      "preview": report["preview"], "manifest": str(args.output / "manifest.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
