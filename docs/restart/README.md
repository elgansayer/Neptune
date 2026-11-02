# Neptune restart: AI factory, Saturn research and community game

**Current priority, 2 November:** build the existing shared AI development factory
and use it primarily for Saturn Bomberman reverse engineering. Follow
[FACTORY_FIRST_GOAL.md](FACTORY_FIRST_GOAL.md) for task selection, tool/package
preparation, agent handoffs and operational acceptance. Ordinary product expansion
follows that critical path; active work and the full game scope are preserved.

Status: the [bounded libretro bridge has real boot/replay evidence](evidence/2026-10-29-libretro-bridge.md).
Real input, bridge and static disc/regional inventory work is accepted through
#467/#468/#473. Full disc-graphics extraction and continuous Neptune factory
operation remain unverified. Start with [research execution](RESEARCH_EXECUTION.md)
and [issue #477](https://github.com/elgansayer/Neptune-Bomberman/issues/477).
Development must stay on the latest stable packages and Godot, following the
[dependency policy](DEPENDENCY_POLICY.md). The recorded toolchain uses Godot 4.7.2 with current stable native addons. Refresh pins and validate
compatibility as part of adopting current releases.

## Goal

The persistent objective and dispatch order are in
[FACTORY_FIRST_GOAL.md](FACTORY_FIRST_GOAL.md). Factory supervision/recovery and
real Saturn experiments take precedence over independent feature breadth.

The owner's 1 November clarification requires exact maps/assets, timing, speeds,
mechanics, effects, music and sound in the faithful profile. Apply
[SATURN_FIDELITY.md](SATURN_FIDELITY.md) to task intake and completion: exact
state/events, native pixels and sample-timed audio at the declared digital boundary.
Existing metadata/native CI is not whole-game parity. Select independent work
under the factory/Saturn priority while #29/#76/#511 build measured acceptance slices.

The owner's clarified ethos is [Saturn first, additions only, automatic sharing](COMMUNITY_CONTENT.md#owners-ethos-saturn-first-everything-extensible-additions-only).
The initial game should look and act like Saturn Bomberman; creators then extend
every supported content category without replacing original content. Player-hosted
servers and automatic server/character downloads are central to this goal.
Read the [30 October project evaluation and build recommendations](PROJECT_EVALUATION.md)
for implementation gaps and the first end-to-end acceptance slice.

Build a multiplayer-first platform with strong bots, desktop/browser cross-play,
community-authored characters, maps, power-ups and complete solo/co-op stories,
player profiles, detailed stats and a creator workshop. Support both standard
(non-wide) and wide battle arenas as first-class layouts. Reproduce Saturn campaign
and battle behaviour using measured references and independently implement Power
Bomberman feature coverage in separate ruleset profiles. A continuously running
AI factory should work through GitHub issues, with deterministic verification and
tests-gated automatic merging. AI review is optional, following [MERGE_POLICY.md](MERGE_POLICY.md).

The work has three tracks: factory/build, Saturn research and Power Bomberman
research. Keep one shared implementation with separate ruleset profiles. The
research gate is repeatable control of the original, real graphics and one campaign
room/battle arena comparison. Community runtime work can proceed independently
using original/permitted fixtures; full extraction and reference feature parity
are not prerequisites for a moddable multiplayer prototype. The current product
contract is [COMMUNITY_CONTENT.md](COMMUNITY_CONTENT.md).

## Documents

- [Current factory/Saturn-first goal and dispatch priority](FACTORY_FIRST_GOAL.md)
- [Exact Saturn fidelity, tools and agent handoffs](SATURN_FIDELITY.md)

- [Source-backed project evaluation and build recommendations](PROJECT_EVALUATION.md)
- [Latest stable dependencies and Godot policy](DEPENDENCY_POLICY.md)
- [Tests-only automatic merge policy and setup](MERGE_POLICY.md)
- [Multiplayer, power-ups, campaigns and co-op contract](COMMUNITY_CONTENT.md)
- [Everything to provide and install](REQUIREMENTS.md)
- [Paste-ready server Codex prompt](CODEX_START.md)
- [Three-track factory operating contract](FACTORY_PLAYBOOK.md)
- [Next Saturn reconstruction experiments and capture gates](SATURN_RECONSTRUCTION.md)
- [Factory intake and durable lease tools](../../tools/factory/README.md)
- [Reverse-engineering pipeline and evidence contracts](REVERSE_ENGINEERING.md)
- [Power Bomberman research and feature scope](POWER_BOMBERMAN.md)
- [Machine-readable starter feature catalogue](feature-catalogue.json)
- [Netplay benchmark and architecture decision](NETPLAY_BENCHMARKS.md)
- [Open-source and content release contract](OPEN_SOURCE_AND_CONTENT.md)
- [Factory and platform architecture](ARCHITECTURE.md)
- [Online bots and evaluation](BOTS.md)
- [Gameplay protocol negotiation and remaining save scope](PROTOCOL_NEGOTIATION.md)
- [Room capacity, presets and pre-start validation](ROOM_CAPACITY.md)
- [Initial-round authoritative bot filling](ROOM_BOT_FILL.md)
- [Server Codex handoff](SERVER_HANDOFF.md)
- [Ordered backlog](BACKLOG.md)
- [Runnable inventory and input lock tools](../../tools/saturn_lab/README.md)
- [Catalogue validation and report tools](../../tools/research_catalog/README.md)
- [Static Saturn disc inventories and regional diff](saturn-disc/README.md)
- [Saturn coverage and unknowns ledger](asset-audit/saturn-coverage-ledger.json)

## Historical initial inspection

Source inspection at `6da6f5f5f187cab272699603a7bc1bc09fe3c885` found:

- A Godot authoritative server and ENet clients, plus existing map/character PCK loaders.
- Temporary in-memory authentication and incomplete persistent backend interfaces.
- A test runner whose main-branch discovery misses nested and `test_*.gd` tests,
  and whose load/contract failures do not consistently increment failure counts.
- Open PRs #18 and #20 both address test selection/discovery. Review and reconcile
  them before opening another implementation of the same change.
- Other open PRs #17, #19, #21 and #22 need normal review; none is assumed correct
  from its description or claimed benchmark.
- `SaturnBomberman-Assets` contains named Saturn sprite sheets and a larger export
  collection. Sources, exact completeness and licence status require a catalogue;
  directory names alone do not prove Saturn provenance.

No original disc was provided for analysis. No emulator/game run was performed
as part of this source inspection. Python tooling tests use synthetic bytes and
make no claim about valid Saturn disc structures.

Power Bomberman planning adds public-source observations, not a downloaded or
executed reference build. Its feature presence and Neptune implementation are
tracked separately. Subsequent server PRs #49/#51 contain runtime evidence for
runner/startup work, with remaining scenario contracts in #50. Inspect their
current status and evidence; this documentation update does not certify those PRs.

## Milestones

First prove the operational factory and real Saturn acceptance in
[FACTORY_FIRST_GOAL.md](FACTORY_FIRST_GOAL.md). The product milestones below remain
required; they are not the order for new claims when factory/research work is eligible.

1. Finish a trustworthy Godot baseline. Inspect current PRs #49/#51 and remaining
   legacy test task #50 before duplicating server work.
2. Prove bot decisions, online room filling and tournaments (#30–#32), then mixed
   browser/native play (#34). Establish public packs and profiles (#35/#43).
3. Prove independently authored power-ups (#52), a two-level solo story (#53),
   co-op checkpoints (#54) and companion/enemy roles (#55).
4. Add identity/stats (#36), workshop (#37), item/story editors (#56) and the
   integrated creator-to-play demonstration (#57). The smaller map-only gate
   can ship before the story editors.
5. Independently advance Saturn inputs/control/extraction/parity (#26–#29/#38)
   and Power reference experiments/measured modes (#41/#42/#44). Missing media
   blocks only dependent experiments, not original creator-system work.

Network quality is measured through #45; source/content release readiness through
#46. Installed compatible custom characters remain usable without compulsory unlocks.
These are implementation targets, not completed features; read live issue evidence.

Do not equate committed files, green tooling CI, a PNG count, or lack of newly
observed frames with completion of a milestone.
