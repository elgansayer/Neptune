# Static Saturn disc inventory (`EXP-SAT-DISC-001`): 30 October 2026

Gemini #464 programme, milestone 2. Informs #394 (`REF-001`), #28 and #399 (`REF-006`).
Base `8bd5d89` (includes Codex #467 media identity and #468 libretro bridge, unchanged).
Machine-readable results: [`docs/restart/saturn-disc/`](../saturn-disc/README.md).
No disc, BIOS, track, file, state or memory bytes are committed or sent to a model provider.

## Method

[`tools/saturn_disc`](../../../tools/saturn_disc/README.md) is a dependency-free Python package. It reads
the supplied CUE sets read-only from `/home/dev/Sega-Saturn-BIOS` and does the following:

1. Parses the CUE and hashes every track.
2. Checks Mode 1 sync, BCD MSF and the 32-bit EDC for every Track 01 block.
3. Parses `IP.BIN` (LBA 0..15).
4. Walks ISO-9660 and gives every Track 01 block exactly one owner.
5. Classifies files by magic bytes and structure, not by extension.
6. Diffs the two regions, including a CD-DA sample-shift test.

It also cross-checks the results against Codex's #462 media reports and the #463 asset-repo manifest.
Each inspection ran twice per disc. The two outputs matched byte for byte (`cmp -s`).
`python3 tools/saturn_disc/check.py` runs 7 synthetic tests. These include a corrupted EDC,
CUE path traversal and symlink rejection, an invalid `IP.BIN`, a self-diff rejection and `--help` rendering.
Synthetic tests only cover parser behaviour. They say nothing about the game.

## Disc identity and integrity

| | USA | Japan |
| --- | --- | --- |
| `IP.BIN` product / version / date | `MK-81070` `V1.003` 1997-05-12 | `T-14302G` `V1.000` 1996-05-31 |
| Maker / title / area | `SEGA ENTERPRISES` / `SATURN BOMBERMAN` / `U` | `SEGA TP T-143` / `BOMBERMAN SS` / `J` |
| First-read load address / IP size | `0x06010000` / 4096 | `0x0600a000` / 6144 |
| CUE SHA-256 | `785e6f9f…9da` | `ac6c34bb…bcdb` |
| Track 01 SHA-256 | `34c3c15b…126c` | `fab95240…3d10` |
| Tracks (data + CD-DA) | 1 + 29 | 1 + 29 |
| Track 01 blocks / EDC-valid / mismatches | 60,969 / 60,969 / 0 | 55,949 / 55,949 / 0 |
| Unaccounted blocks / unreferenced non-zero | 0 / 0 | 0 / 0 |
| Trailing zero padding | 150 blocks (60819..60968) | 150 blocks |
| ISO-9660 files / directories | 430 / 5 | 25 / 1 |
| #462 media report cross-check | IP header consistent, 30 track hashes | IP header consistent, 30 track hashes |

## File classification

| Class | USA files (bytes) | Japan files (bytes) |
| --- | --- | --- |
| `decoded` (structure validated) | 366 (9,769,553) | 20 (3,773,034) |
| `executable` (SH-2 / M68000) | 3 (1,245,648) | 1 (786,432) |
| `identified_undecoded` (`PROGRAM.BIN`, 3 `FILM` CPKs, …) | 5 (110,477,964) | 4 (109,651,718) |
| `unknown` | 56 (2,544,559) | 0 |

The 56 USA unknowns are NetLink/XBAND support files: 38 `NETLINK/*.BMP` files without `BM`
magic, 8 `*.WDT`, `DATASECT.BIN`, `PARENTAL.HTM`, `XS028000.EXE`, 5 `XBAND/*`, plus
root `FLD_KNL.BIN` and `XBMAP.BIN`. They remain `unknown` and are not counted as decoded.
They are low priority for game rules.

## `PROGRAM.BIN`: Hudson Low-WRAM bank container

USA `BOMSS/PROGRAM.BIN` (SHA-256 `f5154d4a…96d5`) and Japan `PROGRAM.BIN` (`928b959f…a348`)
are both 12,976,962 bytes. They are sequences of 2048-byte-aligned banks. Each bank starts with this 52-byte header:

| Offset | Field |
| --- | --- |
| `+0x00..+0x2b` | 11 big-endian `u32` slots: 0 or a Low-WRAM address; non-zero slots are strictly increasing |
| `+0x2c..+0x33` | ASCII bank name, padded with `0xFF` |

The first non-zero slot is always `load_base + 0x34`.

Measured structure:

- USA has 236 banks and Japan has 240. Across both releases, all 655 non-zero slots
  (330 USA, 325 Japan) fall inside `[load_base + 0x34, load_base + length)`.
- `base1` and `base2` load at `0x00200000` and end exactly at `0x00254000`. World, mode
  and battle banks start at that address, and the largest ends exactly at `0x00300000`,
  the top of the 1 MiB Low-WRAM. Sub-sound banks use base `0x002ee000`.
- Voice banks are tagged `0x002fb000` but extend to `0x00325000` (USA). That is beyond
  Low-WRAM, so this value is not a direct Low-WRAM placement for them. Another group uses
  `0x00250000`, which overlaps the `base*` range. Both are unexplained.
- Bank payload entropy is about 7.03 bits/byte. This suggests compressed sections inside banks (hypothesis).

**Hypothesis to test next:** the game copies core, world, mode and battle banks verbatim to
`load_base`, and the header slots are section entry points. Static evidence supports this:
the pointers are contained, ordered and tile the memory map. It is not yet confirmed at
runtime (see `EXP-SAT-ARCHIVE-002`).

Bank names: `s_init`, `base1`, `base2`, `openning`, `normal1..5`, `battle1`, `master1`,
`staff`, USA-only `xband1`, sound banks `s_open`, `s_nor1..5`, `s_nor5b`, `s_nor5c`,
`s_mst1`, `s_bat1`, `s_bat1b`, plus 209 USA / 215 Japan `s_vo*` voice banks. The role
labels in the JSON come from these names and are not decoded content.

Regional bank diff (by name and occurrence):

- 52 banks are byte-identical across USA and Japan, including `normal2`, `normal3`,
  `normal4`, `s_init` and 45 voice banks.
- 166 banks have the same name and occurrence but different bytes, including `base1`,
  `base2`, `normal1`, `normal5`, `battle1` and `master1`.
- 18 banks exist only in USA, including `xband1` (540,672 bytes) and one `s_nor5c` occurrence.
- 22 banks exist only in Japan, all voice banks.

## Provenance of the #463 asset repo

- `M_007`, `M_015`, `M_021`, `M_025`, `M_026`, `M_030`, `M_032`, `M_037`, `M_039.AIF`
  are byte-identical on both discs and in the asset repo.
- `M_058..M_067.AIF` (10 files) and `LOADING.BMP` match USA only. Japan has different
  `M_058..M_067` and a Japan-only `M_087.AIF`. Total: 20 USA and 9 Japan exact matches.
- The asset repo's `BOMSS1..3.CPK` match neither disc. `BOMSS1.CPK` and `BOMSS3.CPK`
  are byte-identical between USA and Japan, while `BOMSS2.CPK` differs. Asset-repo
  `BOMSS2.CPK` has 2,845 `STAB` video frames against 3,414 on both NTSC discs. That ratio
  is exactly 5/6, the same as 25 fps to 30 fps. **Hypothesis:** the asset-repo CPKs are
  PAL rips. No PAL disc is available to confirm this, so they must not be used for NTSC profiles.

## CD-DA tracks 02..30

Relative to USA, Japan's audio is offset by −588 stereo samples, which is one CD-DA sector.

- Tracks 19, 22, 24, 25, 26 and 30 are bit-exact over the whole overlap, and the non-overlapping edges are all zero.
- The remaining aligned tracks differ in a total of 17,766 of 433,666,464 overlapping bytes (99.9959% identical).
  The differences are scattered at tens to about 1,700 bytes per track. The cause is unknown:
  it could be rip/read noise or a mastering difference.
- Track 02 differs in length by one sector and was not aligned.
- The mapping from tracks to game screens is unknown and needs runtime observation.

## Not established

This report does not establish:

- Decompression or section formats inside any bank, or any graphics, palette, map or sequence extraction.
- Runtime load behaviour, menu or stage graph, gameplay rules, timings or CPU behaviour.
- Emulator-versus-hardware accuracy.

No assets were uploaded to `SaturnBomberman-Assets`. The overall coverage denominators for
campaign, battle, characters, items and audio remain `unknown` in the
[coverage ledger](../asset-audit/saturn-coverage-ledger.json).

## Next: `EXP-SAT-ARCHIVE-002`

1. Statically segment `base1` and one byte-identical world bank (`normal2`) at the header
   slots. Identify code versus data sections and candidate compression headers.
2. Coordinate one heavy slot with Codex. On a separate forked core build (#468 inputs and
   states unchanged), restore a #27 checkpoint after the game loads those banks, and export
   Low-WRAM `0x00200000..0x00300000` privately.
3. Compare the exported memory with the static bank bytes. If they are identical, the
   verbatim-copy hypothesis holds. If they differ, the differences mark compressed or
   relocated sections, and the decoder is validated byte-exact against the resident data.
4. Only after that comparison, publish lossless decoded sections with manifests to the
   private `SaturnBomberman-Assets` repo, on a dedicated branch.
