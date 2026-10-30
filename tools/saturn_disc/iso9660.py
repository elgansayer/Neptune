"""ISO-9660 volume/directory/extent decoder and 100% sector & byte-range accountant."""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any

from .classify import classify_disc_file
from .cue import CueSheet, DataTrackReader, DiscError, summarize_audio_track
from .ipbin import SYSTEM_AREA_SECTORS, read_ip_bin

ISO_STANDARD_ID = b"CD001"
LOGICAL_BLOCK_BYTES = 2048


def _both_endian_u16(buf: bytes, offset: int, label: str) -> int:
    le, be = struct.unpack_from("<H", buf, offset)[0], struct.unpack_from(">H", buf, offset + 2)[0]
    if le != be:
        raise DiscError(f"ISO-9660 {label} both-endian u16 mismatch: LE={le} vs BE={be}")
    return le


def _both_endian_u32(buf: bytes, offset: int, label: str) -> int:
    le, be = struct.unpack_from("<I", buf, offset)[0], struct.unpack_from(">I", buf, offset + 4)[0]
    if le != be:
        raise DiscError(f"ISO-9660 {label} both-endian u32 mismatch: LE={le} vs BE={be}")
    return le


def _decode_iso_str(raw: bytes) -> str:
    return raw.decode("latin-1").rstrip(" \x00")


def _decode_pvd_datetime(raw17: bytes) -> str | None:
    if len(raw17) != 17:
        return None
    digits = raw17[:16]
    if digits == b"0" * 16 or not digits.isdigit():
        return None
    s = digits.decode("ascii")
    tz_quarters = struct.unpack("b", raw17[16:17])[0]
    tz_minutes = tz_quarters * 15
    sign = "+" if tz_minutes >= 0 else "-"
    abs_min = abs(tz_minutes)
    return (
        f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}.{s[14:16]}"
        f"{sign}{abs_min // 60:02d}:{abs_min % 60:02d}"
    )


def _decode_dir_datetime(raw7: bytes) -> str | None:
    if len(raw7) != 7 or raw7[:6] == b"\x00" * 6:
        return None
    year_off, month, day, hour, minute, second = raw7[:6]
    if month == 0 or day == 0:
        return None
    tz_quarters = struct.unpack("b", raw7[6:7])[0]
    tz_minutes = tz_quarters * 15
    sign = "+" if tz_minutes >= 0 else "-"
    abs_min = abs(tz_minutes)
    return (
        f"{1900 + year_off:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
        f"{sign}{abs_min // 60:02d}:{abs_min % 60:02d}"
    )


def _parse_directory_record(rec: bytes) -> dict[str, Any]:
    if len(rec) < 34:
        raise DiscError(f"ISO-9660 directory record shorter than 34 bytes ({len(rec)})")
    rec_len = rec[0]
    if rec_len != len(rec):
        raise DiscError(f"Directory record length mismatch ({rec_len} != {len(rec)})")
    xar_blocks = rec[1]
    extent_lba = _both_endian_u32(rec, 2, "directory_record.extent_lba")
    data_length = _both_endian_u32(rec, 10, "directory_record.data_length")
    recorded_at = _decode_dir_datetime(rec[18:25])
    flags = rec[25]
    file_unit_size = rec[26]
    interleave_gap = rec[27]
    vol_seq = _both_endian_u16(rec, 28, "directory_record.volume_sequence_number")
    name_len = rec[32]
    if 33 + name_len > rec_len:
        raise DiscError("Directory record file identifier exceeds record length")
    raw_name = rec[33 : 33 + name_len]
    sys_offset = 33 + name_len + (1 if name_len % 2 == 0 else 0)
    system_use = rec[sys_offset:rec_len]
    xa_info: dict[str, Any] | None = None
    if len(system_use) >= 14 and system_use[6:8] == b"XA":
        xa_attr = struct.unpack_from(">H", system_use, 4)[0]
        xa_filenum = system_use[8]
        xa_info = {
            "attributes_u16_hex": f"0x{xa_attr:04x}",
            "file_number": xa_filenum,
            "mode2_form2": bool(xa_attr & 0x1000),
            "interleaved": bool(xa_attr & 0x2000),
            "cdda": bool(xa_attr & 0x4000),
        }

    return {
        "xar_blocks": xar_blocks,
        "extent_lba": extent_lba,
        "data_length": data_length,
        "recorded_at": recorded_at,
        "flags": flags,
        "is_hidden": bool(flags & 0x01),
        "is_directory": bool(flags & 0x02),
        "is_associated": bool(flags & 0x04),
        "is_multi_extent": bool(flags & 0x80),
        "file_unit_size": file_unit_size,
        "interleave_gap_size": interleave_gap,
        "volume_sequence_number": vol_seq,
        "raw_name": raw_name,
        "system_use_len": len(system_use),
        "xa": xa_info,
    }


