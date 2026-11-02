#!/usr/bin/env python3
"""Reconcile code-module leads with pinned disc metadata; never claim code recovery.

No original binaries are opened by this command. Source identities below are
declarations from accepted disc receipts, not freshly authenticated extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "neptune.saturn-code-candidates.v1"
UPSTREAM = {
    "repository": "callumjenkins/pc-saturnbomberman",
    "revision": "c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3",
    "path": "game.toml",
    "git_blob_sha1": "0ec8d923776c90935d415f4e9209612e55c401a9",
}
RECEIPTS = {
    "usa-mk81070-v1003": "4c325529d89451a236fbb34fb7172b183e054de48ece81e0f7c7acfcd34dfdf5",
    "japan-t14302g-v1000": "1bc46cf5e0cee2c41c0686e59886d347493629ce7b0557e7ba29ea9c01e8c290",
}
# name, source, source offset, length (None: derived extent unknown), CPU,
# candidate load address, lifetime identity, derivation, candidate entry seeds.
USA = (
    ("SYSTEM_BOOTSTRAP", "@track01-system-area", 0, "file", "sh2-role-unresolved", None, "bios-system-area-bootstrap", "original-system-area", []),
    ("BOOT", "0", 0, "file", "sh2-role-unresolved", 0x06010000, "netlink-boot", "original", []),
    ("TRAMP", "0", 0x3B4B0, None, "sh2-role-unresolved", 0x00200000, "derived-boot-trampoline", "upstream-derived", []),
    ("XS", "NETLINK/XS028000.EXE", 0, "file", "sh2-role-unresolved", 0x00280000, "netlink-launcher", "original", []),
    ("SAMPLEIP", "SAMPLEIP.BIN", 0, "file", "sh2-role-unresolved", None, "original-ip-template-unmapped", "original-template", []),
    ("IP_PATCHED", "SAMPLEIP.BIN", 0, None, "sh2-role-unresolved", 0x06002000, "upstream-patched-ip", "upstream-patched", [0x06002100, 0x06002E20]),
    ("FLD", "FLD_KNL.BIN", 0, "file", "sh2-role-unresolved", 0x00200000, "field-loader", "original", [0x002001A4]),
    ("H2H", "XBAND/H2HLIBUS.BIN", 0, "file", "sh2-role-unresolved", 0x06002F00, "online-h2h-library", "original", [0x06003320]),
    ("XBAND", "XBAND/XBAND.BIN", 0, "file", "sh2-role-unresolved", 0x06006000, "xband-client", "original", [0x06006002]),
    ("KRNL", "BOMSS/0KRNL.BIN", 0, "file", "sh2-role-unresolved", 0x06006000, "resident-game-kernel", "original", [0x06006174]),
    ("SND", "BOMSS/PROGRAM.BIN", 0x44, 0x63D4, "m68000", 0, "game-sound-driver", "original-slice-lead", []),
    ("XBSND", "XBAND/XBAND.DAT", 0x11868, 0x63D4, "m68000", 0, "xband-sound-driver", "original-slice-lead", []),
    ("NLSND", "NETLINK/SNDDRV.BIN", 0, "file", "m68000", 0, "netlink-sound-driver", "original", []),
)
JAPAN = (
    ("SYSTEM_BOOTSTRAP", "@track01-system-area", 0, "file", "sh2-role-unresolved", None, "bios-system-area-bootstrap", "original-system-area", []),
    ("KRNL", "0KRNL.BIN", 0, "file", "sh2-role-unresolved", 0x0600A000, "boot-and-resident-game-kernel", "original", []),
)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path, limit: int) -> tuple[dict, str]:
    path = path.absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("Symlink metadata paths are unsupported")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Metadata must be a regular file within its size budget")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Metadata exceeds size budget")
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Metadata must be an object")
    return value, sha(raw)


def safe_source(path: str) -> None:
    if (not isinstance(path, str) or not path or "\\" in path
            or PurePosixPath(path).is_absolute() or path != str(PurePosixPath(path))
            or any(part in (".", "..") for part in path.split("/"))):
        raise ValueError("Source identity must be a confined disc path")


def files(summary: dict) -> dict[str, dict]:
    if summary.get("schema") != "neptune.saturn-disc-inventory.v1":
        raise ValueError("Unsupported disc inventory schema")
    rows = summary["iso9660"]["files"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError("Require a bounded nonempty file inventory")
    result = {}
    for row in rows:
        path = row["path"]
        safe_source(path)
        if path in result or type(row["byte_length"]) is not int or row["byte_length"] <= 0:
            raise ValueError("Duplicate source identity or invalid source length")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid source digest")
        result[path] = row
    return result


def mapping(release: str, definition: tuple, sources: dict[str, dict]) -> dict:
    name, path, offset, length, cpu, base, lifetime, derivation, seeds = definition
    source = sources[path]
    count = source["byte_length"] if length == "file" else length
    if type(offset) is not int or not 0 <= offset < source["byte_length"]:
        raise ValueError("Candidate source offset outside file")
    if count is not None and (type(count) is not int or count <= 0 or offset + count > source["byte_length"]):
        raise ValueError("Candidate source extent outside file")
    if base is not None and (type(base) is not int or not 0 <= base < 2**32
                             or (count is not None and base + count > 2**32)):
        raise ValueError("Candidate load range outside address space")
    if any(type(seed) is not int or seed % 2 or base is None or seed < base
           or (count is not None and seed >= base + count) for seed in seeds):
        raise ValueError("Candidate entry outside mapping")
    identity = {"release": release, "source_sha256": source["sha256"],
                "source_path": path, "offset": offset, "bytes": count,
                "source_kind": source.get("source_kind", "iso9660-file"),
                "cpu": cpu, "load_address": base, "lifetime": lifetime,
                "derivation": derivation}
    return {"id": release + ":" + name + ":" + sha(canonical(identity).encode())[:16],
            "name": name, **identity,
            "source_container_bytes": source["byte_length"],
            "source_format_declaration": source["classification"]["detected_format"],
            "candidate_entries": seeds,
            "mapping_status": "candidate-not-runtime-validated",
            "original_byte_extent": derivation in ("original", "original-slice-lead", "original-template", "original-system-area"),
            "derived_artifact_sha256": None,
            "classified_code_bytes": None, "function_count": None,
            "semantic_validation": "not-established-by-census"}


def build(summaries: dict[str, dict], receipt_hashes: dict[str, str]) -> dict:
    if set(summaries) != set(RECEIPTS) or set(receipt_hashes) != set(RECEIPTS):
        raise ValueError("Require separate USA and Japan inventories")
    if any(receipt_hashes[key] != expected for key, expected in RECEIPTS.items()):
        raise ValueError("Disc receipt identity changed; reconcile explicitly before regeneration")
    sources = {release: files(value) for release, value in summaries.items()}
    for release, summary in summaries.items():
        system = summary["ip_bin"]
        if (system["byte_length"] != 32768 or system["lba_start"] != 0
                or system["sector_count"] != 16
                or not re.fullmatch(r"[0-9a-f]{64}", system["system_area_sha256"])):
            raise ValueError("Invalid retained system-area identity")
        sources[release]["@track01-system-area"] = {
            "byte_length": system["byte_length"], "sha256": system["system_area_sha256"],
            "source_kind": "track01-index01-relative-lba0-system-area",
            "classification": {"detected_format": "saturn-system-area-with-bootstrap-lead"}}
    if summaries["usa-mk81070-v1003"]["ip_bin"]["first_read_load_addr_hex"].lower() != "0x06010000":
        raise ValueError("USA first-read mapping changed")
    if summaries["japan-t14302g-v1000"]["ip_bin"]["first_read_load_addr_hex"].lower() != "0x0600a000":
        raise ValueError("Japan first-read mapping changed")
    candidates = [mapping(release, item, sources[release])
                  for release, definitions in (("usa-mk81070-v1003", USA), ("japan-t14302g-v1000", JAPAN))
                  for item in definitions]
    if len({item["id"] for item in candidates}) != len(candidates):
        raise ValueError("Duplicate module/lifetime identity")
    return {"schema": SCHEMA, "upstream_leads": UPSTREAM,
            "disc_receipts": {release: {"path": "docs/restart/saturn-disc/" + release + ".summary.json",
                                        "sha256": receipt_hashes[release]} for release in sorted(RECEIPTS)},
            "scope": "Metadata reconciliation only; original binaries were not read or executed.",
            "candidates": candidates,
            "coverage": {"candidate_mappings": len(candidates), "complete_module_denominator": None,
                         "code_bytes_denominator": None, "function_denominator": None,
                         "whole_program_complete": False},
            "accepted_results_outside_census": [
                {"result": "USA helper 0x0600A4B0 isolated original-byte samples",
                 "evidence": "docs/restart/research/2026-10-30-saturn-original-kernel-result.md",
                 "scope": "One helper, not natural caller/timing or whole-program validation."},
                {"result": "Hudson decompressor implementation and selected resident byte comparisons",
                 "evidence": "docs/restart/evidence/2026-10-30-gemini-program-bin-archive-002.md",
                 "scope": "Output-byte evidence, not a complete original-function coverage denominator."}],
            "unresolved": ["Master/slave SH-2 roles and module residency transitions",
                           "System-area bootstrap code versus SAMPLEIP template and runtime patches",
                           "Executable ranges versus literals/data inside all candidate files and banks",
                           "Bank-contained, copied, generated and self-modifying code",
                           "Indirect calls/jumps, task yield/resume and dynamic entry targets",
                           "68000 driver/data boundaries, runtime patches and DSP instruction programs",
                           "Japan-only modules and regional equivalents beyond the known first-read kernel",
                           "Natural caller, ABI, state effects and semantic equivalence for every function"]}


def generate(root: Path = ROOT) -> dict:
    summaries, identities = {}, {}
    for release in RECEIPTS:
        summaries[release], identities[release] = read_json(
            root / "docs/restart/saturn-disc" / (release + ".summary.json"), 4 * 1024**2)
    return build(summaries, identities)


def verify(value: dict, expected: dict) -> None:
    # Exact canonical comparison catches type coercion, dropped overlays,
    # invented complete/verified fields and changed source/mapping identities.
    if canonical(value) != canonical(expected):
        raise ValueError("Code census differs from pinned source identities and candidate mappings")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--census", type=Path, required=True,
                        help="New output for generate; existing metadata for verify")
    args = parser.parse_args(argv)
    try:
        expected = generate(args.root)
        if args.command == "generate":
            if any(p.is_symlink() for p in (args.census.absolute(), *args.census.absolute().parents)):
                raise ValueError("Symlink output path unsupported")
            with args.census.open("x", encoding="utf-8") as stream:
                stream.write(canonical(expected))
        else:
            value, _ = read_json(args.census, 1024**2)
            verify(value, expected)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("FAIL: code census rejected (" + type(error).__name__ + ")", file=sys.stderr)
        return 1
    print(json.dumps({"status": "metadata-consistent", "candidate_mappings": len(expected["candidates"]),
                      "whole_program_complete": False, "original_execution": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
