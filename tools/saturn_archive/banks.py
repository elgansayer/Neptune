"""Kernel bank directory extraction, PROGRAM.BIN accounting, and per-bank slot decoding."""

from __future__ import annotations

import hashlib
import struct
from typing import Any

from . import BANK_DECODE_SCHEMA, KERNEL_BANK_DIRECTORY_SCHEMA, TOOL_VERSION, ArchiveError
from .codec import (
    decode_slot0_entry,
    decode_slot1_palette,
    decode_slot2_tilemap,
    decode_slot7_grid,
    decode_slot8_sprites,
)

SECTOR_BYTES = 2048
WORKRAM_L_START = 0x00200000
WORKRAM_L_END = 0x00300000


def parse_header_name(header_52b: bytes) -> str:
    """Decode the 8-byte 0xFF/0x00-padded ASCII tag at +0x2C..+0x33 of a 0x34 bank header."""
    raw = header_52b[0x2C:0x34].rstrip(b"\xff\x00 ")
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ArchiveError(f"Non-ASCII bank header tag: {header_52b[0x2C:0x34].hex()}") from exc


def scan_static_headers(program_bin: bytes) -> list[dict[str, Any]]:
    """Scan sector-aligned 0x34 bank headers across PROGRAM.BIN (matching saturn_disc #473 rules)."""
    hits: list[dict[str, Any]] = []
    total_sectors = (len(program_bin) + SECTOR_BYTES - 1) // SECTOR_BYTES
    for sec in range(total_sectors):
        off = sec * SECTOR_BYTES
        if off + 64 > len(program_bin):
            break
        hdr = program_bin[off : off + 64]
        ptrs = struct.unpack_from(">11I", hdr, 0)
        if not all(v == 0 or (WORKRAM_L_START <= v <= WORKRAM_L_END) for v in ptrs):
            continue
        nonzero_slots = [v for v in ptrs if v != 0]
        if not nonzero_slots:
            continue
        if any(nonzero_slots[i] > nonzero_slots[i + 1] for i in range(len(nonzero_slots) - 1)):
            continue
        if (nonzero_slots[0] & 0xFFF) != 0x034:
            continue
        tag_bytes = hdr[0x2C:0x34]
        ff_pos = tag_bytes.find(b"\xff")
        core = tag_bytes if ff_pos == -1 else tag_bytes[:ff_pos]
        pad = b"" if ff_pos == -1 else tag_bytes[ff_pos:]
        if not (2 <= len(core) <= 8 and all(b == 0xFF for b in pad)):
            continue
        if not all(32 <= b <= 126 and (chr(b).isalnum() or chr(b) in "_-") for b in core):
            continue
        load_base = nonzero_slots[0] - 0x34
        hits.append(
            {
                "header_index": len(hits),
                "sector_offset": sec,
                "byte_offset": off,
                "inferred_load_base": load_base,
                "inferred_load_base_hex": f"0x{load_base:08x}",
                "name": core.decode("ascii"),
            }
        )
    for i, item in enumerate(hits):
        next_off = hits[i + 1]["byte_offset"] if i + 1 < len(hits) else len(program_bin)
        span = next_off - item["byte_offset"]
        item["header_to_header_bytes"] = span
        item["inferred_end_hex"] = f"0x{item['inferred_load_base'] + span:08x}"
    return hits


