#!/usr/bin/env python3
"""Whole-disc code-bearing census: screen every file, bank and system area.

``extract`` copies EDC-checked original files from a CUE/BIN image into a
private directory outside Git and verifies every byte against the committed
disc receipt. ``screen`` measures SH-2 and 68000 code signatures, with an
odd-alignment control for each, over every file, every PROGRAM.BIN directory
entry, every stream the accepted Hudson decoder can unpack, the unreferenced
container tail and the system area. It writes a metadata-only census: hashes,
offsets, counts and classes, never original bytes. ``verify`` checks that a
committed census still matches the pinned receipts and keeps its claims bounded.

A signature screen is static evidence about where instructions are likely to
be. It is not disassembly, a function inventory or semantic recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tempfile
from typing import Any, Iterable

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SCHEMA = "neptune.saturn-disc-code-census.v1"
EXTRACTION_SCHEMA = "neptune.saturn-disc-private-extraction.v1"
RELEASES = {
    "usa-mk81070-v1003": {
        "summary": "docs/restart/saturn-disc/usa-mk81070-v1003.summary.json",
        "directory": "docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json",
        "program": "BOMSS/PROGRAM.BIN",
    },
    "japan-t14302g-v1000": {
        "summary": "docs/restart/saturn-disc/japan-t14302g-v1000.summary.json",
        "directory": "docs/restart/saturn-archive/japan-t14302g-v1000.kernel-directory.json",
        "program": "PROGRAM.BIN",
    },
}
SYSTEM_AREA = "@track01-system-area"
SYSTEM_AREA_FILE = "@track01-system-area.bin"
SECTOR = 2048
BLOCK = 4096
SMALL_SOURCE_BYTES = 512

# Screen definition. Halfwords are big-endian. "Aligned" means an even offset
# from the start of the source (all candidate load addresses are even); the
# same pattern at odd offsets is the built-in control for structured data.
SH2_RTS = 0x000B
SH2_NOP = 0x0009
SH2_LDS_PR_POP = 0x4F26      # lds.l @r15+,pr
SH2_STS_PR_PUSH = 0x4F22     # sts.l pr,@-r15
SH2_EPILOGUE_WINDOW = 8      # rts within this many halfwords after lds.l
M68K_RTS = 0x4E75
M68K_UNLK = range(0x4E58, 0x4E60)   # unlk a0-a7
M68K_MOVEM_POP = 0x4CDF      # movem.l (sp)+,<list>; one extension word
SIGNAL_MIN = 4
SIGNAL_RATIO = 4
M68K_RTS_MIN = 16           # 68000 rts alone: stricter, data tables contain 0x4E75 rarely
M68K_RTS_RATIO = 8
RANGE_MIN_HITS = 2


class CensusError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CensusError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path, limit: int = 32 * 1024 * 1024) -> tuple[dict, str]:
    path = path.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise CensusError("Symlink metadata paths are unsupported")
    if not path.is_file() or path.stat().st_size > limit:
        raise CensusError("Metadata must be a regular file within its size budget")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=unique_keys)
    if not isinstance(value, dict):
        raise CensusError("Metadata must be an object")
    return value, sha256(raw)


def confined(path: str) -> PurePosixPath:
    pure = PurePosixPath(path)
    if (not isinstance(path, str) or not path or "\\" in path or pure.is_absolute()
            or str(pure) != path or any(part in (".", "..") for part in path.split("/"))):
        raise CensusError("Source identity must be a confined disc path")
    return pure


def private_output(path: Path) -> Path:
    """Reject outputs inside the public repository; original bytes stay private."""
    resolved = path.absolute().resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        raise CensusError("Private original bytes must not be written inside the repository")
    return resolved


# --------------------------------------------------------------------------
# Private extraction


def extract(root: Path, cue_relpath: str, summary_path: Path, output_dir: Path) -> dict:
    from saturn_disc.cue import DataTrackReader, parse_cue_sheet
    from saturn_disc.ipbin import SYSTEM_AREA_SECTORS
    from saturn_disc.iso9660 import (ISO_STANDARD_ID, _walk_directory_tree,
                                     parse_primary_volume_descriptor)

    output_dir = private_output(output_dir)
    summary, summary_sha = read_json(summary_path)
    cue = parse_cue_sheet(root, cue_relpath)
    if cue.cue_sha256 != summary["cue"]["sha256"]:
        raise CensusError("CUE digest differs from the committed disc receipt")
    expected_tracks = {row["file_relpath"].rsplit("/", 1)[-1]: row["file_sha256"] for row in summary["tracks"]}
    for track in cue.tracks:
        name = track.file_relpath.rsplit("/", 1)[-1]
        if expected_tracks.get(name) != track.file_sha256:
            raise CensusError("Track digest differs from the committed disc receipt: " + name)
    expected = {row["path"]: row for row in summary["iso9660"]["files"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with DataTrackReader(cue.tracks[0]) as reader:
        system = b"".join(reader.read_sector(lba, verify_edc=True) for lba in range(SYSTEM_AREA_SECTORS))
        if sha256(system) != summary["ip_bin"]["system_area_sha256"]:
            raise CensusError("System area digest differs from the committed disc receipt")
        (output_dir / SYSTEM_AREA_FILE).write_bytes(system)
        written.append({"path": SYSTEM_AREA, "bytes": len(system), "sha256": sha256(system)})
        lba, pvd = SYSTEM_AREA_SECTORS, None
        while True:
            sector = reader.read_sector(lba, verify_edc=True)
            if sector[1:6] != ISO_STANDARD_ID:
                raise CensusError("Invalid ISO-9660 volume descriptor")
            if sector[0] == 1 and pvd is None:
                pvd = parse_primary_volume_descriptor(sector, lba)
            if sector[0] == 255:
                break
            lba += 1
        if pvd is None:
            raise CensusError("Missing primary volume descriptor")
        _, records = _walk_directory_tree(reader, pvd["root_extent_lba"], pvd["root_data_length"])
        if sorted(row["path"] for row in records) != sorted(expected):
            raise CensusError("ISO-9660 file set differs from the committed disc receipt")
        for row in records:
            relative = confined(row["path"])
            digest, length = hashlib.sha256(), 0
            target = output_dir.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as stream:
                for extent in row["extents"]:
                    remaining = extent["byte_length"]
                    for index in range(extent["sector_count"]):
                        data = reader.read_sector(extent["extent_lba"] + index, verify_edc=True)
                        data = data[:min(SECTOR, remaining)]
                        remaining -= len(data)
                        digest.update(data)
                        stream.write(data)
                        length += len(data)
            want = expected[row["path"]]
            if length != want["byte_length"] or digest.hexdigest() != want["sha256"]:
                target.unlink()
                raise CensusError("Extracted file differs from the committed receipt: " + row["path"])
            written.append({"path": row["path"], "bytes": length, "sha256": digest.hexdigest()})
        edc_sectors = len(reader.edc_verified_lbas)
    receipt = {"schema": EXTRACTION_SCHEMA, "cue_sha256": cue.cue_sha256,
               "disc_summary_sha256": summary_sha, "files": sorted(written, key=lambda r: r["path"]),
               "edc_verified_sectors": edc_sectors,
               "note": "Private original bytes; never commit this directory."}
    (output_dir / "extraction.json").write_text(canonical(receipt))
    return receipt


# --------------------------------------------------------------------------
# Signature screen


def positions(data: bytes, pattern: bytes) -> list[int]:
    found, index = [], data.find(pattern)
    while index != -1:
        found.append(index)
        index = data.find(pattern, index + 1)
    return found


def split(hits: Iterable[int]) -> tuple[list[int], list[int]]:
    aligned, odd = [], []
    for hit in hits:
        (odd if hit & 1 else aligned).append(hit)
    return aligned, odd


def sh2_epilogues(data: bytes) -> list[int]:
    """Offsets of ``lds.l @r15+,pr`` followed by ``rts`` within the window, same parity."""
    rts = set(positions(data, b"\x00\x0b"))
    return [i for i in positions(data, b"\x4f\x26")
            if any(i + 2 * step in rts for step in range(1, SH2_EPILOGUE_WINDOW + 1))]


PRINTABLE = frozenset((9, 10, 13, *range(0x20, 0x7F)))


def in_text(data: bytes, index: int, before: int = 12, after: int = 12) -> bool:
    """True when a hit sits inside printable ASCII (``Nu`` in ``Num`` is not a 68000 rts)."""
    window = data[max(0, index - before):index + after]
    return len(window) == before + after and all(byte in PRINTABLE for byte in window)


def m68k_rts(data: bytes) -> list[int]:
    return [i for i in positions(data, b"\x4e\x75") if not in_text(data, i)]


def m68k_epilogues(data: bytes) -> list[int]:
    """Offsets of ``rts`` directly after ``unlk An`` or a one-extension ``movem.l (sp)+``."""
    found = []
    for i in m68k_rts(data):
        if i >= 2 and data[i - 2] == 0x4E and 0x58 <= data[i - 1] <= 0x5F:
            found.append(i)
        elif i >= 4 and data[i - 4:i - 2] == b"\x4c\xdf":
            found.append(i)
    return found


def signal(aligned: int, odd: int, minimum: int = SIGNAL_MIN, ratio: int = SIGNAL_RATIO) -> bool:
    return aligned >= minimum and aligned >= ratio * (odd + 1)


def ranges(hits: Iterable[int], size: int, block: int = BLOCK, minimum_hits: int = RANGE_MIN_HITS) -> list[dict]:
    """Coarse code-bearing ranges: adjacent hit blocks merged (an empty block splits a range).

    Ranges with fewer than ``minimum_hits`` hits are dropped as isolated
    coincidences; their count is reported separately by the caller.
    """
    hit_list = sorted(hits)
    merged: list[list[int]] = []
    for index in sorted({hit // block for hit in hit_list}):
        if merged and index <= merged[-1][1]:
            merged[-1][1] = index + 1
        else:
            merged.append([index, index + 1])
    result = []
    for first, last in merged:
        start, end = first * block, min(size, last * block)
        count = sum(1 for hit in hit_list if start <= hit < end)
        if count >= minimum_hits:
            result.append({"start": start, "end": end, "hits": count})
    return result


def byte_profile(data: bytes) -> dict:
    if not data:
        return {"entropy_bits_per_byte": 0.0, "zero_fraction": 0.0, "text_fraction": 0.0}
    counts = [data.count(bytes((value,))) for value in range(256)]
    total = len(data)
    entropy = -sum(c / total * math.log2(c / total) for c in counts if c)
    text = sum(counts[value] for value in (9, 10, 13, *range(0x20, 0x7F)))
    return {"entropy_bits_per_byte": round(entropy, 4),
            "zero_fraction": round(counts[0] / total, 4),
            "text_fraction": round(text / total, 4)}


def screen(data: bytes) -> dict:
    sh2_epi_a, sh2_epi_o = split(sh2_epilogues(data))
    sh2_rts_a, sh2_rts_o = split(positions(data, b"\x00\x0b"))
    nop_a, nop_o = split(positions(data, b"\x00\x0b\x00\x09"))
    m68_epi_a, m68_epi_o = split(m68k_epilogues(data))
    m68_rts_a, m68_rts_o = split(m68k_rts(data))
    sh2 = {"epilogue_aligned": len(sh2_epi_a), "epilogue_odd": len(sh2_epi_o),
           "rts_aligned": len(sh2_rts_a), "rts_odd": len(sh2_rts_o),
           "rts_nop_aligned": len(nop_a), "rts_nop_odd": len(nop_o)}
    sh2["signal"] = signal(sh2["epilogue_aligned"], sh2["epilogue_odd"])
    m68 = {"epilogue_aligned": len(m68_epi_a), "epilogue_odd": len(m68_epi_o),
           "rts_aligned": len(m68_rts_a), "rts_odd": len(m68_rts_o)}
    m68["signal"] = (signal(m68["epilogue_aligned"], m68["epilogue_odd"])
                     or signal(m68["rts_aligned"], m68["rts_odd"], M68K_RTS_MIN, M68K_RTS_RATIO))
    for row, hits in ((sh2, set(sh2_epi_a) | set(nop_a)), (m68, set(m68_epi_a) | set(m68_rts_a))):
        row["ranges"] = ranges(hits, len(data)) if row["signal"] else []
        row["hits_outside_ranges"] = (sum(1 for hit in hits if not any(r["start"] <= hit < r["end"] for r in row["ranges"]))
                                      if row["signal"] else len(hits))
    return {"bytes": len(data), "constant_fill": bool(data) and data.count(data[:1]) == len(data),
            "sh2": sh2, "m68000": m68, **byte_profile(data), "text_residue": text_residue(data),
            "dsp_exb_names": dsp_program_names(data)}


def range_fraction(rows: list[dict], size: int) -> float:
    return round(sum(row["end"] - row["start"] for row in rows) / size, 4) if size else 0.0


# --------------------------------------------------------------------------
# Lightweight structure checks for files the disc receipt left unknown


def bmp_header(data: bytes) -> dict | None:
    """Parse BITMAPFILEHEADER/BITMAPINFOHEADER and check internal consistency."""
    if len(data) < 54 or data[:2] != b"BM":
        return None
    file_size, _, offset, header = struct.unpack_from("<IIII", data, 2)
    width, height, planes, bits, compression, image_size, _, _, used = struct.unpack_from("<iiHHIIiiI", data, 18)
    if header != 40 or planes != 1 or bits not in (1, 4, 8, 16, 24, 32) or width <= 0 or height == 0:
        return None
    colours = used or (1 << bits if bits <= 8 else 0)
    if offset != 54 + 4 * colours or offset > len(data):
        return None
    stride = ((width * bits + 31) // 32) * 4
    raster = stride * abs(height)
    if compression == 0 and len(data) - offset < raster:
        return None
    if compression in (1, 2):
        # RLE8/RLE4: the stream must end in an end-of-bitmap escape.
        if image_size and offset + image_size > len(data):
            return None
        if data[offset + (image_size or len(data) - offset) - 2:offset + (image_size or len(data) - offset)] != b"\x00\x01":
            return None
    elif compression != 0:
        return None
    return {"width": width, "height": height, "bits": bits, "compression": compression,
            "header_file_size": file_size, "actual_size": len(data)}


def text_like(data: bytes) -> bool:
    """Printable prose/markup: mostly letters with word spacing, not glyph bitmaps."""
    if len(data) < 16:
        return False
    letters = sum(1 for byte in data if 0x41 <= byte <= 0x5A or 0x61 <= byte <= 0x7A)
    spaces = sum(1 for byte in data if byte in (9, 10, 13, 0x20))
    printable = sum(1 for byte in data if byte in PRINTABLE)
    return printable >= 0.95 * len(data) and letters >= 0.4 * len(data) and spaces >= 0.05 * len(data)


TEXT_RUN = re.compile(rb"[\t\n\r -~]{32,}")
C_TOKENS = re.compile(rb"\b(?:typedef|struct|#define|#include|Uint8|Uint16|Uint32|Sint8|Sint16|Sint32|void|extern|static)\b")
DSP_NAME = re.compile(rb"[A-Za-z0-9_]{1,16}\.EXB")


def text_residue(data: bytes) -> dict:
    """Long printable runs and C-declaration tokens: build residue, not instructions."""
    runs = [match.span() for match in TEXT_RUN.finditer(data)]
    tokens = sum(len(C_TOKENS.findall(data[start:end])) for start, end in runs)
    return {"runs_32_plus": len(runs), "run_bytes": sum(end - start for start, end in runs),
            "c_declaration_tokens": tokens}


def dsp_program_names(data: bytes) -> list[dict]:
    """ASCII ``*.EXB`` names (SCSP DSP program containers named in banks)."""
    return [{"name": match.group().decode("ascii"), "offset": match.start()} for match in DSP_NAME.finditer(data)]


# --------------------------------------------------------------------------
# Census construction

# Accepted Neptune static function inventories over exact original bytes.
MEASURED = {
    ("usa-mk81070-v1003", "BOMSS/0KRNL.BIN", None): {
        "cpu": "sh2", "entries": 4868, "lane": "usa-code",
        "sha256": "20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7",
        "evidence": "docs/restart/research/2026-11-05-usa-function-inventory.md"},
    ("usa-mk81070-v1003", "0", None): {
        "cpu": "sh2", "entries": 1751, "lane": "usa-code",
        "sha256": "5d966992dfcca575653f4184711f4fde28ca0285cb0a40de210754eba6596827",
        "evidence": "docs/restart/research/2026-11-05-usa-function-inventory.md"},
    ("usa-mk81070-v1003", "BOMSS/PROGRAM.BIN", (0x44, 0x6418)): {
        "cpu": "m68000", "entries": 146, "lane": "sound-68k",
        "sha256": "c8842cc957bf82693ddd72d996353c9cb92feb34fe5f2834c0651aebacb4bd04",
        "evidence": "docs/restart/research/2026-11-05-snd-natural-function-inventory.md"},
}
# Exact byte anchors searched for in every other source of both releases.
ANCHORS = (
    ("SND", "usa-mk81070-v1003", "BOMSS/PROGRAM.BIN", 0x44, 0x6418, "m68000"),
    ("NLSND", "usa-mk81070-v1003", "NETLINK/SNDDRV.BIN", 0, None, "m68000"),
    ("H2H", "usa-mk81070-v1003", "XBAND/H2HLIBUS.BIN", 0, None, "sh2"),
    ("FLD", "usa-mk81070-v1003", "FLD_KNL.BIN", 0, None, "sh2"),
    ("XS", "usa-mk81070-v1003", "NETLINK/XS028000.EXE", 0, None, "sh2"),
)
DATA_FORMATS = {"aiff_audio", "ascii_text", "bmp_bitmap", "gif_image", "jpeg_image",
                "riff_wave_audio", "sega_film_cpk"}
CODE_FORMATS = {"saturn_sh2_boot_executable", "saturn_sh2_executable", "saturn_m68k_sound_driver",
                "saturn_ip_header_template", "saturn-system-area"}
CLASSES = ("code-module-measured", "code-candidate", "mixed-code-and-data", "compressed-code-candidate",
           "data-format-identified", "data-no-code-signal", "padding", "unresolved-small",
           "unresolved-high-entropy", "unresolved-conflict")
HIGH_ENTROPY = 7.2
CODE_MAJORITY = 0.5


def code_fraction(row: dict) -> float:
    spans = sorted((r["start"], r["end"]) for cpu in ("sh2", "m68000") for r in row["screen"][cpu]["ranges"])
    spans += sorted((r["start"], r["end"]) for r in row.get("identity_links", ()) if not r.get("self"))
    covered, cursor = 0, 0
    for start, end in sorted(spans):
        start = max(start, cursor)
        if end > start:
            covered += end - start
            cursor = end
    return round(covered / row["bytes"], 4) if row["bytes"] else 0.0


def classify(row: dict) -> tuple[str, list[str]]:
    """Pure classification from recorded evidence; ``verify`` recomputes it."""
    screened = row["screen"]
    code = [cpu for cpu in ("sh2", "m68000") if screened[cpu]["signal"]]
    measured = row.get("measured_inventory")
    fmt = row.get("format_evidence")
    decoded = row.get("decoded_streams")
    basis = ["screen:" + ("+".join(code) + "-signal" if code else "no-code-signal")]
    if fmt:
        basis.append("format:" + fmt["kind"] + ":" + fmt["format"])
    if decoded:
        basis.append("decoded-streams:" + ("code-signal" if decoded["signal"] else "no-code-signal"))
    if screened["constant_fill"]:
        return "padding", basis + ["constant-fill"]
    if measured:
        basis.append("measured-inventory:" + measured["evidence"])
        return ("code-module-measured" if measured["cpu"] in code else "unresolved-conflict"), basis
    if code and fmt and fmt["kind"] == "disc-receipt" and fmt["format"] in DATA_FORMATS:
        return "unresolved-conflict", basis + ["data-format-with-code-signal"]
    if code or any(not link.get("self") for link in row.get("identity_links", ())):
        return ("code-candidate" if code_fraction(row) >= CODE_MAJORITY else "mixed-code-and-data"), basis
    if decoded and decoded["signal"]:
        return "compressed-code-candidate", basis
    if fmt:
        return "data-format-identified", basis
    if row["bytes"] < SMALL_SOURCE_BYTES:
        return "unresolved-small", basis + ["screen-power-insufficient"]
    if screened["entropy_bits_per_byte"] >= HIGH_ENTROPY and not decoded:
        return "unresolved-high-entropy", basis + ["possible-undecoded-compression"]
    return "data-no-code-signal", basis


def format_evidence(entry: dict, data: bytes) -> dict | None:
    cls = entry["classification"]
    if cls["detected_format"] in DATA_FORMATS and cls.get("valid"):
        return {"kind": "disc-receipt", "format": cls["detected_format"]}
    if cls["detected_format"] in CODE_FORMATS:
        return None
    header = bmp_header(data)
    if header:
        return {"kind": "census-bmp-header", "format": "bmp-rle" if header["compression"] else "bmp",
                "detail": header}
    if text_like(data):
        return {"kind": "census-text", "format": "text"}
    return None


def finish(row: dict) -> dict:
    row["code_range_fraction"] = code_fraction(row)
    row["class"], row["basis"] = classify(row)
    return row


def decoded_streams(bank: bytes, load_dest: int, bank_id: int) -> dict:
    from saturn_archive import ArchiveError
    from saturn_archive.banks import parse_and_decode_bank

    try:
        parsed = parse_and_decode_bank(bank, bank_id=bank_id, expected_load_base=load_dest,
                                       include_raw_decoded=True)
    except (ArchiveError, ValueError, IndexError, struct.error) as error:
        return {"error": type(error).__name__ + ": " + str(error)[:160], "streams": 0, "decoded_bytes": 0,
                "input_bytes_covered": 0, "signal": False, "sh2_epilogue_aligned": 0, "sh2_epilogue_odd": 0,
                "m68000_epilogue_aligned": 0, "m68000_epilogue_odd": 0, "m68000_rts_aligned": 0,
                "m68000_rts_odd": 0, "streams_with_signal": 0}
    slots = parsed["decoded_slots"]
    records = []
    for name, header in (("slot0_vdp2_patterns", 8), ("slot1_cram_palettes", 4),
                         ("slot2_vdp2_tilemaps", 6), ("slot7_stage_grids", 1)):
        records += [(row, header) for row in slots[name]]
    if slots["slot8_vdp1_sprites"]:
        records += [(row, 4) for row in slots["slot8_vdp1_sprites"]["blocks"]]
    totals = {"streams": len(records), "decoded_bytes": 0, "sh2_epilogue_aligned": 0, "sh2_epilogue_odd": 0,
              "m68000_epilogue_aligned": 0, "m68000_epilogue_odd": 0, "m68000_rts_aligned": 0,
              "m68000_rts_odd": 0, "streams_with_signal": 0}
    spans = []
    for row, header in records:
        data = row["_raw_decoded"]
        result = screen(data)
        totals["decoded_bytes"] += len(data)
        totals["sh2_epilogue_aligned"] += result["sh2"]["epilogue_aligned"]
        totals["sh2_epilogue_odd"] += result["sh2"]["epilogue_odd"]
        for key in ("epilogue_aligned", "epilogue_odd", "rts_aligned", "rts_odd"):
            totals["m68000_" + key] += result["m68000"][key]
        totals["streams_with_signal"] += bool(result["sh2"]["signal"] or result["m68000"]["signal"])
        consumed = row.get("compressed_stream_bytes") if row.get("compressed") else row["decoded_bytes"]
        start = row["bank_rel_offset"]
        spans.append((start, min(len(bank), start + header + (consumed or 0))))
    covered, cursor = 0, 0
    for start, end in sorted(spans):
        start = max(start, cursor)
        if end > start:
            covered += end - start
            cursor = end
    totals["input_bytes_covered"] = covered
    totals["signal"] = (signal(totals["sh2_epilogue_aligned"], totals["sh2_epilogue_odd"])
                        or signal(totals["m68000_epilogue_aligned"], totals["m68000_epilogue_odd"])
                        or signal(totals["m68000_rts_aligned"], totals["m68000_rts_odd"], M68K_RTS_MIN, M68K_RTS_RATIO))
    totals["error"] = None
    return totals


def load_release(release: str, files_dir: Path, root: Path) -> tuple[dict, dict, dict, dict]:
    spec = RELEASES[release]
    summary, summary_sha = read_json(root / spec["summary"])
    directory, directory_sha = read_json(root / spec["directory"])
    extraction, _ = read_json(files_dir / "extraction.json")
    if extraction.get("disc_summary_sha256") != summary_sha:
        raise CensusError("Private extraction was made against a different disc receipt")
    if directory.get("release_id") != release:
        raise CensusError("Kernel directory receipt release mismatch")
    receipts = {"disc_summary": {"path": spec["summary"], "sha256": summary_sha},
                "kernel_directory": {"path": spec["directory"], "sha256": directory_sha}}
    return summary, directory, extraction, receipts


def read_source(files_dir: Path, path: str, expected_sha: str, expected_len: int) -> bytes:
    target = files_dir / (SYSTEM_AREA_FILE if path == SYSTEM_AREA else Path(*confined(path).parts))
    data = target.read_bytes()
    if len(data) != expected_len or sha256(data) != expected_sha:
        raise CensusError("Private source differs from the committed receipt: " + path)
    return data


def find_links(data: bytes, anchors: dict, origin: tuple) -> list[dict]:
    """Exact copies of anchor bytes; ``self`` marks the anchor's own source location."""
    links = []
    for name, (anchor, cpu, anchor_origin) in anchors.items():
        found = data.find(anchor)
        while found != -1:
            link = {"anchor": name, "cpu": cpu, "start": found, "end": found + len(anchor)}
            if (origin[0], origin[1], origin[2] + found) == anchor_origin:
                link["self"] = True
            measured = [value for key, value in MEASURED.items() if value["sha256"] == sha256(anchor)]
            if measured:
                link["measured_inventory"] = {key: measured[0][key] for key in ("cpu", "entries", "lane", "evidence")}
            links.append(link)
            found = data.find(anchor, found + 1)
    return links


