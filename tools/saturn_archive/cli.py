#!/usr/bin/env python3
"""CLI for Saturn Bomberman PROGRAM.BIN kernel directory auditing, Hudson bank decoding, and resident RAM/VRAM comparison."""

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
    from saturn_archive import (
        BANK_DECODE_SCHEMA,
        KERNEL_BANK_DIRECTORY_SCHEMA,
        RESIDENT_COMPARISON_SCHEMA,
        ArchiveError,
    )
    from saturn_archive.banks import (
        SECTOR_BYTES,
        WORKRAM_L_END,
        WORKRAM_L_START,
        audit_program_bin_directory,
        discover_kernel_bank_directory,
        parse_and_decode_bank,
    )
    from saturn_archive.compare import (
        build_resident_comparison_receipt,
        load_checkpoint_memory,
    )
    from saturn_disc.cue import DataTrackReader, DiscError, parse_cue_sheet
    from saturn_disc.ipbin import SYSTEM_AREA_SECTORS
    from saturn_disc.iso9660 import (
        ISO_STANDARD_ID,
        LOGICAL_BLOCK_BYTES,
        _walk_directory_tree,
        parse_primary_volume_descriptor,
    )
else:
    from . import (
        BANK_DECODE_SCHEMA,
        KERNEL_BANK_DIRECTORY_SCHEMA,
        RESIDENT_COMPARISON_SCHEMA,
        ArchiveError,
    )
    from .banks import (
        SECTOR_BYTES,
        WORKRAM_L_END,
        WORKRAM_L_START,
        audit_program_bin_directory,
        discover_kernel_bank_directory,
        parse_and_decode_bank,
    )
    from .compare import (
        build_resident_comparison_receipt,
        load_checkpoint_memory,
    )
    from saturn_disc.cue import DataTrackReader, DiscError, parse_cue_sheet
    from saturn_disc.ipbin import SYSTEM_AREA_SECTORS
    from saturn_disc.iso9660 import (
        ISO_STANDARD_ID,
        LOGICAL_BLOCK_BYTES,
        _walk_directory_tree,
        parse_primary_volume_descriptor,
    )

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_LOCAL_PREFIXES = ("/home/", "/tmp/", "/var/", "/opt/", "C:\\", "c:\\")


def assert_public_safe_text(encoded_text: str) -> None:
    """Reject accidental leakage of private host filesystem paths in public receipts."""
    for prefix in FORBIDDEN_LOCAL_PREFIXES:
        if prefix in encoded_text:
            raise ArchiveError(f"Public receipt contains forbidden local filesystem path prefix {prefix!r}")


def write_json_atomic(payload: dict[str, Any], target: Path) -> str:
    if target.is_symlink():
        raise ArchiveError(f"Refusing to write through symlink: {target}")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert_public_safe_text(text)
    encoded = text.encode("utf-8")
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


