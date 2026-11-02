# Factory development and Saturn research first

Owner direction: 2 November 2026. This changes the priority for new work. Preserve
active claims, completed game work and the full product requirements. It supersedes
earlier instructions to expand ordinary game/workshop or Power features ahead of
the factory and Saturn research critical path.

## Persistent objective

Build and operate Neptune's AI development factory using the existing Elgl
control plane and authorised shared Codex/OpenAI, Claude and Gemini access.
Use it primarily to reverse-engineer Sega Saturn Bomberman: recover code/data,
graphics, animations, maps, audio and measured campaign/battle rules; implement
recovered contracts in Godot and verify them against pinned originals. Add needed
tools, packages and reusable agent workflows. Work through small GitHub issues
with durable ownership, resumable evidence and tests-gated automatic merges.
Demonstrate real recovery and original-game comparisons before calling the factory
continuous or the game faithful.

The moddable native/browser game, multiplayer, strong bots, community packs,
profiles, stats and workshop remain the end product. They consume the pipeline's
outputs and are not removed from the backlog or marked complete.

## Further owner clarification: reverse engineer all game code

The owner's subsequent 2 November direction is explicit: **reverse engineer all
the code**. Code recovery is the primary research output. The accepted asset
work remains useful, and active owners continue; a newly extracted soundtrack,
another inventory or a tooling PR cannot substitute for the code objective.

Continue #478/#480–#483/#488/#492/#494–#497/#515 through the existing factory.
Account for the original boot chain and resident kernel, master/slave SH-2
functions and tasks, overlays and code-bearing resources, SDK/libraries,
indirect targets and resumptions, 68000 sound drivers and observed DSP programs,
menus/save handling and regional NetLink/XBAND paths. Keep module, source digest,
CPU/address space and load lifetime together: different modules reuse the same
addresses. Upstream generated trampolines and patched boot images are analysis
artifacts, not unmodified original game code.

For each slice recover original code boundaries, arguments/returns, state reads
and writes, callers and behavior, then compare against original instructions and
natural execution with a deliberate wrong branch/state/result. Distinguish source
hypotheses, disassembly, instruction translation, isolated original-byte tests,
natural emulator observations and independent checks. The original source's
names/comments may be unrecoverable. A complete instruction translation or byte
census does not establish complete recovered semantics.

Current bounded continuation: [module candidates](saturn-code/README.md) and the
[next original-function probe](research/2026-11-02-saturn-code-probe.md). The
already verified helper at `0x0600A4B0` and resident-checked decompressor remain
accepted; the new `0x0600B934` hypothesis needs original-host execution before
it counts as a newly validated function. Do not guess RNG taps from its symbol.

If original bytes or the existing VPS command channel are unavailable, record
the precise access blocker and next runnable command. Continue independently
useful code work; do not claim a host job ran or repeatedly repackage the finished
FILM extraction as code recovery. Use the already supplied media, not another
request for discs. Whole-program executable/function/dynamic-target denominators
remain unknown until discovery itself has been reconciled with runtime evidence.

## Select the next work

1. **Make the shared factory usable and recoverable.** Continue #33/#536 manual
   session supervision and effective account-wide accounting, #510 research job
   routing, #75/#518 environment preparation, and #76/#511 executable acceptance.
   Reuse accepted leases, process guards, identity checkpoints, verification and
   native auto-merge rather than rebuilding them because a parent remains open.
2. **Use it on real Saturn research.** Continue #477/#464 and their bounded
   children: original-game navigation, code/overlay discovery, tracing, VDP1/VDP2
   decoding, animation reconstruction, sound recovery and behaviour measurement.
   Reuse existing inputs/bridge and preserve Gemini's research ownership.
3. **Implement and compare the recovered slice.** Use #29 and
   [SATURN_FIDELITY.md](SATURN_FIDELITY.md) for production-Godot state/events,
   native pixels and native-rate audio. Diagnose the first divergence, create a
   reproducible implementation issue, then expand verified coverage.

At each new claim choose eligible factory or Saturn-critical-path work first.
Ordinary UI, workshop, cosmetic, gameplay breadth and Power expansion follow this
priority. A game/build/bot fix is eligible now when it removes a demonstrated
pipeline blocker or executes/compares a named recovered scenario. Missing inputs
block dependent experiments only; continue another eligible factory/research task.
Do not interrupt another owner's bounded work or rewrite its accepted revision.

Infrastructure work must name the research job it unblocks and its executable
operational acceptance. Prefer exercising the pipeline over adding framework
layers. More roles, agents, commits or issue closures are not research progress.

## Coordinated agent roles

These are roles in the existing factory, not new daemons or provider slots.