def build_release(release: str, files_dir: Path, root: Path, anchors: dict) -> dict:
    summary, directory, _, receipts = load_release(release, files_dir, root)
    rows = []
    sources: dict[str, bytes] = {}
    system = summary["ip_bin"]
    entries = [{"path": SYSTEM_AREA, "byte_length": system["byte_length"], "sha256": system["system_area_sha256"],
                "classification": {"detected_format": "saturn-system-area", "valid": True}}]
    entries += sorted(summary["iso9660"]["files"], key=lambda row: row["path"])
    for entry in entries:
        data = read_source(files_dir, entry["path"], entry["sha256"], entry["byte_length"])
        sources[entry["path"]] = data
        row = {"path": entry["path"], "sha256": entry["sha256"], "bytes": len(data),
               "receipt_format": entry["classification"]["detected_format"],
               "screen": screen(data), "format_evidence": format_evidence(entry, data)}
        measured = MEASURED.get((release, entry["path"], None))
        if measured:
            if measured["sha256"] != entry["sha256"]:
                raise CensusError("Measured inventory identity differs from the disc receipt")
            row["measured_inventory"] = {key: measured[key] for key in ("cpu", "entries", "lane", "evidence")}
        links = find_links(data, anchors, (release, entry["path"], 0))
        if links:
            row["identity_links"] = links
        rows.append(row)
    program_path = RELEASES[release]["program"]
    program = sources[program_path]
    banks = []
    for entry in directory["entries"]:
        start, length = entry["byte_offset"], entry["byte_length"]
        data = program[start:start + length]
        if len(data) != length or sha256(data) != entry["sha256"]:
            raise CensusError("PROGRAM.BIN entry differs from the kernel directory receipt")
        row = {"path": program_path + "#bank%d" % entry["bank_id"], "bank_id": entry["bank_id"],
               "header_name": entry.get("header_name"), "entry_format": entry["entry_format"],
               "role_hypothesis": entry.get("role"), "byte_offset": start, "bytes": length,
               "sha256": entry["sha256"], "load_dest": entry["load_dest"], "screen": screen(data)}
        if entry["entry_format"] == "hudson_0x34_bank":
            row["decoded_streams"] = decoded_streams(data, entry["load_dest"], entry["bank_id"])
        links = find_links(data, anchors, (release, program_path, start))
        if links:
            row["identity_links"] = links
        banks.append(finish(row))
    accounting = directory["program_bin_accounting"]
    tail_start = accounting["referenced_bytes"]
    tail = program[tail_start:]
    if sha256(tail) != accounting["unreferenced_tail_sha256"] or len(tail) != accounting["unreferenced_tail_bytes"]:
        raise CensusError("PROGRAM.BIN unreferenced tail differs from the kernel directory receipt")
    covered = sorted((row["byte_offset"], row["byte_offset"] + row["bytes"]) for row in banks)
    if covered[0][0] != 0 or any(a[1] != b[0] for a, b in zip(covered, covered[1:])) or covered[-1][1] != tail_start:
        raise CensusError("PROGRAM.BIN directory entries do not partition the referenced bytes")
    tail_row = finish({"path": program_path + "#unreferenced-tail", "byte_offset": tail_start, "bytes": len(tail),
                       "sha256": accounting["unreferenced_tail_sha256"], "screen": screen(tail)})
    for row in rows:
        finish(row)
    return {"receipts": receipts, "sources": rows, "program_bin": {"path": program_path, "entries": banks,
                                                                    "unreferenced_tail": tail_row}}