def discover_kernel_bank_directory(krnl_bytes: bytes) -> dict[str, Any]:
    """Locate the parallel (u16 sec_off[N], u16 sec_cnt[N], u32 load_dest[N]) tables via literal pool."""
    if len(krnl_bytes) < 0x1000 or len(krnl_bytes) % 2 != 0:
        raise ArchiveError(f"Invalid 0KRNL.BIN size: {len(krnl_bytes)} bytes")

    words = [struct.unpack_from(">I", krnl_bytes, i)[0] for i in range(0, len(krnl_bytes) - 3, 4)]
    candidates: dict[tuple[int, int, int, int], dict[str, Any]] = {}

    for i in range(len(words) - 8):
        win = [w for w in words[i : i + 8] if 0x06000000 <= w < 0x06100000]
        if len(win) < 3:
            continue
        unique_ptrs = sorted(set(win))
        for a in unique_ptrs:
            for b in unique_ptrs:
                delta = b - a
                if not (64 <= delta <= 512 and delta % 2 == 0):
                    continue
                c = b + delta
                if c not in unique_ptrs:
                    continue
                n_entries = delta // 2
                # Try 4 KiB-aligned kernel load bases in High-WRAM (0x06000000..0x06020000)
                for krnl_base in range(0x06002000, 0x06020000, 0x1000):
                    off_a = a - krnl_base
                    off_b = b - krnl_base
                    off_c = c - krnl_base
                    if off_a < 0 or off_c + n_entries * 4 > len(krnl_bytes):
                        continue
                    sec_offs = struct.unpack_from(f">{n_entries}H", krnl_bytes, off_a)
                    sec_cnts = struct.unpack_from(f">{n_entries}H", krnl_bytes, off_b)
                    dests = struct.unpack_from(f">{n_entries}I", krnl_bytes, off_c)
                    if sec_offs[0] != 0:
                        continue
                    if any(cnt == 0 or cnt > 512 for cnt in sec_cnts):
                        continue
                    if any(
                        not (WORKRAM_L_START <= dst and dst + cnt * SECTOR_BYTES <= WORKRAM_L_END)
                        for dst, cnt in zip(dests, sec_cnts)
                    ):
                        continue
                    # Monotonic or mostly non-decreasing sector offsets starting at 0, 16
                    if sec_offs[1] != 16:
                        continue
                    key = (krnl_base, a, b, c)
                    if key not in candidates:
                        candidates[key] = {
                            "krnl_load_base": krnl_base,
                            "krnl_load_base_hex": f"0x{krnl_base:08x}",
                            "literal_pool_addr_hex": f"0x{krnl_base + i * 4:08x}",
                            "sector_offset_table_addr_hex": f"0x{a:08x}",
                            "sector_count_table_addr_hex": f"0x{b:08x}",
                            "load_dest_table_addr_hex": f"0x{c:08x}",
                            "entry_count": n_entries,
                            "entries": [
                                {
                                    "bank_id": idx,
                                    "sector_offset": int(sec_offs[idx]),
                                    "sector_count": int(sec_cnts[idx]),
                                    "byte_offset": int(sec_offs[idx]) * SECTOR_BYTES,
                                    "byte_length": int(sec_cnts[idx]) * SECTOR_BYTES,
                                    "load_dest": int(dests[idx]),
                                    "load_dest_hex": f"0x{dests[idx]:08x}",
                                    "load_end_hex": f"0x{dests[idx] + sec_cnts[idx] * SECTOR_BYTES:08x}",
                                }
                                for idx in range(n_entries)
                            ],
                        }

    if len(candidates) != 1:
        raise ArchiveError(
            f"Expected exactly 1 valid kernel bank directory in 0KRNL.BIN, found {len(candidates)}"
        )
    return next(iter(candidates.values()))


def _classify_kernel_role(load_dest: int, header_name: str | None, entry_format: str) -> str:
    if load_dest == 0x00200000:
        return "resident_base_bank"
    if load_dest == 0x002FB000 and entry_format == "hudson_0x34_bank":
        return "voice_scratchpad_overlay"
    if load_dest == 0x002FB000:
        return "voice_scratchpad_headerless_slot"
    if load_dest in (0x002DA000, 0x002EE000):
        return "upper_wram_sub_overlay"
    if load_dest == 0x00254000 and header_name and header_name.startswith("s_"):
        return "transient_scsp_sound_staging"
    if load_dest == 0x00254000:
        return "world_or_mode_overlay"
    return "workram_l_overlay"


def _inspect_headerless_entry(bank_slice: bytes, load_dest: int) -> tuple[str, int | None]:
    """Check if a headerless kernel entry begins with a monotonic big-endian pointer table at load_dest."""
    if len(bank_slice) >= 8:
        first_ptr = struct.unpack_from(">I", bank_slice, 0)[0]
        rel0 = first_ptr - load_dest
        if 8 <= rel0 <= 1024 and rel0 % 4 == 0 and rel0 <= len(bank_slice):
            count = rel0 // 4
            ptrs = struct.unpack_from(f">{count}I", bank_slice, 0)
            end_addr = load_dest + len(bank_slice)
            if all(load_dest + rel0 <= p < end_addr for p in ptrs) and all(
                ptrs[i] <= ptrs[i + 1] for i in range(count - 1)
            ):
                return "headerless_pointer_table", count
    return "headerless_raw_sectors", None