def _clean_iso_filename(raw_name: bytes) -> tuple[str, str]:
    raw_text = raw_name.decode("latin-1")
    clean = raw_text[:-2] if raw_text.upper().endswith(";1") else raw_text
    if clean.endswith("."):
        clean = clean[:-1]
    if not clean or "/" in clean or "\\" in clean or clean in {".", ".."}:
        raise DiscError(f"Unsafe ISO-9660 filename: {raw_text!r}")
    return raw_text, clean


def parse_primary_volume_descriptor(vd: bytes, lba: int) -> dict[str, Any]:
    if len(vd) != LOGICAL_BLOCK_BYTES or vd[0] != 1 or vd[1:6] != ISO_STANDARD_ID:
        raise DiscError(f"Invalid Primary Volume Descriptor at LBA {lba}")
    logical_block_size = _both_endian_u16(vd, 128, "PVD.logical_block_size")
    if logical_block_size != LOGICAL_BLOCK_BYTES:
        raise DiscError(f"Unsupported ISO-9660 logical_block_size {logical_block_size} (require 2048)")

    volume_space_size = _both_endian_u32(vd, 80, "PVD.volume_space_size")
    path_table_size = _both_endian_u32(vd, 132, "PVD.path_table_size")
    type_l_pt = struct.unpack_from("<I", vd, 140)[0]
    opt_type_l_pt = struct.unpack_from("<I", vd, 144)[0]
    type_m_pt = struct.unpack_from(">I", vd, 148)[0]
    opt_type_m_pt = struct.unpack_from(">I", vd, 152)[0]
    root_rec = _parse_directory_record(vd[156 : 156 + vd[156]])
    if not root_rec["is_directory"]:
        raise DiscError("PVD root directory record lacks directory flag")

    return {
        "pvd_lba": lba,
        "version": vd[6],
        "system_identifier": _decode_iso_str(vd[8:40]),
        "volume_identifier": _decode_iso_str(vd[40:72]),
        "volume_space_size_blocks": volume_space_size,
        "volume_set_size": _both_endian_u16(vd, 120, "PVD.volume_set_size"),
        "volume_sequence_number": _both_endian_u16(vd, 124, "PVD.volume_sequence_number"),
        "logical_block_size": logical_block_size,
        "path_table_size_bytes": path_table_size,
        "type_l_path_table_lba": type_l_pt,
        "opt_type_l_path_table_lba": opt_type_l_pt,
        "type_m_path_table_lba": type_m_pt,
        "opt_type_m_path_table_lba": opt_type_m_pt,
        "root_extent_lba": root_rec["extent_lba"],
        "root_data_length": root_rec["data_length"],
        "volume_set_identifier": _decode_iso_str(vd[190:318]),
        "publisher_identifier": _decode_iso_str(vd[318:446]),
        "data_preparer_identifier": _decode_iso_str(vd[446:574]),
        "application_identifier": _decode_iso_str(vd[574:702]),
        "copyright_file_identifier": _decode_iso_str(vd[702:739]),
        "abstract_file_identifier": _decode_iso_str(vd[739:776]),
        "bibliographic_file_identifier": _decode_iso_str(vd[776:813]),
        "created_at": _decode_pvd_datetime(vd[813:830]),
        "modified_at": _decode_pvd_datetime(vd[830:847]),
        "expires_at": _decode_pvd_datetime(vd[847:864]),
        "effective_at": _decode_pvd_datetime(vd[864:881]),
        "file_structure_version": vd[881],
    }


