# `tools/saturn_disc` — Static Sega Saturn Disc, `IP.BIN`, ISO-9660 & Byte-Range Inspector

Dependency-free Python 3 stdlib tooling for Milestone 2 (`EXP-SAT-DISC-001`) of `#464`, supporting `#394` (`REF-001`), `#28`, and `#399` (`REF-006`).

## Responsibilities & non-claims

- Parses `.cue` layouts (`MODE1/2352`, `MODE1/2048`, `MODE2/2352`, `AUDIO`) strictly inside a confined read-only media root (rejecting symlinks and path escapes).
- Validates raw ECMA-130 CD-ROM Mode 1 12-byte sync headers, BCD `mm:ss:ff` timestamps, and 32-bit EDC CRCs across every logical block of Track 01.
- Extracts and validates Sega Saturn `IP.BIN` (System Area LBAs `0..15`), compatible area symbols (`J`/`T`/`U`/`E`), nominal display standards, peripheral codes, and Master/Slave SH-2 boot metadata without exporting security/executable bytes.
- Walks the ISO-9660 Volume Descriptor Set and directory hierarchy, accounting for **100% of Track 01 logical blocks** (`executable`, `decoded`, `identified_undecoded`, `padding`, or `unknown`, including detection of any unreferenced non-zero sectors outside ISO-9660) and **100% of CD-DA Track `02..N` bytes**.
- Classifies ISO-9660 files by binary magic/structure rather than trusting file extensions (Master SH-2 first-read boot binary, Sega `FILM` `.CPK` streams with `STAB` completeness checks, `FORM/AIFF` audio, Motorola 68000 sound driver vectors, SCSP sound area maps, big-endian offset/length container hypotheses, ASCII/Shift-JIS text, and zero-filled padding).
- Cross-checks disc track hashes and `IP.BIN` identity against `#462` media reports and matches ISO-9660 file SHA-256s (plus 2 MiB prefix hashes) against `#463`'s `SaturnBomberman-Assets` manifest.
- Diffs regional releases (`USA` vs `Japan`) without blending profiles, including bit-exact CD-DA stereo sample-offset alignment testing.
- **What this tool does NOT prove**: Static filesystem and EDC validity do not prove emulator boot compatibility, runtime decompression semantics, animation frame durations, or gameplay rule parity. Synthetic tests in `check.py` verify parser invariants only.

## Usage

```bash
# Run synthetic unit tests
python3 tools/saturn_disc/check.py

# Inspect a read-only CUE disc image
python3 tools/saturn_disc/cli.py inspect \
  --root /home/dev/Sega-Saturn-BIOS \
  --cue "Saturn-Bomberman-EN/Saturn Bomberman (USA) (1S).cue" \
  --media-report /home/dev/neptune-research-private/462/usa.media.json \
  --assets-manifest /home/dev/neptune-gemini-research-private/463/asset_audit_manifest_run1.json \
  --private-out /home/dev/neptune-gemini-research-private/disc-inventory/usa-mk81070-v1003.full.json \
  --summary-out docs/restart/saturn-disc/usa-mk81070-v1003.summary.json

# Diff USA and Japan summaries (with optional CD-DA sample-shift verification)
python3 tools/saturn_disc/cli.py diff \
  --left docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --right docs/restart/saturn-disc/japan-t14302g-v1000.summary.json \
  --left-root /home/dev/Sega-Saturn-BIOS \
  --right-root /home/dev/Sega-Saturn-BIOS \
  --output docs/restart/saturn-disc/usa-vs-japan.diff.json

# Validate committed summaries and regional diff
python3 tools/saturn_disc/cli.py verify \
  --summary docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --summary docs/restart/saturn-disc/japan-t14302g-v1000.summary.json \
  --diff docs/restart/saturn-disc/usa-vs-japan.diff.json
```
