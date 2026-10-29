# Saturn Bomberman reconstruction: executable research programme

Updated 29 October 2026. Parent #23; inputs #26, emulator bridge #27, graphics #28,
first playable comparison #29 and expanded campaign/battle/CPU coverage #38.
REF-001/#394 pins regional releases; REF-002/#395 inventories campaign rooms;
REF-003/#396 inventories enemies/boss phases. Reuse these issues before creating
children. This document turns the research contract into the next experiments;
it is not evidence that the original has been run or that fidelity is achieved.

## Target and success criterion

Reconstruct the selected Saturn release's campaign and battle rules in the shared
Godot authority, with a versioned Saturn profile. Exactness is tied to release,
region, mode, options and observed scenarios. Do not mix a PAL recording, NTSC
timers, a different release's level tables and Power Bomberman defaults.

Separate the claims: behavioural equality, visual reconstruction, sound/timing,
content coverage and transport quality. A correct-looking room can still have
wrong collision, enemy decisions or progression. Neptune's online/browser support
and community extensions are separate contracts; preserve a faithful ruleset
while allowing deliberate platform differences. Existing Neptune bot improvements
do not establish Saturn CPU behaviour.

## Current evidence and concrete missing inputs

- Main has input-lock/inventory tooling; original media remain unidentified in
  #48's last bounded VPS inspection. This is not proof no copy exists anywhere.
- Asset repository root tree `b55b5a55a4c76c73f4622ffcd20d92bf4755d8b3`
  contains sprite/image, audio, character and export directories. Its README
  credits Spriters Resource rips by Ragey, Pulse Commander and PlayBud101.
  Those credits do not identify every file's release, animation timing or rights.
  Only root/first-directory metadata was inspected in this update; do not treat
  that as a full byte inventory or completeness audit. Existing exports are leads.
- `tools/saturn_lab/compare_trace.py` now compares canonical traces and reports
  first divergence. Its tests use labelled synthetic fixtures, not Saturn captures.
- No verified original boot, real emulator checkpoint, frame-controlled capture,
  original memory map, decoded room or reference-versus-Neptune result is claimed.

The operator input needed first is the **local path to a complete disc image and
matching BIOS**, plus which release/region it is. Use the user's existing authorised
copy; keep originals in private storage. Do not buy hardware/software or upgrade
the VPS before measuring the existing host. A different provider/API key is not
needed to implement local tools with the existing supported Codex worker.

## Experiment 1: establish a reproducible original

1. On the VPS, inspect current jobs and reserve one bounded research slot. Reuse
   existing tools and private input paths. Keep original media read-only; give
   each experiment its own save/RTC/configuration directory.
2. Fingerprint the complete CUE and every referenced track, or the selected CHD,
   BIOS, emulator executable and settings with the existing lock tool. Record
   release/serial/revision evidence separately; a filename is not sufficient.
   Verify a modified temporary input is rejected without touching the original.
3. Pin the Beetle Saturn source revision, build recipe/toolchain, core binary,
   frontend binary and selected options. Start with a small libretro frontend;
   RetroArch is useful for a manual boot/controller sanity check. Check core
   compatibility before claiming either frontend is suitable for this game.
4. Apply and record actual region, RTC, backup RAM, cartridge, controller topology,
   language and input synchronisation settings. Disable host-clock auto-seeding
   where supported and verify effective behaviour; a JSON setting is not proof
   it was applied. Record all environment callbacks/options the core requests.
5. Boot, navigate through an input recording to a known room/arena and checkpoint.
   Reload the checkpoint in a fresh process, replay fixed inputs and compare
   canonical video/observable traces. Repeat at least three times. Keep boot/load
   frames distinct from active gameplay frames and report any unstable fields.
6. Repeat the same sequence after process restart with identical save/configuration
   input. Deliberately change one core/configuration/checkpoint identity and require
   rejection. Record native engine errors/timeouts as failures.

