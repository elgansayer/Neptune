# Verified data-only pack cache

This PACK-004/PACK-003 slice extends the manifest, dependency lock, arena and
character loaders already used by the Stage1 and character authoring exporters.
It packages their JSON and raw RGBA8 files without mounting resources or PCKs.
The original fixtures and built-in defaults remain unchanged.

## Archive contract

`shared/content/pack_archive.gd` builds a deterministic stored-only `.npack`
envelope. All integers are unsigned little-endian 32-bit values:

1. Eight ASCII magic bytes: `NEPTPK01`.
2. Manifest byte length, followed by the exact UTF-8 manifest bytes.
3. File count, followed by records sorted by their relative ASCII path.
4. Each record: path byte length, path bytes, payload byte length, payload bytes.

No timestamps, compression, symlinks or executable record types exist. ZIP, PCK
and other archive formats are refused. The complete envelope's SHA-256 differs
from the raw manifest's SHA-256 and each declared payload's SHA-256.

Limits are 32 MiB per archive, 512 file records, 256-byte paths, 16 path components
and 1,024 distinct directory prefixes. Existing 64 KiB JSON and character pixel
budgets also apply. Lengths, truncation and trailing bytes are checked before
materialization. Paths reject traversal, absolute paths, case aliases, portable
device names and file/directory collisions.

Only declared arena/character JSON definitions and their referenced `.rgba` files
are accepted. Every definition and pixel file is validated, including content
not chosen for the current room. Unknown files, scripts, native libraries and
scene resources fail. Existing arena geometry and character animation/pixel
validators supply the semantic checks. Dependencies are installed as independent
releases; the session resolver checks the complete graph before readiness.

## APIs and atomic installation

```gdscript
const Archive = preload("res://shared/content/pack_archive.gd")
const Cache = preload("res://shared/content/pack_cache.gd")
var built = Archive.build("res://demo/packs/standard/manifest.json")
if built.accepted:
    var cache = Cache.new("user://pack-cache")
    var installed = cache.install(built.bytes, built.sha256, built.identity)
    var reused = cache.lookup(built.identity, built.sha256)
```

`Archive.validate(bytes, expected_archive_sha256, expected_identity)` checks the
same contract without writing files. `identity` has exactly `pack_id`, `version`
and `manifest_sha256`. Failures retain reason/field/source diagnostics.

The cache publishes `user://pack-cache/<archive_sha256>/` by renaming a fully
written, rechecked random staging directory. Its only children are
`archive.npack` and `content/`; the latter contains `manifest.json` and the
verified payload paths used by the existing runtime loaders. Successful receipts
return `manifest_path`, `identity`, `archive_sha256` and `reused`.

Lookup revalidates the archive and the complete materialized directory, including
hidden entries. Symlinks at any cache path component, changed bytes, undeclared
files/directories and conflicting final entries fail. Existing releases are never
overwritten or silently repaired. Interrupted `.stage-*` directories are never
addressable as ready content. They may remain after a process crash; this slice
does not implement automatic abandoned-stage collection or a disk quota.

Identical whole archives reuse one immutable cache entry. Per-file deduplication
across different archives, publisher ownership, archive signatures and global
authority over a namespaced ID/version remain separate work. Exact session locks
still reject conflicting releases together. A server-provided digest verifies
transfer integrity; it does not establish the publisher's identity or licence.

## Verification

```sh
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_pack_archive --timeout 30
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_pack_cache --timeout 30
```

Tests use original arena/character fixtures, malformed raw envelopes and local
filesystem tampering. They check immutable coexistence, interrupted installation,
offline loading and exact hash failures. Network sharing uses these same APIs;
see [content sharing](CONTENT_SHARING.md). These checks do not establish Saturn
state, native-pixel or audio fidelity.
