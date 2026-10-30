#!/usr/bin/env python3
"""CLI for static Sega Saturn disc inspection, 100% byte accounting and regional diffs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from saturn_disc import DISC_DIFF_SCHEMA, DISC_INVENTORY_SCHEMA, TOOL_VERSION
    from saturn_disc.cue import DiscError, parse_cue_sheet
    from saturn_disc.diff import diff_disc_inventories
    from saturn_disc.iso9660 import inspect_disc
else:
    from . import DISC_DIFF_SCHEMA, DISC_INVENTORY_SCHEMA, TOOL_VERSION
    from .cue import DiscError, parse_cue_sheet
    from .diff import diff_disc_inventories
    from .iso9660 import inspect_disc

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def write_json_atomic(payload: dict[str, Any], target: Path) -> str:
    if target.is_symlink():
        raise DiscError(f"Refusing to write through symlink: {target}")
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(encoded)
        os.replace(tmp_name, target)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return digest


def _load_asset_lookup(manifest_path: Path | None) -> tuple[dict[str, list[str]], dict[str, list[str]], str | None]:
    if manifest_path is None:
        return {}, {}, None
    raw = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw.decode("utf-8"))
    by_sha: dict[str, list[str]] = {}
    by_2mib_sha: dict[str, list[str]] = {}
    for entry in doc.get("files", []):
        sha = entry["sha256"]
        path = entry["path"]
        by_sha.setdefault(sha, []).append(path)
        if entry["bytes"] == 2 * 1024 * 1024:
            by_2mib_sha.setdefault(sha, []).append(path)
    return by_sha, by_2mib_sha, manifest_sha


def _cross_check_media_report(disc_result: dict[str, Any], media_report_path: Path | None) -> dict[str, Any] | None:
    if media_report_path is None:
        return None
    raw = media_report_path.read_bytes()
    report_sha = hashlib.sha256(raw).hexdigest()
    media = json.loads(raw.decode("utf-8"))
    expected_files = {item["path"]: item for item in media.get("files", [])}

    cue_rel = disc_result["cue"]["path"]
    if cue_rel in expected_files:
        exp = expected_files[cue_rel]
        if exp["sha256"] != disc_result["cue"]["sha256"] or exp["bytes"] != disc_result["cue"]["bytes"]:
            raise DiscError(f"CUE hash/size mismatch against #462 media report for {cue_rel}")

    verified_tracks = 0
    for trk in disc_result["tracks"]:
        t_rel = trk["file_relpath"]
        if t_rel not in expected_files:
            raise DiscError(f"Track {t_rel} missing from #462 media report")
        exp = expected_files[t_rel]
        if exp["sha256"] != trk["file_sha256"] or exp["bytes"] != trk["file_bytes"]:
            raise DiscError(f"Track {t_rel} hash/size mismatch against #462 media report")
        verified_tracks += 1

    hdr = media.get("header", {})
    ip = disc_result["ip_bin"]
    if hdr.get("product") != ip["product_number"] or hdr.get("revision") != ip["version"]:
        raise DiscError(
            f"IP.BIN product/version ({ip['product_number']} {ip['version']}) "
            f"differs from #462 media report ({hdr.get('product')} {hdr.get('revision')})"
        )

    return {
        "media_report_sha256": report_sha,
        "region": media.get("region"),
        "selected_bios_path": media.get("bios"),
        "firmware_catalog": media.get("firmware"),
        "verified_track_hashes": verified_tracks,
        "ip_header_consistent": True,
    }


def build_public_summary(full_doc: dict[str, Any], full_sha256: str) -> dict[str, Any]:
    """Create the deterministic, repo-committable disc summary (no raw bytes, compact intervals)."""
    acc = dict(full_doc["accounting"])
    intervals = acc.pop("track01_intervals")
    acc["track01_interval_count"] = len(intervals)
    acc["unreferenced_nonzero_intervals"] = [
        item for item in intervals if item["region_kind"] == "unreferenced_nonzero_sectors"
    ]
    acc["zero_padding_intervals"] = [
        {
            "lba_start": item["lba_start"],
            "lba_end_exclusive": item["lba_end_exclusive"],
            "sector_count": item["sector_count"],
        }
        for item in intervals
        if item["region_kind"] == "unreferenced_zero_padding"
    ]
    return {
        "schema": DISC_INVENTORY_SCHEMA,
        "tool_version": full_doc["tool_version"],
        "private_full_manifest_sha256": full_sha256,
        "media_lock_cross_check": full_doc["media_lock_cross_check"],
        "asset_audit_manifest_sha256": full_doc["asset_audit_manifest_sha256"],
        "cue": full_doc["cue"],
        "ip_bin": full_doc["ip_bin"],
        "track01_edc": full_doc["track01_edc"],
        "iso9660": full_doc["iso9660"],
        "accounting": acc,
        "tracks": full_doc["tracks"],
        "asset_repo_matches": [
            {
                "disc_path": f["path"],
                "disc_bytes": f["byte_length"],
                "disc_sha256": f["sha256"],
                "detected_format": f["classification"]["detected_format"],
                "exact_asset_repo_paths": f["matched_asset_repo_paths"],
                "truncated_2mib_asset_repo_paths": f["matched_asset_repo_truncated_2mib_paths"],
            }
            for f in full_doc["iso9660"]["files"]
            if f["matched_asset_repo_paths"] or f["matched_asset_repo_truncated_2mib_paths"]
        ],
    }


def verify_disc_summary(summary: dict[str, Any]) -> None:
    if not isinstance(summary, dict) or summary.get("schema") != DISC_INVENTORY_SCHEMA:
        raise DiscError("Invalid or unsupported disc summary schema")
    if not SHA256_RE.fullmatch(str(summary.get("private_full_manifest_sha256", ""))):
        raise DiscError("Missing/invalid private_full_manifest_sha256")
    ip = summary.get("ip_bin", {})
    if ip.get("hardware_id") != "SEGA SEGASATURN":
        raise DiscError("Invalid IP.BIN hardware_id in summary")
    edc = summary.get("track01_edc", {})
    if edc.get("edc_mismatches") != 0 or edc.get("edc_checked_sectors", 0) <= 0:
        raise DiscError("Summary fails Mode 1 EDC verification check")
    acc = summary.get("accounting", {})
    total_blocks = acc.get("track01_total_logical_blocks", -1)
    accounted = acc.get("track01_accounted_logical_blocks", -2)
    unaccounted = acc.get("track01_unaccounted_logical_blocks", -1)
    by_class = acc.get("track01_sectors_by_class", {})
    if total_blocks <= 16 or accounted != total_blocks or unaccounted != 0:
        raise DiscError("Track 01 logical blocks are not 100% accounted for")
    if sum(by_class.values()) != total_blocks:
        raise DiscError("Track 01 sector class breakdown does not sum to total_logical_blocks")
    tracks = summary.get("tracks", [])
    if not tracks or sum(t["file_bytes"] for t in tracks) != summary["cue"]["total_track_bytes"]:
        raise DiscError("Track byte totals do not match CUE total_track_bytes")
    iso_files = summary.get("iso9660", {}).get("files", [])
    if len(iso_files) != summary["iso9660"]["file_count"]:
        raise DiscError("ISO-9660 file count mismatch")
    for f in iso_files:
        if not SHA256_RE.fullmatch(str(f.get("sha256", ""))):
            raise DiscError(f"Invalid SHA-256 on ISO-9660 file {f.get('path')}")


def verify_diff_summary(diff_doc: dict[str, Any]) -> None:
    if not isinstance(diff_doc, dict) or diff_doc.get("schema") != DISC_DIFF_SCHEMA:
        raise DiscError("Invalid or unsupported disc diff schema")
    left = diff_doc.get("left_release", {})
    right = diff_doc.get("right_release", {})
    if left.get("cue_sha256") == right.get("cue_sha256") and left.get("track01_sha256") == right.get("track01_sha256"):
        raise DiscError("Diff compares identical disc images")
    iso = diff_doc.get("iso9660_summary", {})
    if (
        iso.get("identical_path_and_sha256_count", 0)
        + iso.get("modified_same_path_count", 0)
        + iso.get("only_in_left_count", 0)
        != iso.get("left_file_count", -1)
    ):
        raise DiscError("Left ISO-9660 file partition counts do not sum to left_file_count")
    if (
        iso.get("identical_path_and_sha256_count", 0)
        + iso.get("modified_same_path_count", 0)
        + iso.get("only_in_right_count", 0)
        != iso.get("right_file_count", -1)
    ):
        raise DiscError("Right ISO-9660 file partition counts do not sum to right_file_count")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Decode Saturn CUE/IP.BIN/ISO-9660 and verify 100%% byte accounting")
    p_inspect.add_argument("--root", type=Path, required=True, help="Read-only media root directory")
    p_inspect.add_argument("--cue", required=True, help="Relative POSIX path to .cue inside --root")
    p_inspect.add_argument("--media-report", type=Path, help="Optional #462 media report JSON to cross-verify")
    p_inspect.add_argument("--assets-manifest", type=Path, help="Optional #463 private asset manifest JSON")
    p_inspect.add_argument("--private-out", type=Path, required=True, help="Private full JSON output path")
    p_inspect.add_argument("--summary-out", type=Path, required=True, help="Committed summary JSON output path")

    p_diff = sub.add_parser("diff", help="Diff two regional disc inventory JSON files without blending profiles")
    p_diff.add_argument("--left", type=Path, required=True)
    p_diff.add_argument("--right", type=Path, required=True)
    p_diff.add_argument("--left-root", type=Path, help="Optional media root for CD-DA sample-shift verification")
    p_diff.add_argument("--right-root", type=Path, help="Optional media root for CD-DA sample-shift verification")
    p_diff.add_argument("--output", type=Path, required=True)

    p_verify = sub.add_parser("verify", help="Validate committed disc summary and diff JSON invariants")
    p_verify.add_argument("--summary", type=Path, action="append", default=[])
    p_verify.add_argument("--diff", type=Path, action="append", default=[])

    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            asset_hashes, prefix_hashes, asset_manifest_sha = _load_asset_lookup(args.assets_manifest)
            cue = parse_cue_sheet(args.root, args.cue)
            inspected = inspect_disc(
                cue,
                asset_hashes=asset_hashes,
                asset_prefix_2mib_hashes=prefix_hashes,
            )
            media_check = _cross_check_media_report(inspected, args.media_report)
            full_doc = {
                "schema": DISC_INVENTORY_SCHEMA,
                "tool_version": TOOL_VERSION,
                "media_lock_cross_check": media_check,
                "asset_audit_manifest_sha256": asset_manifest_sha,
                **inspected,
            }
            full_sha = write_json_atomic(full_doc, args.private_out)
            summary_doc = build_public_summary(full_doc, full_sha)
            verify_disc_summary(summary_doc)
            summary_sha = write_json_atomic(summary_doc, args.summary_out)
            print(
                json.dumps(
                    {
                        "product": full_doc["ip_bin"]["product_number"],
                        "version": full_doc["ip_bin"]["version"],
                        "area_symbols": full_doc["ip_bin"]["area_symbols"],
                        "iso_files": full_doc["iso9660"]["file_count"],
                        "track01_blocks": full_doc["accounting"]["track01_total_logical_blocks"],
                        "edc_checked": full_doc["track01_edc"]["edc_checked_sectors"],
                        "asset_matches": len(summary_doc["asset_repo_matches"]),
                        "private_full_sha256": full_sha,
                        "summary_sha256": summary_sha,
                    },
                    indent=2,
                )
            )
        elif args.command == "diff":
            left_doc = json.loads(args.left.read_text(encoding="utf-8"))
            right_doc = json.loads(args.right.read_text(encoding="utf-8"))
            diff_doc = diff_disc_inventories(
                left_doc,
                right_doc,
                root_a=args.left_root,
                root_b=args.right_root,
            )
            verify_diff_summary(diff_doc)
            diff_sha = write_json_atomic(diff_doc, args.output)
            print(
                json.dumps(
                    {
                        "left": diff_doc["left_release"]["label"],
                        "right": diff_doc["right_release"]["label"],
                        "iso9660_summary": diff_doc["iso9660_summary"],
                        "diff_sha256": diff_sha,
                    },
                    indent=2,
                )
            )
        else:
            if not args.summary and not args.diff:
                raise DiscError("Specify at least one --summary or --diff file to verify")
            for s_path in args.summary:
                verify_disc_summary(json.loads(s_path.read_text(encoding="utf-8")))
            for d_path in args.diff:
                verify_diff_summary(json.loads(d_path.read_text(encoding="utf-8")))
            print(f"Verified {len(args.summary)} disc summaries and {len(args.diff)} regional diffs.")
    except (DiscError, OSError, ValueError, KeyError) as exc:
        print(f"saturn-disc: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
