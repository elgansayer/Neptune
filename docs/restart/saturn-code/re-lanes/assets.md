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
| **Sprite palettes bound from captures** (864 states; 34,660 of 34,704 draws match a decoded block, the rest are 40 RGB movie frames and 4 draws in one stage) | **2,223 blocks, 1,848 sequences (5,836 frames)**; was 930 / 962 before run 2123Z; staff bank 152 / 185 blocks, all 50 sequences |
| VDP2 cell blocks | 84 / 84 |
| Stage grids and background planes | 115 / 115 (exact pattern-name planes + renders) |
| Metatile sets and per-metatile attributes | 39 / 39 sets; 115 attribute maps |
| Colour-cycle scripts | 124 / 124 |
| VDP2 cell animations | 36 records, 232 frames (stage banks) |
| FONTX2 Shift-JIS fonts (16×16) | 2 / 2 (316 glyphs each) |
| VDP2 menu/UI maps | 65 / 65 decoded and rendered; **19 confirmed by capture on every cell** (was 6), rendered in capture colours |
| Normal Game stage descriptors | 50 / 50 |
| Normal Game enemy placement lists (kernel table) | 50 / 50 |
| Master Game enemy placement lists | 20 / 20 |
| Battle stage descriptors (with item lists) | 36 / 36 |
| Master Game stages and item placement | 20 / 20 |
| Gameplay maps (64×64 cell attributes) | 106 / 106 |
| Base1 slot-4 records | 13 / 13 classified (stage descriptors, 10 attract-demo pad recordings, and two older copies of the kernel's enemy tables that no code reads) |
| Slot-9 records outside the base banks | 24 / 24 (battle1 and xband1 list the same battle table twice; master1 20 item lists) |
| FILM movies | USA 3 / 3 (10,421 frames, 320×160, 30 fps, stereo 22,050 Hz); Japan `BOMSS2` 1 / 1 |
| NetLink/XBAND images | 174 / 174 |
| NetLink font strips and width tables | 58 / 58 and 8 / 8 |
| HTML/TXT text | 42 / 42 |
| **Sprite text frames** (story, save-system messages, Master Game intro, staff credits, animated words) | **54 / 54 found; 30 checked glyph by glyph against the bank data, 0 conflicts** |
| **Sprite word blocks** (menu labels, arena, character, world and boss names, banners, Master Game labels, battle taunts) | **293 blocks read** (every text-bearing banner-shaped block of four banks; 477 entries with pixel-identical copies; partial inventory) |
| **Menu, screen and play capture states** (scripted pad input, no memory writes) | **338 new** (incl. 8 battle arena previews) |
| **Ending, staff roll and boss capture states** (the game's own end-of-game path, entered by a memory write; Normal and Master boss stages continued from stage select) | **382 new** (864 states in all) |

### Formats confirmed (own words)

- **Stage descriptors.** Normal Game keeps one 152-byte
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
- **Enemy placement.** The game reads it from two
  tables inside the kernel executable, not from the base bank:
  - The Normal Game table has one 64-byte row per (world, stage), with up to
    16 (kind, x, y) entries ending at kind 0.
  - The Master Game table has one row per Master stage.
  - A short (world, stage) list names the seven boss stages that spawn
    nothing from the table. Their objects come from stage code.

  The spawner creates each entry at its cell and stores the kind in the
  object. Some kinds bring extra objects with them that code spawns, such as
  a companion on the same cell or a three-part body. The base bank holds two
  older copies that nothing reads:
  - The Normal copy differs on 27 of 60 rows. Every World 5 row in it lists
    only the exit mechanism; earlier outputs used it.
  - The Master copy has 25 rows in five groups of four stages and a boss,
    against the shipped five groups of three stages and a boss.

  Japan's kernel holds the same table bytes.
- **Gameplay map.** The kernel builds the 64×64 cell map by looking
  each field-grid metatile up in its set's attribute table. The upper bits
  go into the cell map (solid and floor-class flags), and the low nibble
  goes into a parallel map. Soft blocks, bombs, items and fire are run-time
  bits on top. The lookup is unbounded: indices past the attribute table
  read the bytes that follow it, which explains battle arena 17's outer
  columns.
- **Soft blocks and hidden items.** Placement is generated by code,
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
  colour-bank sprites. Over 470 capture states, 22,001 of 22,008 draws
  match a decoded pixel block byte-exactly. The rest are three captures of
  the RGB movie frame and 4 draws in stage 2-2. Each match binds the
  object's runtime colour base.
- **Battle characters (new this run).** The battle base bank holds one group
  of about 34 animation sequences per character (12 groups). Every captured
  sequence of group k uses the runtime colour base 0x60 + 0x10·k; some also
  use a second base, 0x200 + 0x10·k. Ten groups are bound from captures.
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
  pattern names; the title maps equal live NBG0 on every cell. The battle
  menus use one-page planes (each of the four planes is a single 64×64-cell
  page). The capture checker now reads that layout, which confirmed four
  battle maps.
- **Scenes, modes and the ending (new this run).** The kernel runs one
  scene at a time. Each scene stores the next scene's entry point and a mode
  number, and the mode picks the banks loaded for the next scene: title,
  Normal Game (bank by world), Battle (or the XBAND bank), Master Game, and
  the ending (staff bank). A Normal Game stage ends when its 16-bit flag word
  gets the stage-over bit. A cleared stage runs the stage's clear hook; a
  game over sets another bit. With that bit set and the world number one
  past the last world, the game starts the ending scene: the ending movie,
  then the staff roll. Setting those two values in a running stage reaches
  the staff roll and then the title screen.
- **Sprite text (new this run).** The English story screens, save-system
  messages, the Master Game intro and the staff credits are each one sprite
  frame. Its parts are glyph blocks shared across frames, one character per
  block. The fonts draw the apostrophe with the comma glyph, placed higher.
  The checker splits a frame's parts into the transcribed lines and aligns
  them with the characters: 30 frames align, and no glyph block reads as two
  characters. The save-system font packs several characters into a block,
  so those frames are visual transcriptions only. Menu labels, arena names
  and character names are single "word blocks".
- **Palette and tile animation, fonts, movies.** As in the previous update:
  (CRAM index, count, (delay, colours) frames) cycles; tile animations as
  4-bit cell frames; a FONTX2 Shift-JIS font in the base banks; Japan
  `BOMSS2.CPK` is a separate dub.

### Live checks of the stage data

| Check | Result |
| --- | --- |
| Solid bit, table-derived map vs live cell map | 4,092–4,096 / 4,096 for normal 1-1, 2-1, 3-1, 4-1, battle 10-0, master 9 and 13 (the rest are standing enemies) |
| 1-1 at stage start: enemies, player starts, soft-block count | 7/7 cells, 2/2 cells, 56 = 56 |
| Kernel enemy tables vs all stage-select captures (this run) | Normal Game: every listed (kind, cell) present at build on 50/50 stages (405/405 entries); Master Game: live kinds equal the row and every (kind, cell) present on 20/20 (166/166) |
| Hidden item kinds vs live item slots | equal for 1-1, 2-1, 3-1, 4-1 and battle 17-0 (75/75, two runs); battle 10-0 32/33 (one slot already used) |
| Master item cells | 5/5 and 12/12 in demos |
| All 36 battle arenas, selected through world/variant in the battle demo's pre-build state | solid bit 4,090–4,096/4,096 on 36; item lists 36/36; soft-block count exact on 35/36 (one arena runs out of free cells); descriptor grids equal the live planes on 32/36 (arena 17's large field is on a plane layout the checker doesn't read), cell block and palette confirmed on 36/36 |
| All 20 Master Game stages, selected through the stage byte in a demo's pre-build state | solid bit 4,092–4,096/4,096 on 20; field grid s+1 and background grid s+21 equal the live planes on every cell on 20; item kinds 19/20 and item cells 98/100 (stage 14 skips one item and shifts the rest) |
| Battle arena 17 | 4,096/4,096 solid bits in two captures (once the lookup reads past the table) |
| Japan | same tables and maps byte for byte |
| All 50 Normal Game stages, selected through the game's stage variables in a cold-boot menu state | 47 build (1-8–1-10 are identical placeholder records); timer = descriptor minutes × 3,600 frames 47/47; hidden item kinds 47/47; soft-block count exact 43/47; solid bit ≥ 4,083/4,096; the single bomber on its entry cell (31) or player-1 cell (16); enemies: see the kernel-table row above (the old base-bank source matched 17 stages) |
| Backgrounds of all 47 built stages (display-on stage-select captures) | every descriptor grid equals a live plane on all 16,384 cells on 44 stages; descriptor cell block in VRAM on 47 (byte-exact on 20, ≥ 98% where tiles animate); descriptor palette the best CRAM match on 47 |
| Soft-block generator from the captured generator state | with a per-stage set-up offset: exact on 24 of the 39 built stages with soft blocks when the bomber area and the kernel table's enemy cells are reserved, 28 of 39 when the objects code spawns are reserved too (the other 11 within 1–5 blocks); 1-1 exact in two demo captures including hidden items |

## Private repository state (runs 20261105T1623Z, 1833Z and 2123Z)

Run 2123Z: `6b795ae` (head) word blocks of four banks · `ba74aa2` battle arena previews (864-state pass) · `5f69132` Master boss floors, 852-state capture pass, 241 word
blocks · `35176ac` 200 word blocks · `1f46dfd` ending, staff roll and boss
captures (722-state capture pass) · `080174c` ending trigger and capture-pass update · `47e1792`
capture pass over 470 states (sprite bindings, map
checks, one-page planes, deduplicated draw PNGs, Counts section) ·
`6265cec` 133 word blocks · `d400937` sprite text recipe and output, menu and
play walk recipe, multi-checkpoint emulator wrapper, draw lister. Run 1833Z:
`d9862b4` enemy placement from the kernel tables (Normal, Master, boss skip
list) with stage-select checks · `e398b07` soft-block fit with the kernel
table, format document and progress. Run 1623Z: `38952ec` master1 pairing confirmed by capture and the second attract walk's
checks · `0f256a2` stage data recipe and outputs · `ef1b663` backgrounds
paired from the stage tables, starting-field generator · `2d55396` emulator
wrapper after the host kernel update · `7946a43` stage-select checks of all
50 stages · `8e22b08`, `7a71f0e` generator fit · `bce4e78` demo-input
records · `69902d2` capture checks and sprite bindings over 86 states ·
`be65314` progress · `1bbdf46` format document
(`docs/assets/STAGE_DATA.md`) · `54a85be`, `771f5a1` Master Game checks and
106-state capture run · `d04c8dd`, `3ad230c` battle arena checks and
142-state capture run · `7d07e38` menu maps from the cold-boot states. Earlier: `8c81955`, `6f02041`, `7925bb6`, `058e59d`, `43239a1`,
`0eb90a8`, `f6f075b`, `21e5e2e`, `df30aee`, `4d94bee`.

## Frontier

1. Sprite palettes: 2,223 of 10,659 blocks are bound.
   - Next captures: Normal Game Louie rides, items and world-transition
     story screens; more Master Game floors; the two base2 character groups
     whose characters character select doesn't offer.
   - Or bind from the draw code (each object's colour base).
   - The per-character groups could bind the rest of base2 by inference,
     reported separately from capture bindings.
2. VDP2 map colours: 46 of 65 maps still need a capture of their screen or a
   reader for their plane layout.
3. Text: the word-block inventory across all banks, then the Japanese
   banks. XBAND/NetLink data layouts.
4. Soft-block layouts: make the per-stage set-up offset and the
   code-spawned objects derivable from code instead of fitted (usa-code
   scope). Also the open descriptor parameters, the two unpaired
   background grids and the open slot-6 attribute bits.
5. Neptune implementation issues: #877 (soft blocks and items), #887
   (enemy placement) and #890 (battle arena set-up) are filed.

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
  - Then checked all 50 Normal Game stages in the running game: stage data, background pairing and sprite palettes (860 blocks).
- 20261105T1833Z:
  - Found the enemy spawner in the kernel. It reads two kernel tables (Normal Game and Master Game) and a boss-stage skip list. This closes World 5 and Master Game enemy placement.
  - Classified base1 records 17 and 18 as unread older copies; record 18 was the last open base-bank record.
  - Checked both tables against every stage-select capture: 405/405 and 166/166 entries.
  - Re-fitted the soft-block generator with the correct enemy cells.
- 20261105T2123Z:
  - Walked the menus and play with scripted pad input from the cold-boot
    states. No memory writes. The walks reached:
    - the title menus and Option Mode;
    - the whole Battle set-up chain;
    - an 8-player random match through HURRY, TIME UP, DRAW and the
      scoreboard;
    - Normal Game play to GAME OVER and continue;
    - the Master Game intro and floors.
  - Captured 326 new states. A new emulator wrapper saves many checkpoints
    in one pass; its states are byte-identical to the one-at-a-time chain.
  - The capture pass over all 470 states:
    - doubled the sprite palette bindings;
    - raised the maps confirmed on every cell from 6 to 18, after the checker
      learned the battle menus' one-page planes.
  - Found that the English text is glyph-built sprite frames. Transcribed all
    54, with 30 checked glyph by glyph (0 conflicts). Read 133 word blocks.
  - Filed Neptune #887 (enemy placement) and #890 (battle arena set-up).
  - Read the kernel's scene and mode logic. Started the ending through the
    game's own end-of-game path, which bound the staff bank: 152 of 185
    blocks and all 50 sequences.
  - Continued the seven Normal Game boss stages and the five Master Game
    boss floors from stage select.
  - Read 293 word blocks: every text-bearing banner-shaped block in four banks.
  - Total: 2,223 blocks bound over 864 states, 19 maps confirmed.
