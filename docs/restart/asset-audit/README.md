# Saturn Bomberman existing-asset audit, provenance, and reconstruction gaps (`#463` / `#464`)

Audited snapshot of private repository `elgansayer/SaturnBomberman-Assets` (`visibility: private`):
- **Commit SHA**: `b55b5a55a4c76c73f4622ffcd20d92bf4755d8b3`
- **Tree SHA**: `7d265616d71d98b6f5e8754db05334e22cdcba60`
- **Working tree state**: clean (`0` dirty tracked files, `0` untracked files; read-only throughout `#463`)
- **`tools/saturn_lab/cli.py inventory` SHA-256** (identical across 2 runs): `3d27c1450f3044e867546479c4dc22cc7195237a31bcfbd5739700279026cd9e`
- **Full private per-file audit manifest SHA-256** (identical across 2 runs): `c82ee4ddbbc036efe82e85b1b8be96937f7ad527376a728b0c350f99731b8537`
- **Committed compact summary** ([`saturn-assets-b55b5a55.summary.json`](saturn-assets-b55b5a55.summary.json)): `0a916c817c84d077adef214416471978c8da24fa4b201703005e82c4d3099424`
- **Machine-readable `#464` coverage & unknowns ledger**: [`saturn-coverage-ledger.json`](saturn-coverage-ledger.json)

No source asset, audio file, disc image, BIOS, or capture was modified or uploaded to any model provider.

---

## 1. Byte inventory, format verification, and duplication summary

| Metric | Value | Notes |
| --- | ---: | --- |
| Total files | `50,407` | Excludes `.git` |
| Total bytes | `485,234,959` | ~462.76 MiB |
| Unique SHA-256 payloads | `23,622` | 46.86% unique files |
| Exact-duplicate groups | `12,209` | Covering `38,994` files |
| Redundant duplicate copies | `26,785` | **53.14%** of all files (`80,234,632` redundant bytes) |
| Full PNG CRC32 + `zlib` IDAT stream verified | `50,004` | Verified via `python-stdlib/3.13.5/zlib-1.3.1` |
| Corrupt / truncated files detected | `1` | `audio/rips/.goutputstream-4XSJ30` (truncated Sega `FILM` 1.04 stream) |
| Extension-vs-magic mismatches | `3` | `.goutputstream-4XSJ30` (no ext, `FILM`) + `images/UI/map/GO-G.png` & `GO-O.png` (BMP `BM` magic named `.png`) |

### Top-level directory breakdown & origin assessment

| Top-level entry | Files | Bytes | Observed container structures | Inferred origin status (`saturn_provenance_verified = false`) |
| --- | ---: | ---: | --- | --- |
| `exports/` | `46,351` | `309,384,112` | PNG (`46,235`), HLSL/GLSL shader `.txt` (`90`) + `.bin` (`22`), `jsonstr.json`, `strings.txt`, `tl_map_alpha_reversi.png`, `rm_battle_*.png` | **Non-Saturn GameMaker Studio / UndertaleModTool dump** (likely *Power Bomberman* — includes Reversi tileset, `shd_*` HLSL9/HLSL11/GLSL shaders, `rm_*` rooms, and `10,615` cross-folder duplicate groups across `grouped text/`, `textures/`, and `sprites/`). Must **not** be treated as Sega Saturn assets. |
| `images/` | `3,567` | `12,393,871` | PNG (`3,440`), BMP (`53`, two misnamed `.png`), Godot `.import` (`50`), XML `.plist` (`5`), OLE2 `Thumbs.db` (`4`), `.json` (`2`), `.xcf` (`2`), `.avif` (`2`), `.txt` (`2`), `.bat` (`1`), `.gif` (`1`), `.jpeg` (`1`) | Mixed community sprite-sheet rips (`Sprite Sheets/`, `Single Sprites/`), 5 emulator VDP1 debugger dumps (`images/other/vdp1-418..554.png`), GIMP UI mockups, and PC/Atomic-style `BMP` UI buttons (`images/UI/options images/`). |
| `characters/` | `302` | `246,994` | PNG (`298`), TexturePacker `.tps` (`2`) + `.tpsheet` (`2`) | Repacked TexturePacker atlases (`chara/` and `robin_hood/`); `62` PNGs are byte-identical across both character folders. |
| `audio/` | `161` | `162,175,012` | Sega `FILM` 1.04 (`4`: 3 valid `.CPK` + 1 truncated `.goutputstream-4XSJ30`), AIFF (`19`, 44.1 kHz), Audacity `.aup` (`27`) + `.au` (`102`), Ogg Vorbis (`9`) | `BOMSS1..3.CPK` (`320x160` Cinepak `cvid`, 22,050 Hz stereo) and `M_007..M_067.AIF` are candidate Saturn disc rips awaiting `#462` sector/hash cross-check; `.aup`/`.au` and `.ogg` are derived Audacity edits and lossy re-encodes. |
| `(root)` | `25` | `614,451` | PNG (`23`), `README.md` (`1`), `window-options.xcf` (`1`) | Loose UI mockups, `Animation reference guide by Kaiju.png`, and `spr_b_white_0.png` (exact duplicate of `exports/` GameMaker sprite). |
| `Stupid_Rat/` | `1` | `420,519` | PNG (`1`) | Unattributed non-Saturn image (`Stupidrat.png`). |

