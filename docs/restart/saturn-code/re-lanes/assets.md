LANE-STATUS: ACTIVE

# Lane ledger: assets (graphics, animation, stage data, text, movies)

Scope: every non-audio asset of Saturn Bomberman, USA MK-81070 V1.003
first, with Japan where it differs. That covers VDP1 sprites and palettes,
sprite animation tables, VDP2 cells, maps and backgrounds, stage data, fonts
and text, UI layouts and the FILM movies. Audio banks and files are
classified here but owned by `sound-68k`. Issues: #485, #486, #487, #489,
#494, #28 and the REF inventories #395–#399. Gemini's #464 is read-only.

Outputs live only in the private `elgansayer/saturn-bomberman-decomp`
repository (`assets/usa/…`, recipes in `tools/assets/`). This ledger records
counts, formats in our own words and the private commit, with no game bytes.

## Denominator

Every file and byte range on the disc must be classified, and every asset
inside it extracted by a deterministic recipe with a manifest (source
file/offset/hash → output hash).

### `BOMSS/PROGRAM.BIN`: 72 kernel-directory banks

| Bank class | Banks | Status |
| --- | ---: | --- |
| Graphics: `base1`, `base2`, `openning`, `normal1`–`5`, `battle1`, `master1`, `staff`, `xband1` | 12 | decoded |
| Sound `s_*` (slot-10 SCSP transfers) | 11 | classified; owner sound-68k |
| Voice `s_vo*` | 45 | classified; owner sound-68k |
| Headerless (ids 23, 41, 42, 43) | 4 | classified unknown; semantics open |
| Bytes after the last directory entry (2,169,666 B) | — | build-container residue |

Extracted from the 12 graphics banks (run 20261105T1123Z):

| Category | Extracted / known |
| --- | ---: |
| CRAM palettes (slot 1) | 414 / 414 |
| VDP1 sprite frames (slot 8) | 11,695 / 11,695 (34,681 parts) |
| VDP1 unique pixel blocks | 10,659 / 10,659 |
| Sprite animation sequences | 4,915 / 4,915 |
| VDP2 cell blocks (slot 0) | 84 / 84 decoded, 0 rendered |
| VDP2 maps (slot 2) | 65 / 65 decoded, 0 rendered |
| Stage grids (slot 7) | 115 / 115 |
| Record tables in slots 3, 4, 5, 6 and 9 | 0 / 293 (semantics open) |

Sprite format check: all 34,681 parts are VDP1 4-bit colour-bank sprites,
and each one's decoded pixel length equals width × height / 2. A frame is a
list of 20-byte part records (control, character id, draw mode, colour
offset, size, x/y offset, pixel-block pointer). A sequence is a list of
(frame, duration) pairs. Pixel indices are exact. Colours are previews until
each object's runtime colour base is bound from the draw code or a capture.

Other disc files: 429 ISO files remain to classify with this lane's tools.
The accepted Gemini inventory has 56 unknown files (NETLINK fonts and width
tables, XBAND data, `FLD_KNL.BIN`, `XBMAP.BIN`).

## Private repository state

- Commit `8c81955`: recipe `tools/assets/extract_program_bin.py`, disc
  reader `tools/assets/satdisc.py` (it matches all 430 accepted USA file
  hashes), and outputs under `assets/usa/program_bin/` (478 hashed outputs,
  checked by `tools/assets/verify_manifest.py`).

## Frontier

1. Bind runtime sprite colour bases for exact palettes, and confirm against
   VDP1/CRAM captures.
2. Bind VDP2 colour depth and cell size, then render backgrounds from
   cells, maps and palettes.
3. Record semantics for slots 3–6 and 9 (object and stage tables).
4. Classify the other disc files, the 4 headerless banks and the FILM movies.
5. Japan differences.

## Run log

- 20261105T0828Z–1028Z: no work; the runs stopped at start on the account
  usage limit.
- 20261105T1123Z: first working run; PROGRAM.BIN graphics extraction.
