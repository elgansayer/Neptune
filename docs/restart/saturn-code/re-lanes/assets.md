LANE-STATUS: ACTIVE

# Lane ledger: assets (graphics, animation, stage data, text, movies)

Scope: every non-audio asset of Saturn Bomberman, USA MK-81070 V1.003
first, with Japan T-14302G V1.000 where it differs. That covers VDP1 sprites
and palettes, sprite animation tables, VDP2 cells, maps and backgrounds, stage
data, fonts and text, UI layouts and the FILM movies. Audio banks and files
are classified here but owned by `sound-68k`; executables are classified here
but owned by `usa-code` and `code-map`. Issues: #485, #486, #487, #489, #494,
#28 and the REF inventories #395–#399. Gemini's #464 is read-only.

Outputs live only in the private `elgansayer/saturn-bomberman-decomp`
repository (`assets/usa/…`, `assets/japan/…`, recipes in `tools/assets/`,
progress in `docs/progress/assets.md`). This ledger records counts, formats
in our own words and private commits, with no game bytes.

## Denominator

Every file and byte range on the disc must be classified, and every asset
inside it extracted by a deterministic recipe with a manifest (source
file/offset/hash → output hash).

### Disc files

| Release | ISO files | Unknown | Notes |
| --- | ---: | ---: | --- |
| USA | 430 | 0 | 1 archive, 3 movies, 174 images, 66 font files, 42 text, 5 data (layout open), 8 code, 131 audio |
| Japan | 25 | 0 | `BOMSS1.CPK`, `BOMSS3.CPK` and 9 AIFs are byte-identical to USA |

### `PROGRAM.BIN` banks

| Bank class | USA | Japan | Status |
| --- | ---: | ---: | --- |
| Graphics | 12 | 11 (no `xband1`) | decoded |
| Sound `s_*` | 11 | 10 | classified; owner sound-68k |
| Voice `s_vo*` | 45 | 45 | classified; owner sound-68k |
| Headerless (USA ids 23, 41, 42, 43) | 4 | 0 | classified unknown; semantics open |
| Bytes after the last directory entry | 2,169,666 | 2,931,522 | build-container residue |

Japan graphics banks `base1`, `base2`, `openning`, `normal5`, `battle1`,
`master1` and `staff` decode to different outputs from USA (localised text
sprites, palettes, VDP2 data). `normal1` differs only in bank bytes, and
`normal2`–`normal4` are identical.

### Extracted (USA; Japan where it differs)

| Category | Extracted / known |
| --- | ---: |
| CRAM palettes | 414 / 414 |
| VDP1 sprite frames | 11,695 / 11,695 (34,681 parts) |
| VDP1 unique pixel blocks | 10,659 / 10,659 |
| Sprite animation sequences | 4,915 / 4,915 |
| VDP2 cell blocks | 84 / 84 |
| Stage grids | 115 / 115 |
| Stage background planes (exact pattern-name planes + renders) | 115 / 115 |
| VDP2 menu/UI maps (slot 2) | 65 / 65 decoded, 0 rendered |
| Record tables in slots 3, 4, 6 and 9 | 0 / 238 |
| FILM movies | USA 3 / 3 (10,421 frames, 320×160, 30 fps, stereo 22,050 Hz); Japan `BOMSS2` 1 / 1 |
| NetLink/XBAND images | 174 / 174 |
| NetLink font strips and width tables | 58 / 58 and 8 / 8 |
| HTML/TXT text | 42 / 42 |

### Formats confirmed this run (own words)

- Sprite frames are lists of 20-byte part records. All 34,681 parts are VDP1
  4-bit colour-bank sprites, and each one's decoded pixel length equals
  width × height / 2. Animation sequences are (frame, duration) lists. Pixel
  indices are exact. Colours are previews until each object's runtime colour
  base is bound.
- Stage backgrounds: a slot-7 grid of 64×64 16-bit metatile indices expands
  through a slot-5 metatile set (four 2-word VDP2 pattern names per 16×16
  block) into the 128×128-cell NBG plane the game writes. Against natural
  Beetle checkpoints, World 2-1 NBG0/NBG1/NBG3 and World 1-1 NBG1/NBG2 equal
  the disc-derived planes on all 16,384 cells. World 2-1's cell block is
  byte-exact in VDP2 VRAM. The background palette agrees on 223 of 256
  entries; the rest are colour-cycled.
- The story and menu text is pre-rendered as VDP1 sprites in the base banks.
- The Japan `BOMSS2.CPK` is a separate dub: all 3,414 frames (re-timed mouth
  animation) and the audio differ from USA.

## Private repository state

- `8c81955`: PROGRAM.BIN graphics recipe and outputs.
- `6f02041`: disc-wide classification, standard formats, FILM movies.
- `7925bb6`: stage background planes and capture checks.
- `058e59d`: Japan outputs. `c1c9287`: progress file.

## Frontier

1. Stage set table: which grids, metatile set, cell blocks and palette each
   stage uses. The counts differ in normal1/3/5, battle1 and master1.
2. Sprite palettes: runtime colour base per object, from the draw code or
   VDP1 command lists in captures.
3. Slot-2 menu/title maps: geometry and palette placement, then render.
4. Slots 3, 4, 6 and 9; headerless banks 23/41/42/43; XBAND/NetLink data
   layouts.
5. Transcribe the pre-rendered story/menu text with sprite ids.

## Run log

- 20261105T0828Z–1028Z: no work; the runs stopped at start on the account
  usage limit.
- 20261105T1123Z: first working run. PROGRAM.BIN graphics, disc
  classification, movies, stage backgrounds checked against captures, Japan
  differences (PR #866 merged; this update).
