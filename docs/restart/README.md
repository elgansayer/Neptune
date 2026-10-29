# Neptune restart: multiplayer, bots and community content

Status: the [bounded libretro bridge has real boot/replay evidence](evidence/2026-10-29-libretro-bridge.md).
Continuous VPS factory operation and disc-graphics extraction remain unverified.
The current repository targets Godot 4.5. Pin that baseline
for the first reproducible build; choose any engine upgrade through a separate
compatibility task.

## Goal

Build a multiplayer-first platform with strong bots, desktop/browser cross-play,
community-authored characters, maps, power-ups and complete solo/co-op stories,
player profiles, detailed stats and a creator workshop. Reproduce Saturn campaign
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
- [Server Codex handoff](SERVER_HANDOFF.md)
- [Ordered backlog](BACKLOG.md)
- [Runnable inventory and input lock tools](../../tools/saturn_lab/README.md)
- [Catalogue validation and report tools](../../tools/research_catalog/README.md)

## Current evidence

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
