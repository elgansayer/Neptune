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
| USA | 430 | 0 | 1 archive, 3 movies, 174 images, 66 font files, 42 text, 5 data (2 XBAND files partly decoded, 3 layouts open), 8 code, 131 audio |
| Japan | 25 | 0 | `BOMSS1.CPK`, `BOMSS3.CPK` and 9 AIFs are byte-identical to USA |

### `PROGRAM.BIN` banks

| Bank class | USA | Japan | Status |
| --- | ---: | ---: | --- |
| Graphics | 12 | 11 (no `xband1`) | decoded |
| Sound `s_*` | 11 | 10 | classified; owner sound-68k |
| Voice `s_vo*` | 45 | 45 | classified; owner sound-68k |
| Headerless voice container (USA id 23) | 1 | 0 | classified audio; owner sound-68k |
| Headerless voice-slot sectors (USA ids 41–43) | 3 | 0 | unidentified (likely audio); handed to sound-68k |
| Bytes after the last directory entry | 2,169,666 | 2,931,522 | build-container residue |

Japan graphics banks `base1`, `base2`, `openning`, `normal5`, `battle1`,
`master1` and `staff` decode to different outputs from USA. `normal1`
differs only in bank bytes, and `normal2`–`normal4` are identical.

### Extracted (USA; Japan where it differs)

| Category | Extracted / known |
| --- | ---: |
| CRAM palettes | 414 / 414 |
| VDP1 sprite frames | 11,695 / 11,695 (34,681 parts) |
| VDP1 unique pixel blocks | 10,659 / 10,659 |
| Sprite animation sequences | 4,915 / 4,915 |
| Sprite palettes bound from captures | 355 blocks, 315 sequences (873 frames) |
| VDP2 cell blocks | 84 / 84 |
| Stage grids and background planes | 115 / 115 (exact pattern-name planes + renders) |
| Metatile sets and per-metatile attributes | 39 / 39 sets; 115 attribute maps |
| Colour-cycle scripts | 124 / 124 |
| VDP2 cell animations | 36 records, 232 frames (stage banks) |
| FONTX2 Shift-JIS fonts (16×16) | 2 / 2 (316 glyphs each) |
| VDP2 menu/UI maps | 65 / 65 decoded and rendered; 2 confirmed by capture |
| **Normal Game stage descriptors** | **50 / 50** |
| **Normal Game enemy placement lists** | **50 / 50** |
| **Battle stage descriptors (with item lists)** | **36 / 36** |
| **Master Game stages and item placement** | **20 / 20** |
| **Gameplay maps (64×64 cell attributes)** | **106 / 106** |
| Base1 slot-4 records | 3 / 13 decoded (descriptors, enemies, one open list); 10 probable demo-input lists raw |
| Slot-9 records outside the base banks | 21 / 24 (battle1 1, master1 20; xband1 3 open) |
| FILM movies | USA 3 / 3 (10,421 frames, 320×160, 30 fps, stereo 22,050 Hz); Japan `BOMSS2` 1 / 1 |
| NetLink/XBAND images | 174 / 174 |
| NetLink font strips and width tables | 58 / 58 and 8 / 8 |
| HTML/TXT text | 42 / 42 |

### Formats confirmed (own words)

- **Stage descriptors (new this run).** Normal Game keeps one 152-byte
  record per stage (5 worlds × 10 slots) in the first base bank's slot 4.
  The kernel finds it as world × 10 + stage. In order, the record names:
  - the stage's cell block and palette;
  - the metatile and attribute set;
  - the gameplay-layer grid and up to two more background-layer grids;
  - up to ten colour-cycle scripts;
  - up to five tile animations, each with its VDP2 target address;
  - the field's bounding box;
  - the soft-block count;
  - the start view;
  - both players' start cells;
  - a zero-terminated list of the item kinds hidden in the stage.

  Battle mode keeps 36 shorter records (9 arenas × 4 variants) in the
  battle bank, each with its own item list. Master Game stages are set up
  by code: field grid n, background grid n + 20. Each also has a list of
  fixed item cells.
- **Enemy placement (new).** Up to 16 (type, x, y) entries per normal stage.
- **Gameplay map (new).** The kernel builds the 64×64 cell map by looking
  each field-grid metatile up in its set's attribute table. The upper bits
  go into the cell map (solid and floor-class flags), and the low nibble
  goes into a parallel map. Soft blocks, bombs, items and fire are run-time
  bits on top. Soft-block cells and the cells of normal-mode hidden items
  are generated by code from the descriptor's count. They are identical
  across independent runs.
