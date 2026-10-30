# Standard and wide arena framing

Issue #186 / ARENA-002 now has an original standard/wide presentation slice.
`maps/neptune_standard.json` (15×13) and `maps/neptune_wide.json` (27×13) contain
original Apache-2.0 geometry with four distinct, reachable starts each. They are
not Saturn fixtures or claims about reference capacity, balance or dimensions.

Use either installed JSON arena through the existing trusted startup path:

```sh
"$GODOT" --headless --path . res://main_server.tscn -- \
  --room-map=res://maps/neptune_wide.json --room-seats=4 \
  --room-preset-limit=4 --room-fill-to=4
```

Change only the filename to `neptune_standard.json` for the non-wide layout.
Map width never grants extra seats. Both pass through the same map loader,
reservation checks, human/bot admission and authoritative simulation. Existing
room/preset limits remain independent of the twelve-seat protocol ceiling. No
new named Saturn or Power profile is invented by this presentation change.

The initial map's optional `map_config.render_geometry` flag selects the existing
primitive geometry renderer for explicitly installed JSON arenas. Clients no
longer apply unrelated legacy stage artwork to these maps. Legacy PCK sessions
retain their existing presentation path. This is a local installed-map interface,
not a public pack schema or runtime code-loading permission.

Camera framing fits the full rectangular arena below the screen-pinned HUD with
four logical pixels of margin. It shrinks uniformly when necessary, never changes
physics/tile size, and does not enlarge native pixels on a larger viewport. Resize
and a second participant row trigger reframing. A minimized viewport preserves the
last valid camera until usable dimensions return. Primitive destructible blocks
share the normal update bookkeeping so destruction leaves no duplicate visual;
always-on hard-wall debug circles are removed from this presentation path.

## Validation and limits

`test_arena_layouts.gd` exercises production rendering, camera transforms and HUD
scenes, resize, the two-row roster, invalid dimensions, block destruction, and
actual two-human/two-bot admission on both maps. Seven tests pass on pinned Godot
4.5. `test_participant_hud.gd` separately covers six roster cases. Real local
server/client protocol and capacity probes pass, including twelve mixed seats.

Local Xvfb/OpenGL software-rendered captures of both arenas were inspected at a
640×448 window / 320×224 logical viewport with twelve HUD entries. Captures remain
outside Git under `/workspace/.tools/arena-standard.png` and `arena-wide.png`;
they include existing reference character icons and are not release media. The
Xvfb driver reports unsupported V-Sync configuration; no engine/script errors were
observed in these captures. Required PR CI separately gates the full native suite
and graphical connection checks.

This does not close #186's entire product scope. Browser rendering, reference
profile fidelity, large-layout readability on more devices, public pack validation,
and complete gameplay/balance comparisons remain unverified. No unrelated issue
or parent epic is closed by these fixtures.
