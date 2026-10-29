#!/usr/bin/env python3
"""Read-only CUE/IP-header/firmware evidence, separate from emulator input locks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from cli import CUE_FILE, LabError, confined_file, disc_files, output_json, read_json, record

SCHEMA = "neptune.saturn-media.v1"
FIRMWARE = {
    "usa": {"filename": "mpr-17933.bin", "md5": "3240872c70984b6cbfda1586cab68dbe"},
    "europe": {"filename": "mpr-17933.bin", "md5": "3240872c70984b6cbfda1586cab68dbe"},
    "japan": {"filename": "sega_101.bin", "md5": "85ec9ca47d8f6807718151cbcca8b964"},
}
AREA = {"usa": "U", "europe": "E", "japan": "J"}


def first_data_track(root: Path, cue: str) -> dict:
    """Resolve TRACK 01 and its INDEX 01; never assume a filename or file offset."""
    disc_files(root, cue)  # Validate every FILE dependency, including audio.
    entry = confined_file(root, cue)
    if entry.suffix.lower() != ".cue":
        raise LabError("IP-header inspection requires CUE, not opaque CHD")
    current_file = None
    data_file = None
    mode = None
    index = None
    first_seen = False
    for line in entry.read_text(encoding="utf-8-sig").splitlines():
        file_match = CUE_FILE.fullmatch(line)
        if file_match:
            if first_seen and index is None:
                raise LabError("Data track lacks INDEX 01")
            current_file = file_match.group(1) or file_match.group(2)
        track = re.fullmatch(r"\s*TRACK\s+(\d+)\s+(\S+)\s*", line, re.I)
        if track:
            if first_seen:
                break
            if track.group(1) != "01" or current_file is None:
                raise LabError("First track must be numbered 01 with a FILE")
            mode = track.group(2).upper()
            data_file = current_file
            if mode not in ("MODE1/2352", "MODE1/2048"):
                raise LabError("First track must use supported MODE1 sectors")
            first_seen = True
        if first_seen and re.match(r"\s*INDEX\s+01(?:\s|$)", line, re.I):
            match = re.fullmatch(r"\s*INDEX\s+01\s+(\d{2}):(\d{2}):(\d{2})\s*", line, re.I)
            if match is None or index is not None:
                raise LabError("Invalid or repeated data INDEX 01")
            minutes, seconds, frames = map(int, match.groups())
            if seconds >= 60 or frames >= 75:
                raise LabError("CUE index time exceeds second/frame bounds")
            index = (minutes * 60 + seconds) * 75 + frames
    if not first_seen or index is None:
        raise LabError("CUE has no supported data TRACK 01 / INDEX 01")
    relative = (Path(cue).parent / data_file).as_posix()
    return {"path": relative, "mode": mode, "index_sector": index}


def read_ip_header(root: Path, cue: str) -> dict:
    track = first_data_track(root, cue)
    sector_size = 2352 if track["mode"] == "MODE1/2352" else 2048
    with confined_file(root, track["path"]).open("rb") as stream:
        stream.seek(track["index_sector"] * sector_size)
        sector = stream.read(sector_size)
    if len(sector) != sector_size:
        raise LabError("Truncated or out-of-range first data sector")
    if sector_size == 2352:
        if sector[:12] != b"\x00" + b"\xff" * 10 + b"\x00" or sector[15] != 1:
            raise LabError("Invalid raw MODE1 sync/mode header")
        data = sector[16:2064]
    else:
        data = sector
    if data[:16] != b"SEGA SEGASATURN ":
        raise LabError("Missing Saturn IP-header signature")

    def ascii_field(start, length):
        try:
            value = data[start:start + length].decode("ascii").rstrip(" \x00")
        except UnicodeError as error:
            raise LabError("Non-ASCII Saturn identification field") from error
        if any(ord(char) < 32 for char in value):
            raise LabError("Control byte in Saturn identification field")
        return value

    # Pinned core disc.c CalcGameID reads product/version at0x20 (16 bytes),
    # area at0x40 (16), and name at0x60 (112). Split on its last V marker.
    combined = ascii_field(0x20, 16)
    product, marker, revision = combined.rpartition("V")
    if not marker or not product.strip() or not re.fullmatch(r"\d+(?:\.\d+)*", revision):
        raise LabError("Unrecognised product/revision identification field")
    return {"source": track, "product": product.rstrip(), "revision": "V" + revision,
            "product_revision_field": combined, "area_symbols": ascii_field(0x40, 16),
            "title": ascii_field(0x60, 112), "user_sector_sha256": hashlib.sha256(data).hexdigest(),
            "scope": "Header identity only; no EDC/ECC/full-disc validity, pressed-disc provenance or boot proof"}


def inspect_media(root: Path, disc: str, region: str, bios: str | None = None) -> dict:
    if region not in FIRMWARE:
        raise LabError("Unsupported reference region")
    paths = disc_files(root, disc)
    header = read_ip_header(root, disc)
    if AREA[region] not in header["area_symbols"]:
        raise LabError("Requested region does not match observed IP-header area")
    candidates = []
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in (".bin", ".rom", ".bios"):
            continue
        item = record(root, path.name)
        # MD5 is only the compatibility-catalogue lookup, never research identity.
        lookup = hashlib.md5(usedforsecurity=False)
        with confined_file(root, path.name).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                lookup.update(chunk)
        item["md5"] = lookup.hexdigest()
        candidates.append(item)
    expected = FIRMWARE[region]
    matches = [item for item in candidates if item["bytes"] == 524288 and item["md5"] == expected["md5"]]
    if bios is not None:
        selected = next((item for item in matches if item["path"] == bios), None)
        if selected is None:
            raise LabError("Explicit BIOS does not match expected region firmware bytes")
    else:
        if not matches:
            raise LabError("No checksum-matching firmware candidate for region")
        if len({item["sha256"] for item in matches}) != 1:
            raise LabError("Ambiguous MD5 matches with differing SHA-256 identities")
        selected = matches[0]  # Stable alias selection only after byte identity.
    files = {item["path"]: {key: item[key] for key in ("path", "bytes", "sha256")} for item in candidates}
    files.update({path: record(root, path) for path in paths})
    return {"schema": SCHEMA, "region": region, "disc": disc, "header": header,
            "files": [files[key] for key in sorted(files)], "track_file_count": len(paths) - 1,
            "bios_candidates": candidates, "bios": selected["path"], "matching_bios_paths": [item["path"] for item in matches],
            "firmware": dict(expected), "scope": "Media evidence only; not an emulator/core/configuration lock or reference-ready claim"}


def verify_media(root: Path, manifest) -> int:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise LabError("Unsupported media report schema")
    if not all(isinstance(manifest.get(key), str) for key in ("disc", "region", "bios")):
        raise LabError("Missing media input identities")
    actual = inspect_media(root, manifest["disc"], manifest["region"], manifest["bios"])
    if actual != manifest:
        raise LabError("Media report differs from current files/header/firmware")
    return len(actual["files"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--disc")
    parser.add_argument("--region", choices=tuple(FIRMWARE))
    parser.add_argument("--bios")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            if args.report is None:
                raise LabError("verify requires --report")
            print(f"Verified {verify_media(args.root, read_json(args.report))} media files; no emulator readiness claim.")
        else:
            if args.disc is None or args.region is None:
                raise LabError("inspect requires --disc and --region")
            result = inspect_media(args.root, args.disc, args.region, args.bios)
            if args.output is not None and any(args.output.resolve() == confined_file(args.root, item["path"]).resolve() for item in result["files"]):
                raise LabError("Output must not overwrite media input")
            output_json(result, args.output)
    except (LabError, OSError, ValueError, UnicodeError) as error:
        print(f"saturn-media: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
