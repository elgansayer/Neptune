# Saturn `PROGRAM.BIN` bank directory & resident decode receipts (`EXP-SAT-ARCHIVE-002`)

Committed public-safe receipts of [`tools/saturn_archive`](../../../tools/saturn_archive/README.md) for [`#484`](https://github.com/elgansayer/Neptune-Bomberman/issues/484) (`RSAT-007` under [`#464`](https://github.com/elgansayer/Neptune-Bomberman/issues/464)). These files contain structural metadata, sector/address bounds, codec parameters, SHA-256 digests, resident byte-equality ratios, and negative-control outcomes only. No disc, BIOS, save-state, framebuffer, or raw RAM/VRAM bytes are committed. Private checkpoints remain under `/home/dev/neptune-research-private/27/` and `/home/dev/neptune-gemini-research-private/484/`.

| File | Schema | SHA-256 | Content |
| --- | --- | --- | --- |
| `usa-mk81070-v1003.kernel-directory.json` | `neptune.saturn-archive.kernel-directory.v1` | `7fb543edca68969ed06658948cfafa649e61b7706fc814e7d6b2862df9fe2d55` | USA `BOMSS/0KRNL.BIN` 72-entry directory & 100% `PROGRAM.BIN` sector/header reconciliation |
| `japan-t14302g-v1000.kernel-directory.json` | `neptune.saturn-archive.kernel-directory.v1` | `82b6aebd754e5e37d7fff60d35e7d49160bc8afde06b6d4d30883f55ac5c3d47` | Japan `0KRNL.BIN` 66-entry directory & 100% `PROGRAM.BIN` sector/header reconciliation |
| `usa-mk81070-v1003.base1-decode.json` | `neptune.saturn-archive.bank-decode.v1` | `657e524ec29ab6b0055a3aa695f288d24af669b015dfb56615434a8dcb3dd091` | USA `base1` (`bank_id=1`, `0x00200000..0x00254000`) slot & Hudson-codec decode manifest |
| `cross-region.normal2-decode.json` | `neptune.saturn-archive.bank-decode.v1` | `8fc054ab3c1d693fc31437e03e4539460cb5619ae87b8f056ce5a45e37182976` | Byte-identical USA/Japan `normal2` (`bank_id=5`, `0x00254000..0x002e0000`) decode manifest |
| `base1-normal2-resident-comparison.json` | `neptune.saturn-archive.resident-comparison.v1` | `05c430723e1e39e3bb19c10ac99bb862e8021451493ee37973af494beed43319` | Resident `WorkRAML`/`WorkRAMH`/`VDP1`/`VDP2`/`SCSP` comparisons, two-run replay determinism & `NC-01..NC-06` |

Historical findings and the **2 November technical correction**:
[evidence report](../evidence/2026-10-30-gemini-program-bin-archive-002.md#correction-and-supersession--2-november-2026).
The original prose codec/layout specification and CUE digests conflict with the
merged implementation and disc metadata. Use the correction, tools and receipts;
do not copy the superseded layout into new extractors. No original-host replay or
input rehash is claimed by that documentation reconciliation.

## Verify committed receipts (offline, no private media or states required)

```sh
python3 tools/saturn_archive/check.py
python3 tools/saturn_archive/cli.py verify \
  --directory docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json \
  --directory docs/restart/saturn-archive/japan-t14302g-v1000.kernel-directory.json \
  --bank docs/restart/saturn-archive/usa-mk81070-v1003.base1-decode.json \
  --bank docs/restart/saturn-archive/cross-region.normal2-decode.json \
  --comparison docs/restart/saturn-archive/base1-normal2-resident-comparison.json
```

## Regenerate (requires read-only private media root and resident checkpoints)

Run `audit-directory`, `decode-bank`, and `compare-resident` from [`tools/saturn_archive/README.md`](../../../tools/saturn_archive/README.md#usage). Every committed file was generated twice and verified byte-identical via `cmp -s`.

## Limits

- Synthetic tests in `tools/saturn_archive/check.py` validate parser/codec logic only; original-game claims rest on the real-disc decode receipts and resident memory comparisons.
- Slots `3, 4, 5, 6, 9` record layouts remain open under their code/consumer research tasks. `0x060095E0` SCSP audio command payloads (`Slot 10` and stage `Slot 2`) remain open under **RSAT-011 / #488**; the RSAT-008 references retained inside historical JSON receipt text are task-reference errors (RSAT-008 / #485 covers VDP1).
- Slot 8's decoder reads a pixel pointer at descriptor +16 and requires 20 readable bytes. This is not a proven fixed stride or a recovered dimensions/palette/anchor/animation layout.
- USA and Japan remain separate regional profiles (`base1` differs; `normal2` is `573,440 / 573,440` bytes identical across both discs).
