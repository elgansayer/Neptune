# Automated Saturn research lab

The next executable research sequence is [SATURN_RECONSTRUCTION.md](SATURN_RECONSTRUCTION.md).
The canonical comparison tool and its limits are documented in
[TRACE_FORMAT.md](../../tools/saturn_lab/TRACE_FORMAT.md).

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
events, outcomes and aligned rendered regions. Use exact equality where defined
and explicit, justified tolerances for renderer differences. Match the reference
timebase; do not silently assume every region is exactly 60 Hz.

Recover RNG behaviour when exact replay requires it; otherwise use controlled
cases and labelled statistical comparisons. Local scripted controllers establish
battle rules first; browser/native networking tests establish transport behaviour
separately. Neither test substitutes for the other.

## Completion gate for the first slice

- Clean-checkout tooling can fingerprint the actual selected reference inputs.
- Repeated recorded runs have identical canonical outputs in the pinned environment.
- One real character's required animations are exported with palettes and timing evidence.
- One campaign room and one battle arena have visual and behavioural fixtures.
- A deliberate change to movement or fuse behaviour causes parity CI to fail.
- A failure produces a reproducible GitHub issue with evidence IDs and the first divergence.

## Primary references checked during planning

- [libretro frontend/core execution and state API](https://docs.libretro.com/development/cores/developing-cores/)
- [Beetle Saturn formats, BIOS and controller options](https://docs.libretro.com/library/beetle_saturn/)
- [Yabause VDP1 debugger implementation](https://github.com/Yabause/yabause/blob/master/yabause/src/vdp1.c)
- [Ghidra headless analysis](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md)
- [Saturn loader and its documented limitations](https://github.com/VGKintsugi/Ghidra-SegaSaturn-Loader)
- [Firsthand Saturn sprite ripping notes and campaign animation gaps](https://randomhoohaas.flyingomelette.com/spr/bomberman.html)
