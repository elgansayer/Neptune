"""Core audit pipeline for read-only asset snapshots, provenance, and gap analysis."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.asset_audit.formats import DECODER_VERSION, inspect_file_bytes
from tools.saturn_lab import cli as saturn_lab_cli

MANIFEST_SCHEMA = "neptune.asset-audit-manifest.v1"
SUMMARY_SCHEMA = "neptune.asset-audit-summary.v1"
LEDGER_SCHEMA = "neptune.saturn-coverage-ledger.v1"
CONFIDENCE_LEVELS = {"unknown", "hypothesis", "observed", "cross_checked", "implemented_and_compared"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class AuditError(Exception):
    """Raised when an audit input, snapshot, or manifest violates safety/validity rules."""


def inspect_git_snapshot(root: Path, require_clean: bool = False) -> dict[str, Any]:
    git_dir = root / ".git"
    if not git_dir.exists():
        if require_clean:
            raise AuditError(f"Expected a Git checkout at {root}, but .git is absent")
        return {
            "present": False,
            "commit_sha": None,
            "tree_sha": None,
            "dirty_tracked": [],
            "untracked": [],
            "is_clean": None,
        }
    try:
        commit_sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        tree_sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        raw_status = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "-uall"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise AuditError(f"Git inspection failed at {root}: {exc.stderr}") from exc

    if not COMMIT_RE.fullmatch(commit_sha) or not COMMIT_RE.fullmatch(tree_sha):
        raise AuditError("Git rev-parse did not return 40-hex commit/tree hashes")

    dirty_tracked: list[str] = []
    untracked: list[str] = []
    entries = raw_status.split(b"\x00")
    idx = 0
    while idx < len(entries):
        entry = entries[idx]
        idx += 1
        if not entry:
            continue
        code = entry[:2].decode("ascii", errors="replace")
        rel_path = entry[3:].decode("utf-8", errors="replace")
        if code == "??":
            untracked.append(rel_path)
        else:
            dirty_tracked.append(rel_path)
            if "R" in code or "C" in code:
                idx += 1  # consume rename/copy source path in -z format

    dirty_tracked.sort()
    untracked.sort()
    is_clean = not dirty_tracked and not untracked
    if require_clean and not is_clean:
        raise AuditError(
            f"Source checkout is not clean (dirty={len(dirty_tracked)}, untracked={len(untracked)})"
        )
    return {
        "present": True,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "dirty_tracked": dirty_tracked,
        "untracked": untracked,
        "is_clean": is_clean,
    }


def classify_path_lead(relative_path: str, detected_format: str) -> dict[str, Any]:
    """Classify content category and origin hypothesis strictly as unverified leads."""
    lower = relative_path.lower()
    parts = lower.split("/")
    top = parts[0] if len(parts) > 1 else "(root)"
    name = parts[-1]

    # Editor, OS, or temporary artifacts
    if (
        name == "thumbs.db"
        or lower.endswith((".import", ".tps", ".tpsheet", ".plist", ".xcf", ".bat", ".aup"))
        or name.startswith(".goutputstream-")
        or "replacecolour" in name
        or detected_format == "audacity_au"
    ):
        return {
            "inferred_category": "editor_project_or_os_artifact",
            "origin_hypothesis": "derived_project_or_os_artifact",
            "classification_basis": "filename_and_container_inference",
            "saturn_provenance_verified": False,
        }

    if name == "readme.md":
        return {
            "inferred_category": "repository_documentation",
            "origin_hypothesis": "repository_metadata",
            "classification_basis": "filename_inference",
            "saturn_provenance_verified": False,
        }

    # Bulk exports directory: GameMaker / UndertaleModTool dump structures
    if top == "exports" or name.startswith("spr_b_"):
        sub = parts[1] if len(parts) > 1 else ""
        if "fonts" in sub or "shd_" in lower:
            cat = "ui_fonts_or_engine_shaders"
        elif sub in ("tilesets", "roms to png"):
            cat = "tiles_maps_and_backgrounds"
        elif sub == "strings":
            cat = "text_and_string_tables"
        elif sub == "sprites" or name.startswith("spr_b_"):
            cat = "characters_items_or_sprites_export"
        elif sub in ("textures", "grouped text", "embedded textures"):
            cat = "packed_or_grouped_textures_export"
        else:
            cat = "unknown"
        return {
            "inferred_category": cat,
            "origin_hypothesis": "non_saturn_gamemaker_export_lead",
            "classification_basis": "directory_and_naming_inference",
            "saturn_provenance_verified": False,
        }

    if top == "audio":
        if detected_format in ("sega_film_cpk", "aiff"):
            origin = "saturn_disc_fmv_or_pcm_lead"
        else:
            origin = "derived_audio_reencode_or_project_lead"
        return {
            "inferred_category": "audio_and_fmv",
            "origin_hypothesis": origin,
            "classification_basis": "container_and_path_inference",
            "saturn_provenance_verified": False,
        }

    if top == "characters":
        return {
            "inferred_category": "characters_and_animations",
            "origin_hypothesis": "repacked_character_frames_lead",
            "classification_basis": "directory_and_naming_inference",
            "saturn_provenance_verified": False,
        }

    if top == "stupid_rat":
        return {
            "inferred_category": "unknown",
            "origin_hypothesis": "unknown_or_custom_image",
            "classification_basis": "directory_inference",
            "saturn_provenance_verified": False,
        }

    if top == "images":
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "maps" or "single player/map" in lower or "/block/map" in lower:
            cat = "tiles_maps_and_backgrounds"
        elif sub == "ui":
            cat = "ui_and_menus"
        elif "vdp1-" in name:
            return {
                "inferred_category": "bombs_items_or_vdp1_dumps",
                "origin_hypothesis": "saturn_vdp1_debugger_dump_lead",
                "classification_basis": "filename_inference",
                "saturn_provenance_verified": False,
            }
        elif any(tok in lower for tok in ("/players/", "/characters/", "bomura", "tirra", "chara")):
            cat = "characters_and_mounts"
        elif any(tok in lower for tok in ("mastergameenemies", "mujoe", "castle joe", "bomber dragon", "bomber debugon", "bomber bomb kami", "madbombercart")):
            cat = "enemies_and_bosses"
        elif any(tok in lower for tok in ("bomb", "fire", "item", "egg", "dino", "shadow")):
            cat = "bombs_items_and_effects"
        else:
            cat = "unknown"
        origin = (
            "unknown_pc_or_mockup_ui_lead"
            if "options images/" in lower
            else "community_rip_or_sheet_lead"
        )
        return {
            "inferred_category": cat,
            "origin_hypothesis": origin,
            "classification_basis": "directory_and_naming_inference",
            "saturn_provenance_verified": False,
        }

    # Root loose files
    if "guide by kaiju" in lower:
        return {
            "inferred_category": "reference_guide",
            "origin_hypothesis": "community_reference_guide_lead",
            "classification_basis": "filename_inference",
            "saturn_provenance_verified": False,
        }
    if any(tok in lower for tok in ("chara_bomberman",)):
        cat = "characters_and_animations"
    elif any(tok in lower for tok in ("arrow", "border", "options_panel", "outline", "panel", "title", "top10", "background", "blue", "pink", "quite_green")):
        cat = "ui_and_menus"
    else:
        cat = "unknown"
    return {
        "inferred_category": cat,
        "origin_hypothesis": "unscoped_root_file_lead",
        "classification_basis": "filename_inference",
        "saturn_provenance_verified": False,
    }


def build_provenance_records(root: Path) -> list[dict[str, Any]]:
    readme_path = root / "README.md"
    readme_text = ""
    readme_sha256 = None
    supplied_credits: list[str] = []
    if readme_path.is_file() and not readme_path.is_symlink():
        raw = readme_path.read_bytes()
        readme_sha256 = hashlib.sha256(raw).hexdigest()
        readme_text = raw.decode("utf-8", errors="replace").strip()
        for line in readme_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("* "):
                supplied_credits.append(stripped[2:].strip())

    return [
        {
            "scope_id": "readme-spriters-resource-credits",
            "applies_to_globs": ["images/Sprite Sheets/**", "images/Single Sprites/**"],
            "readme_sha256": readme_sha256,
            "supplied_source_text": "www.spriters-resource.com" if "spriters-resource.com" in readme_text else None,
            "supplied_contributors": supplied_credits,
            "provenance_status": "partially_credited_unverified_mapping",
            "license_evidence": "none",
            "distribution_permission": "unknown",
            "neptune_apache_2_0_applies": False,
            "unresolved_fields": [
                "per_file_contributor_mapping",
                "original_saturn_release_region_and_revision",
                "capture_emulator_or_decoder_method",
                "local_recolour_and_slicing_modifications",
                "redistribution_permission",
            ],
        },
        {
            "scope_id": "audio-cpk-and-aiff-rips",
            "applies_to_globs": ["audio/rips/BOMSS*.CPK", "audio/rips/M_*.AIF", "audio/rips/.goutputstream-*"],
            "readme_sha256": readme_sha256,
            "supplied_source_text": None,
            "supplied_contributors": [],
            "provenance_status": "uncredited_disc_format_candidates",
            "license_evidence": "none",
            "distribution_permission": "unknown",
            "neptune_apache_2_0_applies": False,
            "unresolved_fields": [
                "exact_disc_track_and_sector_match_against_462_lock",
                "usa_vs_japan_release_identity",
                "extraction_tool_provenance",
                "copyright_and_redistribution_status",
            ],
        },
        {
            "scope_id": "audio-audacity-projects-and-ogg",
            "applies_to_globs": ["audio/projects/**", "audio/rips/*.aup", "audio/rips/*.ogg"],
            "readme_sha256": readme_sha256,
            "supplied_source_text": None,
            "supplied_contributors": [],
            "provenance_status": "derived_audacity_projects_and_lossy_reencodes",
            "license_evidence": "none",
            "distribution_permission": "unknown",
            "neptune_apache_2_0_applies": False,
            "unresolved_fields": [
                "recording_source_emulator_or_game",
                "lossy_vorbis_generation_loss",
                "cue_and_loop_frame_timing",
                "redistribution_permission",
            ],
        },
        {
            "scope_id": "exports-gamemaker-dump-tree",
            "applies_to_globs": ["exports/**", "spr_b_white_0.png"],
            "readme_sha256": readme_sha256,
            "supplied_source_text": None,
            "supplied_contributors": [],
            "provenance_status": "non_saturn_gamemaker_export_structure",
            "license_evidence": "none",
            "distribution_permission": "unknown",
            "neptune_apache_2_0_applies": False,
            "unresolved_fields": [
                "exact_upstream_executable_and_version_probably_power_bomberman",
                "fan_artist_and_developer_authorship",
                "massive_internal_duplication_across_textures_and_grouped_text",
                "redistribution_permission",
            ],
        },
        {
            "scope_id": "repacked-characters-ui-and-misc",
            "applies_to_globs": ["characters/**", "images/UI/**", "images/maps/**", "images/other/**", "Stupid_Rat/**", "*"],
            "readme_sha256": readme_sha256,
            "supplied_source_text": "Animation reference guide by Kaiju.png (filename credit only)" if (root / "Animation reference guide by Kaiju.png").exists() else None,
            "supplied_contributors": ["Kaiju (inferred from filename only)"] if (root / "Animation reference guide by Kaiju.png").exists() else [],
            "provenance_status": "mixed_repacks_mockups_and_unattributed_files",
            "license_evidence": "none",
            "distribution_permission": "unknown",
            "neptune_apache_2_0_applies": False,
            "unresolved_fields": [
                "source_game_per_ui_bitmap_set",
                "author_and_license_for_custom_edits_and_xcf_mockups",
                "redistribution_permission",
            ],
        },
    ]


def _summarize_subset(files: list[dict[str, Any]], prefixes: tuple[str, ...], exact: set[str] | None = None) -> dict[str, Any]:
    exact = exact or set()
    matched = [
        item for item in files
        if item["path"] in exact or any(item["path"].startswith(prefix) for prefix in prefixes)
    ]
    formats = Counter(item["inspection"]["detected_format"] for item in matched)
    color_types = Counter(
        str(item["inspection"]["color_type"])
        for item in matched
        if item["inspection"].get("detected_format") == "png" and "color_type" in item["inspection"]
    )
    return {
        "matched_file_count": len(matched),
        "total_bytes": sum(item["bytes"] for item in matched),
        "unique_sha256_count": len({item["sha256"] for item in matched}),
        "formats": dict(sorted(formats.items())),
        "png_color_types": dict(sorted(color_types.items())),
        "sample_files": [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"], "dimensions": item["inspection"].get("dimensions")}
            for item in matched[:8]
        ],
    }


def build_candidate_gap_report(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "player-white-bomberman",
            "kind": "player_animation_set",
            "selected_paths": [
                "images/Sprite Sheets/characters/Character White Bomberman.png",
                "images/Single Sprites/players/WhiteBomberman/",
                "characters/chara/",
            ],
            "measured_inventory": _summarize_subset(
                files,
                prefixes=(
                    "images/Single Sprites/players/WhiteBomberman/",
                    "characters/chara/",
                ),
                exact={"images/Sprite Sheets/characters/Character White Bomberman.png"},
            ),
            "observed_in_static_files": [
                "1 composite sheet (Character White Bomberman.png), 85 unlabelled frame0..frame84.png slices, 92 named wbm-*.png slices, and 149 PNGs + 2 TexturePacker files under characters/chara/.",
                "Named state leads in wbm/ and chara/data/: walk (4 dirs, 3 frames each), carry_walk (north/south/west only in chara/ — east/carrying is absent), hold, jump, ride, idle, win/celebrate, lose/cry, defeat/explode, panic, stunned/dizzy, fly, and HUD portraits.",
                "Decoded PNG headers/streams are RGB/RGBA raster exports rather than raw Saturn VDP1 4bpp/8bpp indexed colour tables; ReplaceColour.bat indicates offline palette editing.",
            ],
            "missing_requires_27_28_runtime_evidence": [
                "Total authentic animation state denominator for USA and Japan releases (unknown from static PNGs; kick, punch, throw release, illness/curse flashes, campaign warp/cutscene states are unverified or absent).",
                "Exact frame ordering and per-frame durations in rational Saturn frame ticks (including speed-up/slow-down coupling to movement velocity).",
                "Per-frame sprite anchor/pivot offsets relative to authoritative collision/subpixel position and shadow layer.",
                "Original VDP1 character patterns, CLUT/palette RAM banks, colour-calculation/mesh flags, and hardware horizontal-flip vs distinct east/west art.",
                "Separate head/body or mount+rider VDP1 draw-command composition order.",
            ],
        },
        {
            "candidate_id": "campaign-room-normal-map1",
            "kind": "campaign_room",
            "selected_paths": [
                "images/Single Sprites/single player/map1/",
                "images/Single Sprites/Block/map1/",
            ],
            "measured_inventory": _summarize_subset(
                files,
                prefixes=(
                    "images/Single Sprites/single player/map1/",
                    "images/Single Sprites/Block/map1/",
                ),
            ),
            "observed_in_static_files": [
                "29 visual PNG slices under single player/map1/ (full.png 431,272 bytes plus numbered layer/prop slices, cart1..4.png, train1..4.png, water1..3.png, track/wheel/smoke) and 5 destructible-block PNGs under Block/map1/.",
                "Exact byte duplicates already present inside the slice: 2.png == 3.png (27,754 bytes), water1.png == water2.png == water3.png (7,347 bytes), smoke.png == smoke4.png (292 bytes), and block.png == block1.png (3,022 bytes).",
            ],
            "missing_requires_27_28_runtime_evidence": [
                "Exact stage/room identifier in USA vs Japan Normal Mode progression (e.g. World 1 Stage 1 room index and camera bounds).",
                "Authoritative tile collision grid, hard-wall vs soft-block coordinates, and minecart/train track Spline/cell pathing.",
                "Player 1 / Player 2 co-op spawn coordinates, enemy types, enemy initial positions, AI state tables, and hidden power-up spawn table.",
                "Switch/cart/train trigger logic, room-clear condition (destroy generators vs defeat enemies), exit portal activation, and next-room transition.",
                "VDP2 background plane scroll rates, tilemap planes, priority bits over/under sprites, and stage BGM/SFX trigger IDs.",
            ],
        },
        {
            "candidate_id": "battle-arena-standard-and-wide",
            "kind": "battle_arena",
            "selected_paths": [
                "images/maps/",
            ],
            "measured_inventory": _summarize_subset(
                files,
                prefixes=("images/maps/",),
            ),
            "observed_in_static_files": [
                "9 files under images/maps/: original.png and background1.png (exact byte duplicates, 14,761 bytes each), background-wide.png (4,413 bytes), double.png (45,231 bytes), battle stage blocks 1.png (810 bytes), plus HUD banner BMP/PNG/XCF mockups.",
                "Note: exports/roms to png/rm_battle_*.png and exports/tilesets/tl_map_*.png come from a non-Saturn GameMaker dump (including Reversi/Power Bomberman stages) and cannot be used as Saturn arena evidence.",
            ],
            "missing_requires_27_28_runtime_evidence": [
                "Exact tile grid dimensions and pixel-to-cell origin for standard (8-player) vs wide (Hi-Ten / 10-player) Saturn battle arenas.",
                "Per-seat spawn coordinates for all supported player counts and multitap port mappings.",
                "Soft-block spawn mask, random placement density/RNG consumption, and item drop table/counts per stage.",
                "Sudden-death (Hurry!) pressure-block start frame, drop cadence, spiral trajectory, and crush/bomb interaction precedence.",
                "Stage-specific hazard/conveyor/warp mechanics, VDP2 layer composition, and USA vs Japan regional rule differences.",
            ],
        },
    ]


def run_audit(
    root: Path,
    full_png_decode: bool = True,
    require_clean_git: bool = False,
    excluded_paths: list[Path] | None = None,
    saturn_lab_inventory_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute deterministic asset audit returning (private_manifest, compact_summary)."""
    if not root.is_dir() or root.is_symlink():
        raise AuditError(f"Asset root must be a real directory, not a symlink: {root}")

    git_snapshot = inspect_git_snapshot(root, require_clean=require_clean_git)

    # Reuse saturn_lab.inventory for byte hashing, symlink rejection, and duplicate grouping
    base_inv = saturn_lab_cli.inventory(root)
    excluded_abs = {p.absolute() for p in (excluded_paths or [])}
    if excluded_abs:
        filtered_files = [
            f for f in base_inv["files"]
            if (root / f["path"]).absolute() not in excluded_abs
        ]
        by_hash: dict[str, list[str]] = {}
        for f in filtered_files:
            by_hash.setdefault(f["sha256"], []).append(f["path"])
        base_inv = {
            "schema": base_inv["schema"],
            "file_count": len(filtered_files),
            "total_bytes": sum(f["bytes"] for f in filtered_files),
            "files": filtered_files,
            "duplicate_groups": sorted(sorted(paths) for paths in by_hash.values() if len(paths) > 1),
            "provenance": "unverified",
        }

    saturn_lab_sha256 = None
    if saturn_lab_inventory_path is not None:
        raw_lab = saturn_lab_inventory_path.read_bytes()
        saturn_lab_sha256 = hashlib.sha256(raw_lab).hexdigest()
        loaded_lab = json.loads(raw_lab.decode("utf-8"))
        if loaded_lab.get("file_count") != base_inv["file_count"] or loaded_lab.get("total_bytes") != base_inv["total_bytes"]:
            raise AuditError("Supplied saturn_lab inventory disagrees with fresh scan counts/bytes")

    # Map path -> deterministic duplicate group ID (dup-00001 ..)
    path_to_dup_group: dict[str, str] = {}
    duplicate_groups_detailed: list[dict[str, Any]] = []
    size_by_path = {f["path"]: f["bytes"] for f in base_inv["files"]}
    hash_by_path = {f["path"]: f["sha256"] for f in base_inv["files"]}
    for idx, group in enumerate(base_inv["duplicate_groups"], 1):
        gid = f"dup-{idx:05d}"
        for rel in group:
            path_to_dup_group[rel] = gid
        duplicate_groups_detailed.append(
            {
                "group_id": gid,
                "sha256": hash_by_path[group[0]],
                "bytes_each": size_by_path[group[0]],
                "count": len(group),
                "redundant_bytes": (len(group) - 1) * size_by_path[group[0]],
                "paths": group,
            }
        )

    # Memoize byte inspection by (sha256, ext, full_png_decode) for speed & determinism
    inspection_cache: dict[tuple[str, str, bool], dict[str, Any]] = {}
    audited_files: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    ext_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    decode_level_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    origin_counts: Counter[str] = Counter()
    top_dir_counts: Counter[str] = Counter()
    top_dir_bytes: Counter[str] = Counter()

    for item in base_inv["files"]:
        rel = item["path"]
        full_path = saturn_lab_cli.confined_file(root, rel)
        ext = full_path.suffix.lower() or "(none)"
        cache_key = (item["sha256"], ext, full_png_decode)
        if cache_key not in inspection_cache:
            inspection_cache[cache_key] = inspect_file_bytes(full_path, full_png_decode=full_png_decode)
        insp = dict(inspection_cache[cache_key])
        lead = classify_path_lead(rel, insp["detected_format"])

        record: dict[str, Any] = {
            "path": rel,
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "duplicate_group_id": path_to_dup_group.get(rel),
            "inspection": insp,
            "classification": lead,
            "provenance_status": "unverified",
        }
        audited_files.append(record)

        top_dir = rel.split("/")[0] if "/" in rel else "(root)"
        top_dir_counts[top_dir] += 1
        top_dir_bytes[top_dir] += item["bytes"]
        ext_counts[ext] += 1
        format_counts[insp["detected_format"]] += 1
        decode_level_counts[insp["decode_level"]] += 1
        category_counts[lead["inferred_category"]] += 1
        origin_counts[lead["origin_hypothesis"]] += 1

        if not insp["valid"] or not insp["extension_matches_format"]:
            anomalies.append(
                {
                    "path": rel,
                    "bytes": item["bytes"],
                    "sha256": item["sha256"],
                    "detected_format": insp["detected_format"],
                    "extension": insp["extension"],
                    "valid": insp["valid"],
                    "extension_matches_format": insp["extension_matches_format"],
                    "error": insp.get("error"),
                }
            )

    provenance_scopes = build_provenance_records(root)
    candidate_gaps = build_candidate_gap_report(audited_files)

    unique_hashes = {f["sha256"] for f in audited_files}
    redundant_file_count = len(audited_files) - len(unique_hashes)
    redundant_bytes = sum(g["redundant_bytes"] for g in duplicate_groups_detailed)

    # Cross-directory duplicate summary (e.g., exports/grouped text vs exports/textures)
    pair_dups: Counter[str] = Counter()
    for grp in duplicate_groups_detailed:
        prefixes = sorted({"/".join(p.split("/")[:2]) if "/" in p else "(root)" for p in grp["paths"]})
        if len(prefixes) > 1:
            pair_dups[" <-> ".join(prefixes)] += 1

    private_manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "tool": {
            "name": "tools/asset_audit/cli.py",
            "decoder_version": DECODER_VERSION,
            "full_png_decode": full_png_decode,
        },
        "source_snapshot": git_snapshot,
        "saturn_lab_inventory_sha256": saturn_lab_sha256,
        "totals": {
            "file_count": len(audited_files),
            "total_bytes": base_inv["total_bytes"],
            "unique_sha256_count": len(unique_hashes),
            "duplicate_group_count": len(duplicate_groups_detailed),
            "redundant_duplicate_files": redundant_file_count,
            "redundant_duplicate_bytes": redundant_bytes,
            "invalid_or_corrupt_count": sum(1 for f in audited_files if not f["inspection"]["valid"]),
            "extension_mismatch_count": sum(1 for f in audited_files if not f["inspection"]["extension_matches_format"]),
        },
        "anomalies": anomalies,
        "provenance_scopes": provenance_scopes,
        "candidate_gap_sets": candidate_gaps,
        "duplicate_groups": duplicate_groups_detailed,
        "files": audited_files,
    }

    manifest_bytes = (json.dumps(private_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

    largest_dup_groups = sorted(
        duplicate_groups_detailed,
        key=lambda g: (-g["redundant_bytes"], -g["count"], g["group_id"]),
    )[:15]

    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "tool": private_manifest["tool"],
        "source_repository": "elgansayer/SaturnBomberman-Assets",
        "source_snapshot": git_snapshot,
        "private_manifest_sha256": manifest_sha256,
        "saturn_lab_inventory_sha256": saturn_lab_sha256,
        "totals": private_manifest["totals"],
        "by_top_level_entry": {
            k: {"files": top_dir_counts[k], "bytes": top_dir_bytes[k]}
            for k in sorted(top_dir_counts)
        },
        "by_extension": dict(sorted(ext_counts.items())),
        "by_detected_format": dict(sorted(format_counts.items())),
        "by_decode_level": dict(sorted(decode_level_counts.items())),
        "by_inferred_category": dict(sorted(category_counts.items())),
        "by_origin_hypothesis": dict(sorted(origin_counts.items())),
        "cross_directory_duplicate_group_counts": dict(
            sorted(pair_dups.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        ),
        "largest_duplicate_groups_sample": [
            {
                "group_id": g["group_id"],
                "sha256": g["sha256"],
                "bytes_each": g["bytes_each"],
                "count": g["count"],
                "redundant_bytes": g["redundant_bytes"],
                "sample_paths": g["paths"][:4],
            }
            for g in largest_dup_groups
        ],
        "anomalies": anomalies,
        "provenance_scopes": provenance_scopes,
        "candidate_gap_sets": candidate_gaps,
        "boundaries": {
            "saturn_fidelity_certified": False,
            "redistribution_licence_established": False,
            "raw_assets_committed_to_neptune": False,
            "notes": [
                "Filename and directory categories are unverified leads, not proof of Sega Saturn origin.",
                "Neither Neptune's Apache-2.0 licence nor README Spriters Resource credits grant asset redistribution rights.",
                "exports/ (46,351 files) exhibits GameMaker Studio / UndertaleModTool dump layout rather than Saturn disc data.",
            ],
        },
    }
    return private_manifest, summary


def write_json_atomic(data: dict[str, Any], output: Path) -> str:
    """Write deterministic sorted JSON atomically, refusing symlinks or foreign schemas."""
    if output.is_symlink():
        raise AuditError(f"Refusing to write through symlink: {output}")
    if output.exists():
        if not output.is_file():
            raise AuditError(f"Output path exists and is not a regular file: {output}")
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise AuditError(f"Refusing to overwrite non-JSON file: {output}") from exc
        if not isinstance(existing, dict) or existing.get("schema") != data.get("schema"):
            raise AuditError(f"Refusing to overwrite JSON with different schema at {output}")

    body = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as handle:
            tmp_name = handle.name
            handle.write(body)
        os.replace(tmp_name, output)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return digest


def verify_summary(data: Any) -> dict[str, Any]:
    """Fail-closed schema and provenance-boundary validator for committed summary JSON."""
    if not isinstance(data, dict) or data.get("schema") != SUMMARY_SCHEMA:
        raise AuditError("Unsupported or missing asset-audit summary schema")
    if not isinstance(data.get("private_manifest_sha256"), str) or not SHA256_RE.fullmatch(data["private_manifest_sha256"]):
        raise AuditError("Missing or invalid private_manifest_sha256")
    snap = data.get("source_snapshot")
    if not isinstance(snap, dict):
        raise AuditError("Missing source_snapshot object")
    if snap.get("present") is True:
        if not isinstance(snap.get("commit_sha"), str) or not COMMIT_RE.fullmatch(snap["commit_sha"]):
            raise AuditError("Invalid git commit_sha in source_snapshot")
        if not isinstance(snap.get("tree_sha"), str) or not COMMIT_RE.fullmatch(snap["tree_sha"]):
            raise AuditError("Invalid git tree_sha in source_snapshot")

    totals = data.get("totals")
    if not isinstance(totals, dict) or type(totals.get("file_count")) is not int or totals["file_count"] <= 0:
        raise AuditError("Summary totals must report a positive integer file_count")
    if totals.get("unique_sha256_count", 0) + totals.get("redundant_duplicate_files", -1) != totals["file_count"]:
        raise AuditError("Inconsistent unique_sha256_count + redundant_duplicate_files != file_count")

    scopes = data.get("provenance_scopes")
    if not isinstance(scopes, list) or not scopes:
        raise AuditError("Summary must contain non-empty provenance_scopes")
    for scope in scopes:
        if not isinstance(scope, dict) or not scope.get("scope_id"):
            raise AuditError("Invalid provenance scope record")
        if scope.get("neptune_apache_2_0_applies") is not False:
            raise AuditError(f"Scope {scope.get('scope_id')} illegally applies Neptune Apache-2.0 to reference assets")
        if scope.get("license_evidence") == "none" and scope.get("distribution_permission") not in ("unknown", "unestablished", "prohibited"):
            raise AuditError(f"Scope {scope.get('scope_id')} claims distribution permission without licence evidence")

    boundaries = data.get("boundaries")
    if not isinstance(boundaries, dict) or boundaries.get("saturn_fidelity_certified") is not False:
        raise AuditError("Asset inventory summary cannot certify Saturn runtime fidelity")
    if boundaries.get("raw_assets_committed_to_neptune") is not False:
        raise AuditError("Raw assets must not be committed to Neptune")

    gaps = data.get("candidate_gap_sets")
    if not isinstance(gaps, list) or len(gaps) < 3:
        raise AuditError("Summary must include player, campaign-room, and battle-arena gap sets")
    required_kinds = {"player_animation_set", "campaign_room", "battle_arena"}
    seen_kinds = {g.get("kind") for g in gaps if isinstance(g, dict)}
    if not required_kinds.issubset(seen_kinds):
        raise AuditError(f"Missing required candidate gap kinds: {required_kinds - seen_kinds}")
    for g in gaps:
        if not g.get("missing_requires_27_28_runtime_evidence"):
            raise AuditError(f"Candidate {g.get('candidate_id')} omits unresolved runtime gaps")
    return data


def verify_ledger(data: Any) -> dict[str, Any]:
    """Fail-closed validator for the Saturn reconstruction coverage and unknowns ledger."""
    if not isinstance(data, dict) or data.get("schema") != LEDGER_SCHEMA:
        raise AuditError("Unsupported or missing saturn-coverage-ledger schema")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != {"usa", "japan"}:
        raise AuditError("Ledger must maintain separate 'usa' and 'japan' reference profiles")
    policy = data.get("accounting_policy")
    if not isinstance(policy, dict):
        raise AuditError("Missing accounting_policy")
    if policy.get("never_claim_100_percent_without_verified_denominator") is not True:
        raise AuditError("Ledger must forbid 100% coverage claims when denominators are unverified")
    if policy.get("forced_or_debug_states_counted_as_normal_reachable") is not False:
        raise AuditError("Forced/debug states must not be counted as normal reachable coverage")

    domains = data.get("domains")
    if not isinstance(domains, list) or not domains:
        raise AuditError("Ledger must declare non-empty coverage domains")
    seen_ids: set[str] = set()
    for dom in domains:
        if not isinstance(dom, dict) or not isinstance(dom.get("domain_id"), str) or not dom["domain_id"]:
            raise AuditError("Invalid domain record")
        did = dom["domain_id"]
        if did in seen_ids:
            raise AuditError(f"Duplicate domain_id: {did}")
        seen_ids.add(did)
        if not dom.get("backlog_ids") or not dom.get("issues"):
            raise AuditError(f"Domain {did} must reference existing backlog_ids and issues")
        for region in ("usa", "japan"):
            reg = dom.get(region)
            if not isinstance(reg, dict):
                raise AuditError(f"Domain {did} missing {region} profile status")
            denom = reg.get("denominator")
            if denom != "unknown" and (type(denom) is not int or denom <= 0):
                raise AuditError(f"Domain {did}.{region} denominator must be 'unknown' or positive int")
            if reg.get("confidence") not in CONFIDENCE_LEVELS:
                raise AuditError(f"Domain {did}.{region} has invalid confidence {reg.get('confidence')!r}")
            for counter in ("observed", "decoded", "validated", "uploaded", "implemented_and_compared", "forced_or_unreachable"):
                val = reg.get(counter)
                if type(val) is not int or val < 0:
                    raise AuditError(f"Domain {did}.{region}.{counter} must be a non-negative integer")
                if isinstance(denom, int) and counter != "forced_or_unreachable" and val > denom:
                    raise AuditError(f"Domain {did}.{region}.{counter} exceeds denominator {denom}")

    exps = data.get("next_experiments")
    if not isinstance(exps, list) or not exps:
        raise AuditError("Ledger must specify at least one concrete next experiment")
    for exp in exps:
        if not isinstance(exp, dict):
            raise AuditError("Invalid experiment record")
        for req in ("experiment_id", "status", "hypothesis", "controlled_initial_state", "changed_variable"):
            if not isinstance(exp.get(req), str) or not exp[req].strip():
                raise AuditError(f"Experiment missing {req}")
        for req_list in ("expected_observations", "failure_conditions"):
            if not isinstance(exp.get(req_list), list) or not exp[req_list]:
                raise AuditError(f"Experiment {exp['experiment_id']} missing non-empty {req_list}")
    return data
