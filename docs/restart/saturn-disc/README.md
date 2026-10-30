# Saturn disc inventories (`EXP-SAT-DISC-001`)

Committed outputs of [`tools/saturn_disc`](../../../tools/saturn_disc/README.md) for the two
supplied Saturn Bomberman discs. They contain metadata only: sizes, sector ranges, SHA-256
digests and structural fields. No disc, BIOS, track, file or memory bytes are committed.
The full per-sector manifests stay private under `/home/dev/neptune-gemini-research-private/disc-inventory/`.

| File | Schema | Content |
| --- | --- | --- |
| `usa-mk81070-v1003.summary.json` | `neptune.saturn-disc-inventory.v1` | USA `MK-81070 V1.003`, area `U` |
| `japan-t14302g-v1000.summary.json` | `neptune.saturn-disc-inventory.v1` | Japan `T-14302G V1.000`, area `J` |
| `usa-vs-japan.diff.json` | `neptune.saturn-disc-diff.v1` | Regional comparison (no profile blending) |

Each inventory summary records: the CUE and every track hash; Track 01 Mode 1 EDC results;
the `IP.BIN` header; the ISO-9660 volume, directories and every file with its sector extent,
SHA-256 and magic-based classification; a gap-free Track 01 block accounting
(`decoded`, `executable`, `identified_undecoded`, `padding`, `unknown`); CD-DA silence/peak
summaries; matches against the #463 asset-repo manifest; and a cross-check with Codex's #462 media report.

Results and interpretation: [evidence report](../evidence/2026-10-30-gemini-saturn-disc-inventory.md).

## Verify the committed files (no media needed)

```sh
python3 tools/saturn_disc/check.py
python3 tools/saturn_disc/cli.py verify \
  --summary docs/restart/saturn-disc/usa-mk81070-v1003.summary.json \
  --summary docs/restart/saturn-disc/japan-t14302g-v1000.summary.json \
  --diff docs/restart/saturn-disc/usa-vs-japan.diff.json
```

## Regenerate (needs the private media root, read-only)

Use the `inspect` and `diff` commands in the [tool README](../../../tools/saturn_disc/README.md#usage).
Run each command twice and compare outputs with `cmp`. The committed files were
produced this way, and both runs matched byte for byte.

## Limits

- Static structure only. These files do not show that the game boots, how banks are
  decompressed, frame timings or any gameplay rule.
- Classification is by magic bytes and structure, not file extension. Files that fail
  every check are counted as `unknown`.
- Bank role labels such as `campaign_world_bank` come from the bank's ASCII name.
  They are hypotheses, not decoded content.
- USA and Japan are separate profiles. The diff is for provenance and regional deltas
  only. Neither region can stand in for the other.