def totals(rows: list[dict]) -> dict:
    result = {name: {"sources": 0, "bytes": 0} for name in CLASSES}
    for row in rows:
        result[row["class"]]["sources"] += 1
        result[row["class"]]["bytes"] += row["bytes"]
    return {name: value for name, value in result.items() if value["sources"]}


def controls(files: dict[str, Path], anchors: dict[str, bytes]) -> list[dict]:
    """Real-byte controls: shifted, byte-swapped and wrong-CPU copies must lose the signal."""
    usa = files["usa-mk81070-v1003"]
    krnl = (usa / "BOMSS" / "0KRNL.BIN").read_bytes()
    snd = anchors["SND"]
    swapped = bytes(b for pair in zip(krnl[1::2], krnl[0::2]) for b in pair)
    film = (usa / "BOMSS" / "BOMSS1.CPK").read_bytes()
    cases = [
        ("krnl-original", krnl, "sh2", True),
        ("krnl-shifted-one-byte", b"\x00" + krnl, "sh2", False),
        ("krnl-byte-swapped", swapped, "sh2", False),
        ("krnl-as-m68000", krnl, "m68000", False),
        ("snd-original", snd, "m68000", True),
        ("snd-shifted-one-byte", b"\x00" + snd, "m68000", False),
        ("snd-as-sh2", snd, "sh2", False),
        ("film-bomss1-sh2", film, "sh2", False),
        ("film-bomss1-m68000", film, "m68000", False),
    ]
    result = []
    for name, data, cpu, expected in cases:
        observed = screen(data)[cpu]
        result.append({"control": name, "cpu": cpu, "expected_signal": expected, "observed_signal": observed["signal"],
                       "epilogue_aligned": observed["epilogue_aligned"], "epilogue_odd": observed["epilogue_odd"],
                       "passed": observed["signal"] == expected})
    return result


