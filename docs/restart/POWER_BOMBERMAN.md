# Power Bomberman research and feature parity

30 October expansion: [#476](https://github.com/elgansayer/Neptune-Bomberman/issues/476)
and RPWR-001–010 explicitly cover full code/event/resource recovery alongside
controlled original execution. [Research execution](RESEARCH_EXECUTION.md) gives
the current scope. The targeted internals route below is the first bounded slice,
not a cap on eventual recovery. #498 must establish actual VM/native/container and
release identity, including the existing exports, before choosing a decompiler.

Checked 2026-10-29. This is a second reference programme, alongside the Saturn
research lab. Neptune should combine faithful Saturn campaign/battle play with
Power Bomberman's breadth and an open creator ecosystem. These are proposed
Neptune capabilities; no Power Bomberman binary was executed during this audit.

## Source baseline

The [developer's release post](https://www.bombermanboard.com/viewtopic.php?t=1925)
lists **0.7.8c, 1 March 2026**, Windows/macOS/Linux clients and an optional server.
Its feature list advertises twelve participants; quick, local and online play;
six battle rules; Score/Turbo play; configurable items and timings; over 700
characters and over 80 stages with roughly 700 variants. These are advertised
counts, not our measured coverage or a ready-to-import content licence.

The [linked changelog](https://pastee.dev/p/5XtRWu50) supplies regression leads:
health/item interactions, wrap/throw behaviour, synchronisation and round timing.
Fix entries describe changes in that release, not proof those bugs remain.
The announcement in [post #910](https://www.bombermanboard.com/viewtopic.php?start=900&t=1925)
corroborates the release. Download links and same-version hotfixes can change:
record archive and extracted-file hashes, not only the displayed version.

## Check the actual gaps

[A developer reply in March 2022](https://www.bombermanboard.com/viewtopic.php?start=840&t=1925)
described custom characters as low priority. It is historical, not evidence that
the current build cannot load them. [A mod author's instructions](https://www.moddb.com/mods/power-bomberman-styles-mods)
describe replacing game data and sounds. Thus, do not claim that Power Bomberman
has no mods. Test supported authoring, sharing, online compatibility and version
migration in the selected build before describing missing features.

Treat browser support, workshop uploads, arbitrary maps, source availability,
reconnect behaviour and detailed persistent stats as questions to investigate.
Absence from an announcement does not establish absence from the product. A user
report is a candidate experiment, not a verified defect or engine diagnosis.

## Two research routes

1. **Observe behaviour first.** Inventory included manuals, menus, configuration,
   help demonstrations, local play and owned-server matches. Record controlled
   input sequences, video, outcomes and uncertainties. Write an independent
   behaviour specification that another worker can implement and test.
2. **Targeted internals research when needed.** If an unresolved question warrants
   it, inspect the supplied executable/data format in an isolated research job.
   Record build hashes, tool versions and how a proposed interpretation was
   confirmed by execution. Keep decompiled code and extracted materials out of
   Neptune's implementation/release inputs unless their reuse licence is established.

Do not make a full decompilation a prerequisite for the first playable slice.
Do not assume public source exists or that a free download permits relicensing.
The implementation deliverable is our own code and tests, plus separately tracked
content provenance. Do not claim a legally certified clean-room process.

## Desktop harness contract — to implement in #42

- Prefer the official Linux release if it runs correctly on the host. Pin its
  OS/libraries, display backend, resolution, renderer and input device mapping.
  A virtual display/software renderer is an experiment, not a proven deployment.
- Use isolated per-run configuration and save data; record their hashes. Never
  overwrite someone's existing installation or personal saves.
- `launch`, `navigate`, `input`, `capture`, `reset`, `stop` are intended operations,
  not existing APIs. Bound each operation, retain stderr/exit status and verify
  screen checkpoints before entering gameplay.
- Log monotonic input timestamps and capture timestamps. A desktop keypress at a
  wall-clock time is not equivalent to a Saturn emulator frame step. Measure
  missed inputs, focus problems, capture cadence and timing uncertainty.
- Use native menus to select known scenarios. If RNG cannot be pinned, choose
  controlled cases or repeated statistical comparisons and record that limitation.
- Run automated networking experiments against owned local servers/clients.
  Never use the public matchmaking service as a load-test target.
- Store evidence outside Git when it includes reference media. Expose small
  derived observations to model workers; retain private evidence IDs/digests.

Each experiment records: reference version + input manifest digest; harness build;
OS/display/runtime; settings/save digest; scenario and input timeline; measurement
method; capture digest; repeated results; uncertainty; interpretation and open questions.
A timeout, wrong menu, missing capture or failed launch is a failed experiment.

## Shared implementation, explicit rules

Use one authoritative Godot simulation with versioned profiles. The `saturn`
profile preserves the selected original's measured semantics. An extensible
`neptune` profile hosts measured Power-inspired rules and intended improvements.
Record the profile and exact settings in every match, replay and stats event.
Power Bomberman observations must not silently override Saturn reference fixtures.

Design the extensible profile for twelve seats; keep original-mode limits
reference-specific. The first additional mode slice is #44. Other modes and Score
progression remain catalogue entries until split into bounded implementation issues.
Modes need objective, scoring, tie/timeout, team, reset, replay and bot contracts.

## Creator freedom and intentional differences

Any creator can author a compatible character or map without an engine fork.
Installed permitted characters are selectable without mandatory unlock grinding.
Optional collections/progression must not lock out custom content. This is an
intentional Neptune choice, not a claim of identical progression behaviour.

Cosmetic characters share the selected gameplay rules and readable collision cues.
Characters with new abilities declare a ruleset capability and enter compatible
custom rooms. Community packs pin dependencies, hashes and immutable versions;
every player validates the same simulation-affecting content before joining.
The public workshop has attribution and distribution-permission records. A
technical ability to import a character does not authorise publishing its artwork.

## First completion gate

Pin real inputs (#41), automate a bounded local experiment (#42), establish shared
profiles (#43), and compare one mode slice (#44). Measure network quality under
the benchmark contract (#45). Do not claim all-feature parity from a feature count,
generated documentation or green Python tooling checks.

The starter [catalogue](feature-catalogue.json) deliberately separates reference
claims from Neptune implementation status. Expand it from actual observation;
the total number of unobserved features is still unknown.
