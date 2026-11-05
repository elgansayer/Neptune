# Automated Saturn research lab

> **Goal (owner, 5 November 2026):** the full source code and all assets of
> Saturn Bomberman. See [FULL_SOURCE_AND_ASSETS.md](FULL_SOURCE_AND_ASSETS.md).
> Experiments below verify that reconstruction.

This is now a primary delivery track under the owner's 2 November
[factory/Saturn-first goal](FACTORY_FIRST_GOAL.md). Build the shared factory and
necessary tool adapters to run these experiments, then implement and compare
their measured outputs in Godot. Preserve existing owners and exact reference
acceptance; routine feature breadth follows this critical path.

The expanded code/content/behaviour programme is [RESEARCH_EXECUTION.md](RESEARCH_EXECUTION.md)
and execution index #477. Existing input/bridge/disc inventory results remain
accepted; complete static/dynamic code recovery, raw graphics/audio extraction and
Normal/co-op/Master/Battle coverage now have bounded RSAT/RLAB issues. User-authorised
decoded private asset publication follows #512; original discs/BIOS/states/dumps stay
host-private. Existing reconstruction experiments remain applicable.

The next executable research sequence is [SATURN_RECONSTRUCTION.md](SATURN_RECONSTRUCTION.md).
The canonical comparison tool and its limits are documented in
[TRACE_FORMAT.md](../../tools/saturn_lab/TRACE_FORMAT.md).

The owner's 1 November requirement is [SATURN_FIDELITY.md](SATURN_FIDELITY.md).
The faithful baseline must match measured timings, speeds, mechanics, effects,
music and sound as well as every covered map and asset. Require exact state/events,
native-resolution pixels and native-rate digital audio at declared boundaries.
Approximate/prototype comparisons remain useful diagnostics and do not satisfy
exact parity. Unknowns remain incomplete or blocked. Complete source reconstruction
is not a prerequisite for the first measured Godot slice or original creator work.

## Input identity and repeatability

The current `tools/saturn_lab/cli.py` inventories files and creates/verifies input
locks. A lock includes every CUE-referenced BINARY track, the CUE/CHD, BIOS, emulator
binary and actual configuration file. It proves byte identity only. It does not
certify that an image is valid, settings are applied, or the emulator is accurate.

The emulator bridge must record its own build hash, core build hash, BIOS/disc
hashes, settings, region, RTC state, controller topology and starting state. Fix
all relevant settings, including time and threading where needed. Repeated runs
must agree on canonical observable state/image hashes within the pinned setup.
Do not assume an emulator save state is portable across builds or cores.

## Bridge and remaining hooks

`tools/saturn_lab/frontend.py` now implements bounded load, restore, frame stepping,
video/audio/input observations and exact replay comparisons. Read its
[commands and limits](../../tools/saturn_lab/README.md) and
[real private-host evidence](evidence/2026-10-29-libretro-bridge.md).
The full research interface below remains the target: selected game-state symbols,
raw graphics and CD/memory/graphics tracing require additional adapters/hooks.

| Operation | Required behaviour |
| --- | --- |
| load reference | Verify the input lock before execution; boot the selected entry |
| restore checkpoint | Validate checkpoint build/configuration identity |
| step | Apply per-controller inputs and advance specified emulated frames |
| capture | Return frame, raw graphics references, selected memory observations and events |
| trace | Bounded CD/memory/graphics tracing around an experiment |
| replay | Run a recorded input sequence from a known state and compare outputs |

Use one emulator instance per isolated process initially. The libretro API is
designed around a single core instance; do not assume concurrent instances in one
process are safe. AI plans experiments and analyses bounded outputs. Scripts run
the frame loop without a model call per frame.

## Two extraction routes

1. Disc inventory and static decoding: identify archives, pointers, compression,
   graphics tables, animation tables, map definitions and scripts. Decode selected
   files through versioned extractors. Relate outputs to source offsets where known.
2. Instrumented runtime capture: observe graphics after the game has decoded them.
   Capture VDP1 texture bytes and command parameters, palette/colour state, and
   VDP2 background tile/pattern arrangements. Trace relevant loads to associate
   captures with source files. Use bounded tracing to avoid unmanageable logs.

Retain raw bytes and interpretation metadata. PNGs are convenient renderings,
not the complete source of truth: transparency, palette changes, mesh/colour
effects, composition, transforms and frame durations may require separate data.
Rendering layers do not establish collision maps or object spawn logic.