def audit_program_bin_directory(
    krnl_bytes: bytes,
    program_bin_bytes: bytes,
    *,
    release_id: str,
    krnl_iso_path: str,
    program_iso_path: str,
) -> dict[str, Any]:
    """Cross-check 0KRNL.BIN's live bank directory against PROGRAM.BIN sectors and static headers."""
    directory = discover_kernel_bank_directory(krnl_bytes)
    static_headers = scan_static_headers(program_bin_bytes)
    headers_by_sector = {h["sector_offset"]: h for h in static_headers}

    total_sectors = len(program_bin_bytes) // SECTOR_BYTES
    trailing_subsector_bytes = len(program_bin_bytes) % SECTOR_BYTES
    sector_ref_by: list[list[int]] = [[] for _ in range(total_sectors)]

    enriched_entries: list[dict[str, Any]] = []
    active_header_indices: set[int] = set()
    embedded_residual_header_indices: set[int] = set()

    for entry in directory["entries"]:
        bid = entry["bank_id"]
        s_off = entry["sector_offset"]
        s_cnt = entry["sector_count"]
        b_off = entry["byte_offset"]
        b_len = entry["byte_length"]
        if b_off + b_len > len(program_bin_bytes):
            raise ArchiveError(
                f"Kernel bank_id={bid} read [0x{b_off:x}..0x{b_off+b_len:x}] exceeds PROGRAM.BIN ({len(program_bin_bytes)} B)"
            )
        for s in range(s_off, s_off + s_cnt):
            sector_ref_by[s].append(bid)

        bank_slice = program_bin_bytes[b_off : b_off + b_len]
        start_hdr = headers_by_sector.get(s_off)
        headerless_ptr_count: int | None = None
        if start_hdr is not None:
            active_header_indices.add(start_hdr["header_index"])
            if start_hdr["inferred_load_base"] != entry["load_dest"]:
                raise ArchiveError(
                    f"Kernel bank_id={bid} load_dest 0x{entry['load_dest']:08x} != "
                    f"header pointer base {start_hdr['inferred_load_base_hex']}"
                )
            entry_format = "hudson_0x34_bank"
            hdr_idx: int | None = start_hdr["header_index"]
            hdr_name: str | None = start_hdr["name"]
        else:
            entry_format, headerless_ptr_count = _inspect_headerless_entry(bank_slice, entry["load_dest"])
            hdr_idx = None
            hdr_name = None

        mid_slot_headers = [
            {
                "header_index": h["header_index"],
                "sector_offset": h["sector_offset"],
                "byte_offset": h["byte_offset"],
                "name": h["name"],
                "inferred_load_base_hex": h["inferred_load_base_hex"],
            }
            for h in static_headers
            if s_off < h["sector_offset"] < s_off + s_cnt
        ]
        for mh in mid_slot_headers:
            embedded_residual_header_indices.add(mh["header_index"])

        enriched_entries.append(
            {
                **entry,
                "entry_format": entry_format,
                "header_index": hdr_idx,
                "header_name": hdr_name,
                "headerless_pointer_count": headerless_ptr_count,
                "role": _classify_kernel_role(entry["load_dest"], hdr_name, entry_format),
                "sha256": hashlib.sha256(bank_slice).hexdigest(),
                "fits_workram_l": (
                    WORKRAM_L_START <= entry["load_dest"]
                    and entry["load_dest"] + b_len <= WORKRAM_L_END
                ),
                "embedded_residual_headers": mid_slot_headers,
            }
        )

    max_referenced_end_sector = max(e["sector_offset"] + e["sector_count"] for e in enriched_entries)
    referenced_sector_count = sum(1 for s in range(total_sectors) if sector_ref_by[s])
    inter_entry_gap_sectors = [
        s for s in range(max_referenced_end_sector) if not sector_ref_by[s]
    ]
    unreferenced_tail_sector_count = total_sectors - max_referenced_end_sector
    unreferenced_tail_bytes = len(program_bin_bytes) - (max_referenced_end_sector * SECTOR_BYTES)

    embedded_only_indices = embedded_residual_header_indices - active_header_indices
    unreferenced_headers: list[dict[str, Any]] = []
    for h in static_headers:
        idx = h["header_index"]
        if idx in active_header_indices or idx in embedded_only_indices:
            continue
        reason = (
            "unreferenced_build_container_tail"
            if h["sector_offset"] >= max_referenced_end_sector
            else "inter_entry_padding_residual_header"
        )
        unreferenced_headers.append(
            {
                "header_index": idx,
                "sector_offset": h["sector_offset"],
                "byte_offset": h["byte_offset"],
                "name": h["name"],
                "inferred_load_base_hex": h["inferred_load_base_hex"],
                "reason": reason,
            }
        )

    role_counts: dict[str, int] = {}
    dest_counts: dict[str, int] = {}
    for e in enriched_entries:
        role_counts[e["role"]] = role_counts.get(e["role"], 0) + 1
        dest_counts[e["load_dest_hex"]] = dest_counts.get(e["load_dest_hex"], 0) + 1

    return {
        "schema": KERNEL_BANK_DIRECTORY_SCHEMA,
        "tool_version": TOOL_VERSION,
        "release_id": release_id,
        "inputs": {
            "krnl_iso_path": krnl_iso_path,
            "krnl_bytes": len(krnl_bytes),
            "krnl_sha256": hashlib.sha256(krnl_bytes).hexdigest(),
            "program_iso_path": program_iso_path,
            "program_bytes": len(program_bin_bytes),
            "program_sha256": hashlib.sha256(program_bin_bytes).hexdigest(),
        },
        "kernel_directory": {
            "krnl_load_base_hex": directory["krnl_load_base_hex"],
            "literal_pool_addr_hex": directory["literal_pool_addr_hex"],
            "sector_offset_table_addr_hex": directory["sector_offset_table_addr_hex"],
            "sector_count_table_addr_hex": directory["sector_count_table_addr_hex"],
            "load_dest_table_addr_hex": directory["load_dest_table_addr_hex"],
            "entry_count": directory["entry_count"],
            "all_entries_fit_workram_l": all(e["fits_workram_l"] for e in enriched_entries),
            "max_workram_l_end_hex": f"0x{max(e['load_dest'] + e['byte_length'] for e in enriched_entries):08x}",
            "role_counts": dict(sorted(role_counts.items())),
            "destination_counts": dict(sorted(dest_counts.items())),
        },
        "program_bin_accounting": {
            "total_bytes": len(program_bin_bytes),
            "total_full_sectors": total_sectors,
            "trailing_subsector_bytes": trailing_subsector_bytes,
            "max_referenced_end_sector": max_referenced_end_sector,
            "max_referenced_end_byte_hex": f"0x{max_referenced_end_sector * SECTOR_BYTES:07x}",
            "referenced_sector_count": referenced_sector_count,
            "referenced_bytes": referenced_sector_count * SECTOR_BYTES,
            "inter_entry_gap_sector_count": len(inter_entry_gap_sectors),
            "inter_entry_gap_sectors": inter_entry_gap_sectors,
            "unreferenced_tail_start_sector": max_referenced_end_sector,
            "unreferenced_tail_sector_count": unreferenced_tail_sector_count,
            "unreferenced_tail_bytes": unreferenced_tail_bytes,
            "unreferenced_tail_sha256": hashlib.sha256(
                program_bin_bytes[max_referenced_end_sector * SECTOR_BYTES :]
            ).hexdigest(),
            "static_header_total": len(static_headers),
            "active_entry_start_headers": len(active_header_indices),
            "embedded_mid_slot_residual_headers": len(embedded_only_indices),
            "unreferenced_headers_count": len(unreferenced_headers),
        },
        "entries": enriched_entries,
        "unreferenced_static_headers": unreferenced_headers,
    }


