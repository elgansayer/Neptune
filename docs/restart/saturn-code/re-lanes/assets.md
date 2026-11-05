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
| Sprite palettes bound from captures | 860 blocks, 872 sequences (3,061 frames) |
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
| Base1 slot-4 records | 12 / 13 decoded (stage descriptors, enemy placement, 10 attract-demo pad recordings); record 18 open |
| Slot-9 records outside the base banks | 24 / 24 (battle1 and xband1 list the same battle table twice; master1 20 item lists) |
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
  - the start views;
  - the single bomber's entry cell and the two-bomber start cells;
  - the time limit in minutes;
  - a zero-terminated list of the item kinds hidden in the stage.

  Battle mode keeps 36 shorter records (9 arenas × 4 variants) in the
  battle bank, each with its own soft-block count and item list. Master Game stages are set up
  by code: field grid n, background grid n + 20. Each also has a list of
  fixed item cells.
- **Enemy placement (new).** Up to 16 (type, x, y) entries per normal stage.
- **Gameplay map (new).** The kernel builds the 64×64 cell map by looking
  each field-grid metatile up in its set's attribute table. The upper bits
  go into the cell map (solid and floor-class flags), and the low nibble
  goes into a parallel map. Soft blocks, bombs, items and fire are run-time
  bits on top. The lookup is unbounded: indices past the attribute table
  read the bytes that follow it, which explains battle arena 17's outer
  columns.
- **Soft blocks and hidden items (new).** Placement is generated by code,
  from the descriptor's count and the field rectangle:
  - **Random generator:** subtractive, 55 entries, modulus 32768, seed
    1234. Demos re-seed it at stage set-up, so their layouts repeat. Real
    play does not re-seed, so layouts vary from play to play.
  - **Soft blocks:** row sweeps with a rising threshold. Reserved cells
    are the bomber's 3×3 area and the enemy cells.
  - **Hidden items:** each item goes into the first free soft block to the
    right of a random cell.
  - **Stage set-up draws:** enemy set-up draws a stage-dependent number of
    random values first: 0 for 1-1, 34 for 2-1 (the same in a demo and in
    real play).
- **Sprites.** A frame is a list of 20-byte part records; a sequence is a
  list of (frame, duration) pairs. All 34,681 parts are VDP1 4-bit
  colour-bank sprites. Over 86 capture states, 3,190 of 3,195 draws match
  a decoded pixel block byte-exactly; the rest are the RGB movie frame and
  4 draws in stage 2-2. Each match binds the object's runtime colour base.
- **Stage backgrounds.** A 64×64 grid of metatile indices expands through a
  metatile set (four 2-word VDP2 pattern names per 16×16 block) into the
  game's NBG plane. Nine live planes equal the disc-derived planes on all
  16,384 cells. Renders are now paired from the stage tables:
  - USA: 111 of 115 planes, including XBAND's 18 grids through its own
    battle table.
  - 2 more planes come from capture pairings, and 2 still use the old
    heuristic.
  - The earlier index-based renders were wrong for 38 of 93 planes.
  - All five capture-confirmed pairings agree with the tables.
- **Menu and title maps.** The kernel loader gives rows × columns of 2-word
  pattern names; the title maps equal live NBG0 on every cell.
- **Palette and tile animation, fonts, movies.** As in the previous update:
  (CRAM index, count, (delay, colours) frames) cycles; tile animations as
  4-bit cell frames; a FONTX2 Shift-JIS font in the base banks; Japan
  `BOMSS2.CPK` is a separate dub.

### Live checks of the stage data