### Concrete file anomalies detected by byte/structure inspection

1. `audio/rips/.goutputstream-4XSJ30` (`2,097,152` bytes, SHA-256 `98d4cae43f1a285dcf4c0b66102b254e02ea03759e838ae9f09e1def022f22f3`):
   - Byte-identical to the first `2 MiB` of `audio/rips/BOMSS2.CPK` (`32,202,056` bytes). Its Sega `FILM` `1.04` `STAB` sample table requires `32,202,056` bytes, proving an interrupted GLib/GIO output stream copy.
2. `images/UI/map/GO-G.png` (`1,782` bytes, SHA-256 `79d081afd999a295b837e64aee6f7c337bdb2a48ce24a441acb593344684ced5`) and `images/UI/map/GO-O.png` (`1,782` bytes, SHA-256 `2fa0b0cfe2c24c76ef6e5c016696afd348ed5ecf4d164badf9f338d0ee44b481`):
   - Carry `.png` extensions but contain valid Windows `BM` (`BMP`) headers and pixel data.

---

## 2. Scoped provenance and licence boundaries

| Scope ID | Path coverage | Supplied credit / source text | Licence evidence | Redistribution status | Key unresolved fields |
| --- | --- | --- | --- | --- | --- |
| `readme-spriters-resource-credits` | `images/Sprite Sheets/**`, `images/Single Sprites/**` | `README.md` thanks `Ragey`, `Pulse Commander`, `PlayBud101` (`www.spriters-resource.com`) | `none` | `unknown` (`Apache-2.0` inapplicable) | Per-file contributor mapping, USA vs Japan release/revision, ripper emulator settings, local `ReplaceColour` edits, publisher rights |
| `audio-cpk-and-aiff-rips` | `audio/rips/BOMSS*.CPK`, `audio/rips/M_*.AIF`, `.goutputstream-*` | None | `none` | `unknown` (`Apache-2.0` inapplicable) | Exact byte/sector match against `#462` USA/Japan discs, extraction tool, publisher rights |
| `audio-audacity-projects-and-ogg` | `audio/projects/**`, `audio/rips/*.aup`, `audio/rips/*.ogg` | None | `none` | `unknown` (`Apache-2.0` inapplicable) | Recording source, Vorbis generation loss, original SCSP/CD loop cues |
| `exports-gamemaker-dump-tree` | `exports/**`, `spr_b_white_0.png` | None | `none` | `unknown` (`Apache-2.0` inapplicable) | Exact GameMaker `data.win` version (inferred *Power Bomberman*), fan/original authorship |
| `repacked-characters-ui-and-misc` | `characters/**`, `images/UI/**`, `images/maps/**`, `images/other/**`, `Stupid_Rat/**`, root files | Filename string `"Animation reference guide by Kaiju.png"` only | `none` | `unknown` (`Apache-2.0` inapplicable) | Source game per UI BMP set, mockup authors, redistribution terms |

---

## 3. Reconstruction gap tables (handoff to `#27` and `#28`)

### A. Candidate player animation set: `player-white-bomberman`

- **Selected static leads**: `images/Sprite Sheets/characters/Character White Bomberman.png` (`17,594` B), `images/Single Sprites/players/WhiteBomberman/` (`179` files), `characters/chara/` (`151` files) — `331` files total (`313` unique SHA-256s).

| Reconstruction dimension | Observed in static files | Missing — requires `#27` / `#28` runtime & disc evidence |
| --- | --- | --- |
| State inventory & denominator | Named slices cover `walk` (N/S/E/W, 3 frames), `carry_walk` (missing `east/carrying` in `chara/`), `hold`, `jump`, `ride`, `ride_win` (missing `ride_loss` vs `robin_hood/`), `idle`, `win`/`celebrate`, `lose`/`cry`, `defeat`/`explode`, `panic`, `stunned`/`dizzy`, `fly`, HUD icons, plus `85` unlabelled `frame0..84.png`. | True animation state count in USA and Japan releases (`unknown` denominator); `kick`, `punch`, `throw` release, illness/curse flashes, drowned/crushed deaths, and campaign warp/cutscene states require runtime/table extraction. |
| Frame ordering & durations | Sequential filename suffixes (`_0.._2`, `-01..-09`) only; `chara.tpsheet` lists atlas rectangles without game ticks. | Exact state-table frame sequences, loop points, and per-frame tick durations (including velocity-coupled walk cadence). |
| Anchors / pivots & hitboxes | Cropped `33x33` or tight-trimmed bounding boxes; no origin metadata. | VDP1 local draw offsets relative to authoritative subpixel position, shadow offset, and hurtbox/collision extents. |
| Palettes & colour modes | Converted to 24/32-bit RGB/RGBA (`235` files) or arbitrary 8-bit PNG palettes (`93` files); `ReplaceColour.bat` shows manual recolouring. | Original Saturn VDP1 4bpp/8bpp indexed character data, CLUT RAM banks, player slot palettes, mesh/half-transparency flags, and hardware H-flip flags. |
| Multi-part composition | Isolated `wbm-head-*` slices exist alongside whole-body frames without assembly rules. | Exact VDP1 command draw order for head/body, carried bombs, and mount+rider (`Tirra`) layering. |

