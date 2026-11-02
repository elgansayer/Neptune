# Project evaluation: Saturn foundation and an additive creator engine

Evaluated 30 October 2026 against local source at
`f7cc518c6ff338c10fbdd9b92ed3a6c138f2c96c`. This is a source review and build
recommendation, not a gameplay, deployment or reference-parity certification.
The owner's product contract is [COMMUNITY_CONTENT.md](COMMUNITY_CONTENT.md).

## Assessment

The project has reusable foundations: authoritative Godot gameplay, a simulation
clock, validated player commands, protocol negotiation, room/spawn checks, bots,
JSON map tooling and fail-closed test/factory tooling. Preserve working slices.
The fully extensible engine and automatic creator sharing are still largely
design contracts. A legacy PCK loader is not the public mod platform, and existing
Saturn research results do not establish an identical starting game.

The most useful next product proof is a creator hosting a custom arena and
character, a second player finding that server and automatically downloading both,
and both completing a match. Advance a measured Saturn battle/campaign slice
alongside it. Finish active bounded work and check current ownership first.

## Existing pack experiments to extend

Owner clarification and follow-up source inspection, 30 October 2026, from
`7f64513a7835d03213d0a385cfdc8008ca131456`: player and map packs already exist
as early development experiments. They are substantive starting points, not empty
stubs. Customisation is the defining product advantage: personal avatars and
admin-authored maps, game types and power-ups, shared automatically in play.

| Existing work | What to preserve and extend |
| --- | --- |
| [Robin Hood authoring project](<../../pack projects/characters/bomberman-player-robin-hood/player.tscn>) and [player PCK](../../characters/player-robin-hood.pck), 88,828 bytes | Script-free visual scene, 36 named animations, frame timing, 71 atlas resources, trim margins and sprite anchor. Client animation names are an existing contract to preserve during per-player selection work. |
| [Tirra authoring project](<../../pack projects/tirra/blue/tirra.tscn>) and [Tirra PCK](../../tirra/blue-tirra.pck), 123,464 bytes | Baby/teen/adult art, animation/frame data, rider offsets and presentation transitions. Separate declarative presentation data from its trusted controller when designing public packs. |
| [Stage authoring project](<../../pack projects/stages/bomberman-stage1/Stage.tscn>) and [stage PCK](../../maps/stage1.pck), 24,180 bytes | Existing floor/wall and spawn/soft-block tile layers, background art and [map metadata](<../../pack projects/stages/bomberman-stage1/MapMetadata.gd>). Preserve identity, version, geometry, spawns and soft-block settings when exporting data. |
| [Map conversion](../../shared/maps/map_pack_loader.gd), [JSON loader](../../shared/maps/map_loader.gd) and [MapManager](../../shared/maps/map_manager.gd) | Reuse scene-to-grid conversion, file/generated/custom sources, validation, metadata, listing/previews and saving. Strengthen boundaries and missing fields incrementally. |
| [Map preview/demo](../../shared/maps/map_test.gd) and [arena tests](../../tests/test_arena_layouts.gd) | Existing cycling, validation and export controls plus geometry/framing regressions are useful starting points for creator tooling. Verify old documentation against their actual paths. |

The exported PCKs report format v3 / Godot 4.5.1 and use generic root paths. They
also contain executable resources: the player export includes importer scripts,
Tirra includes a controller, and the map includes a metadata script. Keep these
trusted experiments usable while author-time conversion and public data-only
loading are introduced; do not expose raw PCK mounting to automatic server downloads.
The current [PCK inspector](../../inspect-pck.py) assumes an older fixed directory
layout, so do not use its file-count output to certify these v3 archives.

Follow-up inspection found 38 stale directional atlas paths in the Robin Hood
source scene. The checked-in resources use west/east/north/south directories;
the scene referenced left/right/up/down directories. The repair changes only
those resource paths to existing UID-identical atlas entries. Animation names,
timings, anchors, image regions/margins and the existing PCK bytes are preserved.
An existing exported binary alone does not prove the current authoring source
can be rebuilt; fresh import/export validation is part of continuing this work.

Before each content task, record the existing paths and observed behaviour,
what will be reused/adapted/repaired, and the remaining gap. Extend the stage
conversion and character atlas workflows with versioned IDs, additive registration,
per-participant selection and distribution. Do not reimplement map authoring or
animation handling merely because the final public registry is not yet present.

