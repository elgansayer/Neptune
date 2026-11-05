# SND natural 68000 function inventory (sound-68k lane)

Lane `sound-68k`, run `20261105T0635Z`, toward
[#488](https://github.com/elgansayer/Neptune-Bomberman/issues/488) (parent),
with dispatcher findings relevant to
[#665](https://github.com/elgansayer/Neptune-Bomberman/issues/665) and the
68000 side of the mailbox in
[#707](https://github.com/elgansayer/Neptune-Bomberman/issues/707).
The earlier [static sound-code discovery](2026-11-02-original-sound-code.md)
measured only a static partition of SND. This slice adds the first **natural
emulator observation** of SND executing, joins it with the pinned static
descent, and produces a measured function inventory with an explicit
denominator. No function's semantics, arguments or names are claimed here.

Machine-readable derived evidence (addresses, counts and hashes only):
[`2026-11-05-snd-natural-function-inventory.json`](../evidence/2026-11-05-snd-natural-function-inventory.json).
Raw coverage tables, states, captures, disassembly and extracted bytes stay in
the lane's private evidence directory.

## Identity

| Item | Value |
| --- | --- |
| Source | USA MK-81070 V1.003 `BOMSS/PROGRAM.BIN`, 12,976,962 bytes, SHA-256 `f5154d4a…596d5`; private re-extraction of all three containers read 6,626 EDC-verified sectors, 0 mismatches |
| Driver slice | `[0x44, 0x6418)`, 25,556 bytes, SHA-256 `c8842cc9…bd04`; loaded at sound-CPU address 0 |
| XBSND | `XBAND/XBAND.DAT[0x11868:0x17C3C)` is byte-identical (same hash); separate container and lifetime, **not** executed here |
| Embedded text (static) | version string at `0x1020` identifies Sega's Saturn sound driver **Ver2.04, dated 96/01/25** — SDK library code, kept in the accounting |
| NLSND (static) | `NETLINK/SNDDRV.BIN` carries **Ver1.31, dated 95/06/20**: an older build of the same driver family, not a byte variant of SND |

The version identification is a static observation of embedded text. Any
mapping from Sega's published driver interface to these command codes remains a
source hypothesis until each handler is executed and checked.

## Tooling added

- `m68k_coverage.h` + `m68k_coverage_core.py`: a separate copy of the accepted
  reference Beetle checkout (`01bc063f`, tree `2522acca`, reference core
  `c862380e…`) with four exact-anchor insertions in `m68k.c` (include, reset,
  exception, post-`ReadOp` step) and an export-list change. Only `m68k.c` is
  recompiled. Two clean preparations produced the same binary,
  SHA-256 `fa0f92ec051dea0df13ea0de435eb4cf9203363f6ca4892b27a0763fbb24787a`.
  The observer records, per 68000 reset epoch, executed instruction starts with
  hit counts, first frame and the **fetched** opcode word, plus every distinct
  control-flow edge (flow / exception with vector / epoch start). It never calls
  a bus accessor or changes CPU, device or timing state. Capacity exhaustion is
  recorded and rejected. The reference checkout is never modified.
- `run_m68k_coverage.py`: cold-boot runs through the accepted USA lock
  (`eb0d91e0…`) via the pinned frontend loader, in `reference` or `enabled`
  mode, with SND residency and SCSP DSP identity at snapshots; `compare`
  requires identical per-frame video/audio/input observations and final state
  between the reference and every enabled run, and identical coverage between
  enabled runs.
- `m68k_function_inventory.py`: joins the pinned saturn-recomp `f20de94`
  Musashi descent with an opcode-level flow model and one natural epoch;
  derives entries (reset/exception vectors, direct and table calls, natural
  indirect targets) and intra-procedural bodies; classifies resident-vs-disc
  differences; and runs four altered-copy controls that must be rejected.

The first preparation attempt built successfully but failed its own ABI smoke:
`begin()` could be re-armed after `stop()`. The observer was made strictly
one-shot per process before any evidence run. 14 new owned-fixture tests cover
anchor drift/ambiguity, a compiled harness of the real observer header
(epochs, edge kinds, opcode changes, overflow, one-shot), the static/natural
join with rejection cases, and the comparison gate.

## Natural experiment

Cold boot, 7,200 frames, inputs: port-0 Start pulses every 300 frames from
1900 to 4000 (title → 1 PLAYER GAME → intro → loading → Normal Game stage 1-1),
then Saturn A bomb drops, walks and single Saturn B/C presses. The route reaches
gameplay, a bomb death and the stage restart (screens checked privately).
Actions digest `34314526…0554a`.

| Run | Core | Final state | Frame observations | Coverage |
| --- | --- | --- | --- | --- |
| reference-1 | reference `c862380e…` | `b4b25540…a635` | `f4b86ac9…0cf3` | — |
| enabled-1 | coverage `fa0f92ec…` | `b4b25540…a635` | `f4b86ac9…0cf3` | `012dd380…d3d3` |
| enabled-2 | coverage `fa0f92ec…` | `b4b25540…a635` | `f4b86ac9…0cf3` | `012dd380…d3d3` |

All 7,200 frames' video/audio/input observations (5,307,357 audio frames) and
the final state are identical across the three runs, so the observer did not
perturb this window. Coverage and both inventory reports (apart from run
identity) repeat exactly.

Two 68000 lifetimes were observed:

| Epoch | Frames | Reset PC / SSP | Instructions | Distinct starts | Edges | Vector-26 interrupts |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 52–1280 | `0x1000` / `0xA000` | 16,367,021 | 634 | 879 | 10,271 |
| 1 (SND) | 1284–7199 | `0x1000` / `0xA000` | 75,260,476 | 2,061 | 2,576 | 49,526 |

Epoch 0 is a different resident program (20,431 of the SND window's 25,556
bytes differ at frame 1200); it runs during the BIOS/licence screens and is not
counted in the SND denominator. Its loader and identity remain open. Epoch 1
executes SND: every executed opcode word matches the resident image, with no
opcode change and no execution outside sound RAM.

## Runtime patches observed in resident SND

At every SND-lifetime snapshot (frames 1800, 4300, 7200) the resident driver
differs from the disc bytes at eight instruction sites (29 bytes). Coverage shows
that every execution of the seven opcode sites fetched the replacement words:
from the first SND frame (1285) for the main-loop sites, from frame 1483 for
`0x1AAE` and from frame 2190 for `0x2BE6`. No opcode changed during the epoch.
The `0x141E` change is in an extension word, so it is seen only in the resident
image. These are natural emulator observations; the SH-2 code that writes them
is not yet identified.

| Instruction | Change in resident image |
| --- | --- |
| `0x10E4`, `0x10E8` | host-flag test of `0x4E0` bit 7 and its `bpl` replaced by four NOPs: the 8-slot command scan runs every main-loop pass |
| `0x1168`, `0x116C`, `0x1170` | three `bsr` calls replaced by NOPs, disconnecting `0x11AA`, `0x1202`, `0x11D2` (MIDI-out ring writers) |
| `0x141C` | immediate operand changed from `0x0300` to `0x0100` |
| `0x1AAE` | `bsr 0x1B20` in the command executor replaced by NOPs |
| `0x2BE6` | `bsr 0x2C3C` replaced by NOPs |

759 further bytes change in work areas (`0x416`–`0x9xx`, including the command
slots at `0x700` and the history ring at `0x800`); they are runtime data, not
code. A natural-only check rejects analysing the unpatched disc image against
this epoch.

## Measured inventory and denominator

| Measure | Resident image | Disc image |
| --- | --- | --- |
| Function entries (call/vector targets) | 141 (3 interior) | 146 (3 interior) |
| Static instructions / code bytes | 3,967 / 13,098 | 4,051 / 13,428 |
| Entries executed in the accepted window | 58 | — |
| Instruction starts executed | 2,061 | — |

The union denominator is **146 entries**. The resident image adds none; the
five disc-only entries (`0x11AA`, `0x11D2`, `0x1202`, `0x1B20`, `0x2C3C`) are
original routines whose only call sites are patched out. They stay in the
denominator. Static-only entries are 83 resident plus those five. Not executing
in one route does not make an entry dead. A single-run exploratory window that
paused and unpaused the game additionally reached the command-table thunks
`0x1B7A`/`0x1B7E` (60 executed entries in the union). The accepted repeated
window remains 58.

Natural consistency (accepted window): every executed word is a static
instruction start of the resident image, and all 2,576 observed edges are
explained by the static model of the instruction they leave: 1,824
fall-through, 165 taken branches, 80 calls, 67 jumps (including table
dispatch), 263 returns to call sites (including stacked interrupt PCs), 176
exception-vector entries and 1 reset entry. No observed transfer needed an
unresolved indirect target. Instructions owned by more than one entry: 298.

Remaining unknowns are explicit: 10,826 unclassified bytes in the resident
image. They include the 3,072-byte work area `0x400–0xFFF`, the 106-byte
version text at `0x1020`, large table-like regions (`0x25A2` 1,588 B, `0x3D8C`
1,734 B, `0x5BEA` 1,130 B and others), and four **unreferenced code-like
candidates** that decode cleanly to a return: `0x2E8A` (59 instructions),
`0x3D0E` (13), `0x5356` (14) and `0x1A46` (2). These candidates are unproven
and are not counted as functions.

## Command dispatcher map (68000 side of the mailbox)

Static descent plus natural edges establish the dispatch skeleton:

- The main loop at `0x10C6`, with its flag gate patched out, walks eight
  16-byte command slots at `0x700`. For each non-zero command byte it calls the
  executor `0x1A60`. If the slot's first longword is unchanged afterwards, it
  clears the slot's first word. Otherwise it sets bit 3 of `0x416`.
- `0x1A60` copies the slot's first 14 bytes plus a 2-byte stamp into a
  128-entry, 16-byte history ring at `0x800`. It publishes the next ring offset
  at `0x41A`, writes an all-ones end marker, then dispatches on the command
  byte. `0x00–0x1F` go through `jsr` table `0x1B60`
  (entry 0 is a bare `rts`; `0x20–0x7F` are ignored). `0x80–0x90` go through
  `jsr` table `0x1AD2` (index = low nibble; `≥0x91` ignored).
- The `0x1AD2` table has 12 well-formed four-byte entries. Entry 11 is a
  six-byte absolute `jmp`, so commands `0x8C–0x8F` would dispatch into the
  middle of instruction bytes. This explains the decoder's historical
  `0x1B0A`/`0x1B12` overlap conflicts. Command `0x90` passes the bound and
  aliases index 0 (`0x80`). None of these were observed; this is static.

Natural dispatch counts in the accepted window (flow edges from the table
instructions, so interrupts taken at the dispatch site are excluded):

| Command | Thunk → handler | Count | | Command | Thunk → handler | Count |
| --- | --- | --- | --- | --- | --- | --- |
| `0x01` | `0x1B72` → `0x2364` | 23 | | `0x80` | `0x1ADA` → `0x1D10` | 10 |
| `0x02` | `0x1B76` → `0x2396` | 1 | | `0x81` | `0x1ADE` → `0x1D54` | 10 |
| `0x08` | `0x1B8E` → `0x18FE` | 6 | | `0x82` | `0x1AE2` → `0x1D98` | 16 |
| `0x0C` | `0x1B9E` → `0x1C3A` | 3 | | `0x83` | `0x1AE6` → `0x1DA4` | 3 |
| `0x0D` | `0x1BA2` → `0x1C4C` | 3 | | `0x85` | `0x1AEE` → `0x1DAE` | 4 |
| | | | | `0x86` | `0x1AF2` → `0x2056` | 4 |
| | | | | `0x87` | `0x1AF6` → `0x17FC` | 6 |

The other resolved tables (`0x2C28`, `0x2CC8`, `0x3258`, `0x368A`, `0x484C`,
`0x5518`, `0x56F0`) also have observed targets, listed in the evidence JSON.
Handler semantics, argument layouts and the SH-2 writer remain unrecovered.

## SCSP DSP programs observed

`DSP.MPROG` identity at snapshots: frame 1200 (epoch 0) `13700781…e77b`, 100
non-zero steps. Frames 1800, 4300 and 7200 (SND lifetime: intro, gameplay
start, after the death/restart) `b8c82dd4…bc61`, 84 non-zero steps (last step
83), with the same COEF/MADRS hashes. One DSP program is therefore observed in
the SND lifetime of this window. Its source, loader path and microcode
semantics are not decoded.

## Controls and limits

All four altered-copy controls are rejected by the same natural checks:
- one executed opcode changed in the resident image;
- the runtime patches ignored (disc image analysed);
- a fabricated edge from a non-branching instruction;
- a fabricated executed word inside an unclassified gap.

The observer harness tests separately prove the native tables. Evidence is from
one emulator lineage (Beetle/Mednafen), one bounded route and one release. It
does not establish hardware timing, handler semantics, PCM output or Godot
parity. NLSND and XBSND natural lifetimes were not run.

## Reproduce (private inputs, fresh outputs)

```sh
python3 tools/saturn_lab/m68k_coverage_core.py --reference /PRIVATE/beetle-saturn-source \
  --output /PRIVATE/tools/beetle-m68kcov-NEW
python3 tools/saturn_lab/run_m68k_coverage.py run --reference-root /PRIVATE/usa-media \
  --lock /PRIVATE/usa-media/locks/LOCK.json --expected-lock eb0d91e0bebd63af78181ce4d4d6af354554466b1f726bfe700e78eff6275cba \
  --mode enabled --prepared /PRIVATE/tools/beetle-m68kcov-NEW --frames 7200 --actions /PRIVATE/route.json \
  --snapshot 1200 --snapshot 1800 --snapshot 4300 --snapshot 7200 --driver /PRIVATE/SND.driver --output /PRIVATE/runs/NEW
python3 tools/saturn_lab/run_m68k_coverage.py compare --reference /PRIVATE/runs/REF \
  --enabled /PRIVATE/runs/NEW --enabled /PRIVATE/runs/NEW2 --report /PRIVATE/runs/NEW-comparison.json
python3 tools/saturn_lab/m68k_function_inventory.py --source-file /PRIVATE/SND.container --module SND \
  --saturn-recomp /PRIVATE/saturn-recomp-f20de94 --cache /PRIVATE/decoder-cache \
  --coverage-run /PRIVATE/runs/NEW --resident-state /PRIVATE/runs/NEW/final.state --report /PRIVATE/NEW-inventory.json
```

The reference and enabled runs must use identical actions, captures and
snapshot frames. The comparison fails at the first differing frame or state.
