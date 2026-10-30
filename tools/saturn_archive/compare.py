"""Resident memory comparison and negative-control suite for Saturn PROGRAM.BIN banks."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
from typing import Any

from . import RESIDENT_COMPARISON_SCHEMA, TOOL_VERSION, ArchiveError
from .banks import SECTOR_BYTES, parse_and_decode_bank
from .codec import hudson_decompress

# Reuse the accepted MDFNSVST parser in tools/saturn_lab/state_graphics.py without modifying it.
_SATURN_LAB_DIR = str(Path(__file__).resolve().parents[1] / "saturn_lab")
if _SATURN_LAB_DIR not in sys.path:
    sys.path.insert(0, _SATURN_LAB_DIR)
import state_graphics  # type: ignore[import-not-found]


def load_checkpoint_memory(checkpoint_dir: Path, label: str) -> dict[str, Any]:
    """Load CPU/VDP/SCSP memory regions and public-safe provenance from a private checkpoint."""
    ckpt_json = checkpoint_dir / "checkpoint.json"
    if not ckpt_json.is_file():
        raise ArchiveError(f"Missing checkpoint.json in {label}")
    raw_meta = state_graphics.read_bounded(ckpt_json, 16384)
    meta = state_graphics.unique_json(raw_meta)
    state_path = (checkpoint_dir / meta["state_path"]).resolve()
    raw_state = state_graphics.read_bounded(state_path, state_graphics.MAX_STATE)
    if hashlib.sha256(raw_state).hexdigest() != meta["state_sha256"]:
        raise ArchiveError(f"Checkpoint {label} state SHA-256 mismatch against checkpoint.json")

    parsed = state_graphics.parse(raw_state)
    wram_l = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAML", 0x100000), "little")
    wram_h = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little")
    vdp1_vram = state_graphics.cpu_words(state_graphics.field(parsed, "VDP1", "VRAM", 0x80000), "little")
    vdp2_vram = state_graphics.cpu_words(state_graphics.field(parsed, "VDP2", "VRAM", 0x80000), "little")
    vdp2_cram = state_graphics.cpu_words(state_graphics.field(parsed, "VDP2", "CRAM", 0x1000), "little")

    scsp_ram = b""
    for sec_name, sec_obj in parsed["sections"].items():
        if sec_name in ("VDP1", "VDP2"):
            continue
        for fname, fval in sec_obj["fields"].items():
            if len(fval) == 0x80000 and "RAM" in fname:
                scsp_ram = state_graphics.cpu_words(fval, "little")
                break

    return {
        "label": label,
        "checkpoint_json_sha256": hashlib.sha256(raw_meta).hexdigest(),
        "frame": int(meta["frame"]),
        "state_bytes": int(meta["state_bytes"]),
        "state_sha256": str(meta["state_sha256"]),
        "identity": dict(meta["identity"]),
        "kernel_vars": {
            "bank_mode_0x26006158": struct.unpack_from(">H", wram_h, 0x006158)[0],
            "world_idx_0x060c029c": wram_h[0x0C029C],
            "stage_idx_0x060c029d": wram_h[0x0C029D],
            "stage_grid_ptr_0x060d7e94_hex": f"0x{struct.unpack_from('>I', wram_h, 0x0D7E94)[0]:08x}",
        },
        "regions": {
            "WorkRAML": (0x00200000, wram_l),
            "WorkRAMH": (0x06000000, wram_h),
            "VDP1.VRAM": (0x05C00000, vdp1_vram),
            "VDP2.VRAM": (0x05E00000, vdp2_vram),
            "VDP2.CRAM": (0x05F00000, vdp2_cram),
            "SCSP.RAM": (0x05A00000, scsp_ram),
        },
    }


def _diff_intervals(expected: bytes, observed: bytes, max_intervals: int = 16) -> tuple[int, list[dict[str, int]]]:
    if len(expected) != len(observed):
        raise ArchiveError("Length mismatch in byte comparison")
    equal_count = 0
    intervals: list[dict[str, int]] = []
    in_diff = False
    diff_start = 0
    for i, (a, b) in enumerate(zip(expected, observed)):
        if a == b:
            equal_count += 1
            if in_diff:
                if len(intervals) < max_intervals:
                    intervals.append({"start": diff_start, "end_exclusive": i, "length": i - diff_start})
                in_diff = False
        else:
            if not in_diff:
                diff_start = i
                in_diff = True
    if in_diff and len(intervals) < max_intervals:
        intervals.append(
            {"start": diff_start, "end_exclusive": len(expected), "length": len(expected) - diff_start}
        )
    return equal_count, intervals


def _lookup_phys_slice(
    regions: dict[str, tuple[int, bytes]],
    dest_addr: int,
    length: int,
) -> tuple[str, int, bytes] | None:
    phys = dest_addr & 0x1FFFFFFF
    for rname, (rbase, rbuf) in regions.items():
        if rbuf and rbase <= phys and phys + length <= rbase + len(rbuf):
            off = phys - rbase
            return rname, off, rbuf[off : off + length]
    return None


def compare_bank_to_checkpoint(
    bank_bytes: bytes,
    *,
    bank_id: int,
    source_sector_offset: int,
    expected_load_base: int,
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    """Compare both raw WorkRAML staging and unpacked sub-resources of a bank against a checkpoint."""
    decoded = parse_and_decode_bank(
        bank_bytes,
        bank_id=bank_id,
        expected_load_base=expected_load_base,
        source_sector_offset=source_sector_offset,
        include_raw_decoded=True,
    )
    regions = checkpoint["regions"]
    wram_l = regions["WorkRAML"][1]
    wram_h = regions["WorkRAMH"][1]
    vdp1_vram = regions["VDP1.VRAM"][1]
    vdp2_vram = regions["VDP2.VRAM"][1]
    vdp2_cram = regions["VDP2.CRAM"][1]

    wram_off = expected_load_base - 0x00200000
    if wram_off < 0 or wram_off + len(bank_bytes) > len(wram_l):
        raise ArchiveError(f"Bank range 0x{expected_load_base:08x}+{len(bank_bytes)} outside WorkRAML")
    resident_raw = wram_l[wram_off : wram_off + len(bank_bytes)]
    equal_bytes, diff_intervals = _diff_intervals(bank_bytes, resident_raw)

    # Check header & pointer table relocation hypothesis directly:
    header_52b_exact = bank_bytes[:0x34] == resident_raw[:0x34]

    # Slot 0 comparisons (VDP2.VRAM default dest or dynamic search)
    slot0_results: list[dict[str, Any]] = []
    for rec in decoded["decoded_slots"]["slot0_vdp2_patterns"]:
        dec_bytes: bytes = rec.pop("_raw_decoded")
        default_dest = rec["default_dest"]
        matched_region = None
        matched_offset_hex = None
        eq = 0
        if default_dest not in (0, 0xFFFFFFFF):
            hit = _lookup_phys_slice(regions, default_dest, len(dec_bytes))
            if hit is not None:
                rname, roff, rslice = hit
                matched_region = rname
                matched_offset_hex = f"0x{roff:05x}"
                eq = sum(1 for a, b in zip(dec_bytes, rslice) if a == b)
        elif len(dec_bytes) >= 64 and any(dec_bytes):
            for rname, (_, rbuf) in (
                ("VDP2.VRAM", regions["VDP2.VRAM"]),
                ("VDP1.VRAM", regions["VDP1.VRAM"]),
                ("WorkRAMH", regions["WorkRAMH"]),
            ):
                pos = rbuf.find(dec_bytes)
                if pos != -1:
                    matched_region = rname
                    matched_offset_hex = f"0x{pos:05x}"
                    eq = len(dec_bytes)
                    break
        slot0_results.append(
            {
                "index_1based": rec["index_1based"],
                "entry_ptr_hex": rec["entry_ptr_hex"],
                "default_dest_hex": rec["default_dest_hex"],
                "compressed": rec["compressed"],
                "compressed_stream_bytes": rec["compressed_stream_bytes"],
                "decoded_bytes": len(dec_bytes),
                "decoded_sha256": rec["decoded_sha256"],
                "codec": rec["codec"],
                "matched_region": matched_region,
                "matched_region_offset_hex": matched_offset_hex,
                "equal_bytes": eq,
                "exact_match": (eq == len(dec_bytes) and matched_region is not None),
                "match_ratio": round(eq / len(dec_bytes), 6) if dec_bytes else 1.0,
            }
        )

    # Slot 1 CRAM palette comparisons (VDP2.CRAM + kernel shadow CRAM at 0x060CBC60)
    shadow_cram = wram_h[0x0CBC60 : 0x0CBC60 + 0x1000]
    slot1_exact_cram = 0
    slot1_exact_shadow = 0
    for rec in decoded["decoded_slots"]["slot1_cram_palettes"]:
        pal_bytes: bytes = rec.pop("_raw_decoded")
        if pal_bytes and vdp2_cram.find(pal_bytes) != -1:
            slot1_exact_cram += 1
        if pal_bytes and shadow_cram.find(pal_bytes) != -1:
            slot1_exact_shadow += 1

    # Slot 2 cleanup
    for rec in decoded["decoded_slots"]["slot2_vdp2_tilemaps"]:
        rec.pop("_raw_decoded", None)

    # Slot 7 stage collision/tile grid comparisons (unpacked via 0x0600C502 to *(u32*)0x060D7E94)
    grid_ptr = struct.unpack_from(">I", wram_h, 0x0D7E94)[0] & 0x1FFFFFFF
    slot7_results: list[dict[str, Any]] = []
    for rec in decoded["decoded_slots"]["slot7_stage_grids"]:
        grid_bytes: bytes = rec.pop("_raw_decoded")
        found_off = wram_h.find(grid_bytes) if any(grid_bytes) else -1
        eq_at_ptr = 0
        ptr_off: int | None = None
        if 0x06000000 <= grid_ptr and (grid_ptr - 0x06000000) + len(grid_bytes) <= len(wram_h):
            ptr_off = grid_ptr - 0x06000000
            eq_at_ptr = sum(
                1 for a, b in zip(grid_bytes, wram_h[ptr_off : ptr_off + len(grid_bytes)]) if a == b
            )
        slot7_results.append(
            {
                "index_1based": rec["index_1based"],
                "entry_ptr_hex": rec["entry_ptr_hex"],
                "cols": rec["cols"],
                "rows": rec["rows"],
                "compressed_stream_bytes": rec["compressed_stream_bytes"],
                "decoded_bytes": len(grid_bytes),
                "decoded_sha256": rec["decoded_sha256"],
                "codec": rec["codec"],
                "exact_contiguous_offset_in_workram_h_hex": (
                    f"0x{found_off:06x}" if found_off != -1 else None
                ),
                "equal_bytes_at_active_grid_ptr": eq_at_ptr,
                "active_grid_match_ratio": round(eq_at_ptr / len(grid_bytes), 6) if grid_bytes else 0.0,
            }
        )

    # Slot 8 VDP1 sprite pixel block comparisons
    s8 = decoded["decoded_slots"]["slot8_vdp1_sprites"]
    vdp1_exact_blocks = 0
    vdp1_exact_bytes = 0
    tested_nonempty_blocks = 0
    sample_hits: list[dict[str, Any]] = []
    scratchpad_2fb000 = wram_l[0x0FB000:0x100000]
    scratchpad_exact_hits = 0

    if s8 is not None:
        for blk in s8["blocks"]:
            sbytes: bytes = blk.pop("_raw_decoded")
            if len(sbytes) >= 32 and any(sbytes):
                tested_nonempty_blocks += 1
                vpos = vdp1_vram.find(sbytes)
                if vpos != -1:
                    vdp1_exact_blocks += 1
                    vdp1_exact_bytes += len(sbytes)
                    if len(sample_hits) < 12:
                        sample_hits.append(
                            {
                                "pixel_ptr_hex": blk["pixel_ptr_hex"],
                                "compressed": blk["compressed"],
                                "compressed_stream_bytes": blk["compressed_stream_bytes"],
                                "decoded_bytes": blk["decoded_bytes"],
                                "decoded_sha256": blk["decoded_sha256"],
                                "codec": {
                                    "selector_bits": blk["codec"]["selector_bits"],
                                    "stream_mode": blk["codec"]["stream_mode"],
                                },
                                "vdp1_vram_offset_hex": f"0x{vpos:05x}",
                            }
                        )
                if scratchpad_2fb000.startswith(sbytes):
                    scratchpad_exact_hits += 1

    return {
        "bank": decoded["bank"],
        "checkpoint": {
            "label": checkpoint["label"],
            "frame": checkpoint["frame"],
            "checkpoint_json_sha256": checkpoint["checkpoint_json_sha256"],
            "state_bytes": checkpoint["state_bytes"],
            "state_sha256": checkpoint["state_sha256"],
            "identity": checkpoint["identity"],
            "kernel_vars": checkpoint["kernel_vars"],
        },
        "raw_workram_l_comparison": {
            "region": "MAIN.WorkRAML",
            "region_offset_hex": f"0x{wram_off:06x}",
            "saturn_addr_range_hex": f"0x{expected_load_base:08x}..0x{expected_load_base + len(bank_bytes):08x}",
            "bank_bytes": len(bank_bytes),
            "equal_bytes": equal_bytes,
            "mismatch_bytes": len(bank_bytes) - equal_bytes,
            "exact_match": equal_bytes == len(bank_bytes),
            "match_ratio": round(equal_bytes / len(bank_bytes), 6),
            "resident_slice_sha256": hashlib.sha256(resident_raw).hexdigest(),
            "header_0x34_verbatim_unrelocated": header_52b_exact,
            "mismatch_intervals_sample": diff_intervals,
        },
        "hypothesis_verdicts": {
            "verbatim_cd_staging_into_workram_l": equal_bytes == len(bank_bytes),
            "pointer_relocation_at_load_time": False if header_52b_exact else None,
            "subresources_stored_hudson_compressed_and_unpacked_to_vram_wram": (
                any(r["exact_match"] and r["compressed"] for r in slot0_results)
                or vdp1_exact_blocks > 0
            ),
        },
        "decoded_subresource_comparisons": {
            "slot0_vdp2_patterns": slot0_results,
            "slot1_cram_palettes": {
                "total_palettes": len(decoded["decoded_slots"]["slot1_cram_palettes"]),
                "exact_matches_in_vdp2_cram": slot1_exact_cram,
                "exact_matches_in_shadow_cram": slot1_exact_shadow,
            },
            "slot2_vdp2_tilemap_count": len(decoded["decoded_slots"]["slot2_vdp2_tilemaps"]),
            "slot7_stage_grids": slot7_results,
            "slot8_vdp1_sprites": {
                "unique_pixel_blocks": s8["unique_pixel_block_count"] if s8 else 0,
                "tested_nonempty_blocks_ge_32b": tested_nonempty_blocks,
                "exact_vdp1_vram_block_matches": vdp1_exact_blocks,
                "exact_vdp1_vram_matched_bytes": vdp1_exact_bytes,
                "scratchpad_0x002fb000_prefix_matches": scratchpad_exact_hits,
                "sample_vdp1_matches": sample_hits,
            },
        },
    }


def run_negative_controls(
    *,
    base1_bytes: bytes,
    normal1_bytes: bytes,
    normal2_bytes: bytes,
    menu_ckpt: dict[str, Any],
    normal2_ckpt: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute explicit real-input falsification and negative-control checks."""
    controls: list[dict[str, Any]] = []

    # 1. Wrong checkpoint control: normal2 compared against menu-release (where openning is at 0x00254000)
    wrong_ckpt = compare_bank_to_checkpoint(
        normal2_bytes,
        bank_id=5,
        source_sector_offset=912,
        expected_load_base=0x00254000,
        checkpoint=menu_ckpt,
    )
    c1_raw = wrong_ckpt["raw_workram_l_comparison"]
    if c1_raw["exact_match"]:
        raise ArchiveError("Negative control failed: normal2 unexpectedly matched menu-release WorkRAML")
    controls.append(
        {
            "control_id": "NC-01-wrong-checkpoint-normal2-vs-menu-release",
            "description": "Compare normal2 (0x00254000..0x002e0000) against menu-release where openning occupies 0x00254000.",
            "rejected_as_expected": True,
            "observed_match_ratio": c1_raw["match_ratio"],
            "observed_vdp1_sprite_matches": wrong_ckpt["decoded_subresource_comparisons"]["slot8_vdp1_sprites"][
                "exact_vdp1_vram_block_matches"
            ],
        }
    )

    # 2. Wrong bank control: normal1 compared against resident normal2 checkpoint
    wrong_bank = compare_bank_to_checkpoint(
        normal1_bytes,
        bank_id=4,
        source_sector_offset=632,
        expected_load_base=0x00254000,
        checkpoint=normal2_ckpt,
    )
    c2_raw = wrong_bank["raw_workram_l_comparison"]
    if c2_raw["exact_match"]:
        raise ArchiveError("Negative control failed: normal1 unexpectedly matched normal2 WorkRAML")
    controls.append(
        {
            "control_id": "NC-02-wrong-bank-normal1-vs-normal2-checkpoint",
            "description": "Compare normal1 (id=4) against resident normal2 (id=5) WorkRAML.",
            "rejected_as_expected": True,
            "observed_match_ratio": c2_raw["match_ratio"],
        }
    )

    # 3. Non-planar 3-bit selector falsification on a real sb=3 sprite block in normal2
    n2_dec = parse_and_decode_bank(
        normal2_bytes,
        bank_id=5,
        expected_load_base=0x00254000,
        source_sector_offset=912,
        include_raw_decoded=False,
    )
    sb3_block = next(
        b for b in n2_dec["decoded_slots"]["slot8_vdp1_sprites"]["blocks"]
        if b["compressed"] and b["codec"]["selector_bits"] == 3 and b["decoded_bytes"] >= 64
    )
    poff = sb3_block["bank_rel_offset"]
    blen = sb3_block["decoded_bytes"]
    true_sb3, _, _ = hudson_decompress(normal2_bytes, poff + 4, blen, streaming_4byte=False, planar_3bit=True)
    wrong_sb3, _, _ = hudson_decompress(normal2_bytes, poff + 4, blen, streaming_4byte=False, planar_3bit=False)
    if true_sb3 == wrong_sb3:
        raise ArchiveError("Negative control failed: non-planar 3-bit selector produced identical bytes")
    controls.append(
        {
            "control_id": "NC-03-nonplanar-3bit-selector-falsification",
            "description": (
                f"Decode real normal2 Slot 8 sb=3 block ({sb3_block['pixel_ptr_hex']}) with "
                "contiguous 24-bit packing instead of 0x0603434C's 3-byte bit-planar reader."
            ),
            "rejected_as_expected": True,
            "true_sha256": hashlib.sha256(true_sb3).hexdigest(),
            "wrong_nonplanar_sha256": hashlib.sha256(wrong_sb3).hexdigest(),
            "differing_bytes": sum(1 for a, b in zip(true_sb3, wrong_sb3) if a != b),
        }
    )

    # 4. Dual-ring stride-2 vs single-ring / pair-interleave falsification on real normal2 Slot 7 stage grid #1 (sm=1)
    s7_first = n2_dec["decoded_slots"]["slot7_stage_grids"][0]
    s7_off = s7_first["bank_rel_offset"]
    s7_len = s7_first["decoded_bytes"]
    true_s7, _, _ = hudson_decompress(normal2_bytes, s7_off + 1, s7_len, streaming_4byte=True)
    single_ring_s7, _, _ = hudson_decompress(
        normal2_bytes, s7_off + 1, s7_len, streaming_4byte=True, dual_ring_enabled=False
    )
    pair_interleave_s7, _, _ = hudson_decompress(
        normal2_bytes, s7_off + 1, s7_len, streaming_4byte=True, pair_interleave_falsification=True
    )
    if true_s7 == single_ring_s7 or true_s7 == pair_interleave_s7:
        raise ArchiveError("Negative control failed: dual-ring falsification did not diverge on sm=1 stream")
    controls.append(
        {
            "control_id": "NC-04-dual-ring-mode1-falsification",
            "description": (
                f"Decode real normal2 Slot 7 stage grid #1 ({s7_first['entry_ptr_hex']}, sm=1) "
                "with single 512-byte ring and with 2-element pair interleaving instead of 1-element stride-2 rings."
            ),
            "rejected_as_expected": True,
            "differing_bytes_single_ring": sum(1 for a, b in zip(true_s7, single_ring_s7) if a != b),
            "differing_bytes_pair_interleave": sum(1 for a, b in zip(true_s7, pair_interleave_s7) if a != b),
        }
    )

    # 5. Out-of-range predictor code (>19) and truncated stream on real base1 Slot 0 #1
    b1_s0_off = 0x0040
    _, b1_fl = struct.unpack_from(">II", base1_bytes, b1_s0_off)
    b1_out_len = b1_fl & 0x7FFFFFFF
    mutated = bytearray(base1_bytes[: b1_s0_off + 256])
    mutated[b1_s0_off + 8 + 2] = 20  # method[1] = 20 > 19
    bad_method_caught = False
    try:
        hudson_decompress(bytes(mutated), b1_s0_off + 8, b1_out_len)
    except ArchiveError:
        bad_method_caught = True
    trunc_caught = False
    try:
        hudson_decompress(base1_bytes[: b1_s0_off + 32], b1_s0_off + 8, b1_out_len)
    except ArchiveError:
        trunc_caught = True
    if not (bad_method_caught and trunc_caught):
        raise ArchiveError("Negative control failed: invalid predictor or truncated stream not rejected")
    controls.append(
        {
            "control_id": "NC-05-invalid-predictor-and-truncated-stream",
            "description": "Mutate base1 Slot 0 #1 predictor code to 20 (>19) and truncate compressed payload to 24 bytes.",
            "rejected_as_expected": True,
            "invalid_predictor_rejected": bad_method_caught,
            "truncated_stream_rejected": trunc_caught,
        }
    )

    # 6. Single-byte resident memory tamper control on WorkRAML & VDP2.VRAM
    tampered_wram = bytearray(menu_ckpt["regions"]["WorkRAML"][1])
    tampered_wram[0x00100] ^= 0x01
    tampered_vdp2 = bytearray(menu_ckpt["regions"]["VDP2.VRAM"][1])
    tampered_vdp2[0x50010] ^= 0x01
    tampered_ckpt = {
        **menu_ckpt,
        "label": f"{menu_ckpt['label']}-1byte-tampered",
        "regions": {
            **menu_ckpt["regions"],
            "WorkRAML": (0x00200000, bytes(tampered_wram)),
            "VDP2.VRAM": (0x05E00000, bytes(tampered_vdp2)),
        },
    }
    tampered_cmp = compare_bank_to_checkpoint(
        base1_bytes,
        bank_id=1,
        source_sector_offset=16,
        expected_load_base=0x00200000,
        checkpoint=tampered_ckpt,
    )
    wram_ok = (
        not tampered_cmp["raw_workram_l_comparison"]["exact_match"]
        and tampered_cmp["raw_workram_l_comparison"]["mismatch_bytes"] == 1
    )
    s0_1 = tampered_cmp["decoded_subresource_comparisons"]["slot0_vdp2_patterns"][0]
    vdp2_ok = (not s0_1["exact_match"]) and (s0_1["decoded_bytes"] - s0_1["equal_bytes"] == 1)
    if not (wram_ok and vdp2_ok):
        raise ArchiveError("Negative control failed: 1-byte resident RAM/VRAM tamper not detected")
    controls.append(
        {
            "control_id": "NC-06-single-byte-resident-memory-tamper",
            "description": "Flip 1 bit in resident WorkRAML+0x00100 and VDP2.VRAM+0x50010 and verify exact-match rejection.",
            "rejected_as_expected": True,
            "workram_l_mismatch_bytes": tampered_cmp["raw_workram_l_comparison"]["mismatch_bytes"],
            "vdp2_slot0_1_mismatch_bytes": s0_1["decoded_bytes"] - s0_1["equal_bytes"],
        }
    )

    return controls


