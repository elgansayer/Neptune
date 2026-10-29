# Gemini asset audit, provenance, and reconstruction gap evidence (`#463` / `#464`)

Issues: `#463` (first bounded milestone of `#464`), parent `#26`, informs `#28` and `#46`.
Worker: installed VPS Antigravity CLI (`agy 1.4.10`, Gemini 4 Argon High), session `7826170c-5914-4551-aad9-57664407b010`.
Base `main`: `957491ec44cec8b4c14e6bcfc461ed9cca3eb0f8` (fast-forwarded from initial `b0b9f97cd134f8b5014eb85d6ef0c999466a9414` after `#465` merged).
Audit report and gap tables: [docs/restart/asset-audit/README.md](../asset-audit/README.md).
Committed summary manifest: [docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json](../asset-audit/saturn-assets-b55b5a55.summary.json).
Committed `#464` coverage ledger: [docs/restart/asset-audit/saturn-coverage-ledger.json](../asset-audit/saturn-coverage-ledger.json).

## Pinned inputs and coordination

- **Read-only asset source**: `/home/dev/neptune-asset-source` (`elgansayer/SaturnBomberman-Assets`, verified `visibility: private` via GitHub API), commit `b55b5a55a4c76c73f4622ffcd20d92bf4755d8b3`, tree `7d265616d71d98b6f5e8754db05334e22cdcba60`, clean working tree before and after execution.
- **Codex coordination**: Preserved Codex's merged `#121` (`PR #465`, `957491ec44cec8b4c14e6bcfc461ed9cca3eb0f8`), now-active `#462` (`restart/real-saturn-inputs-462`), queued `#27` (libretro bridge), and stood-down `/home/dev/neptune-gemini-463*` artifacts untouched. Because `#462` is actively being executed by Codex (`#462#issuecomment-6505730926`), per `#464` step 4 no media hashes were fabricated and Codex's `#462` input task was not duplicated.
- **Resource bounds**: Host measured `8.5 GiB` free disk (`77%` used of `38 GiB`) and `3.4 GiB` available RAM (`7.6 GiB` total). Ran lightweight local Python 3.13.5 (`zlib 1.3.1`) inspection only; zero paid fallback, zero subagents, zero model uploads of art/audio/binaries, and zero heavy local Godot/emulator jobs.

## Executed commands and repeatability digests

Commands executed from `/home/dev/neptune-gemini-research` with `PRIV=/home/dev/neptune-gemini-research-private/463`:

```sh
python3 tools/saturn_lab/cli.py inventory /home/dev/neptune-asset-source --output "$PRIV/saturn_lab_inventory_run1.json"
python3 tools/saturn_lab/cli.py inventory /home/dev/neptune-asset-source --output "$PRIV/saturn_lab_inventory_run2.json"
python3 tools/asset_audit/cli.py audit /home/dev/neptune-asset-source \
  --saturn-lab-inventory "$PRIV/saturn_lab_inventory_run1.json" \
  --private-manifest "$PRIV/asset_audit_manifest_run1.json" \
  --summary-output docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json \
  --require-clean-git
python3 tools/asset_audit/cli.py audit /home/dev/neptune-asset-source \
  --saturn-lab-inventory "$PRIV/saturn_lab_inventory_run2.json" \
  --private-manifest "$PRIV/asset_audit_manifest_run2.json" \
  --summary-output "$PRIV/saturn-assets-b55b5a55.summary.run2.json" \
  --require-clean-git
python3 tools/asset_audit/cli.py verify-summary docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json
python3 tools/asset_audit/cli.py verify-ledger docs/restart/asset-audit/saturn-coverage-ledger.json
python3 tools/asset_audit/check.py
python3 tools/saturn_lab/check.py
python3 tools/research_catalog/check.py
python3 tools/research_catalog/cli.py validate
python3 tools/factory/check.py
python3 tools/merge_gate/check.py
```

- `saturn_lab_inventory_run1.json` == `run2.json` SHA-256: `3d27c1450f3044e867546479c4dc22cc7195237a31bcfbd5739700279026cd9e`
- `asset_audit_manifest_run1.json` == `run2.json` SHA-256: `c82ee4ddbbc036efe82e85b1b8be96937f7ad527376a728b0c350f99731b8537`
- `saturn-assets-b55b5a55.summary.json` == `run2` SHA-256: `0a916c817c84d077adef214416471978c8da24fa4b201703005e82c4d3099424`

## Key findings and detected failures

1. **Scale & duplication**: `50,407` files (`485,234,959` bytes), `23,622` unique SHA-256 digests, `12,209` duplicate groups (`26,785` redundant copies = `53.14%` of files; `80,234,632` redundant bytes).
2. **Non-Saturn bulk export isolation**: `exports/` (`46,351` files / `91.95%` of file count) + root `spr_b_white_0.png` contain a GameMaker Studio / UndertaleModTool dump (`shd_*` HLSL9/HLSL11/GLSL shaders, `rm_battle_*` room exports, `tl_map_alpha_reversi.png`, `jsonstr.json`/`strings.txt`), not Sega Saturn disc extractions.
3. **Real corrupt/mismatched files caught**:
   - `audio/rips/.goutputstream-4XSJ30` (`2,097,152` B): truncated `2 MiB` GIO temporary copy of `audio/rips/BOMSS2.CPK` (`STAB` sample table requires `32,202,056` B; `valid=false`).
   - `images/UI/map/GO-G.png` and `images/UI/map/GO-O.png` (`1,782` B each): Windows `BM` (`BMP`) bitmaps saved with `.png` extensions (`extension_matches_format=false`).
4. **Synthetic negative regressions verified (`tools/asset_audit/check.py`, 10 tests)**: corrupt PNG IDAT zlib stream (passes `--header-only-png`, fails `full_stream`), bad PNG chunk CRC, wrong scanline byte length, truncated Sega `FILM` `.cpk`, BMP-as-PNG magic mismatch, symlink/unreadable input rejection, dirty/untracked git rejection, output-inside-source rejection, blanket `Apache-2.0`/licence/fidelity claim rejection, and blended-profile/denominator overflow ledger rejection.

## Boundaries and handoff

- **To `#26` / `#462`**: Asset-inventory half of `#26` is evidenced; `#26` remains open until Codex completes `#462` media/BIOS/core input locks. `BOMSS1..3.CPK` and `M_007..M_067.AIF` are queued for byte/sector comparison against `#462` locked discs in `EXP-SAT-DISC-001`.
- **To `#28` / `#29` / `#46`**: Candidate player (`player-white-bomberman`), campaign room (`campaign-room-normal-map1`), and battle arena (`battle-arena-standard-and-wide`) static leads lack frame durations, anchors, indexed VDP1/VDP2 palettes, collision maps, spawns, triggers, and regional verification, and carry no redistribution licence. No Saturn runtime parity, extraction completeness, or public-release clearance is claimed.