def build(files: dict[str, Path], root: Path = ROOT) -> dict:
    if set(files) != set(RELEASES):
        raise CensusError("Require private extractions for both releases")
    anchors = {}
    for name, release, path, start, end, cpu in ANCHORS:
        data = (files[release] / Path(*confined(path).parts)).read_bytes()
        anchors[name] = (data[start:end] if end else data[start:], cpu, (release, path, start))
    census = {"schema": SCHEMA,
              "scope": ("Static signature screen and structure checks over every original file, PROGRAM.BIN "
                        "directory entry, decodable Hudson stream and system area. Not disassembly, a function "
                        "inventory, runtime load reconciliation or semantic recovery."),
              "screen_definition": {
                  "alignment": "even offsets from source start; odd offsets are the per-source control",
                  "sh2": "epilogue = lds.l @r15+,pr (4F26) then rts (000B) within %d halfwords; "
                         "signal when aligned >= %d and aligned >= %d x (odd + 1); ranges also use rts;nop (000B 0009)"
                         % (SH2_EPILOGUE_WINDOW, SIGNAL_MIN, SIGNAL_RATIO),
                  "m68000": "epilogue = rts (4E75) after unlk An or movem.l (sp)+ (4CDF xxxx); signal as SH-2, "
                            "or aligned rts >= %d and >= %d x (odd rts + 1)" % (M68K_RTS_MIN, M68K_RTS_RATIO),
                  "ranges": "%d-byte blocks with hits merged across one empty block; ranges need >= %d hits"
                            % (BLOCK, RANGE_MIN_HITS),
                  "classes": list(CLASSES),
                  "small_source_bytes": SMALL_SOURCE_BYTES, "high_entropy_bits_per_byte": HIGH_ENTROPY,
                  "code_majority_fraction": CODE_MAJORITY},
              "anchors": [{"name": name, "release": release, "path": path, "start": start,
                           "end": end if end else len(anchors[name][0]), "cpu": cpu,
                           "sha256": sha256(anchors[name][0])}
                          for name, release, path, start, end, cpu in ANCHORS],
              "releases": {}}
    for release in sorted(RELEASES):
        result = build_release(release, files[release], root, anchors)
        result["totals"] = {"sources": totals(result["sources"]),
                            "program_bin_entries": totals(result["program_bin"]["entries"])}
        census["releases"][release] = result
    census["controls"] = controls(files, {name: value[0] for name, value in anchors.items()})
    if not all(row["passed"] for row in census["controls"]):
        raise CensusError("A screen control failed; the census is not admissible")
    census["coverage"] = {"files_and_system_areas": sum(len(r["sources"]) for r in census["releases"].values()),
                          "program_bin_entries": sum(len(r["program_bin"]["entries"]) for r in census["releases"].values()),
                          "runtime_load_reconciliation": "not-started",
                          "function_denominator": None, "code_bytes_denominator": None,
                          "whole_program_complete": False}
    return census