def _read_slot_pointer_table(
    bank_bytes: bytes,
    table_off: int,
    load_base: int,
    stop_off: int,
) -> list[int]:
    end_addr = load_base + len(bank_bytes)
    out: list[int] = []
    min_target = stop_off
    off = table_off
    while off + 4 <= min_target:
        val = struct.unpack_from(">I", bank_bytes, off)[0]
        if val == 0:
            out.append(0)
        elif load_base + 0x34 <= val < end_addr:
            out.append(val)
            rel = val - load_base
            if rel > off and rel < min_target:
                min_target = rel
        else:
            break
        off += 4
    while out and out[-1] == 0:
        out.pop()
    return out


def parse_and_decode_bank(
    bank_bytes: bytes,
    *,
    bank_id: int | None,
    expected_load_base: int,
    source_sector_offset: int | None = None,
    include_raw_decoded: bool = False,
) -> dict[str, Any]:
    """Validate a 0x34 bank container header and unpack all supported sub-resource slots."""
    if len(bank_bytes) < 0x34:
        raise ArchiveError(f"Bank too short for 0x34 header: {len(bank_bytes)} bytes")

    slot_ptrs = list(struct.unpack_from(">11I", bank_bytes, 0))
    header_name = parse_header_name(bank_bytes[:0x34])
    end_addr = expected_load_base + len(bank_bytes)

    nonzero_slots = [p for p in slot_ptrs if p != 0]
    if not nonzero_slots or nonzero_slots[0] != expected_load_base + 0x34:
        first_val = nonzero_slots[0] if nonzero_slots else 0
        raise ArchiveError(
            f"Bank {header_name!r} first non-zero slot pointer 0x{first_val:08x} != "
            f"expected 0x{expected_load_base + 0x34:08x}"
        )

    for s_idx, ptr in enumerate(slot_ptrs):
        if ptr != 0 and not (expected_load_base + 0x34 <= ptr < end_addr):
            raise ArchiveError(
                f"Bank {header_name!r} Slot {s_idx} table pointer 0x{ptr:08x} out of bounds "
                f"[0x{expected_load_base + 0x34:08x}..0x{end_addr:08x})"
            )

    valid_table_offs = sorted(
        {ptr - expected_load_base for ptr in slot_ptrs if ptr != 0} | {len(bank_bytes)}
    )

    slot_summaries: dict[str, Any] = {}
    decoded_slot0: list[dict[str, Any]] = []
    decoded_slot1: list[dict[str, Any]] = []
    decoded_slot2: list[dict[str, Any]] = []
    decoded_slot7: list[dict[str, Any]] = []
    decoded_slot8: dict[str, Any] | None = None

    for s_idx, ptr in enumerate(slot_ptrs):
        if ptr == 0:
            slot_summaries[str(s_idx)] = {"table_ptr_hex": "0x00000000", "present": False}
            continue
        t_off = ptr - expected_load_base
        stop_off = next(x for x in valid_table_offs if x > t_off)

        if s_idx == 8:
            s8 = decode_slot8_sprites(bank_bytes, expected_load_base, ptr, stop_off)
            if not include_raw_decoded:
                for blk in s8["blocks"]:
                    blk.pop("_raw_decoded", None)
            decoded_slot8 = s8
            slot_summaries["8"] = {
                "table_ptr_hex": f"0x{ptr:08x}",
                "present": True,
                "status": "decoded_vdp1_sprite_blocks",
                "descriptor_count": s8["descriptor_count"],
                "unique_pixel_block_count": s8["unique_pixel_block_count"],
                "compressed_block_count": s8["compressed_block_count"],
                "raw_fmt5_block_count": s8["raw_fmt5_block_count"],
                "total_decoded_bytes": s8["total_decoded_bytes"],
                "mode_histogram": s8["mode_histogram"],
            }
            continue

        entries = _read_slot_pointer_table(bank_bytes, t_off, expected_load_base, stop_off)
        non_null = [e for e in entries if e != 0]

        if s_idx == 0:
            for idx1, e_ptr in enumerate(entries, start=1):
                if e_ptr == 0:
                    continue
                rec = decode_slot0_entry(bank_bytes, expected_load_base, e_ptr)
                rec["index_1based"] = idx1
                if not include_raw_decoded:
                    rec.pop("_raw_decoded", None)
                decoded_slot0.append(rec)
            slot_summaries["0"] = {
                "table_ptr_hex": f"0x{ptr:08x}",
                "present": True,
                "status": "decoded_vdp2_pattern_blocks",
                "entry_count": len(entries),
                "non_null_count": len(non_null),
                "total_decoded_bytes": sum(r["decoded_bytes"] for r in decoded_slot0),
            }
        elif s_idx == 1:
            for idx1, e_ptr in enumerate(entries, start=1):
                if e_ptr == 0:
                    continue
                rec = decode_slot1_palette(bank_bytes, expected_load_base, e_ptr)
                rec["index_1based"] = idx1
                if not include_raw_decoded:
                    rec.pop("_raw_decoded", None)
                decoded_slot1.append(rec)
            slot_summaries["1"] = {
                "table_ptr_hex": f"0x{ptr:08x}",
                "present": True,
                "status": "decoded_vdp2_cram_palettes",
                "entry_count": len(entries),
                "non_null_count": len(non_null),
                "total_decoded_bytes": sum(r["decoded_bytes"] for r in decoded_slot1),
            }
        elif s_idx == 2:
            first_ro = (non_null[0] - expected_load_base) if non_null else -1
            is_tilemap_slot = (
                first_ro >= 0x34
                and first_ro + 6 <= len(bank_bytes)
                and bank_bytes[first_ro] > 0
                and bank_bytes[first_ro + 1] > 0
            )
            if is_tilemap_slot:
                for idx1, e_ptr in enumerate(entries, start=1):
                    if e_ptr == 0:
                        continue
                    rec = decode_slot2_tilemap(bank_bytes, expected_load_base, e_ptr)
                    rec["index_1based"] = idx1
                    if not include_raw_decoded:
                        rec.pop("_raw_decoded", None)
                    decoded_slot2.append(rec)
                slot_summaries["2"] = {
                    "table_ptr_hex": f"0x{ptr:08x}",
                    "present": True,
                    "status": "decoded_vdp2_tilemaps",
                    "entry_count": len(entries),
                    "non_null_count": len(non_null),
                    "total_decoded_bytes": sum(r["decoded_bytes"] for r in decoded_slot2),
                }
            else:
                has_dsp_exb = b"DSP01" in bank_bytes[t_off:stop_off]
                slot_summaries["2"] = {
                    "table_ptr_hex": f"0x{ptr:08x}",
                    "present": True,
                    "status": "scsp_sound_dsp_command_table_0x060095e0",
                    "entry_count": len(entries),
                    "non_null_count": len(non_null),
                    "contains_dsp_microprogram_exb": has_dsp_exb,
                }
        elif s_idx == 7:
            for idx1, e_ptr in enumerate(entries, start=1):
                if e_ptr == 0:
                    continue
                rec = decode_slot7_grid(bank_bytes, expected_load_base, e_ptr)
                rec["index_1based"] = idx1
                if not include_raw_decoded:
                    rec.pop("_raw_decoded", None)
                decoded_slot7.append(rec)
            slot_summaries["7"] = {
                "table_ptr_hex": f"0x{ptr:08x}",
                "present": True,
                "status": "decoded_stage_collision_grids",
                "entry_count": len(entries),
                "non_null_count": len(non_null),
                "total_decoded_bytes": sum(r["decoded_bytes"] for r in decoded_slot7),
            }
        else:
            slot_summaries[str(s_idx)] = {
                "table_ptr_hex": f"0x{ptr:08x}",
                "present": True,
                "status": "pointer_table_indexed_payload_semantics_open",
                "entry_count": len(entries),
                "non_null_count": len(non_null),
            }

    return {
        "schema": BANK_DECODE_SCHEMA,
        "tool_version": TOOL_VERSION,
        "bank": {
            "bank_id": bank_id,
            "header_name": header_name,
            "byte_length": len(bank_bytes),
            "sha256": hashlib.sha256(bank_bytes).hexdigest(),
            "source_sector_offset": source_sector_offset,
            "source_byte_offset_hex": (
                f"0x{source_sector_offset * SECTOR_BYTES:07x}" if source_sector_offset is not None else None
            ),
            "load_base_hex": f"0x{expected_load_base:08x}",
            "load_end_hex": f"0x{end_addr:08x}",
            "slot_table_ptrs_hex": [f"0x{x:08x}" for x in slot_ptrs],
        },
        "slot_summaries": slot_summaries,
        "decoded_slots": {
            "slot0_vdp2_patterns": decoded_slot0,
            "slot1_cram_palettes": decoded_slot1,
            "slot2_vdp2_tilemaps": decoded_slot2,
            "slot7_stage_grids": decoded_slot7,
            "slot8_vdp1_sprites": decoded_slot8,
        },
        "explicit_unknowns": [
            "Slots 3, 4, 5, 6, and 9 pointer tables are bounds-checked, but per-record gameplay/entity/animation layout semantics remain open.",
            "Slot 10 sound/sequence transfer records (unpacked via 0x060095E0 into SCSP.RAM 0x25A00000) remain open for RSAT-008 audio research.",
        ],
    }