def _walk_directory_tree(
    reader: DataTrackReader,
    root_lba: int,
    root_length: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (directories, files) walked deterministically from the ISO-9660 root directory."""
    directories: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    visited_dir_extents: set[tuple[int, int]] = set()

    def walk(dir_path: str, extent_lba: int, data_length: int, order_prefix: tuple[int, ...]) -> None:
        if data_length <= 0 or data_length % LOGICAL_BLOCK_BYTES != 0:
            raise DiscError(
                f"Directory {dir_path or '/'} has invalid byte length {data_length} at LBA {extent_lba}"
            )
        key = (extent_lba, data_length)
        if key in visited_dir_extents:
            raise DiscError(f"Cyclic ISO-9660 directory extent detected at LBA {extent_lba}")
        visited_dir_extents.add(key)

        sector_count = data_length // LOGICAL_BLOCK_BYTES
        raw_dir = reader.read_logical_bytes(extent_lba, data_length, verify_edc=False)
        records: list[dict[str, Any]] = []
        for sec_idx in range(sector_count):
            sec = raw_dir[sec_idx * LOGICAL_BLOCK_BYTES : (sec_idx + 1) * LOGICAL_BLOCK_BYTES]
            pos = 0
            while pos < LOGICAL_BLOCK_BYTES:
                rec_len = sec[pos]
                if rec_len == 0:
                    # Remainder of directory sector must be padded; advance to next sector
                    break
                if pos + rec_len > LOGICAL_BLOCK_BYTES:
                    raise DiscError(
                        f"Directory {dir_path or '/'} record straddles sector boundary at LBA {extent_lba + sec_idx}"
                    )
                records.append(_parse_directory_record(sec[pos : pos + rec_len]))
                pos += rec_len

        directories.append(
            {
                "path": dir_path or "/",
                "extent_lba": extent_lba,
                "sector_count": sector_count,
                "byte_length": data_length,
                "entry_count": max(0, len(records) - 2),
            }
        )

        # Group multi-extent file sections if present
        idx = 0
        entry_ordinal = 0
        while idx < len(records):
            rec = records[idx]
            if rec["raw_name"] in (b"\x00", b"\x01"):
                idx += 1
                continue
            raw_id, clean_name = _clean_iso_filename(rec["raw_name"])
            rel_path = f"{dir_path}/{clean_name}" if dir_path else clean_name
            entry_ordinal += 1

            if rec["is_directory"]:
                if rec["is_multi_extent"]:
                    raise DiscError(f"Multi-extent directory unsupported: {rel_path}")
                walk(rel_path, rec["extent_lba"], rec["data_length"], (*order_prefix, entry_ordinal))
                idx += 1
                continue

            extents = [rec]
            while extents[-1]["is_multi_extent"]:
                idx += 1
                if idx >= len(records):
                    raise DiscError(f"Unterminated multi-extent file {rel_path}")
                nxt = records[idx]
                if nxt["raw_name"] != rec["raw_name"] or nxt["is_directory"]:
                    raise DiscError(f"Mismatched multi-extent continuation for {rel_path}")
                extents.append(nxt)

            if any(e["xar_blocks"] != 0 or e["file_unit_size"] != 0 or e["interleave_gap_size"] != 0 for e in extents):
                raise DiscError(f"XAR or interleaved ISO-9660 file unsupported without explicit XA layout: {rel_path}")

            files.append(
                {
                    "path": rel_path,
                    "raw_identifier": raw_id,
                    "directory_order": list((*order_prefix, entry_ordinal)),
                    "recorded_at": extents[0]["recorded_at"],
                    "is_hidden": extents[0]["is_hidden"],
                    "is_associated": extents[0]["is_associated"],
                    "xa": extents[0]["xa"],
                    "extents": [
                        {
                            "extent_lba": e["extent_lba"],
                            "byte_length": e["data_length"],
                            "sector_count": math.ceil(e["data_length"] / LOGICAL_BLOCK_BYTES)
                            if e["data_length"] > 0
                            else 0,
                        }
                        for e in extents
                    ],
                }
            )
            idx += 1

    walk("", root_lba, root_length, ())
    return directories, files


def inspect_disc(
    cue: CueSheet,
    *,
    asset_hashes: dict[str, list[str]] | None = None,
    asset_prefix_2mib_hashes: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Decode Track 01 IP.BIN + ISO-9660 + Track 02..N CD-DA and verify 100% byte/sector coverage."""
    track1 = cue.tracks[0]
    with DataTrackReader(track1) as reader:
        total_blocks = reader.logical_blocks

        # Verify raw sector sync + MSF + Mode 1 EDC across EVERY logical block on Track 01!
        sector_zero_bitmap = bytearray(total_blocks)
        for lba in range(total_blocks):
            user_sector = reader.read_sector(lba, verify_edc=True)
            if not any(user_sector):
                sector_zero_bitmap[lba] = 1

        ip_bin = read_ip_bin(reader)

        # Read Volume Descriptor Set starting at LBA 16
        vd_lba = SYSTEM_AREA_SECTORS
        volume_descriptors: list[dict[str, Any]] = []
        pvd: dict[str, Any] | None = None
        while True:
            if vd_lba >= total_blocks:
                raise DiscError("Unterminated ISO-9660 Volume Descriptor Set")
            vd_sector = reader.read_sector(vd_lba, verify_edc=False)
            vd_type = vd_sector[0]
            if vd_sector[1:6] != ISO_STANDARD_ID:
                raise DiscError(f"Invalid Volume Descriptor standard ID at LBA {vd_lba}: {vd_sector[1:6]!r}")
            volume_descriptors.append({"lba": vd_lba, "type": vd_type, "version": vd_sector[6]})
            if vd_type == 1 and pvd is None:
                pvd = parse_primary_volume_descriptor(vd_sector, vd_lba)
            if vd_type == 255:
                break
            vd_lba += 1

        if pvd is None:
            raise DiscError("ISO-9660 Volume Descriptor Set contains no Primary Volume Descriptor")

        directories, raw_files = _walk_directory_tree(
            reader,
            pvd["root_extent_lba"],
            pvd["root_data_length"],
        )

        # Identify Master SH-2 first-read boot binary:
        # Sega Saturn BIOS loads the lowest-LBA root file (matching IP.BIN first_read_size_bytes).
        root_files = [f for f in raw_files if "/" not in f["path"] and f["extents"]]
        lowest_root_file = min(root_files, key=lambda f: f["extents"][0]["extent_lba"]) if root_files else None

        enriched_files: list[dict[str, Any]] = []
        by_sha256: dict[str, list[str]] = {}

        for f_rec in raw_files:
            chunks: list[bytes] = []
            total_file_bytes = 0
            total_extent_sectors = 0
            slack_bytes_total = 0
            nonzero_slack_bytes = 0

            for ext in f_rec["extents"]:
                b_len = ext["byte_length"]
                s_cnt = ext["sector_count"]
                total_file_bytes += b_len
                total_extent_sectors += s_cnt
                if b_len > 0:
                    raw_ext = reader.read_logical_bytes(ext["extent_lba"], s_cnt * LOGICAL_BLOCK_BYTES, verify_edc=False)
                    chunks.append(raw_ext[:b_len])
                    slack = raw_ext[b_len:]
                    slack_bytes_total += len(slack)
                    nonzero_slack_bytes += sum(1 for b in slack if b != 0)

            payload = b"".join(chunks)
            file_sha256 = hashlib.sha256(payload).hexdigest()
            prefix_2mib_sha256 = (
                hashlib.sha256(payload[: 2 * 1024 * 1024]).hexdigest()
                if len(payload) >= 2 * 1024 * 1024
                else None
            )
            by_sha256.setdefault(file_sha256, []).append(f_rec["path"])

            is_boot = (
                lowest_root_file is not None
                and f_rec["path"] == lowest_root_file["path"]
                and ip_bin["first_read_size_bytes"] in (0, total_file_bytes)
            )
            classification = classify_disc_file(f_rec["path"], payload, is_boot_first_read=is_boot)

            matched_assets = sorted(asset_hashes.get(file_sha256, [])) if asset_hashes else []
            matched_truncated = (
                sorted(asset_prefix_2mib_hashes.get(prefix_2mib_sha256, []))
                if (asset_prefix_2mib_hashes and prefix_2mib_sha256)
                else []
            )

            enriched_files.append(
                {
                    "path": f_rec["path"],
                    "raw_identifier": f_rec["raw_identifier"],
                    "directory_order": f_rec["directory_order"],
                    "recorded_at": f_rec["recorded_at"],
                    "is_hidden": f_rec["is_hidden"],
                    "is_associated": f_rec["is_associated"],
                    "xa": f_rec["xa"],
                    "byte_length": total_file_bytes,
                    "sector_count": total_extent_sectors,
                    "extent_lba": f_rec["extents"][0]["extent_lba"] if f_rec["extents"] else 0,
                    "extents": f_rec["extents"],
                    "slack_bytes": slack_bytes_total,
                    "nonzero_slack_bytes": nonzero_slack_bytes,
                    "sha256": file_sha256,
                    "is_boot_first_read": is_boot,
                    "classification": classification,
                    "matched_asset_repo_paths": matched_assets,
                    "matched_asset_repo_truncated_2mib_paths": matched_truncated,
                }
            )

        # Build 100% Track 01 sector ownership map (0 .. total_blocks - 1)
        sector_owner_kind: list[str | None] = [None] * total_blocks
        sector_owner_ref: list[list[str]] = [[] for _ in range(total_blocks)]
        sector_accounting_class: list[str | None] = [None] * total_blocks

        def claim_range(start: int, count: int, kind: str, ac_class: str, ref: str, *, allow_shared_file: bool = False) -> None:
            if count == 0:
                return
            if start < 0 or start + count > total_blocks:
                raise DiscError(f"Extent {ref} ({start}..{start + count}) exceeds Track 01 blocks ({total_blocks})")
            for lba in range(start, start + count):
                existing = sector_owner_kind[lba]
                if existing is not None:
                    if allow_shared_file and existing == "file_extent":
                        sector_owner_ref[lba].append(ref)
                        continue
                    raise DiscError(
                        f"Overlapping Track 01 sector {lba}: already owned by {existing} ({sector_owner_ref[lba]}), "
                        f"conflicting with {kind} ({ref})"
                    )
                sector_owner_kind[lba] = kind
                sector_accounting_class[lba] = ac_class
                sector_owner_ref[lba].append(ref)

        # 1. System Area (IP.BIN)
        claim_range(0, SYSTEM_AREA_SECTORS, "system_area_ip_bin", "executable", "IP.BIN")

        # 2. Volume Descriptor Set
        claim_range(
            volume_descriptors[0]["lba"],
            len(volume_descriptors),
            "iso9660_volume_descriptors",
            "decoded",
            "ISO9660:VD_SET",
        )

        # 3. Path Tables
        pt_sectors = math.ceil(pvd["path_table_size_bytes"] / LOGICAL_BLOCK_BYTES)
        for pt_name, pt_lba in (
            ("ISO9660:PATH_TABLE_L", pvd["type_l_path_table_lba"]),
            ("ISO9660:OPT_PATH_TABLE_L", pvd["opt_type_l_path_table_lba"]),
            ("ISO9660:PATH_TABLE_M", pvd["type_m_path_table_lba"]),
            ("ISO9660:OPT_PATH_TABLE_M", pvd["opt_type_m_path_table_lba"]),
        ):
            if pt_lba != 0 and pt_sectors > 0:
                claim_range(pt_lba, pt_sectors, "iso9660_path_table", "decoded", pt_name)

        # 4. Directory Extents
        for d_rec in directories:
            claim_range(
                d_rec["extent_lba"],
                d_rec["sector_count"],
                "iso9660_directory_extent",
                "decoded",
                f"DIR:{d_rec['path']}",
            )

        # 5. File Extents
        for f_rec in enriched_files:
            ac_class = f_rec["classification"]["accounting_class"]
            for ext in f_rec["extents"]:
                claim_range(
                    ext["extent_lba"],
                    ext["sector_count"],
                    "file_extent",
                    ac_class,
                    f_rec["path"],
                    allow_shared_file=True,
                )

        # 6. Scan all remaining unreferenced sectors on Track 01
        for lba in range(total_blocks):
            if sector_owner_kind[lba] is None:
                if sector_zero_bitmap[lba]:
                    sector_owner_kind[lba] = "unreferenced_zero_padding"
                    sector_accounting_class[lba] = "padding"
                    sector_owner_ref[lba].append("ZERO_PAD")
                else:
                    sector_owner_kind[lba] = "unreferenced_nonzero_sectors"
                    sector_accounting_class[lba] = "unknown"
                    sector_owner_ref[lba].append("UNREFERENCED_NONZERO")

        # Coalesce contiguous Track 01 intervals for compact, exact 100% accounting
        intervals: list[dict[str, Any]] = []
        cur_start = 0
        for lba in range(1, total_blocks + 1):
            same = (
                lba < total_blocks
                and sector_owner_kind[lba] == sector_owner_kind[cur_start]
                and sector_accounting_class[lba] == sector_accounting_class[cur_start]
                and sector_owner_ref[lba] == sector_owner_ref[cur_start]
            )
            if not same:
                s_cnt = lba - cur_start
                interval_item: dict[str, Any] = {
                    "lba_start": cur_start,
                    "lba_end_exclusive": lba,
                    "sector_count": s_cnt,
                    "logical_bytes": s_cnt * LOGICAL_BLOCK_BYTES,
                    "raw_track_bytes": s_cnt * track1.sector_size,
                    "region_kind": sector_owner_kind[cur_start],
                    "accounting_class": sector_accounting_class[cur_start],
                    "owners": list(sector_owner_ref[cur_start]),
                }
                if sector_owner_kind[cur_start] == "unreferenced_nonzero_sectors":
                    raw_unclaimed = reader.read_logical_bytes(cur_start, s_cnt * LOGICAL_BLOCK_BYTES, verify_edc=False)
                    interval_item["sha256"] = hashlib.sha256(raw_unclaimed).hexdigest()
                    interval_item["magic_16b_hex"] = raw_unclaimed[:16].hex()
                intervals.append(interval_item)
                cur_start = lba

        # Verify mathematical 100% completeness on Track 01
        accounted_sectors = sum(item["sector_count"] for item in intervals)
        if accounted_sectors != total_blocks:
            raise DiscError(f"Sector accounting bug: {accounted_sectors} != {total_blocks}")

        edc_summary = {
            "mode": track1.mode,
            "logical_blocks": total_blocks,
            "edc_checked_sectors": len(reader.edc_verified_lbas),
            "edc_mismatches": len(reader.edc_mismatch_lbas),
            "mode2_form2_sectors": len(set(reader.mode2_form2_lbas)),
        }

    # Summarize Tracks 01..N including CD-DA audio tracks
    track_summaries: list[dict[str, Any]] = []
    for trk in cue.tracks:
        t_info: dict[str, Any] = {
            "track_number": trk.number,
            "mode": trk.mode,
            "sector_size": trk.sector_size,
            "file_relpath": trk.file_relpath,
            "file_bytes": trk.file_bytes,
            "file_sha256": trk.file_sha256,
            "track_sectors": trk.track_sectors,
            "pregap_sectors_in_file": trk.pregap_sectors_in_file,
            "disc_lba_index01": trk.disc_lba_index01,
            "indices": [
                {"index": idx.number, "msf": idx.msf, "file_offset_frames": idx.file_offset_frames}
                for idx in trk.indices
            ],
        }
        if trk.mode == "AUDIO":
            t_info["accounting_class"] = "decoded"
            t_info["cdda_summary"] = summarize_audio_track(trk)
        else:
            t_info["accounting_class"] = "partitioned_in_track01_intervals"
        track_summaries.append(t_info)

    # Aggregate Track 01 sector counts by accounting class and file counts by format
    sector_totals_by_class: dict[str, int] = {}
    for item in intervals:
        cls = item["accounting_class"]
        sector_totals_by_class[cls] = sector_totals_by_class.get(cls, 0) + item["sector_count"]

    file_totals_by_class: dict[str, dict[str, int]] = {}
    file_totals_by_format: dict[str, dict[str, int]] = {}
    for f_rec in enriched_files:
        cls = f_rec["classification"]["accounting_class"]
        fmt = f_rec["classification"]["detected_format"]
        c_bucket = file_totals_by_class.setdefault(cls, {"files": 0, "bytes": 0})
        c_bucket["files"] += 1
        c_bucket["bytes"] += f_rec["byte_length"]
        f_bucket = file_totals_by_format.setdefault(fmt, {"files": 0, "bytes": 0})
        f_bucket["files"] += 1
        f_bucket["bytes"] += f_rec["byte_length"]

    duplicate_disc_files = sorted(sorted(paths) for paths in by_sha256.values() if len(paths) > 1)
    shared_extent_intervals = [
        {
            "lba_start": item["lba_start"],
            "sector_count": item["sector_count"],
            "owners": item["owners"],
        }
        for item in intervals
        if item["region_kind"] == "file_extent" and len(item["owners"]) > 1
    ]

    total_disc_track_bytes = sum(t.file_bytes for t in cue.tracks)

    return {
        "cue": {
            "path": cue.cue_relpath,
            "bytes": cue.cue_bytes,
            "sha256": cue.cue_sha256,
            "catalog": cue.catalog,
            "track_count": len(cue.tracks),
            "total_track_bytes": total_disc_track_bytes,
        },
        "ip_bin": ip_bin,
        "track01_edc": edc_summary,
        "iso9660": {
            "volume_descriptors": volume_descriptors,
            "pvd": pvd,
            "directory_count": len(directories),
            "file_count": len(enriched_files),
            "directories": directories,
            "files": sorted(enriched_files, key=lambda item: item["path"]),
            "duplicate_file_groups": duplicate_disc_files,
            "shared_extent_intervals": shared_extent_intervals,
        },
        "accounting": {
            "track01_total_logical_blocks": total_blocks,
            "track01_accounted_logical_blocks": accounted_sectors,
            "track01_unaccounted_logical_blocks": 0,
            "track01_logical_bytes": total_blocks * LOGICAL_BLOCK_BYTES,
            "track01_raw_bytes": track1.file_bytes,
            "track01_sectors_by_class": dict(sorted(sector_totals_by_class.items())),
            "iso_files_by_class": dict(sorted(file_totals_by_class.items())),
            "iso_files_by_format": dict(sorted(file_totals_by_format.items())),
            "cdda_track_count": sum(1 for t in cue.tracks if t.mode == "AUDIO"),
            "cdda_total_bytes": sum(t.file_bytes for t in cue.tracks if t.mode == "AUDIO"),
            "disc_total_track_bytes": total_disc_track_bytes,
            "track01_intervals": intervals,
        },
        "tracks": track_summaries,
    }
