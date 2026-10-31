# Local data-only character visuals

Issue [#548](https://github.com/elgansayer/Neptune-Bomberman/issues/548), a PACK-007/PACK-006 slice,
extends the existing `neptune.pack.v1` manifest and session registry. It reuses
Robin Hood's SpriteFrames/TexturePacker authoring workflow and the existing
GameView animation vocabulary. Network avatar selection, automatic sharing,
archive installation and palette/voice metadata remain separate work.

## Character definition contract

`neptune.character.v1` definitions describe a name, sprite offset, centering,
a named fallback animation, source provenance and named animation sequences.
Each animation declares FPS, looping and ordered frames with relative duration.
Every frame references hash-bound RGBA8 bytes plus explicit width and height.
Trim margins are baked into the rendered frame pixels; the sprite anchor is
retained independently. This preserves the authored presentation without shipping
scene resources, scripts or TexturePacker importer code.

The runtime accepts declared JSON and fixed-layout RGBA8 payloads only. It checks
paths, hashes, exact byte lengths, dimensions, aggregate pixel budgets, timings,
fields and fallback availability before constructing script-free native visual
objects. RGBA8 avoids calling a codec on untrusted compressed images. Authoring
still uses ordinary imported PNG/atlas resources in a trusted isolated process.

This is cosmetic data. It cannot define physics, hitboxes, abilities or native
extensions. Different namespaced characters coexist through the existing session
registry. An explicit local GameView selection applies to one participant before
its visual is created; default and other participant visuals remain unchanged.

## Trusted authoring export

Use the current stable Godot, from the repository root:

```sh
godot --headless --path . --script res://tools/asset_audit/export_character_pack.gd -- \
  --trusted-pck=res://characters/player-robin-hood.pck \
  --output=user://characters/robinhood/1.0.0 --id=example.robinhood:pack \
  --version=1.0.0 --author=Creator --license=LicenseRef-Private \
  --provenance=Trusted-local-authoring-conversion --name=Robin-Hood
```

All eight options are required. Optional `--scene=res://player.tscn` and
`--fallback=state_idle` select the source visual and fallback. Supply actual
licence/provenance; this example grants no redistribution rights. Existing output
directories are refused. Use a new immutable version for changes.

This tool mounts an explicitly trusted PCK in a disposable process, before game
autoloads can mount default-character remaps. Never give it downloaded community
PCKs. The source must have one plain script-free Node2D with one plain
AnimatedSprite2D child. Unsupported transforms/materials are refused; source
images must be decoded, unmipmapped 8-bit RGBA/RGB/luminance/luminance-alpha.
Higher precision sources are refused instead of silently quantized. Existing
TexturePacker AtlasTexture trim margins are baked into the frame image.

The output contains `manifest.json`, `character.json` and deduplicated
`frames/<dimensions>-<sha256>.rgba` files. The existing `neptune.pack.v1` manifest
uses `kind: character`, the caller's pack ID, and `<namespace>:character` as its
content ID. The exporter reloads the output through the runtime and compares a
pixel/timing fingerprint before reporting `NEPTUNE_CHARACTER_EXPORT`. It never
rewrites the source PCK. An interrupted export is not an installed pack.

## Exact fields and budgets

See the small original [Ruby definition](../../demo/characters/ruby/character.json)
and [manifest](../../demo/characters/ruby/manifest.json) for runnable examples.
All fields are required; unknown fields and duplicate JSON keys fail.

| Object | Fields and constraints |
| --- | --- |
| Definition | `schema: neptune.character.v1`, nonblank `name` (128 characters), `offset: [x,y]` (finite, each ±256), boolean `centered`, `flip_h`, `flip_v`, `fallback`, `provenance`, `animations` |
| Provenance | Nonblank `description` (512 characters), lowercase SHA-256 `source_sha256` of trusted source bytes; metadata does not verify ownership |
| Animation | Unique `name`, finite `fps` (0.001–240), boolean `loop`, nonempty ordered `frames` |
| Frame | Relative `path` ending `.rgba`, lowercase `sha256`, integer `width`/`height` (1–256), finite relative `duration` (0.001–60) |

Animation/fallback names match `[a-z][a-z0-9_]{0,63}`. The declared fallback must
exist. Missing directional/state animations use it; no missing frames are allowed.
Existing GameView names include `state_idle`, `down_walk`, `up_walk`, `left_walk`
and `right_walk`; the source's named animations are retained. Timing uses the
same native SpriteFrames API and precision as the trusted source.

Limits are 64 animations, 512 frame uses, 256 unique pixel paths and 16 MiB total
unique pixel bytes. Each payload is exactly `width * height * 4` bytes in row-major
RGBA8 order. Repeated paths must agree on hash and dimensions. All metadata and
every pixel file's exact length/hash are checked before image textures are built.
Paths reject traversal, absolute paths, URLs and symlinks. Existing manifest
rules apply: 64 KiB JSON, 32 nesting levels, at most 32 selected manifests, exact
versions, reserved namespaces, collision refusal and exact local dependency resolution.
The adapter currently accepts character-only manifest selections; mixed kinds
remain separate work. `load_character` also accepts an optional expected manifest
lock and returns the resolved lock/hash, using the same registry as arenas.
Manifest locks identify dependencies; only the chosen character payload is loaded.

## Explicit local selection

Before the first `update_player` for a participant, call:

```gdscript
var result = game_view.select_local_character("701", [
    "res://demo/characters/ruby/manifest.json",
    "res://demo/characters/jade/manifest.json"
], "example.ruby:character")
if not result.accepted:
    push_error(str(result))
```

The result returns a detached exact content descriptor or source/field rejection.
Invalid choices preserve a previous valid choice. Once a visual exists, selection
is refused. Removing the participant from a complete roster clears the choice
before ID reuse. Each visual owns detached animation state. Other participants,
the existing default character and authoritative movement/collision retain their
existing behavior. The loader creates native Node2D/AnimatedSprite2D objects;
it never mounts a runtime PCK or loads pack scripts/resources.

This is an API for local world visuals, not a finished avatar picker. Lobby/wire
selection, client content locks, automatic exact-version transfer, archive
installation, HUD portraits, palette/voice metadata and clean-client sharing still
need implementation. This does not complete the broader PACK-006/PACK-007 goals.

## Verification

```sh
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_character_packs --timeout 30
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_character_export --timeout 45
```

The runtime suite checks two original characters plus the unchanged default,
isolation, fallback, roster cleanup, malformed definitions, budgets, hashes,
symlinks and raw pixel length. Export checks run real fresh processes and compare
against the existing independent authoring checker: the trusted Robin Hood source
retains 36 animations, 77 frame uses, 139080 raw pixel bytes and offset `(0,-8)`.
Fresh original PCKs check fractional timings/flips and changed-source cache
isolation. Original examples contain no reference art. Whole-project and native
room checks remain required; none of these results proves network sharing,
browser rendering or Saturn fidelity.
