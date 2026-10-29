# Asset audit tooling (`#463`)

Python 3.11+, standard library only. Operates locally on a read-only checkout
without modifying source files or uploading image/audio bytes to external services.

## Usage

First run the baseline `saturn_lab` byte inventory:

```sh
python3 tools/saturn_lab/cli.py inventory /path/to/SaturnBomberman-Assets \
  --output /private/output/saturn_lab_inventory.json
```

Then run the full structural, provenance, and gap audit:

```sh
python3 tools/asset_audit/cli.py audit /path/to/SaturnBomberman-Assets \
  --saturn-lab-inventory /private/output/saturn_lab_inventory.json \
  --private-manifest /private/output/asset_audit_manifest.json \
  --summary-output docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json \
  --require-clean-git
```

Validate a committed summary manifest and coverage ledger:

```sh
python3 tools/asset_audit/cli.py verify-summary \
  docs/restart/asset-audit/saturn-assets-b55b5a55.summary.json
python3 tools/asset_audit/cli.py verify-ledger \
  docs/restart/asset-audit/saturn-coverage-ledger.json
```

Run synthetic unit and failure-boundary checks:

```sh
python3 tools/asset_audit/check.py
```

## Boundaries

- Reuses `tools/saturn_lab/cli.py` byte hashing, exact-duplicate grouping, and symlink rejection.
- Distinguishes `header_only` inspection (`--header-only-png`) from `full_stream` PNG chunk CRC32 + `zlib` IDAT scanline verification, Sega `FILM` (`STAB`) payload completeness, `AIFF` (`COMM`), `BMP`, `GIF`, `JPEG`, `AVIF`, `XCF`, `Ogg`, `AU`, `JSON`, `XML`, and Godot `.import` checks.
- Keeps filename/directory categories explicitly labelled as unverified leads (`saturn_provenance_verified: false`).
- Rejects any summary that claims Saturn runtime fidelity or applies Neptune's `Apache-2.0` licence to unverified reference assets.
