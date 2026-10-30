# `tools/saturn_archive` — `PROGRAM.BIN` Kernel Bank Directory, Hudson Ring/Delta Codec & Resident Memory Verifier

Dependency-free Python 3 stdlib tooling for `EXP-SAT-ARCHIVE-002` (`#484` / `RSAT-007` under `#464`), reusing [`tools/saturn_disc`](../saturn_disc/README.md) for Mode 1 EDC-verified ISO-9660 file reads and [`tools/saturn_lab/state_graphics.py`](../saturn_lab/state_graphics.py) for `MDFNSVST` save-state memory extraction without modifying either package.

## Responsibilities & non-claims

- **Live `0KRNL.BIN` bank directory extraction (`banks.py`)**: Locates the parallel `(u16 sector_offset[N], u16 sector_count[N], u32 load_dest[N])` tables via SH-2 literal pool (`72` entries on USA `MK-81070 V1.003` at `0x06093ECC`/`0x06093F5C`/`0x06093FEC`; `66` entries on Japan `T-14302G V1.000` at `0x06095018`/`0x0609509C`/`0x06095120`), reconciles **100% of `PROGRAM.BIN` sectors and bytes**, and partitions all static `0x34` headers (`236` USA / `240` Japan) into active entry starts, mid-slot build residuals, and the unreferenced build-container tail.
- **Hudson Predictive Ring/Delta Codec (`codec.py`)**: Implements the exact decompressor derived from `0KRNL.BIN` (`0x0603443C` direct / `0x0603461C`+`0x0603469E` 4-byte streaming, `0x060B53B4` 1..4-bit selector readers including `0x0603434C`'s 3-byte bit-planar 3-bit reader, `0x060B53C8` 5-mode single/dual ring table, and `0x060B52C4..0x060B5364` 20-entry delta/lookback predictor catalogs).
- **Sub-resource slot unpacking (`codec.py` & `banks.py`)**: Unpacks Slot 0 (`0x06009470` VDP2 pattern blocks), Slot 1 (`0x06008E06` RGB555 CRAM palettes), Slot 2 (`0x060094E2` VDP2 tilemaps where dimensions are non-zero, distinguishing `0x060095E0(slot=2)` SCSP command tables in stage banks), Slot 7 (`0x0600C502` `64x64` u16 stage collision/tile grids), and Slot 8 (`0x06068BDC`/`0x06068B86` two-table VDP1 sprite descriptors and unique pixel blocks).
- **Resident memory comparison & negative controls (`compare.py`)**: Compares both verbatim `MAIN.WorkRAML` staging (`base1` and `normal2`) and unpacked sub-resources across `VDP1.VRAM`, `VDP2.VRAM`, `VDP2.CRAM`, `MAIN.WorkRAMH`, and `SCSP.RAM`, enforces two-run fresh-process replay determinism, and runs 6 falsification/negative controls (`NC-01..NC-06`).
- **Public-safety guard (`cli.py`)**: Rejects symlinks and refuses to emit JSON containing local filesystem prefixes (`/home/`, `/tmp/`, `/var/`, `/opt/`).
- **What this tool does NOT prove**: Synthetic tests in `check.py` verify parser/codec invariants only; original-game recovery rests on the real-media receipts and resident checkpoint comparisons. Slots `3, 4, 5, 6, 9` and `0x060095E0` SCSP binary command payloads (`Slot 10` and stage `Slot 2`) remain explicitly open.

## Usage

```bash
# Run synthetic zero-copyrighted-byte unit tests
python3 tools/saturn_archive/check.py

# Extract live kernel bank directory and audit 100% of PROGRAM.BIN sectors/headers
python3 tools/saturn_archive/cli.py audit-directory \
  --root /home/dev/Sega-Saturn-BIOS \
  --cue "Saturn-Bomberman-EN/Saturn Bomberman (USA) (1S).cue" \
  --release-id usa-mk81070-v1003 \
  --krnl-path BOMSS/0KRNL.BIN \
  --program-path BOMSS/PROGRAM.BIN \
  --disc-summary docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --output docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json

# Decode a specific bank container by kernel bank_id (1 = base1, 5 = normal2)
python3 tools/saturn_archive/cli.py decode-bank \
  --root /home/dev/Sega-Saturn-BIOS \
  --cue "Saturn-Bomberman-EN/Saturn Bomberman (USA) (1S).cue" \
  --krnl-path BOMSS/0KRNL.BIN \
  --program-path BOMSS/PROGRAM.BIN \
  --bank-id 5 \
  --disc-summary docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --output docs/restart/saturn-archive/cross-region.normal2-decode.json

# Compare base1 and normal2 against private resident checkpoints
python3 tools/saturn_archive/cli.py compare-resident \
  --usa-root /home/dev/Sega-Saturn-BIOS \
  --usa-cue "Saturn-Bomberman-EN/Saturn Bomberman (USA) (1S).cue" \
  --usa-disc-summary docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --japan-root /home/dev/Sega-Saturn-BIOS \
  --japan-cue "Saturn-Bomberman-JA/Saturn Bomberman (Japan).cue" \
  --japan-disc-summary docs/restart/saturn-disc/japan-t14302g-v1000.summary.json \
  --menu-checkpoint /home/dev/neptune-research-private/27/menu-release \
  --nav-checkpoint /home/dev/neptune-research-private/27/navigation-release-late \
  --normal2-run1 /home/dev/neptune-gemini-research-private/484/normal2-run1 \
  --normal2-run2 /home/dev/neptune-gemini-research-private/484/normal2-run2 \
  --actions-json /home/dev/neptune-gemini-research-private/484/normal2-actions.json \
  --frames-advanced 20160 \
  --output docs/restart/saturn-archive/base1-normal2-resident-comparison.json

# Offline CI verification of all committed receipts
python3 tools/saturn_archive/cli.py verify \
  --directory docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json \
  --directory docs/restart/saturn-archive/japan-t14302g-v1000.kernel-directory.json \
  --bank docs/restart/saturn-archive/usa-mk81070-v1003.base1-decode.json \
  --bank docs/restart/saturn-archive/cross-region.normal2-decode.json \
  --comparison docs/restart/saturn-archive/base1-normal2-resident-comparison.json
```