Follow-up authoring validation used official Godot 4.7.2 stable in disposable
project copies with writable XDG directories. Fresh player and Tirra imports
completed without script/engine errors after updating both existing TexturePacker
copies to upstream v4.3.0 plus the documented unknown-preset return fix. The player
scene loaded, exported to a fresh PCK and loaded from that PCK in an empty harness.
Source/export results matched: 36 animations, 77 frame uses, offset `(0, -8)` and
pixel/timing fingerprint
`45aa601ba8d012906ad9ef4641b734b7f35e0408fcf64324876d05ed69697c28`.
The reusable [character authoring check](../../tools/asset_audit/check_character_pack.gd)
rejected unknown arguments, a missing pack and an empty animation; changing a
frame sequence's speed changed the fingerprint. All 71 source references also
matched their checked-in resource UIDs and TexturePacker regions/trim margins.
Original PCK bytes remain unchanged. See the [authoring guide](<../../pack projects/README.md>)
for commands, dependency sources, the local importer patch and remaining public
pack/runtime boundaries. This validates the repaired authoring path, not automatic
online sharing, a complete public mod API or whole-game Godot 4.7.2 compatibility.

## Implementation gaps and recommendations

| Priority | Source finding | Recommended change |
| --- | --- | --- |
| P0 | [PCK startup](../../scripts/pck_loader.gd) mounts shared resources, while [map PCK loading](../../shared/maps/map_pack_loader.gd) mounts into `res://`, finds generic `Stage.tscn` names and instantiates scenes. These paths can collide and do not enforce the public data-only contract. | Keep trusted legacy packs separate. Build a validated data-only loader and registry with reserved namespaces, isolated immutable storage and duplicate rejection. Merely disabling PCK replacement does not validate nested executable resources. |
| P0 | [Player visuals](../../client/game_view.gd), `update_player()`, load the same `res://player.tscn`. There is no per-player pack selection in that path. | Carry namespaced character ID/version/digest per participant. Resolve animation data through the registry and distribute accepted personal packs through the server content pipeline, including unpublished session uploads and late joiners. |
| P0 | [Protocol negotiation](../../shared/network/protocol_negotiation.gd) explicitly excludes pack locks. [Login](../../client/ui/login_screen.gd) auto-connects locally; [client transport](../../client/main_client.gd) is direct ENet. | Add server discovery and direct joins, then a separate content-lock/download/readiness exchange. Cache verified bytes, support interrupted transfers and select the correct lock when switching servers. |
| P0 before public hosting | [RPC declarations](../../shared/rpc_interface.gd) expose `set_debug_timescale` to `any_peer`; [server handling](../../main_server.gd) changes process-wide `Engine.time_scale` without checking the sender. This is a source finding; no exploit was run. | Restrict debug/admin actions to trusted local or authenticated authorised control, with a denied-client runtime case, before opening a community server. |
| P1 | [Power-up definitions](../../shared/entities/server_powerup.gd) use a fixed network enum and [collection](../../shared/entities/server_player.gd), `collect_powerup()`, branches on it. | Preserve existing wire compatibility while adding namespaced public definitions and deterministic session wire mappings. Implement bounded triggers/conditions/effects so a new supported item needs data and art rather than a new item-specific branch. |
| P1 | [GameInstance](../../game_instance.gd) owns battle timers/outcomes and writes the global [GameConfig](../../shared/game_config.gd) when a map loads. The [protocol handoff](PROTOCOL_NEGOTIATION.md) records campaign saves as future work. | Introduce a shared mode lifecycle and immutable session configuration. Until distinct simultaneous sessions are proven isolated, use a process per hosted session. Build typed campaign progression and atomic checkpoints through the same public API. |
| P1 | [Client](../../client/main_client.gd) and [server](../../main_server.gd) instantiate ENet. This does not implement browser cross-play. | Add a transport boundary preserving the validated action path; prove native/browser connection, content transfer and a full match with the actual signalling/relay arrangement. |
| P1, parallel | [Reference contracts](REVERSE_ENGINEERING.md) and [accepted research](RESEARCH_EXECUTION.md) distinguish control/extraction evidence from gameplay parity. No full Saturn presentation/behaviour parity is established by this review. | Pin the chosen release/region and compare one battle arena and campaign room, including movement, collision, fuse/blasts, animation, audio and framing. Expand to original menus, modes, CPUs and progression. Deliberately changed movement/fuse/rendering must fail comparisons. |

The existing [JSON map loader](../../shared/maps/map_loader.gd) already offers
validation, dimensions and export; adapt useful pieces instead of rebuilding
all map handling. Keep the faithful Saturn default intact and make enhanced
profiles explicit selections. Reference assets and distributable content retain
their separate provenance rules.

## A staged build using the current backlog

These are deliverable recommendations, not new competing epics or claims that
their linked issues are open/unowned. Inspect live issue/PR state before dispatch.

