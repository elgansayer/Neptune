# Saturn and Power reverse-engineering execution

Execution index: [#477](https://github.com/elgansayer/Neptune-Bomberman/issues/477).
Saturn mission: [#464](https://github.com/elgansayer/Neptune-Bomberman/issues/464).
Power mission: [#476](https://github.com/elgansayer/Neptune-Bomberman/issues/476).
The [catalogue](backlog/catalogue.json) has 418 desired features, including 38 new
research jobs. This document records the 30 October 2026 evidence and dispatch
contract, not completed reconstruction.

## Accepted starting points

- #466 audited 50,407 existing asset files. Much of the collection is GameMaker
  export data; exact Power build identity remains unverified. Preserve all history,
  aliases and original files instead of relabelling the whole repository Saturn.
- #467/#468 validated real USA MK-81070 V1.003 and Japan T-14302G V1.000 inputs and
  the bounded libretro bridge. Source media live under
  `/home/dev/Sega-Saturn-BIOS/`. Both supplied images have 30 tracks.
- The accepted Beetle core source is
  `01bc063fdd0fb5fc208850c9ecc658834df762ab`. Input locks/evidence, not this
  source revision alone, identify the actual executable, BIOS and settings.
  Repeated fresh checkpoint continuations are evidence of repeatability in that
  setup; they do not certify game fidelity or raw VDP hook availability.
- #473 inventories 430 USA and 25 Japan files, 236/240 PROGRAM.BIN banks,
  validated in-file header pointers and regional differences. Static inventory
  is not semantic code recovery or decoded graphics. The existing movie files'
  possible PAL provenance remains a hypothesis.
- Gemini's existing research workspace is `/home/dev/neptune-gemini-research`.
  Preserve its active ownership and queued EXP-SAT-ARCHIVE-002 rather than starting
  another worker on the same slice. An expired old lease is not proof of a stopped
  process; reconcile live ownership first.
- #474/#475 integrated Neptune offline verification into the existing Elgl Repo
  Factory. Live Neptune unattended task/merge/restart recovery remains to be
  demonstrated. Read current #33 evidence before scheduling.

## Immediate experiments

| Priority | Bounded result | Issue |
| --- | --- | --- |
| First | Reproduce one upstream normal route and one battle route against our original bridge; map useful code/tools and disagreements | #478 |
| First | Continue EXP-SAT-ARCHIVE-002: base1/normal2 bank bytes versus resident memory | #484 |
| Next | Bounded trace hooks, then one player/effect and background from VDP data | #482, #485, #486 |
| Independent | Pin Power client/server/manual, VM/YYC/container identity and existing-export match | #498, #400 |
| Independent | Verify one private decoded asset batch with regeneration and source manifest | #512 |
| Factory | Route one bounded research job through existing intake, capabilities and trusted receipts | #510, #511 |

Each issue supplies role, first slice, dependencies, acceptance and source leads.
Parent epics are coordination only. Dependencies denote demonstrated contracts,
not merely closed issues. REF-011 interaction experiments can begin independently
for either game; declare the specific item/reference inputs in each experiment.

## Existing work worth testing first

[pc-saturnbomberman](https://github.com/callumjenkins/pc-saturnbomberman), inspected
at `c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3`, is an existing AI-assisted
static recompilation targeting the same USA release. Its author reports extensive
Claude Code use. It includes scripted routes, symbols, extraction/research helpers
and reference-comparison work. #478 must reproduce selected results and record
reuse candidates before building equivalent tools.

Its documentation includes forced-state/invincibility techniques and known
loading, audio, CPU and RNG divergences. Preserve that distinction when testing.
Use its actual pinned [saturn-recomp](https://github.com/callumjenkins/saturn-recomp)
submodule, not an arbitrary latest revision. Review MIT code and optional GPL
renderer notices component by component; the Neptune root licence stays unchanged.
No upstream demonstration is automatically accepted Neptune parity evidence.

Other primary tool leads, requiring local capability tests and version pins:

- [Beetle Saturn/libretro](https://docs.libretro.com/library/beetle_saturn/),
  [Mednafen Saturn](https://mednafen.github.io/documentation/ss.html),
  [Yabause](https://github.com/Yabause/yabause), and
  [Kronos](https://github.com/FCare/Kronos): #479 compares actual controls/debug
  hooks, state compatibility, correctness and resource cost.
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra),
  [Saturn loader](https://github.com/VGKintsugi/Ghidra-SegaSaturn-Loader), and
  [GhidraMCP](https://github.com/LaurieWired/GhidraMCP): #481/#508 test bounded,
  reproducible local workflows. Loader support is not a guarantee every overlay,
  disc or save state is imported correctly.
- [Power developer release thread](https://www.bombermanboard.com/viewtopic.php?t=1925)
  identifies 0.7.8c, 1 March 2026, with clients and an optional server. Pin real
  bytes and same-version hotfix identity before using advertised counts.
- [UndertaleModTool](https://github.com/UnderminersTeam/UndertaleModTool) and
  [Underanalyzer](https://github.com/UnderminersTeam/Underanalyzer) are candidates
  only after identifying the actual GameMaker version and VM/native code in #498.
  Do not assume every executable is decompilable through the same route.

The source registry #509 records retrieved revisions, capabilities, licences,
failed experiments and new leads. Do not create tools/skills from untested recipes.

## Complete scope and evidence

RSAT-001–020 cover master/slave SH-2 modules/overlays, sound 68000 and observed DSP
programs, static and dynamic code, bank formats, VDP1/VDP2, animation, SCSP/CD audio,
movies, original navigation, typed state, RNG/timing, mechanics, saves, presentation,
NetLink/XBAND and hidden/unused paths. RPWR-001–010 cover actual code/events,
textures, media, rooms, timing, modes, CPU policies, owned-server protocol and
authoring formats.

REF-001–014 retain exhaustive regional content and interaction inventories.
Normal solo/co-op, Master, standard/wide Battle, original CPU, enemy/boss phases,
items, menus, progression, secrets and endings must have measured per-entity
contracts. #410 grows bounded children idempotently from discovered stable IDs.
SATURN/POWER implementation and community multiplayer/bot/modding features consume
these results independently; complete decompilation does not block original packs.

Every result links source range/resource ID, build/region, tool/core/settings,
input/checkpoint/timebase, output hash, command, confidence and counterexamples.
Track separately: discovered/static-classified, decoded/disassembled/decompiled,
executed, semantically validated, privately published, and Neptune parity.
Instruction translation and full byte classification do not prove behaviour or
recover lost source names/comments. Unknown denominators remain unknown.

Require representative real runs, replay/regeneration, relevant corrupt/missing/
stale controls, and deliberate semantic or rendering mutations. Independent
comparison #513 must disclose common emulator lineage and timing precision.
Never silently alter fixtures, mask drift or inflate tolerances.

## Automatic tool setup

Routine free emulator/analysis/dependency setup is authorised factory work.
[FACTORY-017 / #518](https://github.com/elgansayer/Neptune-Bomberman/issues/518)
adds pinned preparation recipes, actual smoke checks, cache recovery and automatic
missing-recipe follow-ups. See [the runnable installer contract](../../tools/factory/PROVISIONING.md).
Keep preparation separate from offline verification and preserve accepted
reference binaries. Live job provisioning/resumption needs its own VPS evidence.

## Factory, assets and continuity

Reuse `elgansayer/elgl`'s deployed Repo Factory and supported shared provider broker.
This is the operator-authorised integration direction, superseding older blanket
language against that reuse. Preserve existing services, shared health/limits,
manual sessions and each repository's merge policy. Do not create a competing
scheduler or treat an account-wide limit as a new per-repository allowance.

RLAB-001–008 add tested skills, source discovery, research queues, trusted private
receipts, asset publication, independent comparisons, recovery/storage and coverage.
Scripts execute frame/trace loops; agents plan and inspect bounded outputs.
No unlimited spending, concurrency or storage purchase is implied.

The user authorises decoded Saturn/Power research assets in the private
`elgansayer/SaturnBomberman-Assets` repository. #512 requires separate game/release
namespaces, source hashes/recipes, lossless formats where applicable, deterministic
regeneration, provenance and bounded uploads. Preserve existing files/history.
Full discs, BIOS, save states, raw dumps and credentials remain host-private.
Engine licences, reference content and public default/community packs remain
separate; private publication is not automatic public-release approval.

Apply the existing exact-head/current-base test gate with no mandatory AI/human
approving review. Trusted private receipts #511 prove the applicable reference
experiment; ordinary metadata CI does not. Preserve completed evidence, report
failed hypotheses, and reconcile active ownership before resuming work.

## Applied web and source investigation (30 October)

The [deep-dive report](research/2026-10-30-deep-dive.md) and
[39-source registry](research/sources-2026-10-30.json) add pinned upstream
function candidates, concrete graphics/audio exporters, comparison hazards and
Power/Ghidra capability checks. `tools/saturn_lab/probe_kernel.py` is the bounded
EXP-SAT-CODE-001 entrypoint for the accepted USA kernel. It has synthetic contract
coverage; the original-file VPS execution and independent trace remain pending.
Use the report's issue map and preserve current owners.