libretro supplies frame execution, input/video/audio callbacks and serialization.
Implement one core instance per process. During a stepped frame, return the same
recorded controller state at every input poll unless the chosen input contract
explicitly models subframe polls. Never use wall-clock keypress sleeps as a frame
oracle. Capture dimensions, pixel format and row pitch; remove padding before
hashing canonical video bytes. Preserve the unmodified raw capture privately.

Query timing from the loaded core and record a rational experiment timebase and
its measurement method. The core documentation lists different PAL/NTSC rates;
do not round them to an assumed 50/60 Hz. Distinguish a video frame from an actual
game update, especially when the game stalls or uses mode-dependent rendering.

Record the port/device map and both multitap settings. Prove each intended player
can independently move/place a bomb without controlling another slot. The core's
support for twelve input devices does not establish a game's player limit. Measure
the selected battle configurations, including any special large arena separately.

## Experiment 2: find rules and data

Use controlled gameplay measurements and targeted static/runtime analysis together.
Start with an unchanged reference, vary one input or parameter, then minimise the
first divergent interval. Record hypotheses, counterexamples and confidence.

| Question | Initial experiment | Internal evidence when needed |
| --- | --- | --- |
| Movement and corners | Short/held direction runs at different speeds, offsets and corridor entries; release/reverse on boundaries | Position/subpixel writes, collision queries and speed tables |
| Bomb placement and chains | Empty/blocked/capacity cases; simultaneous placement; blast touching another bomb at fuse boundaries | Bomb slots, timer updates, iteration order and event priorities |
| Blast/hit behaviour | Edge-of-flame movement, overlapping blasts, deaths, invulnerability, walls and hidden items | Hitboxes, flame lifetime, damage order and drop/state changes |
| Kick/throw/mounts/items | Moving/stationary collisions, landing edges, ability combinations and loss on death | Trajectory tables, ability flags, action state transitions and timers |
| Campaign room | Entry/spawns, switches/doors/objectives, exits, death/retry, transitions and save/continue | Room tables, trigger scripts, progression flags and spawn records |
| Enemy or boss | Approach from different distances; attack boundaries; phase transitions; reset | Actor state machines, movement tables, vulnerabilities and RNG use |
| Battle result | Ties, last-survivor events, timeouts, sudden death, options and multi-controller combinations | Round state, scoring/tie precedence and restart conditions |
| Saturn CPU | Controlled observations/difficulty, identical starts and repeated seeds if recoverable | Decision cadence, perception rules, chosen actions and random branches |

Identify candidate RAM variables by controlled state differences, then validate
with read/write watchpoints and repeated unmodified play. Record address space,
byte order, width, signedness, units, region and validity interval for every symbol.
A coincidental changing value is not a discovered player coordinate or RNG state.

Use Ghidra for targeted SH-2 analysis of the loaded code/data around unresolved
questions. Pin Ghidra/JDK/loader versions and preserve import maps, labels and scripts.
The available Saturn loader is WIP: its ISO path only loads the first disc file and
its documented memory map has limitations. Validate overlays and runtime-loaded
code from observed load addresses; do not infer the whole game from the boot file.
Verify save-state format compatibility before importing a Beetle capture into a
loader advertising Mednafen states. Use headless analysis for repeatable extraction.

Recover RNG state/advance rules where deterministic behaviour requires them. Keep
uncertain RNG cases labelled statistical until the original algorithm, ordering
and state can be demonstrated. Replacing it with an arbitrary seeded generator
does not make an exact Saturn profile. Disassembly findings become independently
written specifications and tests; keep private dumps out of implementation prompts.

## Experiment 3: recover original graphics and content structure

Run two bounded extraction paths:

- Inventory disc files and identify archives/compression/tables through validated
  decoders. Preserve source file/offset/length and input hashes for each output.
- Instrument the pinned core for VDP1 command/texture data and VDP2 tile/background
  state with palette/colour information. Standard libretro frame callbacks do not
  provide these internal tracing hooks; instrument and verify them separately.

