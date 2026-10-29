# Multiplayer, bots and community-created adventures

Status: accepted product direction, 29 October 2026. This is an implementation
contract, not a claim that these features exist. Tracker: [#23](https://github.com/elgansayer/Neptune-Bomberman/issues/23).

## Priority and scope

Neptune is a multiplayer-first, open-source community platform with strong bots.
Solo play and co-op are first-class supported modes. Creators must eventually be
able to publish complete stories as well as characters, maps, power-ups and modes.
All bundled content uses the public pack/runtime interfaces; a sample that needs
special-case engine code does not prove the creator workflow.

Keep one authoritative Godot simulation. Separate faithful Saturn rules from
extensible Neptune rules. Continue Saturn extraction and Power Bomberman behaviour
research, but do not block an original community prototype on complete extraction,
the full Power feature inventory or hundreds of characters. Original/permitted
fixture assets are sufficient for creator-system tests. Reference parity still
requires the laboratories' evidence and must never be inferred from this work.

The engine, netplay, bots, tools and starter content need active maintenance.
Community adoption is a product outcome, not something an AI factory can guarantee.
Do not equate a large feature catalogue with polish or a healthy creator community.

## Public content contracts

| Pack | Author supplies | Runtime responsibility |
| --- | --- | --- |
| Character | Frames, named animations, anchors, portrait, sounds | Common collision/readability rules; appearance independent of abilities |
| Arena | Layout, spawns, tile definitions, hazards, item pool | Navigation, collision, supported player counts and objectives |
| Power-up | Art, triggers, conditions, effects, consumption and stacking | Authoritative bounded effects, event ordering and expiry |
| Mode | Objectives, scoring, teams, end/reset conditions | Shared lifecycle, replay/state and bot objective interface |
| Campaign | Level graph, encounters, dialogue, variables, transitions and checkpoints | Progression, saves and declared solo/co-op modes |
| Collection | References to compatible pack versions | Dependency resolution and an exact lockfile |

Extend #35's manifest with namespaced IDs, API/schema versions, author/permission
records, immutable content digests, dependencies/conflicts, declared capabilities,
platform support and tested player/mode combinations. Unknown capabilities fail
clearly. Cosmetic packs cannot silently alter simulation or hide collision cues.
Installed compatible characters have no compulsory unlock gate.

A room resolves and locks the full dependency graph before starting. Every client
obtains and validates the required versions; the server owns outcomes. Enforce
archive, image/audio, memory, event and entity budgets. Never execute downloaded
GDScript, native extensions or code-bearing scenes through the public pack loader.
Arbitrary pack combinations are not guaranteed compatible. Explain conflicts to
the host before play instead of selecting a silent fallback.

## Power-ups: bounded composition first

Issue [#52](https://github.com/elgansayer/Neptune-Bomberman/issues/52) introduces a
small reusable set of triggers, conditions and actions. Examples: on pickup,
on bomb creation, on blast contact; target/team predicates; apply/remove status,
modify supported bomb properties and consume a charge. Specify tick durations,
seeded randomness, event ordering, stacking, replacement, death/reset and expiry.
Prevent recursive event/spawn loops and define deterministic budget-failure behaviour.

The first public example is an Ice Bomb: change the next three bombs, apply a
two-second freeze on blast contact and allow fire to thaw it. This is a proposed
Neptune fixture, not a statement about either reference game. Define simultaneous
fire/freeze precedence and confirm it in runtime tests. The creator supplies the
definition and graphics; no code may branch on this example pack's item ID.

Expose actual supported effect semantics to danger prediction and bot planning.
Author labels such as "safe" are untrusted hints, not authoritative hazard data.
Predictive clients must use matching semantics or supported authoritative fallback
behaviour; do not promise flawless prediction for every future script.

Novel behaviour beyond these primitives needs an engine extension or a later
restricted scripting API. Before public scripting, prove capability-limited host
calls, no filesystem/network access, instruction/memory limits, bounded callbacks,
state serialisation, deterministic ordering and browser/native behaviour. A choice
of Lua/Wasm or a signature alone is not a sandbox. Record a separate runtime
decision and adversarial tests before enabling executable community logic. This
later work must not block the data-only first slice.

## Campaigns are playable packages

Issue [#53](https://github.com/elgansayer/Neptune-Bomberman/issues/53) implements a
two-level solo fixture through the public API. Define an entry level, transition
graph, typed progression variables, objectives, dialogue/localisation, encounter
and boss states, success/failure paths and checkpoints. Validate references and
reachability; intentional graph cycles need explicit exit conditions and budgets.
Dialogue is text/data with explicit skip policy, never executable markup.

A campaign declares solo/co-op support, minimum/maximum humans and total party
size, companion support and required mechanics. An untested solo story must not
be advertised as co-op-ready. Initially target one player and two-player co-op;
larger parties require explicit scenario and resource testing. This does not
reduce the independent twelve-seat extensible battle-room target.

Local solo play uses the same authority semantics and supports local checkpoint
saves without requiring a public account. Online sessions use authenticated
participant identities. Importing a local/custom save never awards trusted ranked
progress. Default campaign content must use the same schema as creator content.

## Co-op session and save policy

Issue [#54](https://github.com/elgansayer/Neptune-Bomberman/issues/54) adds the first
two-player browser/native campaign gate. The dedicated session is authoritative;
the initiating player owns access to a party run, not the simulation process.
The run has a stable ID and participant slots; personal completion records are
separate from the shared save. Define who may resume/invite, and require the owner
for resume initially. Owner disconnect follows the bounded reconnect policy;
after timeout preserve the latest committed checkpoint and end the run cleanly.

The initial join/rejoin boundary is a safe checkpoint. Do not promise arbitrary
mid-level joins or host migration. Specify waiting/spectating, slot reservation,
reconnect timeout and whether an absent actor is parked or replaced by a declared
companion. Snapshot current actors and locks consistently before resuming play.

Every mode explicitly defines shared/personal lives and items, friendly fire,
revives, full-party wipe, loot ownership and simultaneous objective completion.
Dialogue/transition waits need a bounded timeout and an announced skip/consensus
policy so a disconnected participant cannot stall the session indefinitely.

Checkpoint commits are atomic and versioned: campaign/pack lock, schema/runtime
compatibility, level, variables, objectives, RNG state and participant mapping.
Resume from the latest committed checkpoint after a crash; uncommitted progress
may be lost and that boundary must be visible. Reward/transition IDs are idempotent.
Never silently migrate a save to a newly published pack. Keep old versions when
available; otherwise explain the unavailable dependency and preserve the save.
Any future migration uses a copied save and separately verified conversion.

## Bots: role and policy are different dimensions

| Role | Required behaviour | Evaluation |
| --- | --- | --- |
| Competitive opponent | Survival, tactics, item use and mode objectives | Existing #30/#32 fairness, held-out quality and CPU gates |
| Companion | Objectives, assistance/revives and cooperative navigation | Completion, stuck time, friendly harm and useful assistance |
| Enemy/boss | Creator-defined encounters, attacks and phases | Reachability, phase transitions, reset and difficulty behaviour |

Keep role separate from faithful Saturn/enhanced Neptune/authored policy lineage.
Share navigation, observation and supported hazard queries where semantics agree.
Opponent and companion decisions use permitted observations and validated actions;
campaign enemies may have explicitly authored abilities, not hidden competitive
cheats. No external LLM call occurs in a match tick.

Issue [#55](https://github.com/elgansayer/Neptune-Bomberman/issues/55) proves these
roles using one human with a companion, two humans without a companion and a
bounded authored encounter, alongside competitive regression scenarios. A room
requiring bots rejects unsupported mechanics before start. A creator hint alone
cannot mark a mod bot-compatible; exercise its actual effects in tests.

## Creator experience, workshop and statistics

Extend #37's character/map workflow, then add the power-up and campaign editors in
[#56](https://github.com/elgansayer/Neptune-Bomberman/issues/56). Support templates,
undoable edits, draft saves, import/export, readable previews and public format
documentation. Provide large scalable text and keyboard alternatives to graph
dragging. A creator should be able to preview a level or run a bounded bot test
without rebuilding the engine. Validation proves defined properties, not fun.

Workshop pages expose author credit, permissions, screenshots, mode/player counts,
dependencies, compatible game/API versions and immutable release history. Support
draft/private play links before publication, reporting, reversible moderation,
quotas and eventual self-hosted registries. Publication must not change active
matches, existing campaign saves or replay dependencies.

Extend #36's events with campaign/run/checkpoint/objective and content versions.
Separate battle, campaign and custom metrics, plus human/companion/opponent roles.
Creator-authored rewards never directly credit official competitive rankings.
Only trusted ingestion produces official completion receipts; retrying a transition
must not duplicate progress. Bot playtests are labelled tests, not player activity.

## Delivery order and acceptance

Finish the currently owned baseline work first. PRs #49 and #51 cover runner and
runtime-role work; #50 tracks remaining legacy test contracts. Read their current
state rather than assuming they have merged. Keep #30 bot fixes and #31/#32 room
filling/evaluation central. Coordinate #34 cross-play, #35 packs and #43 profiles.
Generic profile interfaces do not require a completed Power reference experiment;
claims of reproduced Power behaviour still require #41/#42 evidence.

| Issue | Bounded result | Depends on |
| --- | --- | --- |
| [#52](https://github.com/elgansayer/Neptune-Bomberman/issues/52) | Declarative effects and independently authored Ice Bomb | #35, #43 |
| [#53](https://github.com/elgansayer/Neptune-Bomberman/issues/53) | Two-level solo campaign with save/resume | #35, #43 |
| [#54](https://github.com/elgansayer/Neptune-Bomberman/issues/54) | Two-player co-op and checkpoint recovery | #53, #34 |
| [#55](https://github.com/elgansayer/Neptune-Bomberman/issues/55) | Companion/enemy roles and mod-aware bot checks | #30, #52, #54 |
| [#56](https://github.com/elgansayer/Neptune-Bomberman/issues/56) | Accessible item/story editors and publishing | #37, #52, #53 |
| [#57](https://github.com/elgansayer/Neptune-Bomberman/issues/57) | Integrated creator-to-play acceptance | #34, #35, #36, #37, #52, #54, #55, #56 |

The earlier map-only workshop gate remains useful and must not wait for every
editor. Split any implementation issue further if it exceeds one reviewable PR.
Satisfying an issue means runtime evidence at its exact build, not generated docs.

The expanded gate is a creator publishing a character, arena, power-up and short
story through the documented tools. A clean second client downloads exact packs;
browser/native players complete a battle with bots, then the story in solo with a
companion and in two-human co-op. Saves survive the specified restart/reconnect
cases; profile results are correct; a pack update preserves prior versions.
Record hashes, commands, recordings and limitations. This does not establish full
Saturn/Power parity or that an external community has adopted the platform.