### B. Candidate campaign room: `campaign-room-normal-map1`

- **Selected static leads**: `images/Single Sprites/single player/map1/` (`29` files) and `images/Single Sprites/Block/map1/` (`5` files) — `34` PNGs (`31` unique SHA-256s; `2,053,305` B).

| Reconstruction dimension | Observed in static files | Missing — requires `#27` / `#28` runtime & disc evidence |
| --- | --- | --- |
| Identity & regional mapping | Folder named `single player/map1`; composite `full.png` (`431,272` B) + `320x320` layer quadrants and minecart/train props. | Exact USA/Japan Normal Mode stage ID, world/sub-stage index, and regional parameter comparison. |
| Tile layers & VDP2 composition | Pre-rendered RGB/RGBA crops (`water1..3.png` are byte-identical; `2.png == 3.png`). | VDP2 NBG0/NBG1 pattern names, palette banks, scroll registers, water/smoke animation cycles, and sprite-vs-BG priority bits. |
| Collision, bounds & tracks | None (raster pixels only). | Authoritative tile collision grid, hard-wall vs soft-block coordinates (`block.png == block1.png`), camera bounds, and minecart/train path cells. |
| Spawns, enemies & items | None. | P1/P2 spawn coordinates, enemy roster/positions/AI seeds, soft-block density, and hidden power-up table. |
| Triggers, clear rule & transitions | Prop graphics (`cart1..4.png`, `train1..4.png`, `track.png`) suggest interactive rail mechanics. | Switch/cart/train state machine, damage/crush rules, clear condition, exit reveal/activation, and next-room transition timing. |

### C. Candidate battle arena: `battle-arena-standard-and-wide`

- **Selected static leads**: `images/maps/` (`9` files, `8` unique SHA-256s, `105,912` B; `original.png == background1.png` at `336x224`, `background-wide.png` at `320x224`, `double.png` at `640x448`, `battle stage blocks 1.png` at `192x40`).
- **Explicit exclusion**: `exports/roms to png/rm_battle_*.png` and `exports/tilesets/tl_map_*.png` are excluded as non-Saturn GameMaker dumps.

| Reconstruction dimension | Observed in static files | Missing — requires `#27` / `#28` runtime & disc evidence |
| --- | --- | --- |
| Stage & mode geometry | Cropped `336x224`, `320x224`, and `640x448` background rasters plus a `192x40` block strip and GIMP `.xcf` HUD banner edit. | Exact grid dimensions (rows/columns), tile size, and playfield origin for standard (up to 8P) vs wide/Hi-Ten (up to 10P) modes. |
| Spawns & controller mapping | None. | Exact spawn cell/subpixel coordinates per seat and player-count configuration across both Saturn multitap ports. |
| Soft blocks & item pool | Visual soft/hard block strip (`battle stage blocks 1.png`) only. | Fixed pillar mask, random soft-block count/RNG placement, and stage-specific power-up drop counts/weights. |
| Sudden death (`Hurry!`) & timers | None. | Round timer options, `Hurry!` warning trigger frame, falling-block start tick, drop interval, spiral path, and crush/bomb precedence. |
| Stage gimmicks & regional parity | None. | Stage-specific mechanics (conveyors, warps, roofs, bounce tiles, etc.) and USA vs Japan rule verification. |

---

## 4. Initial `#464` coverage & unknowns summary

All domain denominators remain `"unknown"` (except the `1` harness per region under `#27`) until `#462` locks the USA/Japan discs and `EXP-SAT-DISC-001` parses Track 01's `IP.BIN` and ISO-9660 file tables. Forced/debug states are tracked separately (`forced_or_unreachable: 0`) and never counted toward normal reachability. See [`saturn-coverage-ledger.json`](saturn-coverage-ledger.json) for full per-domain counters and the next three bounded experiments (`EXP-SAT-DISC-001`, `EXP-SAT-VDP-002`, `EXP-SAT-TRACE-003`).
