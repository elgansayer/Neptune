"""Regional Sega Saturn disc comparison without blending regional profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import DISC_DIFF_SCHEMA, TOOL_VERSION


def detect_cdda_sample_shift(path_a: Path, path_b: Path, max_shift_samples: int = 4096) -> dict[str, Any]:
    """Test whether two 16-bit LE stereo PCM CD-DA BIN files are bit-exact up to a fixed sample shift."""
    data_a = path_a.read_bytes()
    data_b = path_b.read_bytes()
    len_a, len_b = len(data_a), len(data_b)
    if data_a == data_b:
        return {
            "exact_byte_match": True,
            "sample_shifted_pcm_match": True,
            "stereo_sample_shift_b_minus_a": 0,
            "interior_overlap_bytes": len_a,
            "interior_mismatch_bytes": 0,
        }

    # Find a non-zero 4096-byte anchor near the midpoint of track A
    mid = (len_a // 2) & ~3
    anchor_len = 4096
    max_shift_bytes = max_shift_samples * 4
    anchor_pos: int | None = None
    for candidate in (mid, len_a // 3 & ~3, (2 * len_a // 3) & ~3):
        if 0 <= candidate and candidate + anchor_len <= len_a:
            window = data_a[candidate : candidate + anchor_len]
            if any(window) and len(set(window)) > 8:
                anchor_pos = candidate
                break

    if anchor_pos is None:
        return {
            "exact_byte_match": False,
            "sample_shifted_pcm_match": False,
            "stereo_sample_shift_b_minus_a": None,
            "note": "No non-silent anchor window found",
        }

    anchor = data_a[anchor_pos : anchor_pos + anchor_len]
    search_start = max(0, anchor_pos - max_shift_bytes)
    search_end = min(len_b, anchor_pos + anchor_len + max_shift_bytes)
    found = data_b.find(anchor, search_start, search_end)
    if found == -1 or (found - anchor_pos) % 4 != 0:
        return {
            "exact_byte_match": False,
            "sample_shifted_pcm_match": False,
            "stereo_sample_shift_b_minus_a": None,
        }

    shift_bytes = found - anchor_pos  # b_offset = a_offset + shift_bytes
    shift_samples = shift_bytes // 4
    a_start = max(0, -shift_bytes)
    b_start = max(0, shift_bytes)
    overlap = min(len_a - a_start, len_b - b_start)

    if overlap <= 0:
        return {
            "exact_byte_match": False,
            "sample_shifted_pcm_match": False,
            "stereo_sample_shift_b_minus_a": None,
        }

    slice_a = memoryview(data_a)[a_start : a_start + overlap]
    slice_b = memoryview(data_b)[b_start : b_start + overlap]
    if slice_a == slice_b:
        # Check whether non-overlapping edges are digital silence (0x00)
        a_non_overlap = data_a[:a_start] + data_a[a_start + overlap :]
        b_non_overlap = data_b[:b_start] + data_b[b_start + overlap :]
        edges_silent = (not any(a_non_overlap)) and (not any(b_non_overlap))
        return {
            "exact_byte_match": False,
            "sample_shifted_pcm_match": True,
            "stereo_sample_shift_b_minus_a": shift_samples,
            "byte_shift_b_minus_a": shift_bytes,
            "interior_overlap_bytes": overlap,
            "interior_mismatch_bytes": 0,
            "non_overlapping_edges_all_zero": edges_silent,
        }

    # Count differing bytes if anchor matched locally but full track diverged
    mismatches = sum(1 for x, y in zip(slice_a, slice_b) if x != y)
    return {
        "exact_byte_match": False,
        "sample_shifted_pcm_match": False,
        "candidate_stereo_sample_shift": shift_samples,
        "interior_overlap_bytes": overlap,
        "interior_mismatch_bytes": mismatches,
    }


def diff_disc_inventories(
    inv_a: dict[str, Any],
    inv_b: dict[str, Any],
    *,
    root_a: Path | None = None,
    root_b: Path | None = None,
) -> dict[str, Any]:
    """Compare two regional disc inventories (e.g. USA vs Japan) while preserving strict separation."""
    ip_a, ip_b = inv_a["ip_bin"], inv_b["ip_bin"]
    label_a = f"{ip_a['product_number']}_{ip_a['version']}_{''.join(ip_a['area_symbols'])}"
    label_b = f"{ip_b['product_number']}_{ip_b['version']}_{''.join(ip_b['area_symbols'])}"

    ip_fields = (
        "product_number",
        "version",
        "release_date_iso",
        "area_symbols",
        "peripheral_codes",
        "game_title",
        "maker_id",
        "device_information",
        "ip_size_bytes",
        "master_sh2_stack_addr_hex",
        "slave_sh2_stack_addr_hex",
        "first_read_load_addr_hex",
        "first_read_size_bytes",
        "system_area_sha256",
        "boot_code_sha256",
    )
    ip_comparison = {
        field: {
            "equal": ip_a[field] == ip_b[field],
            "left": ip_a[field],
            "right": ip_b[field],
        }
        for field in ip_fields
    }

    files_a = {f["path"]: f for f in inv_a["iso9660"]["files"]}
    files_b = {f["path"]: f for f in inv_b["iso9660"]["files"]}
    all_paths = sorted(set(files_a) | set(files_b))

    identical_files: list[dict[str, Any]] = []
    modified_same_path: list[dict[str, Any]] = []
    only_in_left: list[dict[str, Any]] = []
    only_in_right: list[dict[str, Any]] = []

    hashes_b: dict[str, list[str]] = {}
    for path_b, rec_b in files_b.items():
        hashes_b.setdefault(rec_b["sha256"], []).append(path_b)

    hashes_a: dict[str, list[str]] = {}
    for path_a, rec_a in files_a.items():
        hashes_a.setdefault(rec_a["sha256"], []).append(path_a)

    for path in all_paths:
        fa = files_a.get(path)
        fb = files_b.get(path)
        if fa is not None and fb is not None:
            if fa["sha256"] == fb["sha256"]:
                identical_files.append(
                    {
                        "path": path,
                        "byte_length": fa["byte_length"],
                        "sha256": fa["sha256"],
                        "detected_format": fa["classification"]["detected_format"],
                        "left_lba": fa["extent_lba"],
                        "right_lba": fb["extent_lba"],
                    }
                )
            else:
                modified_same_path.append(
                    {
                        "path": path,
                        "left_bytes": fa["byte_length"],
                        "right_bytes": fb["byte_length"],
                        "byte_delta_right_minus_left": fb["byte_length"] - fa["byte_length"],
                        "left_sha256": fa["sha256"],
                        "right_sha256": fb["sha256"],
                        "left_format": fa["classification"]["detected_format"],
                        "right_format": fb["classification"]["detected_format"],
                        "left_lba": fa["extent_lba"],
                        "right_lba": fb["extent_lba"],
                    }
                )
        elif fa is not None:
            only_in_left.append(
                {
                    "path": path,
                    "byte_length": fa["byte_length"],
                    "sha256": fa["sha256"],
                    "detected_format": fa["classification"]["detected_format"],
                    "renamed_match_in_right": sorted(hashes_b.get(fa["sha256"], [])),
                }
            )
        elif fb is not None:
            only_in_right.append(
                {
                    "path": path,
                    "byte_length": fb["byte_length"],
                    "sha256": fb["sha256"],
                    "detected_format": fb["classification"]["detected_format"],
                    "renamed_match_in_left": sorted(hashes_a.get(fb["sha256"], [])),
                }
            )

    tracks_a = {t["track_number"]: t for t in inv_a["tracks"]}
    tracks_b = {t["track_number"]: t for t in inv_b["tracks"]}
    track_diffs: list[dict[str, Any]] = []
    for t_num in sorted(set(tracks_a) | set(tracks_b)):
        ta = tracks_a.get(t_num)
        tb = tracks_b.get(t_num)
        entry: dict[str, Any] = {
            "track_number": t_num,
            "left_present": ta is not None,
            "right_present": tb is not None,
        }
        if ta and tb:
            entry.update(
                {
                    "mode_equal": ta["mode"] == tb["mode"],
                    "left_mode": ta["mode"],
                    "right_mode": tb["mode"],
                    "left_bytes": ta["file_bytes"],
                    "right_bytes": tb["file_bytes"],
                    "byte_delta_right_minus_left": tb["file_bytes"] - ta["file_bytes"],
                    "exact_sha256_equal": ta["file_sha256"] == tb["file_sha256"],
                    "left_sha256": ta["file_sha256"],
                    "right_sha256": tb["file_sha256"],
                }
            )
            if ta["mode"] == "AUDIO" and tb["mode"] == "AUDIO" and root_a is not None and root_b is not None:
                entry["cdda_alignment"] = detect_cdda_sample_shift(
                    root_a / ta["file_relpath"],
                    root_b / tb["file_relpath"],
                )
        track_diffs.append(entry)

    # Compare Hudson Low-WRAM bank archives (PROGRAM.BIN) if present in both releases
    archives_a = [f for f in files_a.values() if f["classification"].get("detected_format") == "hudson_lwr_bank_archive"]
    archives_b = [f for f in files_b.values() if f["classification"].get("detected_format") == "hudson_lwr_bank_archive"]
    hudson_archive_diff: dict[str, Any] | None = None
    if len(archives_a) == 1 and len(archives_b) == 1:
        arch_a, arch_b = archives_a[0], archives_b[0]
        banks_a = arch_a["classification"]["banks"]
        banks_b = arch_b["classification"]["banks"]
        by_name_a: dict[str, list[dict[str, Any]]] = {}
        by_name_b: dict[str, list[dict[str, Any]]] = {}
        for b in banks_a:
            by_name_a.setdefault(b["name"], []).append(b)
        for b in banks_b:
            by_name_b.setdefault(b["name"], []).append(b)

        all_bank_names = sorted(set(by_name_a) | set(by_name_b))
        identical_banks: list[dict[str, Any]] = []
        modified_banks: list[dict[str, Any]] = []
        left_only_banks: list[dict[str, Any]] = []
        right_only_banks: list[dict[str, Any]] = []

        for b_name in all_bank_names:
            list_a = by_name_a.get(b_name, [])
            list_b = by_name_b.get(b_name, [])
            paired = min(len(list_a), len(list_b))
            for occ in range(paired):
                ba, bb = list_a[occ], list_b[occ]
                if ba["sha256"] == bb["sha256"]:
                    identical_banks.append(
                        {
                            "name": b_name,
                            "occurrence": occ,
                            "role_hypothesis": ba["role_hypothesis"],
                            "byte_length": ba["byte_length"],
                            "sha256": ba["sha256"],
                            "left_sector_offset": ba["sector_offset"],
                            "right_sector_offset": bb["sector_offset"],
                        }
                    )
                else:
                    modified_banks.append(
                        {
                            "name": b_name,
                            "occurrence": occ,
                            "role_hypothesis": ba["role_hypothesis"],
                            "left_bytes": ba["byte_length"],
                            "right_bytes": bb["byte_length"],
                            "byte_delta_right_minus_left": bb["byte_length"] - ba["byte_length"],
                            "left_sha256": ba["sha256"],
                            "right_sha256": bb["sha256"],
                            "left_sector_offset": ba["sector_offset"],
                            "right_sector_offset": bb["sector_offset"],
                            "left_load_base_lwr_hex": ba["load_base_lwr_hex"],
                            "right_load_base_lwr_hex": bb["load_base_lwr_hex"],
                        }
                    )
            for occ in range(paired, len(list_a)):
                ba = list_a[occ]
                left_only_banks.append(
                    {
                        "name": b_name,
                        "occurrence": occ,
                        "role_hypothesis": ba["role_hypothesis"],
                        "byte_length": ba["byte_length"],
                        "sha256": ba["sha256"],
                        "left_sector_offset": ba["sector_offset"],
                    }
                )
            for occ in range(paired, len(list_b)):
                bb = list_b[occ]
                right_only_banks.append(
                    {
                        "name": b_name,
                        "occurrence": occ,
                        "role_hypothesis": bb["role_hypothesis"],
                        "byte_length": bb["byte_length"],
                        "sha256": bb["sha256"],
                        "right_sector_offset": bb["sector_offset"],
                    }
                )

        hudson_archive_diff = {
            "left_path": arch_a["path"],
            "right_path": arch_b["path"],
            "left_bank_count": len(banks_a),
            "right_bank_count": len(banks_b),
            "identical_bank_count": len(identical_banks),
            "modified_bank_count": len(modified_banks),
            "left_only_bank_count": len(left_only_banks),
            "right_only_bank_count": len(right_only_banks),
            "identical_banks": identical_banks,
            "modified_banks": modified_banks,
            "left_only_banks": left_only_banks,
            "right_only_banks": right_only_banks,
        }

    return {
        "schema": DISC_DIFF_SCHEMA,
        "tool_version": TOOL_VERSION,
        "separation_policy": (
            "USA and Japan profiles are compared for provenance and regional delta analysis only; "
            "neither profile may substitute for or overwrite the other."
        ),
        "left_release": {
            "label": label_a,
            "cue_sha256": inv_a["cue"]["sha256"],
            "track01_sha256": inv_a["tracks"][0]["file_sha256"],
            "product_number": ip_a["product_number"],
            "version": ip_a["version"],
            "area_symbols": ip_a["area_symbols"],
            "game_title": ip_a["game_title"],
            "release_date_iso": ip_a["release_date_iso"],
        },
        "right_release": {
            "label": label_b,
            "cue_sha256": inv_b["cue"]["sha256"],
            "track01_sha256": inv_b["tracks"][0]["file_sha256"],
            "product_number": ip_b["product_number"],
            "version": ip_b["version"],
            "area_symbols": ip_b["area_symbols"],
            "game_title": ip_b["game_title"],
            "release_date_iso": ip_b["release_date_iso"],
        },
        "ip_bin_comparison": ip_comparison,
        "iso9660_summary": {
            "left_file_count": len(files_a),
            "right_file_count": len(files_b),
            "identical_path_and_sha256_count": len(identical_files),
            "identical_bytes_total": sum(item["byte_length"] for item in identical_files),
            "modified_same_path_count": len(modified_same_path),
            "only_in_left_count": len(only_in_left),
            "only_in_right_count": len(only_in_right),
        },
        "iso9660_identical_files": identical_files,
        "iso9660_modified_same_path": modified_same_path,
        "iso9660_only_in_left": only_in_left,
        "iso9660_only_in_right": only_in_right,
        "hudson_lwr_bank_archive_comparison": hudson_archive_diff,
        "track_comparison": track_diffs,
    }
