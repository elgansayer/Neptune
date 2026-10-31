# Continue the existing pack authoring experiments

These projects are the starting point for the mod/customisation engine. Extend
their useful authoring and rendering work before proposing replacements.

For the first additive runtime path, see [data-only arena packs](#data-only-arena-packs)
below. The existing scene/PCK authoring experiments and the new JSON runtime path
coexist; the latter never mounts an uploaded scene or script.

| Project | Existing workflow |
| --- | --- |
| [Robin Hood](characters/bomberman-player-robin-hood/player.tscn) | TexturePacker sheet/PNG, atlas regions and trim margins, 36 named animations, frame timing and sprite anchor. The visual scene is separate from server collision/abilities. |
| [Blue Tirra](tirra/blue/tirra.tscn) | Three growth stages, animation/frame data, rider positioning and a trusted presentation controller. |
| [Stage 1](stages/bomberman-stage1/Stage.tscn) | TileMap layers for floor/walls and spawns/soft blocks, background art and map identity/version/dimensions. |

Inspect the corresponding exports in `characters/`, `tirra/` and `maps/`, plus
the main project's PCK loader, client animation paths and `shared/maps/` APIs.
These exports use shared root paths and may contain executable resources. They
are trusted local experiments, not validated public download packages. Preserve
them while adding namespaced identities, per-player selection, data-only author
exports, dependency locks and automatic distribution. Mods remain additions.

## Open, rebuild and check

From the repository root, use the current stable Godot executable:

```sh
godot --headless --editor --path "pack projects/characters/bomberman-player-robin-hood" --import
godot --headless --path "pack projects/characters/bomberman-player-robin-hood" --script "$PWD/tools/asset_audit/check_character_pack.gd"
godot --headless --path "pack projects/characters/bomberman-player-robin-hood" --export-pack Linux /tmp/robin-hood-test.pck
```

The check reports actual animation/frame-use counts, the sprite offset and a
fingerprint of frame pixels/timing. It rejects missing scenes/sprites/textures,
empty animations and unknown arguments. It is an author-time probe for trusted
projects/exports, not the public pack validator. Options after `--` are
`--scene=res://player.tscn`, `--sprite=AnimatedSprite2D` and `--pack=/absolute/path.pck`.

For a round trip, run the same checker from a separate empty Godot project with
`--pack=/tmp/robin-hood-test.pck` and compare the source/export JSON results.
Inspect logs as well as exit codes: Godot can return zero after editor script
errors. Use disposable copies and writable XDG data/config/cache directories for
automated checks, so authoring imports do not rewrite the working checkout.
Do not overwrite the checked-in PCKs until a deliberate, verified content update.

The Robin Hood atlas directories are west/east/north/south; its public animation
names currently use left/right/up/down. These are different contracts. Preserve
the client animation vocabulary while fixing file references or adding aliases.

## Importer provenance and compatibility

Checked 30 October 2026 against official upstream releases:

- Godot [4.7.2 stable](https://github.com/godotengine/godot/releases/tag/4.7.2-stable)
  was used for isolated authoring validation. Archive SHA-256:
  `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4`.
- Both projects vendor the existing CodeAndWeb TexturePacker importer, updated
  to [v4.3.0](https://github.com/CodeAndWeb/texturepacker-godot-plugin/releases/tag/v4.3.0),
  retaining its MIT licence/notices and upstream normal-map support.
- The downstream compatibility patch adds an explicit empty-string return for
  an unknown preset in `_get_preset_name()`. Godot 4.7.2 rejects the upstream
  function because not all paths return a value. The valid default preset is unchanged.

Recheck upstream versions under the dependency policy; these are recorded test
identities, not permanent version ceilings. This isolated authoring result does
not certify a whole-game/native-addon/browser migration to Godot 4.7.2.

## Data-only arena packs

The first PACK-001 runtime slice connects a versioned manifest and additive
registry to the existing JSON `MapLoader`, authoritative room, bots and geometry
renderer. Administrators can select a local arena by content ID; existing default
PCK startup and `--room-map` selection remain available.

Two original examples live in `demo/packs/standard/` and `demo/packs/wide/` in the
main project. Their `arena.json` files are byte-identical to the existing
`maps/neptune_standard.json` and `maps/neptune_wide.json` fixtures. They use the
same schema and execution path as a creator's local pack, without an example-ID
branch in the game. They contain no reference-game art.

From the repository root:

```sh
godot --headless --path . res://main_server.tscn -- \
  --room-pack=res://demo/packs/standard/manifest.json \
  --room-pack=res://demo/packs/wide/manifest.json \
  --room-arena=example.wide:arena --room-seats=4 --room-fill-to=4
```

Repeat `--room-pack` for each explicitly selected manifest (maximum 32). Supply
`--room-arena` with it, and omit `--room-map`. Manifest paths must be normalized
local `res://` or `user://` JSON paths. A private creator can place a directory
under `user://packs/` without publishing to a workshop or rebuilding the engine.
An invalid selection refuses before the server listens, with source/field
diagnostics; it never silently selects the legacy arena.

### Manifest contract

```json
{
  "schema": "neptune.pack.v1",
  "pack_id": "creator.example:my_pack",
  "version": "1.0.0",
  "author": "Creator name",
  "license": "Apache-2.0",
  "dependencies": [],
  "content": [{
    "id": "creator.example:my_arena",
    "kind": "arena",
    "path": "arena.json",
    "sha256": "replace_with_64_lowercase_hex_digits_of_the_exact_arena_file"
  }]
}
```

The digest above is a placeholder, not a runnable example. Use either committed
example for valid data. Compute a definition digest from its exact bytes, for
example `sha256sum arena.json`. Any change requires a new immutable pack version
and an updated digest. Metadata is not proof of authorship or reuse permission.

- Every field shown is required; unknown fields and duplicate JSON keys fail.
  JSON must be canonical UTF-8 without decoding replacements. Each manifest and
  selected arena definition is limited to 64 KiB and 32 nesting levels.
- IDs are lowercase `namespace:name`, at most 128 characters. Namespace segments
  begin with a letter and allow letters, digits, `_` and `-`, separated by dots;
  content names begin with a letter and allow letters, digits, `_` and `-`.
  Content must use its pack's namespace. Root namespaces `engine`, `neptune`,
  `builtin` and `saturn` are reserved. Namespace validation is isolation, not a
  verified publisher-ownership service.
- Versions are exact stable `major.minor.patch` strings, without leading zeroes,
  ranges, prerelease or build suffixes. Author and licence strings are nonblank
  and bounded to 128 characters. Retain provenance separately when migrating art.
- A pack has 1–128 content entries. Definition paths are normalized relative
  portable ASCII paths ending in `.json`; no absolute paths, traversal, URL,
  backslash, query or percent encoding. Manifest/payload paths reject symlinks.
- Dependency descriptors have exactly `pack_id`, `version`, `manifest_sha256`;
  at most 32 declarations are accepted. Dependency resolution is still #250:
  the current runtime refuses a nonempty dependency list rather than guessing.
- The metadata validator recognizes `arena`, `character`, `powerup`, `mode`,
  `campaign` and `collection`. The current room adapter accepts arena packs only.
  Recognition is not implementation of the other kinds' gameplay or asset schemas.

### Additions, versions and verification

`shared/content/pack_manifest.gd` validates definitions and computes
`manifest_sha256` from the exact manifest text bytes. Each entry's `sha256`
identifies its definition file. These are different digests; neither is called a
PCK hash. `session_content_registry.gd` stores detached metadata for immutable
releases, then explicitly selects a collision-free set for one session.

Versions can coexist in the in-memory catalogue. Different bytes for the same
pack ID/version are refused. Selecting another version of an already selected
pack or an addition that shadows a selected content ID fails atomically. No
load order can replace the original selection. This catalogue is not an on-disk
installer or download cache.

`arena_pack_loader.gd` reads and verifies the **chosen arena** against its digest,
preflights grid/spawn/text types and budgets, then reuses the existing JSON map
conversion. Selection metadata for other registered entries does not claim that
their payloads have been installed or verified. The room sends a detached chosen
content descriptor and selected-manifest identities with its initial map; local
filesystem paths stay off the wire. This is not a client content-lock handshake.

Preserve the stage project's TileMap-to-grid conversion and metadata when adding
an author-time exporter. Source stage version `1.0` must be explicitly normalized
to a public semantic release such as `1.0.0`, retaining the original source identity.
Player/Tirra atlases, animation names/timing, trim margins and offsets remain the
source for subsequent character definitions and per-player selection. This slice
does not replace those experiments or make their executable PCKs public packs.

### Runtime checks

```sh
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_pack_manifest --timeout 60
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_pack_room --timeout 60
python3 tools/godot/check_runtime.py --godot /absolute/path/to/godot --room-only
```

The final command uses real local servers and native clients. It includes both
registered arenas with two humans, two bots, actual auth/admission, initial map
identity, active-round snapshots and full-room refusal, alongside the existing
legacy capacity/layout cases. Unit scenarios also exercise the existing client
geometry renderer. These checks do not establish a complete match, browser play,
automatic downloads, per-player avatar sharing or Saturn fidelity.

## Export a trusted stage into the existing arena format

The existing TileMap authoring project and `MapPackLoader` scene-to-grid
conversion can now produce a local data-only arena pack:

```sh
godot --headless --path . --script res://tools/asset_audit/export_map_pack.gd -- \
  --trusted-pck=res://maps/stage1.pck \
  --output=user://packs/stage-one/1.0.0 --id=example.stage-one:pack \
  --version=1.0.0 --author=Neptune --license=LicenseRef-Private \
  --provenance=Trusted-local-stage-conversion
```

All seven options are required. `--output` must be a new portable `user://` or
`res://` directory, compatible with the merged arena loader. The tool reuses
`MapLoader.save_map_to_file`, computes the exact arena digest, writes the existing
`neptune.pack.v1` manifest, then loads it through `ArenaPackLoader` before reporting
`NEPTUNE_MAP_EXPORT`. It refuses an existing output directory without changing
its files. An incomplete authoring export is not an installed or selected pack.

For the checked-in Stage 1, the conversion preserves the 21×14 grid, 147 hard
blocks, 135 authored soft slots and four spawn points. Static exported soft slots
become active soft blocks; random density, art, audio and full stage behaviour
are outside this first arena format. The original source version `1.0` remains
in map metadata while the caller explicitly selects public pack version `1.0.0`.
Metadata also retains `authoring_source_sha256` over the original PCK and the
caller-supplied `authoring_provenance`. The original PCK is never rewritten.

Start a server using the generated pack through the existing runtime:

```sh
godot --headless --path . res://main_server.tscn -- \
  --room-pack=user://packs/stage-one/1.0.0/manifest.json \
  --room-arena=example.stage-one:arena --room-seats=4
```

This is a **trusted author-time** operation in a disposable process: legacy PCKs
may contain executable scenes/scripts. Never use this converter on automatic
downloads. Only its validated JSON output enters the data-only arena runtime.
Supply actual author/licence/provenance; the private example label grants no
distribution permission. This adds no second manifest, registry or host API.

```sh
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_stage_pack_export --timeout 30
```

These checks execute the real exporter and merged loader, including exact
identity/provenance, original/output preservation, input/option rejection and a
mutated-byte negative. The existing full native/room checks remain required.