| Check | Result |
| --- | --- |
| Solid bit, table-derived map vs live cell map | 4,092–4,096 / 4,096 for normal 1-1, 2-1, 3-1, 4-1, battle 10-0, master 9 and 13 (the rest are standing enemies) |
| 1-1 at stage start: enemies, player starts, soft-block count | 7/7 cells, 2/2 cells, 56 = 56 |
| Hidden item kinds vs live item slots | equal for 1-1, 2-1, 3-1, 4-1 and battle 17-0 (75/75, two runs); battle 10-0 32/33 (one slot already used) |
| Master item cells | 5/5 and 12/12 |
| Battle arena 17 | 4,096/4,096 solid bits in two captures (once the lookup reads past the table) |
| Japan | same tables and maps byte for byte |
| All 50 Normal Game stages, selected through the game's stage variables in a cold-boot menu state | 47 build (1-8–1-10 are identical placeholder records); timer = descriptor minutes × 3,600 frames 47/47; hidden item kinds 47/47; soft-block count exact 43/47; solid bit ≥ 4,083/4,096; the single bomber on its entry cell (31) or player-1 cell (16); every listed enemy cell occupied on 17 stages |
| Backgrounds of all 47 built stages (display-on stage-select captures) | every descriptor grid equals a live plane on all 16,384 cells on 44 stages; descriptor cell block in VRAM on 47 (byte-exact on 20, ≥ 98% where tiles animate); descriptor palette the best CRAM match on 47 |
| Soft-block generator from the captured generator state | exact on 28 of 35 stage-select captures with a soft-block count, when every object present at build time reserves its cell and each stage gets its set-up offset (the other 7 within 1–5 blocks); 1-1 exact in two demo captures including hidden items |

## Private repository state (run 20261105T1623Z)

`38952ec` master1 pairing confirmed by capture and the second attract walk's
checks · `0f256a2` stage data recipe and outputs · `ef1b663` backgrounds
paired from the stage tables, starting-field generator · `2d55396` emulator
wrapper after the host kernel update · `7946a43` stage-select checks of all
50 stages · `8e22b08`, `7a71f0e` generator fit · `bce4e78` demo-input
records · `69902d2` capture checks and sprite bindings over 86 states ·
`be65314` progress. Earlier: `8c81955`, `6f02041`, `7925bb6`, `058e59d`, `43239a1`,
`0eb90a8`, `f6f075b`, `21e5e2e`, `df30aee`, `4d94bee`.

## Frontier

1. Enemy placement still to locate: World 5 (its stages use a separate
   set-up path) and Master Game (not in its item lists). Then the 1–2 extra
   soft blocks on four stages, and enemy set-up's random draws (usa-code
   scope) to make every demo layout exact.
2. Base1 slot 4 record 18: matches neither normal enemies nor Master spawn
   cells. The open descriptor parameters.
3. The two background grids no table or capture pairs.
4. Sprite palettes for the objects no capture has drawn yet; menu/title
   map colours; open slot-6 attribute bits.
5. Text transcription of the sprite text; XBAND/NetLink data layouts.
6. Neptune implementation issues: #877 (soft-block and item placement) is
   filed; stage layouts and enemies next.

## Run log

- 20261105T0828Z–1028Z: no work; the runs stopped at start on the account
  usage limit.
- 20261105T1123Z: first working run. Covered PROGRAM.BIN graphics, disc
  classification, movies, stage backgrounds, attributes, colour and tile
  animations, fonts, sprite palette bindings, attract-mode captures and
  Japan differences (PRs #866, #868). It stopped on the usage limit during
  its closing pass.
- 20261105T1328Z: no work (usage limit).
- 20261105T1623Z:
  - Finished the 1123Z closing pass.
  - Found the game's stage tables through the kernel code that reads them, and exported every stage's descriptor, enemy and item placement and gameplay map (PR #876).
  - Re-paired the backgrounds from those tables.
  - Re-implemented the soft-block and item placement.
  - Filed Neptune #877.
  - Blocker found and fixed: the host's kernel update made the pinned emulator frontend refuse to run, because its platform-string pin no longer matched. A wrapper maps only that string. Checked byte-identical against a pre-update checkpoint.
  - Then checked all 50 Normal Game stages in the running game: stage data, background pairing and sprite palettes (860 blocks) (this update).