Automated clustering may identify duplicate frames and probable animations, but
heuristic labels remain provisional. Memory editing can expose animations after
the relevant selectors are understood; compare unmodified gameplay to establish
normal ordering and timing. Never mistake a forced state for a valid game rule.

## Evidence records

Every observation must carry:

- Stable observation ID, source input lock digest, bridge/core build and settings.
- Scenario ID, starting checkpoint, controller input recording, emulated frame range.
- Original bytes/capture digest; source file/offset or memory/draw command when known.
- Interpretation, confidence (`unknown`, `hypothesis`, `observed`, `cross_checked`),
  counterexamples and a reproducible comparison command.
- Whether the original execution was modified to expose content.

Create confidence transitions from evidence, not the worker's prose. Original
reference fixtures and tolerance changes require traceable evidence and executable
regression checks. MERGE_POLICY.md makes review optional without permitting silent
fixture weakening.

## Campaign and battle coverage

Build explicit inventories of stages, maps, characters, animation states, items,
enemy families, boss phases, progression rules, cutscenes, menus, scoring and
multiplayer configurations for the chosen release. Include campaign-only and
mode-specific animations. Record unresolved entries; do not invent totals.

Use saved checkpoints and scripted navigation; search for new states/graphics
when coverage stalls. Where practical compare critical results with another
emulator or hardware recording to distinguish game behaviour from emulator bugs.

## Behavioural experiments and parity

Measure movement/subpixels, corner assistance, collision timing, bomb placement,
fuse/explosion timing, chain reactions, throwing/kicking, item effects, enemy
transitions, boss attacks and round outcomes. Sweep one variable at a time and
include boundary conditions and simultaneous events.

Create equivalent initial conditions in Neptune through a scenario adapter;
Saturn RAM addresses are not Neptune's state model. Compare canonical positions,
events, outcomes, native-resolution pixels and native-rate digital audio according
to the declared faithful comparison contract. Map input polling, game ticks,
VBlank/presentation, task ordering and audio sample indices explicitly. Match the
reference timebase without assuming every region is exactly 60 Hz or using local
render/wall-clock time as a substitute. Retain the original and candidate capture,
adapter and content identities. Any tolerant renderer/audio comparison must be
labelled diagnostic or approximate and cannot pass the exact baseline gate.

Recover source samples separately from SCSP sequence/driver/mix behavior and
CD/streamed audio. Preserve native formats, rates, channels, sample counts,
trigger/loop boundaries, pitch/envelopes, pan/volume and interruption/priority
semantics. Verify the resulting production Godot event and PCM timelines,
including transitions, pause/slowdown and repeated loops. A successful WAV export
or a correct soundtrack played at the wrong event/sample boundary is incomplete.

Recover RNG behavior and call ordering for exact replay of affected systems.
Controlled cases and labelled statistical comparisons may advance research while
RNG remains unknown, but cannot establish the exact baseline. Local scripted
controllers establish battle rules first; browser/native networking tests
establish transport behavior separately. Neither test substitutes for the other.

## Completion gate for the first slice

- Clean-checkout tooling can fingerprint the actual selected reference inputs.
- Repeated recorded runs have identical canonical outputs in the pinned environment.
- One real character's required animations are exported with palettes and timing evidence.
- One campaign room and one battle arena have production Godot comparisons for
  state/events, visuals and representative triggered sound/music, with explicit
  frame/sample clocks and native output boundaries.
- Deliberate movement/fuse, animation/pixel and audio/sample/loop mutations each
  cause the applicable faithful comparison to fail at a reproducible divergence.
- Authentic real-source receipts identify reference and candidate inputs/builds,
  adapters, captures and task revision/head/current base. Missing, stale,
  truncated or forged evidence fails rather than becoming a passing placeholder.
- A failure produces a reproducible GitHub issue with evidence IDs and the first divergence.

## Primary references checked during planning

- [libretro frontend/core execution and state API](https://docs.libretro.com/development/cores/developing-cores/)
- [Beetle Saturn formats, BIOS and controller options](https://docs.libretro.com/library/beetle_saturn/)
- [Yabause VDP1 debugger implementation](https://github.com/Yabause/yabause/blob/master/yabause/src/vdp1.c)
- [Ghidra headless analysis](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md)
- [Saturn loader and its documented limitations](https://github.com/VGKintsugi/Ghidra-SegaSaturn-Loader)
- [Firsthand Saturn sprite ripping notes and campaign animation gaps](https://randomhoohaas.flyingomelette.com/spr/bomberman.html)
