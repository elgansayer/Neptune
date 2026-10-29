# Codex execution handoff: community Bomberman

Use this as the next instruction for the existing server Codex session or a
repository-connected worker. A saved prompt or GitHub mention does not establish
that a task started or that a continuous factory is running.

---

Continue implementing `elgansayer/Neptune-Bomberman` autonomously for Elgan. The goal
is a multiplayer-first community Bomberman platform with strong fair bots,
measured Saturn/Power mechanics, browser/native cross-play, portable community
characters/maps/power-ups/modes, complete solo and explicitly authored co-op
stories, and shared player/mod services available in-game and on a website.

This is an execution request. Make tested implementation progress, not another
broad roadmap. Use long-lived goals and small verifiable changes. Continue through
eligible tasks until the current milestone is demonstrated or all remaining work
within your access is concretely blocked. Elgan is available for missing inputs;
routine implementation choices and tests-gated merges are already authorised.

## Establish current state

Read `AGENTS.md` and its required documents. Under `docs/restart/`, also read
`ARCHITECTURE.md`, `COMMUNITY_CONTENT.md`, `BOTS.md`, `SIMULATION_TIME.md`,
`FACTORY_PLAYBOOK.md`, `REVERSE_ENGINEERING.md`, `POWER_BOMBERMAN.md`,
`NETPLAY_BENCHMARKS.md`, `OPEN_SOURCE_AND_CONTENT.md`, `MERGE_POLICY.md` and
`backlog/README.md`, `backlog/catalogue.json`, `backlog/INDEX.md`.
Use #23 as the restart epic and #69 as the comprehensive roadmap. The asset
research repository is `elgansayer/SaturnBomberman-Assets`.

Snapshot, 29 October 2026, to verify against live GitHub:

- The earlier runtime stack and repairs #17/#19/#21/#22 are merged.
- #444 merged the 379-feature catalogue, linked to 372 new and seven reused issues.
  Its 573 acyclic dependency edges are planning metadata, not completed gameplay.
- #443/#70 merged the simulation clock as `8ef4fddc429cf3c6465230532df9c2544854b3df`.
  Accepted head `f461e7adad895027061962cfccd05b2cccbc2c29`, required run
  `40866045910`: 64 passing native results across 17 files. Reuse this work.
- Remaining #30 work includes observation fairness, observer-specific information,
  policy RNG and advanced hazards; #50 retains cleanup/legacy concerns.
- Required CI and tests-gated merging work. #33's durable live factory job and
  restart-recovery proof remain unverified. #48 records missing operator inputs.

Fetch current main, open PRs and latest issue claims/heartbeats. Preserve active
ownership, uncommitted work and evidence. Use isolated branches/worktrees; never
reset a running checkout or force-push over concurrent changes. Older bootstrap
instructions are historical where current merged evidence supersedes them.
Do not assume a cloud worker has the VPS's access, private media or credentials.

## First assignment and ownership

If you are the existing server worker, finish your active bounded task before
adopting the next milestone. If newly dispatched, avoid competing with its #30/#50
work. Inspect #71 (FACTORY-001), #72 (FACTORY-002) and parent #33. Claim the first
unowned, independently implementable factory foundation:

1. Validate issue readiness against stable IDs, concrete acceptance, prerequisite
   evidence, available capabilities and active issue/PR ownership. A closed issue
   alone does not prove its prerequisite contract.
2. Implement a transactional durable job store: atomic claims, leases, heartbeats,
   attempts, transitions and resumable checkpoints. Test simultaneous claimants,
   expiry, restart, duplicate intake and cancellation.

Deliver the smallest useful one first with meaningful failure-case tests and a
focused PR. Reuse an existing implementation or owner and choose the next eligible
child if necessary. Synthetic provider tests cannot satisfy #33's live-job gate.
This first slice does not require starting a paid provider or altering host services.

## Three coordinated workstreams

Use one coordinator with three logical queues: development/integration, Saturn
research, and Power research. Laboratories produce pinned scenarios, observations,
captures, uncertainty and executable comparisons. Development consumes those
contracts and returns reproducible divergences. Keep separate ownership and private
evidence stores. Begin with one active job; more concurrency requires configured
limits and measured capacity, not three new machines by default.

### Dependable multiplayer and bots

Complete concrete #30/#50 prerequisites, then #31 configurable bot filling and safe
human replacement, and #32 repeatable bot evaluation. Use public observations and
the same validated action path as humans. Measure self-KO, stuck/oscillation,
illegal actions and CPU cost. Keep faithful Saturn CPUs separate from enhanced
Neptune bots. No external LLM calls inside a match tick. Preserve twelve-seat
extensibility and reference-specific original limits. Prove #34 cross-play with
actual browser/native clients.

### One recoverable factory job