# --------------------------------------------------------------------------
# Verification of a committed census (no private bytes needed)

CONTROL_NAMES = ("krnl-original", "krnl-shifted-one-byte", "krnl-byte-swapped", "krnl-as-m68000",
                 "snd-original", "snd-shifted-one-byte", "snd-as-sh2", "film-bomss1-sh2", "film-bomss1-m68000")


def check_screen(row: dict) -> None:
    screened = row["screen"]
    if screened["bytes"] != row["bytes"]:
        raise CensusError("Screen length differs from source length: " + row["path"])
    for cpu in ("sh2", "m68000"):
        values = screened[cpu]
        expected = signal(values["epilogue_aligned"], values["epilogue_odd"])
        if cpu == "m68000":
            expected = expected or signal(values["rts_aligned"], values["rts_odd"], M68K_RTS_MIN, M68K_RTS_RATIO)
        if values["signal"] is not expected:
            raise CensusError("Recorded signal differs from its counts: " + row["path"])
        if values["ranges"] and not expected:
            raise CensusError("Ranges recorded without a signal: " + row["path"])
        cursor = 0
        for item in values["ranges"]:
            if not (cursor <= item["start"] < item["end"] <= row["bytes"]) or item["hits"] < RANGE_MIN_HITS:
                raise CensusError("Invalid code range: " + row["path"])
            cursor = item["end"]
    for link in row.get("identity_links", ()):
        if not 0 <= link["start"] < link["end"] <= row["bytes"]:
            raise CensusError("Identity link outside source: " + row["path"])


