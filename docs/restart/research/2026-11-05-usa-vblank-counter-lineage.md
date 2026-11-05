# USA kernel frame counter versus pad-read tick in one restore lineage

Run `usa-code` 20261105T0632Z, second slice, for #492. **Natural emulator
observation** by passive sampling: WorkRAM-H values were read from three existing
captured states that form one verified restore lineage. Nothing was executed or
modified. The roles of the sampled addresses come from **static disassembly** in
the [USA function inventory](2026-11-05-usa-function-inventory.md). Derived
values and hashes are in the [receipt](../evidence/2026-11-05-usa-vblank-counter-lineage.json).

## Static roles (disassembly only)

Startup `06006372` first calls `060064E0`, which:

- registers `SYS_SETUINT` vector `0x40` → `06006652`, which increments the word at `0x060B2D20`;
- registers vector `0x41` → `0600665C`, which stores to the VDP1 registers at `0x25D00000`;
- clears both VBlank bits in the SCU mask through `SYS_CHGSCUIM`;
- spin-waits on the `0x060B2D20` word through `0600667E`.

Back in `06006372`, startup then re-registers vector `0x41` → `06006368`. That
handler increments the longword at cache-through `0x26006038`. Startup zeroes that
longword at `060063C6` and spins until it becomes nonzero.

This corrects the order given in the inventory note and the #492 comment: `06006368`
is the later, surviving VBlank-OUT handler. Pad-reading code in `06006FC6`,
`06007014` and `06007326` loads four longword counters through `0x26006100`.
Upstream `game.toml` describes these as VBlanks since each port's pad changed,
counted only while pads are read.

## Lineage

| Sample | Frame | State SHA-256 | How it was made |
| --- | --- | --- | --- |
| `continuation-release` | 3,000 | `a6f7f4ad…` | cold boot, checkpoint at 3,000 |
| `navigation-release-late` | 10,200 | `7049c389…` | restored the 3,000 state, ran 7,200 frames |
| `menu-release` | 10,800 | `e5bd5164…` | restored the 10,200 state, ran 600 frames with menu input |

[`sample_workram.py`](../../../tools/saturn_lab/sample_workram.py) verifies each link
from the later run's recorded command. The restored checkpoint's state hash must
equal the earlier state, and the frame numbers must add up. Only verified pairs
yield deltas. Every sample also had to hold the original kernel bytes for the three
handlers, `0600667E`, the startup reset loop and their literals (six witnesses).

## Result

| Value | f3,000 | f10,200 | f10,800 | Δ over 7,200 frames | Δ over 600 frames |
| --- | --- | --- | --- | --- | --- |
| `0x06006038` frame counter (u32) | 1,752 | 8,952 | 9,552 | **7,200** | **600** |
| `0x06006104`/`08`/`0C` pad ports 1–3 (u32) | 692 | 5,039 | 5,467 | 4,347 | 428 |
| `0x06006100` pad port 0 (u32) | 692 | 5,039 | 226 | 4,347 | reset (input) |
| `0x060B2D20` VBlank-IN word (u16) | 5 | 5 | 5 | 0 | 0 |

Readings:

- **The VBlank-OUT counter advances exactly once per emulated frame** across both
  windows (7,800 frames), consistent with `06006368` running once per frame. The kernel image initializes it to 0 and startup zeroes it.
  At 1 per frame, the value 1,752 at frame 3,000 places its first increment near
  frame 1,249. That is an extrapolation; the window before frame 3,000 is unobserved.
- **The pad-port counters advance on only 60.4% and 71.3% of frames.** Their tick
  domain differs from the VBlank counter's, in the same lineage. This is the #492
  boundary between "tick" and VBlank, measured rather than assumed. The skipped
  frames' cause (loading, task scheduling or SMPC timing) is not established.
- **The VBlank-IN word stayed at 5** throughout. The `06006652` handler is
  therefore not incrementing it in these windows. It may have been replaced
  through one of the four `SYS_SETUINT` calls whose handler is not a constant,
  or masked. That remains open.

Negative controls, each failing as required:

- expecting the frame counter at 2 per frame;
- expecting pad port 1 at 1 per frame;
- pairing the frame-600 cold boot from another run with frame 10,800 (lineage not verified, so no delta is claimed);
- a kernel witness over the runtime-mutated port counters.

A fresh repeat produced a byte-identical report.

## Limits

- Deltas are net changes between samples, not counts of handler invocations or proof of their interrupt source.
- Frames are the pinned Beetle frontend's emulated frames, not hardware VBlank measurements.
- One lineage and one scenario. Other modes, loading paths, pause and slowdown are unmeasured.
- No handler was executed in isolation.
- The Godot timing contract still needs per-frame ordering of pad reads, game tasks and presentation.

Reproduce privately with the recipe in the
[lane ledger](../saturn-code/re-lanes/usa-code.md). It runs three
`--checkpoint` directories, six `--value` declarations, six `--witness` ranges and
`--expect-rate frame_counter=1/1`.