Implement #33 through its bounded children and available #25 prerequisites. Persist
issue/acceptance/dependencies, input/base/head identities, lease, attempt, commands,
usage and evidence. Demonstrate a real issue -> isolated implementation -> tests ->
PR -> current-base merge -> reconciled completion. Interrupt/restart and prove
recovery without duplicate claims, charges or merges. Exercise provider failure,
bounded retries and cancellation. Use supported, already authorised credentials and
configured spending limits. If missing, finish independent machinery, record the
precise block in #48, and continue another eligible task. A prompt is not a daemon.

### Reference laboratories and exact mechanics

Saturn: #26 -> #27 -> #28 -> #29, then #38. Audit/install reproducibly pinned tools
in authorised isolated environments. Evaluate Beetle Saturn/libretro control,
save/restore and frame capture. Require the complete selected disc, matching BIOS,
region, emulator/settings hashes and repeated-run evidence. Measure movement,
corner/collision, placement, fuse, flame lifetime and chains first; then throws,
kicks, items, mounts, enemies and bosses. Compare equivalent Neptune scenarios.
A deliberate movement/fuse regression must make parity checks fail.

Investigate both static assets and instrumented runtime graphics. Preserve raw
pixels/texture bytes, palettes, transparency, composition, animation timing and
anchors; export PNG plus metadata. Do not infer collision from art or equate a
screenshot with a complete spritesheet. Use Ghidra/validated Saturn support for
targeted unanswered questions. Keep recovered reference materials private;
distributed starter content needs separate provenance and reuse permission.

Power: #41 -> #42, with profiles #43 and measured mode slice #44. Obtain the
developer-distributed client/server/manual and pin actual hashes, initially the
documented 0.7.8c baseline. Verify newer releases separately. Test Linux launch,
input and capture before choosing other infrastructure. Record desktop timing
uncertainty; it is not emulator frame stepping. Use owned local servers. Inspect
actual asset formats before choosing extractors; full decompilation is not a
prerequisite for the first behavioural comparison.

Keep Saturn and Power-compatible rules/defaults versioned separately in the shared
engine. Exactness is per measured release/profile. Generate idempotent per-entity
children from observed inventories. Missing media blocks only reference-dependent
work; original community fixtures can proceed independently.

### Community content, solo and co-op

Build public interfaces #35/#43, then #52's original Ice Bomb and #53's two-level
campaign. First-party content uses the same documented API as community content.
Validate manifests, immutable versions/dependency locks, resource limits and
capabilities. Downloaded packs remain data-only: no arbitrary GDScript, native
libraries or scripted scenes. Bots consume supported effect semantics, not an
author's unverified claim that an effect is safe.

Prove one creator-defined character, arena and power-up in a match with humans and
bots. Then #54 adds authoritative two-player co-op/checkpoint recovery, #55 companion
and enemy roles, #56 accessible editors, and #57 the full upload-to-play journey.
Co-op compatibility must be explicitly authored and tested.

### In-game interface and companion website

Extend #36/#37 using one shared identity, mod registry, compatibility/version service
and trusted statistics API. Godot retains gameplay authority. Reuse supported
account/social APIs rather than internal database tables.

In-game: rooms, bots, browsing/installing/selecting packs, playtests and basic
personal results. Website: public profiles, detailed match history/statistics,
mod pages, upload/version management, documentation and share links. Both use the
same data and permissions. Implement shared contracts and small working flows
before UI breadth. Support large scalable text, keyboard access and clear focus.
Installed compatible characters remain freely selectable. Website implementation
and local tests do not require purchasing a domain or publishing production services.

## Execution loop and continuity

Audit overlap -> claim -> implement -> applicable real tests -> inspect logs ->
attach evidence -> focused PR -> required current-base checks -> merge -> reconcile
the issue -> next eligible task. No mandatory AI/human approving review is required.
Never bypass failing gates, weaken assertions/tolerances, fabricate reference
captures or treat missing/skipped/empty checks as passing.

Baseline metadata commands include `python3 tools/saturn_lab/check.py`,
`python3 tools/research_catalog/check.py` and
`python3 docs/restart/backlog/build_catalogue.py --check`. Gameplay changes also
require the pinned real native suite and applicable browser/network/pack checks.
Metadata validation does not prove runtime behaviour or reference fidelity.

Use the catalogue as a dependency-aware queue. Split oversized tasks, preserve IDs
and reuse accepted work. Persist a checkpoint before context limits or interruption:
owner/lease, branch/head/base, changes, commands/results, evidence paths, remaining
steps and blockers. Resume that record rather than restarting setup.

Ask Elgan only for genuinely missing inputs, credential provisioning, spending or
deployment choices, or unresolved consequential product decisions. Continue other
ready work while blocked. Do not expose secrets, buy infrastructure/tools, start
unlimited provider usage or silently repurpose another repository's factory.

Report implemented, actually validated, still unverified, blocked inputs, evidence
links, observed usage/cost and the next eligible task. Unknown account-wide spend
stays unknown. Claim a live continuous factory only after actual execution and
restart recovery. Begin the first eligible implementation now.