def check_row(row: dict) -> None:
    check_screen(row)
    if row["class"] not in CLASSES:
        raise CensusError("Unknown class: " + row["path"])
    if row["code_range_fraction"] != code_fraction(row):
        raise CensusError("Code fraction differs from recorded ranges: " + row["path"])
    if (row["class"], row["basis"]) != classify(row):
        raise CensusError("Class differs from the recorded evidence: " + row["path"])


def verify(census: dict, root: Path = ROOT) -> dict:
    if census.get("schema") != SCHEMA or set(census.get("releases", {})) != set(RELEASES):
        raise CensusError("Unsupported census schema or release set")
    coverage = census["coverage"]
    if (coverage.get("whole_program_complete") is not False or coverage.get("function_denominator") is not None
            or coverage.get("code_bytes_denominator") is not None
            or coverage.get("runtime_load_reconciliation") != "not-started"):
        raise CensusError("Census must not claim completion, totals or runtime reconciliation")
    names = [row["control"] for row in census["controls"]]
    if tuple(names) != CONTROL_NAMES or not all(row["passed"] is True and row["observed_signal"] is row["expected_signal"]
                                                for row in census["controls"]):
        raise CensusError("Screen controls missing or failed")
    sources = 0
    for release, result in census["releases"].items():
        summary, directory = None, None
        for key, spec in (("disc_summary", RELEASES[release]["summary"]),
                          ("kernel_directory", RELEASES[release]["directory"])):
            value, digest = read_json(root / spec)
            if result["receipts"][key] != {"path": spec, "sha256": digest}:
                raise CensusError("Receipt identity changed; regenerate the census explicitly: " + spec)
            summary, directory = (value, directory) if key == "disc_summary" else (summary, value)
        expected = {row["path"]: (row["sha256"], row["byte_length"]) for row in summary["iso9660"]["files"]}
        expected[SYSTEM_AREA] = (summary["ip_bin"]["system_area_sha256"], summary["ip_bin"]["byte_length"])
        seen = {}
        for row in result["sources"]:
            if row["path"] in seen:
                raise CensusError("Duplicate source: " + row["path"])
            seen[row["path"]] = (row["sha256"], row["bytes"])
            check_row(row)
        if seen != expected:
            raise CensusError("Census sources differ from the disc receipt: " + release)
        sources += len(seen)
        program = result["program_bin"]
        if program["path"] != RELEASES[release]["program"]:
            raise CensusError("PROGRAM.BIN path mismatch")
        want = {row["bank_id"]: row for row in directory["entries"]}
        got = {row["bank_id"]: row for row in program["entries"]}
        if set(want) != set(got) or len(got) != len(program["entries"]):
            raise CensusError("PROGRAM.BIN entries differ from the kernel directory receipt")
        for bank_id, row in got.items():
            entry = want[bank_id]
            if (row["byte_offset"], row["bytes"], row["sha256"], row["load_dest"]) != (
                    entry["byte_offset"], entry["byte_length"], entry["sha256"], entry["load_dest"]):
                raise CensusError("PROGRAM.BIN entry identity changed: %d" % bank_id)
            check_row(row)
        tail = program["unreferenced_tail"]
        accounting = directory["program_bin_accounting"]
        if (tail["byte_offset"], tail["bytes"], tail["sha256"]) != (
                accounting["referenced_bytes"], accounting["unreferenced_tail_bytes"],
                accounting["unreferenced_tail_sha256"]):
            raise CensusError("PROGRAM.BIN tail identity changed")
        check_row(tail)
        spans = sorted((row["byte_offset"], row["byte_offset"] + row["bytes"]) for row in program["entries"])
        spans.append((tail["byte_offset"], tail["byte_offset"] + tail["bytes"]))
        if spans[0][0] != 0 or any(a[1] != b[0] for a, b in zip(spans, spans[1:])) or \
                spans[-1][1] != expected[program["path"]][1]:
            raise CensusError("PROGRAM.BIN entries and tail do not partition the file")
        if result["totals"] != {"sources": totals(result["sources"]),
                                "program_bin_entries": totals(program["entries"])}:
            raise CensusError("Recorded totals differ from rows: " + release)
    if coverage["files_and_system_areas"] != sources:
        raise CensusError("Coverage count differs from rows")
    return {"status": "census-consistent", "sources": sources,
            "program_bin_entries": coverage["program_bin_entries"], "whole_program_complete": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("extract", help="Copy EDC-checked original files to a private directory")
    one.add_argument("--root", type=Path, required=True)
    one.add_argument("--cue", required=True)
    one.add_argument("--release", choices=sorted(RELEASES), required=True)
    one.add_argument("--output-dir", type=Path, required=True)
    two = commands.add_parser("screen", help="Write a metadata-only census from private extractions")
    two.add_argument("--usa-files", type=Path, required=True)
    two.add_argument("--japan-files", type=Path, required=True)
    two.add_argument("--output", type=Path, required=True)
    three = commands.add_parser("verify", help="Check a committed census against pinned receipts")
    three.add_argument("--census", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            receipt = extract(args.root, args.cue, ROOT / RELEASES[args.release]["summary"], args.output_dir)
            print(json.dumps({"status": "extracted", "files": len(receipt["files"]),
                              "edc_verified_sectors": receipt["edc_verified_sectors"]}))
        elif args.command == "screen":
            census = build({"usa-mk81070-v1003": args.usa_files, "japan-t14302g-v1000": args.japan_files})
            verify(census)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(canonical(census))
            print(json.dumps(verify(read_json(args.output)[0])))
        else:
            print(json.dumps(verify(read_json(args.census)[0])))
    except (CensusError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print("FAIL: disc code census rejected (" + type(error).__name__ + ": " + str(error)[:200] + ")",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
