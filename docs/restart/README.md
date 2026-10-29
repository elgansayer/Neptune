# Neptune restart: research first

Status: foundation work; no VPS factory, emulator bridge or disc extraction is
claimed to be running. The current repository targets Godot 4.5. Pin that baseline
for the first reproducible build; choose any engine upgrade through a separate
compatibility task.

## Goal

Reproduce Saturn Bomberman's campaign and battle content and behaviour using
measured references, independently implement Power Bomberman's feature breadth,
then provide desktop/browser cross-play, community packs,
player profiles, detailed stats and a creator workshop. A continuously running
AI factory should work through GitHub issues, with deterministic verification and
independent review of the exact proposed commit.

The work has three tracks: factory/build, Saturn research and Power Bomberman
research. Keep one shared implementation with separate ruleset profiles. The
immediate product is the automated research lab. First prove repeatable
control of the original, capture real graphics, reconstruct one campaign room and
one battle arena, and compare movement and bomb interactions against Neptune.
The community website remains in scope but must not displace this dependency.

## Documents

- [Everything to provide and install](REQUIREMENTS.md)
- [Paste-ready server Codex prompt](CODEX_START.md)
- [Three-track factory operating contract](FACTORY_PLAYBOOK.md)
- [Reverse-engineering pipeline and evidence contracts](REVERSE_ENGINEERING.md)
- [Power Bomberman research and feature scope](POWER_BOMBERMAN.md)
- [Machine-readable starter feature catalogue](feature-catalogue.json)
- [Netplay benchmark and architecture decision](NETPLAY_BENCHMARKS.md)
- [Open-source and content release contract](OPEN_SOURCE_AND_CONTENT.md)
- [Factory and platform architecture](ARCHITECTURE.md)
- [Online bots and evaluation](BOTS.md)
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
tracked separately. Server Codex has started runner task #40; avoid duplicate work.

## Milestones

1. Reproducible source inputs, real game build and trustworthy test discovery.
   In parallel, catalogue and pin the Power Bomberman reference (#41).
2. Emulator control bridge with measured repeatability.
3. Raw sprite/background capture and source-file decoding.
4. One campaign room and battle arena with executable parity comparisons; in
   parallel, reproducible bot survival and decision regression scenarios.
5. Broader campaign, enemy/boss and battle coverage driven by missing-evidence issues.
   Add measured Power-inspired modes through shared profiles (#42–#44).
6. Browser/desktop cross-play, pack schema and online compatibility validation.
7. Accounts, trusted event statistics, workshop publishing and community features.

Network quality is measured through #45; source/content release readiness through
#46. Installed compatible custom characters remain usable without compulsory unlocks.

Do not equate committed files, green tooling CI, a PNG count, or lack of newly
observed frames with completion of a milestone.