def read_iso_files_from_disc(
    root: Path,
    cue_relpath: str,
    iso_paths: list[str],
    *,
    disc_summary_path: Path | None = None,
) -> dict[str, bytes]:
    """Read exact ISO-9660 files from Track 01 with Mode 1 EDC verification via tools/saturn_disc."""
    cue = parse_cue_sheet(root, cue_relpath)
    expected_summary_files: dict[str, dict[str, Any]] = {}
    if disc_summary_path is not None:
        summary = json.loads(disc_summary_path.read_text(encoding="utf-8"))
        if summary.get("cue", {}).get("sha256") != cue.cue_sha256:
            raise ArchiveError(f"CUE SHA-256 mismatch against disc summary {disc_summary_path.name}")
        expected_summary_files = {
            f["path"]: f for f in summary.get("iso9660", {}).get("files", [])
        }

    with DataTrackReader(cue.tracks[0]) as reader:
        vd_lba = SYSTEM_AREA_SECTORS
        pvd: dict[str, Any] | None = None
        while True:
            if vd_lba >= reader.logical_blocks:
                raise ArchiveError("Unterminated ISO-9660 Volume Descriptor Set")
            vd_sector = reader.read_sector(vd_lba, verify_edc=True)
            vd_type = vd_sector[0]
            if vd_sector[1:6] != ISO_STANDARD_ID:
                raise ArchiveError(f"Invalid ISO-9660 standard ID at LBA {vd_lba}")
            if vd_type == 1 and pvd is None:
                pvd = parse_primary_volume_descriptor(vd_sector, vd_lba)
            if vd_type == 255:
                break
            vd_lba += 1
        if pvd is None:
            raise ArchiveError("Missing ISO-9660 Primary Volume Descriptor")

        _, raw_files = _walk_directory_tree(reader, pvd["root_extent_lba"], pvd["root_data_length"])
        by_path = {f["path"]: f for f in raw_files}

        out: dict[str, bytes] = {}
        for req_path in iso_paths:
            rec = by_path.get(req_path)
            if rec is None:
                raise ArchiveError(f"ISO-9660 file {req_path!r} not found on disc {cue_relpath}")
            chunks: list[bytes] = []
            for ext in rec["extents"]:
                b_len = ext["byte_length"]
                s_cnt = ext["sector_count"]
                if b_len > 0:
                    raw_ext = reader.read_logical_bytes(
                        ext["extent_lba"], s_cnt * LOGICAL_BLOCK_BYTES, verify_edc=True
                    )
                    chunks.append(raw_ext[:b_len])
            payload = b"".join(chunks)
            if req_path in expected_summary_files:
                exp = expected_summary_files[req_path]
                actual_sha = hashlib.sha256(payload).hexdigest()
                if exp["byte_length"] != len(payload) or exp["sha256"] != actual_sha:
                    raise ArchiveError(
                        f"ISO-9660 file {req_path} hash/length mismatch against disc summary {disc_summary_path}"
                    )
            out[req_path] = payload
        return out