- **Sprites.** A frame is a list of 20-byte part records; a sequence is a
  list of (frame, duration) pairs. All 34,681 parts are VDP1 4-bit
  colour-bank sprites. Over 36 natural capture states, 910 of 911 draws
  match a decoded pixel block byte-exactly; the remaining draw is the RGB
  movie frame. Each match binds the object's runtime colour base.
- **Stage backgrounds.** A 64×64 grid of metatile indices expands through a
  metatile set (four 2-word VDP2 pattern names per 16×16 block) into the
  game's NBG plane. Nine live planes equal the disc-derived planes on all
  16,384 cells. Five stage sets have capture-confirmed pairings. The new
  descriptors give the exact pairing for 93 of the 115 planes. The current
  index-based renders agree on set, cell block and palette for 55 of them.
- **Menu and title maps.** The kernel loader gives rows × columns of 2-word
  pattern names; the title maps equal live NBG0 on every cell.
- **Story and menu text.** It is pre-rendered as VDP1 sprites in the base
  banks, so transcription needs sprite ids. Japan graphics banks `base1`,
  `base2`, `openning`, `normal5`, `battle1`, `master1` and `staff` carry
  localised text sprites, palettes and VDP2 data.
- **Palette and tile animation, fonts, movies.** As in the previous update:
  (CRAM index, count, (delay, colours) frames) cycles; tile animations as
  4-bit cell frames; a FONTX2 Shift-JIS font in the base banks; Japan
  `BOMSS2.CPK` is a separate dub.

### Live checks of the stage data (11 natural captures)

| Check | Result |
| --- | --- |
| Solid bit, table-derived map vs live cell map | 4,092–4,096 / 4,096 for normal 1-1, 2-1, 3-1, 4-1, battle 10-0, master 9 and 13 (the rest are standing enemies) |
| 1-1 at stage start: enemies, player starts, soft-block count | 7/7 cells, 2/2 cells, 56 = 56 |
| Hidden item kinds vs live item slots | equal for 1-1, 2-1, 3-1, 4-1 and battle 17-0 (75/75, two runs); battle 10-0 32/33 (one slot already used) |
| Master item cells | 5/5 and 12/12 |
| Battle arena 17 | field partly built by code (3,634/4,096 from the grid alone) |
| Japan | same tables and maps byte for byte |

## Private repository state (run 20261105T1623Z)

`38952ec` master1 pairing confirmed by capture and the second attract walk's
checks · `0f256a2` stage data recipe and outputs · `1f4c702`, `60cf877`
progress. Earlier: `8c81955`, `6f02041`, `7925bb6`, `058e59d`, `43239a1`,
`0eb90a8`, `f6f075b`, `21e5e2e`, `df30aee`, `4d94bee`.

## Frontier

1. Re-render backgrounds from the stage descriptors (38 of 93 referenced
   planes change cell block or palette); keep the heuristic only for the
   22 grids no table references (18 XBAND, 4 normal).
2. Soft-block and hidden-item placement routine (count from the
   descriptor), so every stage's starting field is reproducible from data
   plus code; then battle arena 17's code-built field.
3. Remaining records: base1 slot 4 record 18 and the probable demo-input
   lists; the open descriptor parameters; xband1 slot 9.
4. Sprite palettes for the objects no capture has drawn yet; menu/title
   map colours; open slot-6 attribute bits.
5. Text transcription of the sprite text; XBAND/NetLink data layouts.
6. Neptune implementation issues for stage layouts, enemies and items.

## Run log

- 20261105T0828Z–1028Z: no work; the runs stopped at start on the account
  usage limit.
- 20261105T1123Z: first working run. Covered PROGRAM.BIN graphics, disc
  classification, movies, stage backgrounds, attributes, colour and tile
  animations, fonts, sprite palette bindings, attract-mode captures and
  Japan differences (PRs #866, #868). It stopped on the usage limit during
  its closing pass.
- 20261105T1328Z: no work (usage limit).
- 20261105T1623Z: finished the 1123Z closing pass and found the game's stage
  tables through the kernel code that reads them. Exported every
  normal/battle/master stage's descriptor, enemy and item placement and
  gameplay map, and checked them against live RAM (this update).
