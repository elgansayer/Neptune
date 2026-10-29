# Saturn lab: input inventory and locks

Python 3.11+, standard library only. Run commands from the repository root.
These tools operate locally; no files are sent to an AI service.

## Inventory an existing asset checkout

```sh
python3 tools/saturn_lab/cli.py inventory /srv/neptune/repos/SaturnBomberman-Assets \
  --output /srv/neptune/private/manifests/assets.inventory.json
```

Reports sorted relative paths, byte sizes, streaming SHA-256 hashes and groups of
byte-identical files. PNG header dimensions are reported when readable; this is
not complete image validation or provenance certification. `.git`, `.godot`,
`__pycache__` and `.venv` directories are excluded. Symlinks and unreadable files
cause failure; they are not silently followed/skipped. An existing output file is
excluded from the inventory to keep repeat runs stable.

## Lock a reference input set

Place the actual inputs below a private root. In this example their relative paths
are `disc/game.cue`, `bios/saturn.bin`, `emulator/core.so` and
`settings/reference.json`. Substitute actual filenames and the correct region.
The settings file must contain a non-empty JSON object describing the actual
configuration intended for the future emulator bridge; this tool does not apply it.

```sh
python3 tools/saturn_lab/cli.py lock \
  --root /srv/neptune/private \
  --disc disc/game.cue \
  --bios bios/saturn.bin \
  --emulator emulator/core.so \
  --settings settings/reference.json \
  --region usa \
  --output /srv/neptune/private/manifests/reference.lock.json
```

The CUE and every referenced BINARY track are included. CUE references must use
portable relative paths within the CUE's directory (or its subdirectories).
Parent traversal, absolute paths, Windows separators and symlinks are rejected.
CHD is accepted as a single opaque input file; the tool does not decompress or
validate its container. WAV/MP3 track declarations, bare BIN and ISO inputs are
currently unsupported. Preserve the original complete disc separately.

```sh
python3 tools/saturn_lab/cli.py verify \
  --root /srv/neptune/private \
  --lock /srv/neptune/private/manifests/reference.lock.json
```

Verification re-hashes every input, validates the manifest and requires complete
coverage of the selected CUE tracks. Changing a track, BIOS, core or settings
causes a non-zero exit. Locks contain relative paths and can move with the input
root. They are not signatures: protect the lock itself in research evidence storage.

Output JSON is atomically replaced. Existing output must be a JSON document with
the same schema; unrelated files and symlinks are refused. Use a dedicated output
path. The lock command also explicitly refuses to overwrite selected inputs.

## Tests and scope

```sh
python3 tools/saturn_lab/check.py
```

Tests use synthetic bytes in temporary directories, including multitrack input,
tampering, omitted dependencies, unsafe paths and failure exits. No test requires
or includes a disc, BIOS or emulator. The check fails if no tests are discovered.

Not implemented yet: emulator boot/control, graphics extraction, archive decoding,
animation reconstruction, repeatability measurement, gameplay parity and a live
AI factory. Track those separately in `docs/restart/BACKLOG.md`.