1. **Secure additive loading.** Reuse PACK-001/002/003/004/005/006
   ([#237](https://github.com/elgansayer/Neptune-Bomberman/issues/237),
   [#250](https://github.com/elgansayer/Neptune-Bomberman/issues/250),
   [#252](https://github.com/elgansayer/Neptune-Bomberman/issues/252),
   [#251](https://github.com/elgansayer/Neptune-Bomberman/issues/251),
   [#254](https://github.com/elgansayer/Neptune-Bomberman/issues/254),
   [#258](https://github.com/elgansayer/Neptune-Bomberman/issues/258)). Prove two
   additions coexist, overwrite attempts fail and interrupted installs remain inactive.
   Adapt the existing pack projects and conversion paths; new identity/validation
   work is not a reason to discard their authoring or animation systems.
2. **One server-to-play journey.** Combine bounded slices of ROOM-004/006/013
   (#123/#255/#131), PACK-007/009/010/016 (#259/#266/#261/#270),
   WORKSHOP-005 (#359) and OPS-012 (#236). A fresh self-hosted server advertises
   permitted content; clean clients download/cache it and finish a battle. A joining
   player's unique character reaches another clean client and a late joiner.
   Private playtests work before public workshop publication. Add a custom mode
   through PACK-012 (#264) when that lifecycle is ready.
3. **Mechanics as content.** Use PACK-011/012 (#263/#264), the EFFECT tasks and
   Ice Bomb #52. An independently authored item/mode exercises general primitives,
   server authority, replay and bot hazard/objective queries. No engine branch may
   identify the fixture by pack ID. Keep existing human/bot regressions passing.
4. **Playable stories and co-op.** Use PACK-013 (#267), story #53, co-op #54 and
   roles #55. Prove a two-level solo campaign, then two-human checkpoint recovery,
   companion/enemy behaviour and version-pinned save resumption. First-party and
   creator campaigns follow the same format.
5. **Creation and publishing tools.** Wrap the demonstrated runtime in SDK/templates,
   validators, previews, editors #56 and the integrated journey #57. Expand workshop,
   profiles and statistics around working flows. A polished upload page alone does
   not prove that downloaded content can be played.

Saturn fidelity, browser/native cross-play and measured bot quality remain separate
acceptance tracks throughout. Research can supply exact fixtures incrementally;
complete extraction is not a prerequisite for original creator-system tests.

## How AI should build it

- Use the existing catalogue and coordinator. Pick one observable result with
  concrete dependencies, paths, acceptance and evidence. Preserve leases and active
  work; do not replace the authorised Elgl factory with another scheduler.
- Separate interface definition from parallel implementations. Agree the manifest,
  registry identity, mode lifecycle and network lock first; assign bounded owners
  for runtime, downloads, UI and reference experiments. Integrate changes in dependency order.
- Prefer general public APIs and independently authored fixtures. Require a second
  fixture or clean client where it detects hard-coded demo behaviour. Bundled content
  exercises the same API; remove privileged assumptions incrementally.
- Put relevant ethos checks into the existing task acceptance/evidence fields:
  unchanged Saturn baseline, additions coexisting, overwrite rejection, exact locks,
  clean/cached server joins and custom-character propagation. Refresh trusted intake
  revisions explicitly; changing local catalogue text does not update a live issue or lease.
- Extend real harnesses as capabilities ship. Current [merge checks](../../tools/merge_gate/run.py)
  exercise tooling and applicable native/runtime/bot paths; they do not by themselves
  prove browser downloads, pack isolation or Saturn frame/behaviour parity. Keep
  exact-build/current-base checks and add the applicable production-path cases.
- Record implemented, actually tested, still unverified and blocked separately.
  Keep replay/log/capture identities and the next eligible task in a durable handoff.
  A model's completion message, generated catalogue or saved prompt is not evidence
  that a feature works or a continuous factory is running.

## Original evaluation update and validation

The initial evaluation change records the ethos in agent/handoff guidance and strengthens existing
catalogue acceptance for additive content, self-hosting, downloads and character
sharing. It does not implement those runtime features, change remote GitHub issue
bodies, deliver instructions to already-running workers, or start a factory.
The locally authored catalogue source is [features.tsv](backlog/features.tsv);
regenerate with `python3 docs/restart/backlog/build_catalogue.py` and validate with
`python3 tools/research_catalog/check.py`.

Validation run for this documentation/catalogue update:

- `python3 tools/research_catalog/check.py`: 14 tests passed, including generated
  catalogue consistency; 418 feature IDs and issue mappings retained, no cycles.
- `python3 tools/research_catalog/cli.py validate`: metadata valid; evidence not executed.
- `python3 tools/saturn_lab/check.py`: 93 tooling tests passed.
- `python3 tools/factory/check.py`: 68 contract tests passed.
- `python3 tools/merge_gate/check.py`: 17 gate tests passed.
- `git diff --check`: passed. No game/emulator session, browser test, live factory
  or reference-parity comparison was run for this update.