def build_resident_comparison_receipt(
    *,
    usa_program_bin: bytes,
    japan_program_bin: bytes,
    menu_ckpt: dict[str, Any],
    nav_ckpt: dict[str, Any],
    normal2_run1_ckpt: dict[str, Any],
    normal2_run2_ckpt: dict[str, Any],
    normal2_capture_info: dict[str, Any],
) -> dict[str, Any]:
    """Build the complete, public-safe EXP-SAT-ARCHIVE-002 resident comparison receipt."""
    base1_usa = usa_program_bin[16 * SECTOR_BYTES : (16 + 168) * SECTOR_BYTES]
    base1_jpn = japan_program_bin[16 * SECTOR_BYTES : (16 + 168) * SECTOR_BYTES]
    normal1_usa = usa_program_bin[632 * SECTOR_BYTES : (632 + 280) * SECTOR_BYTES]
    normal2_usa = usa_program_bin[912 * SECTOR_BYTES : (912 + 280) * SECTOR_BYTES]
    normal2_jpn = japan_program_bin[912 * SECTOR_BYTES : (912 + 280) * SECTOR_BYTES]

    if normal2_usa != normal2_jpn:
        raise ArchiveError("USA and Japan normal2 slices unexpectedly differ")

    # Verify two-run fresh-process replay determinism on the captured normal2 checkpoint!
    determinism_checks = {}
    for rname in ("WorkRAML", "WorkRAMH", "VDP1.VRAM", "VDP2.VRAM", "VDP2.CRAM", "SCSP.RAM"):
        b1 = normal2_run1_ckpt["regions"][rname][1]
        b2 = normal2_run2_ckpt["regions"][rname][1]
        determinism_checks[rname] = {
            "bytes": len(b1),
            "sha256": hashlib.sha256(b1).hexdigest(),
            "identical_across_two_runs": b1 == b2,
        }
        if b1 != b2:
            raise ArchiveError(f"Fresh-process replay mismatch in {rname} between normal2 run1 and run2")

    # Also check transient s_nor2 (USA bank_id=15, sec=3496, cnt=208, load=0x00254000) sound transfer into SCSP.RAM!
    s_nor2_usa = usa_program_bin[3496 * SECTOR_BYTES : (3496 + 208) * SECTOR_BYTES]
    s_nor2_s10_ptr = struct.unpack_from(">I", s_nor2_usa, 10 * 4)[0]
    s_nor2_s10_first_rec = struct.unpack_from(">I", s_nor2_usa, s_nor2_s10_ptr - 0x00254000)[0]
    scsp_ram = normal2_run1_ckpt["regions"]["SCSP.RAM"][1]
    # Check 256-byte sample from s_nor2 payload inside SCSP.RAM
    s_nor2_probe_off = (s_nor2_s10_first_rec - 0x00254000) + 0x20
    s_nor2_probe = s_nor2_usa[s_nor2_probe_off : s_nor2_probe_off + 256]
    scsp_probe_pos = scsp_ram.find(s_nor2_probe) if any(s_nor2_probe) else -1

    comparisons = [
        compare_bank_to_checkpoint(
            base1_usa,
            bank_id=1,
            source_sector_offset=16,
            expected_load_base=0x00200000,
            checkpoint=menu_ckpt,
        ),
        compare_bank_to_checkpoint(
            base1_usa,
            bank_id=1,
            source_sector_offset=16,
            expected_load_base=0x00200000,
            checkpoint=nav_ckpt,
        ),
        compare_bank_to_checkpoint(
            base1_usa,
            bank_id=1,
            source_sector_offset=16,
            expected_load_base=0x00200000,
            checkpoint=normal2_run1_ckpt,
        ),
        compare_bank_to_checkpoint(
            normal2_usa,
            bank_id=5,
            source_sector_offset=912,
            expected_load_base=0x00254000,
            checkpoint=normal2_run1_ckpt,
        ),
    ]

    neg_controls = run_negative_controls(
        base1_bytes=base1_usa,
        normal1_bytes=normal1_usa,
        normal2_bytes=normal2_usa,
        menu_ckpt=menu_ckpt,
        normal2_ckpt=normal2_run1_ckpt,
    )

    return {
        "schema": RESIDENT_COMPARISON_SCHEMA,
        "tool_version": TOOL_VERSION,
        "experiment_id": "EXP-SAT-ARCHIVE-002",
        "issue": 484,
        "cross_region_bank_identity": {
            "base1": {
                "sector_offset": 16,
                "sector_count": 168,
                "byte_length": len(base1_usa),
                "usa_sha256": hashlib.sha256(base1_usa).hexdigest(),
                "japan_sha256": hashlib.sha256(base1_jpn).hexdigest(),
                "byte_identical_usa_vs_japan": base1_usa == base1_jpn,
                "equal_bytes_usa_vs_japan": sum(1 for a, b in zip(base1_usa, base1_jpn) if a == b),
            },
            "normal2": {
                "sector_offset": 912,
                "sector_count": 280,
                "byte_length": len(normal2_usa),
                "usa_sha256": hashlib.sha256(normal2_usa).hexdigest(),
                "japan_sha256": hashlib.sha256(normal2_jpn).hexdigest(),
                "byte_identical_usa_vs_japan": normal2_usa == normal2_jpn,
                "equal_bytes_usa_vs_japan": len(normal2_usa),
            },
        },
        "normal2_checkpoint_replay_determinism": {
            "capture_protocol": normal2_capture_info,
            "run1_state_sha256": normal2_run1_ckpt["state_sha256"],
            "run2_state_sha256": normal2_run2_ckpt["state_sha256"],
            "state_sha256_identical": normal2_run1_ckpt["state_sha256"] == normal2_run2_ckpt["state_sha256"],
            "memory_regions": determinism_checks,
        },
        "transient_sound_overlay_proof": {
            "sound_bank_id": 15,
            "sound_bank_name": "s_nor2",
            "sound_bank_sector_offset": 3496,
            "sound_bank_byte_length": len(s_nor2_usa),
            "sound_bank_sha256": hashlib.sha256(s_nor2_usa).hexdigest(),
            "staging_addr_hex": "0x00254000",
            "overwritten_in_workram_l_by_normal2": True,
            "scsp_ram_256b_payload_probe_offset_hex": (
                f"0x{scsp_probe_pos:05x}" if scsp_probe_pos != -1 else None
            ),
            "scsp_ram_retained_after_overwrite": scsp_probe_pos != -1,
        },
        "comparisons": comparisons,
        "negative_controls": neg_controls,
        "explicit_unknowns": [
            "Slots 3, 4, 5, 6, and 9 record layouts inside base1 and normal2 remain open beyond pointer-table bounds.",
            "Slot 10 sound/sequence binary record headers (0x060095E0 -> SCSP.RAM) remain open for RSAT-008.",
            "Dynamic VDP2 plane destination selection for Slot 0 entries with default_dest=0x00000000 and Slot 2 tilemaps is driven by per-scene SH-2 callers rather than bank headers.",
        ],
    }