def verify_kernel_directory_receipt(doc: dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != KERNEL_BANK_DIRECTORY_SCHEMA:
        raise ArchiveError("Invalid or unsupported kernel directory receipt schema")
    assert_public_safe_text(json.dumps(doc))

    inputs = doc.get("inputs", {})
    for key in ("krnl_sha256", "program_sha256"):
        if not SHA256_RE.fullmatch(str(inputs.get(key, ""))):
            raise ArchiveError(f"Invalid SHA-256 in inputs.{key}")

    kd = doc.get("kernel_directory", {})
    entries = doc.get("entries", [])
    entry_count = kd.get("entry_count", -1)
    if entry_count <= 0 or len(entries) != entry_count:
        raise ArchiveError("Kernel directory entry_count mismatch")
    if kd.get("all_entries_fit_workram_l") is not True:
        raise ArchiveError("Kernel directory reports entries outside WorkRAML")
    if sum(kd.get("role_counts", {}).values()) != entry_count:
        raise ArchiveError("role_counts sum does not equal entry_count")
    if sum(kd.get("destination_counts", {}).values()) != entry_count:
        raise ArchiveError("destination_counts sum does not equal entry_count")

    for idx, entry in enumerate(entries):
        if entry.get("bank_id") != idx:
            raise ArchiveError(f"Non-sequential bank_id at index {idx}")
        if not SHA256_RE.fullmatch(str(entry.get("sha256", ""))):
            raise ArchiveError(f"Invalid SHA-256 on bank_id={idx}")
        dst = int(entry.get("load_dest", -1))
        blen = int(entry.get("byte_length", -1))
        if blen <= 0 or entry.get("sector_count", -1) * SECTOR_BYTES != blen:
            raise ArchiveError(f"Invalid byte_length/sector_count on bank_id={idx}")
        if not (WORKRAM_L_START <= dst and dst + blen <= WORKRAM_L_END) or entry.get("fits_workram_l") is not True:
            raise ArchiveError(f"Bank_id={idx} exceeds WorkRAML bounds [0x00200000..0x00300000]")

    acc = doc.get("program_bin_accounting", {})
    total_bytes = int(acc.get("total_bytes", -1))
    total_sectors = int(acc.get("total_full_sectors", -1))
    subsector = int(acc.get("trailing_subsector_bytes", -1))
    if total_bytes <= 0 or total_sectors * SECTOR_BYTES + subsector != total_bytes:
        raise ArchiveError("PROGRAM.BIN sector/subsector accounting does not sum to total_bytes")
    max_ref_end = int(acc.get("max_referenced_end_sector", -1))
    ref_cnt = int(acc.get("referenced_sector_count", -1))
    gap_cnt = int(acc.get("inter_entry_gap_sector_count", -1))
    tail_cnt = int(acc.get("unreferenced_tail_sector_count", -1))
    tail_bytes = int(acc.get("unreferenced_tail_bytes", -1))
    if ref_cnt + gap_cnt != max_ref_end:
        raise ArchiveError("Referenced + inter-entry gap sectors do not partition [0..max_referenced_end_sector)")
    if max_ref_end + tail_cnt != total_sectors:
        raise ArchiveError("max_referenced_end_sector + unreferenced_tail_sector_count != total_full_sectors")
    if tail_cnt * SECTOR_BYTES + subsector != tail_bytes:
        raise ArchiveError("Unreferenced tail bytes mismatch")
    if not SHA256_RE.fullmatch(str(acc.get("unreferenced_tail_sha256", ""))):
        raise ArchiveError("Invalid unreferenced_tail_sha256")
    if (
        int(acc.get("active_entry_start_headers", -1))
        + int(acc.get("embedded_mid_slot_residual_headers", -1))
        + int(acc.get("unreferenced_headers_count", -1))
        != int(acc.get("static_header_total", -2))
    ):
        raise ArchiveError("Static 0x34 header classification counts do not partition static_header_total")


def verify_bank_decode_receipt(doc: dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != BANK_DECODE_SCHEMA:
        raise ArchiveError("Invalid or unsupported bank decode receipt schema")
    assert_public_safe_text(json.dumps(doc))
    bank = doc.get("bank", {})
    if not SHA256_RE.fullmatch(str(bank.get("sha256", ""))):
        raise ArchiveError("Invalid bank.sha256")
    if len(bank.get("slot_table_ptrs_hex", [])) != 11:
        raise ArchiveError("Expected 11 slot table pointers in bank header")
    ds = doc.get("decoded_slots", {})
    for group_key in ("slot0_vdp2_patterns", "slot1_cram_palettes", "slot2_vdp2_tilemaps", "slot7_stage_grids"):
        for rec in ds.get(group_key, []):
            if not SHA256_RE.fullmatch(str(rec.get("decoded_sha256", ""))):
                raise ArchiveError(f"Invalid decoded_sha256 in {group_key}")
    s8 = ds.get("slot8_vdp1_sprites")
    if s8 is not None:
        if len(s8.get("blocks", [])) != s8.get("unique_pixel_block_count", -1):
            raise ArchiveError("Slot 8 unique_pixel_block_count mismatch")
        for blk in s8.get("blocks", []):
            if not SHA256_RE.fullmatch(str(blk.get("decoded_sha256", ""))):
                raise ArchiveError("Invalid decoded_sha256 in Slot 8 block")
    if not doc.get("explicit_unknowns"):
        raise ArchiveError("Bank decode receipt missing explicit_unknowns")


def verify_resident_comparison_receipt(doc: dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != RESIDENT_COMPARISON_SCHEMA:
        raise ArchiveError("Invalid or unsupported resident comparison receipt schema")
    assert_public_safe_text(json.dumps(doc))

    xreg = doc.get("cross_region_bank_identity", {})
    b1_id = xreg.get("base1", {})
    n2_id = xreg.get("normal2", {})
    for grp in (b1_id, n2_id):
        for k in ("usa_sha256", "japan_sha256"):
            if not SHA256_RE.fullmatch(str(grp.get(k, ""))):
                raise ArchiveError(f"Invalid SHA-256 in cross_region_bank_identity ({k})")
    if n2_id.get("byte_identical_usa_vs_japan") is not True or n2_id.get("usa_sha256") != n2_id.get("japan_sha256"):
        raise ArchiveError("normal2 cross-region byte identity check failed")

    det = doc.get("normal2_checkpoint_replay_determinism", {})
    for k in ("run1_state_sha256", "run2_state_sha256"):
        if not SHA256_RE.fullmatch(str(det.get(k, ""))):
            raise ArchiveError(f"Invalid {k} in replay determinism block")
    mem_regs = det.get("memory_regions", {})
    for rname in ("WorkRAML", "WorkRAMH", "VDP1.VRAM", "VDP2.VRAM", "VDP2.CRAM", "SCSP.RAM"):
        rinfo = mem_regs.get(rname, {})
        if rinfo.get("identical_across_two_runs") is not True:
            raise ArchiveError(f"Memory region {rname} was not deterministic across two fresh runs")
        if not SHA256_RE.fullmatch(str(rinfo.get("sha256", ""))):
            raise ArchiveError(f"Invalid SHA-256 for deterministic region {rname}")

    comparisons = doc.get("comparisons", [])
    if len(comparisons) < 4:
        raise ArchiveError("Expected at least 4 bank-vs-checkpoint comparisons (3x base1 + 1x normal2)")
    seen_base1 = 0
    seen_normal2 = 0
    for cmp_item in comparisons:
        b = cmp_item.get("bank", {})
        raw_cmp = cmp_item.get("raw_workram_l_comparison", {})
        verdicts = cmp_item.get("hypothesis_verdicts", {})
        if not SHA256_RE.fullmatch(str(b.get("sha256", ""))):
            raise ArchiveError("Invalid bank.sha256 in comparison entry")
        if not SHA256_RE.fullmatch(str(raw_cmp.get("resident_slice_sha256", ""))):
            raise ArchiveError("Invalid resident_slice_sha256 in comparison entry")
        if raw_cmp.get("exact_match") is not True or raw_cmp.get("mismatch_bytes") != 0:
            raise ArchiveError(f"Bank {b.get('header_name')} failed verbatim WorkRAML staging match")
        if raw_cmp.get("header_0x34_verbatim_unrelocated") is not True:
            raise ArchiveError(f"Bank {b.get('header_name')} 0x34 header was mutated")
        if verdicts.get("pointer_relocation_at_load_time") is not False:
            raise ArchiveError(f"Bank {b.get('header_name')} pointer relocation falsification missing")
        if verdicts.get("subresources_stored_hudson_compressed_and_unpacked_to_vram_wram") is not True:
            raise ArchiveError(f"Bank {b.get('header_name')} unpacked sub-resource VRAM/WRAM match missing")
        if b.get("header_name") == "base1":
            seen_base1 += 1
        elif b.get("header_name") == "normal2":
            seen_normal2 += 1
    if seen_base1 < 3 or seen_normal2 < 1:
        raise ArchiveError("Missing required base1 or normal2 resident comparison entries")

    controls = doc.get("negative_controls", [])
    if len(controls) < 6:
        raise ArchiveError("Expected at least 6 negative controls")
    for ctrl in controls:
        if ctrl.get("rejected_as_expected") is not True:
            raise ArchiveError(f"Negative control {ctrl.get('control_id')} did not reject as expected")

    if not doc.get("explicit_unknowns"):
        raise ArchiveError("Resident comparison receipt missing explicit_unknowns")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser(
        "audit-directory",
        help="Extract 0KRNL.BIN's live bank directory and reconcile 100%% of PROGRAM.BIN sectors/headers",
    )
    p_audit.add_argument("--root", type=Path, required=True, help="Read-only media root directory")
    p_audit.add_argument("--cue", required=True, help="Relative POSIX path to .cue inside --root")
    p_audit.add_argument("--release-id", required=True, help="Stable release identifier (e.g. usa-mk81070-v1003)")
    p_audit.add_argument("--krnl-path", required=True, help="ISO-9660 path to 0KRNL.BIN (e.g. BOMSS/0KRNL.BIN)")
    p_audit.add_argument("--program-path", required=True, help="ISO-9660 path to PROGRAM.BIN (e.g. BOMSS/PROGRAM.BIN)")
    p_audit.add_argument("--disc-summary", type=Path, help="Optional committed #473 disc summary JSON to cross-verify")
    p_audit.add_argument("--output", type=Path, required=True, help="Output JSON receipt path")

    p_decode = sub.add_parser(
        "decode-bank",
        help="Decode a PROGRAM.BIN bank container and all supported Hudson-compressed sub-resource slots",
    )
    p_decode.add_argument("--root", type=Path, required=True, help="Read-only media root directory")
    p_decode.add_argument("--cue", required=True, help="Relative POSIX path to .cue inside --root")
    p_decode.add_argument("--krnl-path", required=True, help="ISO-9660 path to 0KRNL.BIN")
    p_decode.add_argument("--program-path", required=True, help="ISO-9660 path to PROGRAM.BIN")
    p_decode.add_argument("--bank-id", type=int, required=True, help="Kernel bank directory index (0..N-1)")
    p_decode.add_argument("--disc-summary", type=Path, help="Optional committed #473 disc summary JSON")
    p_decode.add_argument("--output", type=Path, required=True, help="Output JSON receipt path")

    p_cmp = sub.add_parser(
        "compare-resident",
        help="Compare base1 and normal2 bank bytes and decoded sub-resources against private resident checkpoints",
    )
    p_cmp.add_argument("--usa-root", type=Path, required=True)
    p_cmp.add_argument("--usa-cue", required=True)
    p_cmp.add_argument("--usa-disc-summary", type=Path)
    p_cmp.add_argument("--japan-root", type=Path, required=True)
    p_cmp.add_argument("--japan-cue", required=True)
    p_cmp.add_argument("--japan-disc-summary", type=Path)
    p_cmp.add_argument("--menu-checkpoint", type=Path, required=True)
    p_cmp.add_argument("--nav-checkpoint", type=Path, required=True)
    p_cmp.add_argument("--normal2-run1", type=Path, required=True)
    p_cmp.add_argument("--normal2-run2", type=Path, required=True)
    p_cmp.add_argument("--actions-json", type=Path, required=True, help="Controller action script used for normal2 capture")
    p_cmp.add_argument("--frames-advanced", type=int, required=True)
    p_cmp.add_argument("--output", type=Path, required=True)

    p_verify = sub.add_parser(
        "verify",
        help="Validate committed kernel-directory, bank-decode, and resident-comparison receipts offline",
    )
    p_verify.add_argument("--directory", type=Path, action="append", default=[])
    p_verify.add_argument("--bank", type=Path, action="append", default=[])
    p_verify.add_argument("--comparison", type=Path, action="append", default=[])

    args = parser.parse_args(argv)
    try:
        if args.command == "audit-directory":
            files = read_iso_files_from_disc(
                args.root,
                args.cue,
                [args.krnl_path, args.program_path],
                disc_summary_path=args.disc_summary,
            )
            doc = audit_program_bin_directory(
                files[args.krnl_path],
                files[args.program_path],
                release_id=args.release_id,
                krnl_iso_path=args.krnl_path,
                program_iso_path=args.program_path,
            )
            verify_kernel_directory_receipt(doc)
            sha = write_json_atomic(doc, args.output)
            print(
                json.dumps(
                    {
                        "release_id": args.release_id,
                        "entry_count": doc["kernel_directory"]["entry_count"],
                        "all_entries_fit_workram_l": doc["kernel_directory"]["all_entries_fit_workram_l"],
                        "max_workram_l_end_hex": doc["kernel_directory"]["max_workram_l_end_hex"],
                        "unreferenced_tail_bytes": doc["program_bin_accounting"]["unreferenced_tail_bytes"],
                        "receipt_sha256": sha,
                    },
                    indent=2,
                )
            )
        elif args.command == "decode-bank":
            files = read_iso_files_from_disc(
                args.root,
                args.cue,
                [args.krnl_path, args.program_path],
                disc_summary_path=args.disc_summary,
            )
            directory = discover_kernel_bank_directory(files[args.krnl_path])
            if not (0 <= args.bank_id < directory["entry_count"]):
                raise ArchiveError(f"--bank-id {args.bank_id} out of range 0..{directory['entry_count'] - 1}")
            entry = directory["entries"][args.bank_id]
            prog = files[args.program_path]
            bank_slice = prog[entry["byte_offset"] : entry["byte_offset"] + entry["byte_length"]]
            doc = parse_and_decode_bank(
                bank_slice,
                bank_id=args.bank_id,
                expected_load_base=entry["load_dest"],
                source_sector_offset=entry["sector_offset"],
                include_raw_decoded=False,
            )
            verify_bank_decode_receipt(doc)
            sha = write_json_atomic(doc, args.output)
            print(
                json.dumps(
                    {
                        "bank_id": args.bank_id,
                        "header_name": doc["bank"]["header_name"],
                        "load_base_hex": doc["bank"]["load_base_hex"],
                        "slot_summaries": doc["slot_summaries"],
                        "receipt_sha256": sha,
                    },
                    indent=2,
                )
            )
        elif args.command == "compare-resident":
            usa_files = read_iso_files_from_disc(
                args.usa_root,
                args.usa_cue,
                ["BOMSS/PROGRAM.BIN"],
                disc_summary_path=args.usa_disc_summary,
            )
            jpn_files = read_iso_files_from_disc(
                args.japan_root,
                args.japan_cue,
                ["PROGRAM.BIN"],
                disc_summary_path=args.japan_disc_summary,
            )
            menu_ckpt = load_checkpoint_memory(args.menu_checkpoint, "accepted-27-menu-release")
            nav_ckpt = load_checkpoint_memory(args.nav_checkpoint, "accepted-27-navigation-release-late")
            n2_run1 = load_checkpoint_memory(args.normal2_run1, "captured-484-normal2-stage-2-1-run1")
            n2_run2 = load_checkpoint_memory(args.normal2_run2, "captured-484-normal2-stage-2-1-run2")

            raw_actions = args.actions_json.read_bytes()
            actions_list = json.loads(raw_actions.decode("utf-8"))
            capture_info = {
                "restored_from_checkpoint_label": "accepted-27-navigation-release-late",
                "restored_from_frame": nav_ckpt["frame"],
                "frames_advanced": args.frames_advanced,
                "final_frame": n2_run1["frame"],
                "actions_sha256": hashlib.sha256(raw_actions).hexdigest(),
                "actions": actions_list,
                "mechanism": (
                    "Advance from accepted navigation-release-late (Attract Demo idx=2, normal1) across 6 bounded "
                    "START skips so Title Screen timeout (0x06052E54, 0x0384 ticks -> 0x06052A00) steps "
                    "*(u8*)0x060C17DA through 0x060B6BC0 to idx=12 ((1, 1) = Normal Game World 2 Stage 1), where "
                    "0x0600AF4C/0x0600AE58 transiently stages s_nor2 (bank_id=15) into SCSP.RAM and then loads "
                    "normal2 (bank_id=5) into 0x00254000..0x002e0000 alongside resident base1 (bank_id=1)."
                ),
            }
            doc = build_resident_comparison_receipt(
                usa_program_bin=usa_files["BOMSS/PROGRAM.BIN"],
                japan_program_bin=jpn_files["PROGRAM.BIN"],
                menu_ckpt=menu_ckpt,
                nav_ckpt=nav_ckpt,
                normal2_run1_ckpt=n2_run1,
                normal2_run2_ckpt=n2_run2,
                normal2_capture_info=capture_info,
            )
            verify_resident_comparison_receipt(doc)
            sha = write_json_atomic(doc, args.output)
            print(
                json.dumps(
                    {
                        "comparisons": [
                            {
                                "bank": c["bank"]["header_name"],
                                "checkpoint": c["checkpoint"]["label"],
                                "raw_exact_match": c["raw_workram_l_comparison"]["exact_match"],
                                "vdp1_sprite_matches": c["decoded_subresource_comparisons"]["slot8_vdp1_sprites"][
                                    "exact_vdp1_vram_block_matches"
                                ],
                            }
                            for c in doc["comparisons"]
                        ],
                        "negative_controls": len(doc["negative_controls"]),
                        "receipt_sha256": sha,
                    },
                    indent=2,
                )
            )
        else:
            if not (args.directory or args.bank or args.comparison):
                raise ArchiveError("Specify at least one --directory, --bank, or --comparison file to verify")
            for p in args.directory:
                raw_text = p.read_text(encoding="utf-8")
                assert_public_safe_text(raw_text)
                verify_kernel_directory_receipt(json.loads(raw_text))
            for p in args.bank:
                raw_text = p.read_text(encoding="utf-8")
                assert_public_safe_text(raw_text)
                verify_bank_decode_receipt(json.loads(raw_text))
            for p in args.comparison:
                raw_text = p.read_text(encoding="utf-8")
                assert_public_safe_text(raw_text)
                verify_resident_comparison_receipt(json.loads(raw_text))
            print(
                f"Verified {len(args.directory)} kernel directories, "
                f"{len(args.bank)} bank decodes, and {len(args.comparison)} resident comparisons."
            )
    except (ArchiveError, DiscError, OSError, ValueError, KeyError) as exc:
        print(f"saturn-archive: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
