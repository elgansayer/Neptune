# Continue the existing pack authoring experiments

These projects are the starting point for the mod/customisation engine. Extend
their useful authoring and rendering work before proposing replacements.

The [local data-only map pack workflow](../docs/restart/DATA_ONLY_MAP_PACKS.md)
now adapts the trusted stage converter into validated namespaced JSON packs and
explicit host selection. Existing PCKs and authoring projects remain intact.

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
