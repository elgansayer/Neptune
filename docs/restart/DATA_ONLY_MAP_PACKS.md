# Additive local map packs: first PACK-001 slice

Issue [#545](https://github.com/elgansayer/Neptune-Bomberman/issues/545) implements
the local map portion of [PACK-001/#237](https://github.com/elgansayer/Neptune-Bomberman/issues/237).
It reuses `MapLoader`, `MapManager`, room/spawn validation and the existing map
snapshot channel. The trusted stage PCK converter remains an author-time input.
Original character/Tirra/stage authoring projects and bundled PCKs are preserved.

This is a runtime implementation for explicit host-selected maps. It does not
implement archive installation, downloads, public registries, dependency solving,
character selection, creator effects or reference fidelity. The broader PACK
issues remain open. First-party content migration to this API is still future work.

## Host a map

Use the pinned current stable Godot binary, with the ordinary server scene:

```sh
godot --headless --path . res://main_server.tscn -- \
  --room-pack=res://tests/fixtures/content/orchard \
  --room-map-id=example.orchard:arena --room-seats=4 --room-fill-to=4
```

`--room-pack` accepts an absolute local directory, `res://` or `user://` directory.
It must accompany `--room-map-id` and cannot accompany the older `--room-map`
option. This is trusted host startup configuration, never a client RPC. An invalid
manifest, missing selection or incompatible dependency refuses the room before
the server listens; it never silently switches to the default map.

Without these options the existing default selection is unchanged. Registered
map geometry is sent through the current reliable map payload and rendered with
the existing geometry renderer. The payload includes `map_config.content_identity`
with pack ID/version, content ID, manifest SHA-256 and content SHA-256. Clients do
not instantiate resources or execute scripts from the selected directory.
This demonstrates geometry replication, not a complete asset-download journey.

## Files and identities

See the complete original examples:

- [Orchard manifest](../../tests/fixtures/content/orchard/pack.json) and
  [map](../../tests/fixtures/content/orchard/arena.json).
- [River manifest](../../tests/fixtures/content/river/pack.json) and
  [map](../../tests/fixtures/content/river/arena.json).

`pack.json` uses schema `neptune.pack/1`. Every field is required: `schema`, `id`,
`version`, `author`, `license`, `provenance`, `dependencies` and `content`. Unknown
fields fail. Pack IDs use lowercase dotted namespaces, such as `example.orchard`.
The first components `neptune`, `engine`, `godot` and `builtin` are reserved.
Versions are exact canonical `major.minor.patch` strings, with at most six digits
per component. Text fields are non-empty and at most 256 characters.

Content entries contain `id`, `type`, `path`, and `sha256`. IDs have the form
`<pack-id>:<local-name>`. Version 1 supports only `type: "map"` and relative JSON
paths. Hashes are lowercase SHA-256 over the exact file bytes. Dependencies are
at most 32 unique `{ "id": "another.pack", "version": "1.0.0" }` objects. The
caller must register exact dependencies first; there is no range solver, fetching,
automatic version upgrade or legacy fallback.

Each `neptune.map/1` file contains exactly `schema`, `name`, `grid`, `spawn_points`
and `metadata`. Grids are rectangular, 3..256 cells on each axis, using integer
terrain codes 0 (empty), 1 (wall), 2 (active soft block). Spawns are explicit,
distinct `{ "x": 1, "y": 1 }` tile coordinates on empty cells. There are 1..256
declared spawns; existing room validation still decides supported player capacity.
Tile size remains the native 16 pixels. `metadata` is descriptive JSON and is not
interpreted as executable resources or configuration. The registry supplies the
authoritative `content_identity` field after validation.

## Registry and failure behaviour

`PackRegistry.register_directory()` validates the whole manifest and every map
before publishing any entry. Two packs with distinct namespaces coexist.
Duplicate IDs/paths and a second version of a selected pack are rejected within
one registry/session. Separate registries can select different versions; this
does not prevent versioned files coexisting on disk. There is no global mounting
or last-load-wins replacement. Registration and lookups return detached data;
editing files or a returned dictionary cannot change already-selected content.

The runtime reads declared JSON through `FileAccess` only. It never calls
`ResourceLoader`, instantiates pack scenes or mounts a pack PCK. Unreferenced
files are not loaded. Relative paths reject traversal, absolute/resource paths,
backslashes, uppercase aliases, Windows device names and unsupported extensions.
Symlinked roots, ancestors, directories and files fail. Limits are 64 KiB for the
manifest, 64 content entries, 4 MiB per map and 16 MiB total map JSON. UTF-8,
duplicate JSON object keys (including escaped spellings), grid cells, spawn
coordinates, content hashes and schema fields are checked before activation.
These directory checks are not an archive-extraction or decompression sandbox.

Expected rejection returns `{ "ok": false, "error": { "file": ..., "field": ...,
"code": ..., "message": ... } }`, rather than logging a script error. Duplicate
JSON keys identify their key and character offset; parser failures include their
source line. The host retains the full diagnostic on room refusal.

## Continue the stage authoring workflow

The existing TileMap authoring project and `MapPackLoader` conversion are reused.
In a disposable authoring process, convert a **trusted local** PCK:

```sh
godot --headless --path . --script res://tools/asset_audit/export_map_pack.gd -- \
  --trusted-pck=res://maps/stage1.pck --output=/tmp/stage-one-v1 \
  --id=example.stage-one --version=1.0.0 --author=Neptune \
  --license=LicenseRef-Private --provenance=Trusted-local-stage-conversion
```

All seven options are required. The exporter creates a new directory, writes
the map and hash-bound manifest, and validates registration before reporting
`NEPTUNE_MAP_EXPORT`. An existing output is refused without changing its files.
The original PCK is unchanged. Supply the actual author/licence/provenance; the
example private label grants no redistribution permission.

Only this explicit trusted authoring step mounts a PCK and instantiates its
scene. PCKs may contain scripts: never run it on automatic downloads. Version 1
exports static terrain; authored soft-slot cells become active soft blocks.
It does not reproduce random soft-block density, tile art, audio or every stage
behaviour. Existing defaults and original reference evidence remain separate.

## Verification and next steps

`test_pack_registry.gd` exercises two original fixtures, names/versions, immutable
selection, dependency diagnostics, hash/UTF-8/schema/parser failures, symlinks,
atomic rejection, default preservation and real room/actor creation. The existing
native capacity probe also starts a pack-selected server with two authenticated
clients and two bots, verifies map identity/geometry and rejects an extra actor.
Bad pack/ID/option selections must fail before listening. Existing gameplay,
default-room and native runtime checks remain required.

Next: extend the repaired Robin Hood atlas export into a declarative character
schema, then bind a selected namespaced character to each participant. Reuse
PACK-002/003/004/005/006 for locks, immutable installation, archive validation and
capability/loading boundaries; ROOM/PACK download tasks then prove clean-client
sharing. Do not expose the trusted legacy PCK loader as the download mechanism.