| Role | Concrete output |
| --- | --- |
| Coordinator | Dependency/ownership checks, bounded issue, shared lease, heartbeat, budget and recovery state |
| Research/capture | Pinned original experiment, input/checkpoint, clocks, bounded traces/video/PCM and uncertainty |
| Analysis/extraction | Repeatable decoder or measured rule, real assets with provenance, coverage gaps |
| Implementation | Small Godot/tool change against the recovered contract, preserving public extension interfaces |
| Executable verifier | Exact source/candidate/task identities, actual comparisons, negative controls and first divergence |

Use supported interfaces for configured agents; a subscription is not proof of
unattended API access. Scripts execute frame/sample loops; models plan, implement
and interpret selected evidence. No model calls per game frame or bulk private
discs/BIOS/save states/raw memory submission. Begin with one heavy job under
existing shared limits; increase disjoint concurrency only after real accounting
and capacity evidence. Preserve manual sessions and other repositories' services.
No competing scheduler or new swarm framework is needed to begin.

## Tools and packages are part of delivery

Use #508 adapters and #518 preparation under
[PROVISIONING.md](../../tools/factory/PROVISIONING.md). Routine required free tool
downloads/builds are authorised; reuse working installations before replacing them.

| Capability | Existing work to extend |
| --- | --- |
| Headless original control, checkpoints and input timelines | Existing libretro bridge; #479/#490/#491 |
| Code, overlays and bounded instruction/memory/DMA traces | #478/#480/#481/#482; evaluate Ghidra/PyGhidra and agent interfaces through #508 |
| Sprite/background/palette and animation extraction | #484/#485/#486/#487; evaluate existing emulator debugging/export hooks |
| PCM, sequences, streams, movies and triggered sound | Existing PCM capture/comparator; #488/#489; FFmpeg/ffprobe preparation where needed |
| Exact state, pixel and sample comparison | Existing trace/PCM tools; #76/#511/#513 and feature-specific mutation controls |
| Reusable skills, libraries and research dependencies | #508/#518; official versioned sources and bounded feature probes |

For a missing capability: create/reuse a focused preparation/recipe task, pin the
official source/release and hashes, install/build in the constrained preparation
environment, run a real feature smoke and identity check, retain the receipt,
refresh the manifest and resume the original job. Executable presence or
`--version` alone does not prove the required feature works. Preserve historical
reference builds and original media. Workers get no host root, production
credentials or unrestricted Docker socket; host packages use the configured
constrained provisioner. No silent purchase, paid fallback, new allowance or
quota reset. Bound retries, time, memory, disk and output; unknown spend stays
unknown. Extra disk capacity is not authority to repartition or delete captures.

## First operational acceptance

Retain evidence for all of the following; documents/tool tests alone do not pass:

1. A real bounded research issue goes through the existing factory to
   implementation, applicable verification, PR and exact-head/current-base merge.
2. Shared manual/worker accounting, ownership and checkpoints survive actual
   interruption/restart. Provider/tool failure stops or retries within policy and
   resumes without duplicate jobs, allowances or publication.
3. Pinned real inputs repeatedly reproduce declared campaign and battle reference
   experiments, retaining release, BIOS/core/settings, controls, clocks and hashes.
4. Real character, room and arena assets are extracted with provenance and a
   reusable command. Missing/uncertain coverage stays explicit.
5. Equivalent production-Godot scenarios pass applicable exact state/events,
   native-pixel and native-rate-audio comparisons; seeded tick/order,
   pixel/palette and sample/trigger regressions fail their respective checks.

Enable continuity only after the shared-session and real recovery gate. Report
supervised success separately when coordinator intervention was needed. Expand
through the same loop to other rooms, characters, enemies, bosses, modes and
presentation; whole-game reconstruction stays open until coverage and evidence
support it. Neptune needs successful applicable tests, not an approving AI/human
review; preserve [MERGE_POLICY.md](MERGE_POLICY.md). Other repositories retain
their own policy. Never relax reference tolerances or use candidate output as its
own oracle. Native CI and synthetic tooling do not establish exact fidelity.

## App Goal and durable instructions

This is the repository's durable objective; it does not itself edit a persisted
app Goal or start workers. If the app still holds an older objective, the user can
set the replacement through its supported Goal command:

```text
/goal Build Neptune's existing shared AI factory and use it to reverse-engineer Sega Saturn Bomberman. Follow docs/restart/FACTORY_FIRST_GOAL.md. Prove shared-account limits, restart/provider-failure recovery, a real issue-to-tested-merge job and real extracted assets with regression-detecting Godot state/pixel/audio comparisons before expanding ordinary game features.
```

Do not mark an unfinished old Goal complete merely to replace its text. Use the
supported user controls when current agent tools cannot edit that objective.