Choose one player animation set, one campaign room and one battle arena first.
Capture raw indexed pixels, palettes, transparency interpretation, composed parts,
anchors, flips/transforms and frame durations. Reconstruct the observed frame and
compare it with the reference. An isolated sprite PNG is not an animation spec.
Use runtime reads to connect decoded assets to disc files/offsets when possible.
Keep forced animation/debug states labelled separately from normal gameplay.

Recover map collision, triggers, objects and enemy spawn logic separately from
background art. For audio, identify samples/sequence data or CD tracks from actual
disc/runtime evidence, with loop/cue timing. Existing ripped assets can help match
known observations but cannot fill unobserved states by assumption.

All raw reference binaries/captures stay private. Track provenance and release
permission for distributed packs separately; the public engine can keep using
original/permitted starter content throughout research.

## Experiment 4: one campaign room and one battle arena

Create a documented scenario adapter on each side. Map the same intended initial
conditions and controller recording into the pinned original and Neptune profile.
The adapter must report unsupported observations; it must not fabricate values,
filter inconvenient events or adjust expected timing to make a comparison pass.

Start with canonical integer/fixed-point observations: positions, facing, collision
cells, bombs, flame lifetimes, actor state, item changes, ordered events and outcomes.
Use evidence-backed alignment and explicit units. Keep renderer/presentation checks
separate; any tolerances require their own versioned rationale and deliberate
regression tests. The initial comparator performs exact comparisons only.

Run `python3 tools/saturn_lab/compare_trace.py reference.json neptune.json`.
It rejects empty or non-contiguous traces and mixed scenario/ruleset/timebase/input
contracts, then returns the first differing frame and JSON field. It compares
supplied data; it does not verify a capture's authenticity. The capture runner
must first verify real input locks and retain raw evidence plus adapter versions.

Completion evidence requires a real reference recording, repeatable original runs,
an equivalent production Neptune run, and deliberate movement/fuse mutations that
fail at the expected divergence. Synthetic comparator tests prove the tool only.
Track a failed comparison by `(reference identity, scenario, first divergence)` to
avoid duplicate issues. Never change fixtures automatically to hide a failure.

## Expansion to the complete game

Inventory modes and options from the actual release, then every reachable campaign
room/transition, enemy state, boss phase, item interaction, character/mount animation,
battle configuration and menu/save flow. Include solo and any supported original
co-op separately, with death/continue/progression interactions and simultaneous
actions. Keep score/Master or regional modes distinct wherever observed.

Use REF-002..REF-014 and #38 to create idempotent per-observed-entity children.
Publish a coverage matrix with `unknown`, `captured`, `specified`, `implemented`,
`compared` and `cross-checked` states. Unknown denominators remain unknown; exhausting
a capture script does not establish completeness. Cross-check representative
mechanics and suspected emulator artefacts against another emulator or hardware.

## Factory/VPS handoff

Keep one coordinator. Development, Saturn and Power are separate logical queues
with input/capability requirements and independent progress. The server Codex worker
must finish its active #452 bot observation task before adopting overlapping work.
Cloud GitHub dispatch has not been confirmed; do not depend on it for the VPS route.

PR #453 supplies local readiness and durable lease APIs in `tools/factory/`.
Next factory work is #73/#74/#75 and the live #33 gate, following that README.
Research can use the same coordinator once #26's real inputs are identified. AI
chooses bounded experiments; scripts run the emulated frames without model calls
inside the frame loop. Missing Saturn media must not stall independent game work.

## Primary sources checked for this implementation plan

- [Beetle Saturn: inputs, BIOS, timing, controller/RTC options](https://docs.libretro.com/library/beetle_saturn/)
- [libretro core/frontend callbacks, stepping and serialization](https://docs.libretro.com/development/cores/developing-cores/)
- [Ghidra headless analysis](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md)
- [Saturn loader support and limitations](https://github.com/VGKintsugi/Ghidra-SegaSaturn-Loader)

These establish tool capabilities and research leads, not Saturn Bomberman mechanics.
