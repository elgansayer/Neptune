LANE-STATUS: ACTIVE

# Lane ledger: sound-68k (68000 sound drivers and SCSP/DSP)

## Charter

Recover every original 68000 sound-CPU program and the SCSP DSP programs it
loads, plus the SH-2 command protocol that drives them:

- SND: `BOMSS/PROGRAM.BIN[0x44:0x6418]`, the main game driver;
- NLSND: `NETLINK/SNDDRV.BIN`;
- XBSND: `XBAND/XBAND.DAT[0x11868:0x17C3C]`.

Issues: #488 (parent), #665, #703, #707, #489.

Priorities:
1. Measured SND function inventory with a denominator.
2. Command dispatcher, handlers and mailbox protocol.
3. Sequence format/interpreter, then sample-timed playback comparison.
4. NLSND/XBSND: recover only what differs from SND.

**Denominator:** all 68000 functions in the three drivers, plus observed DSP
programs. Ownership: do not edit Codex's Japan kernel chain, Gemini's #464
scope, the Factory, or other lanes' ledgers. Earlier NLSND work (#600–#703
probes, `probe_netlink_*`) stays accepted and is reused, not repeated.

## Measured denominator (2026-11-05, updated run 20261105T0750Z)

| Driver | Identity | Function entries | Executed naturally | Status |
| --- | --- | --- | --- | --- |
| SND | `c8842cc9…bd04`, 25,556 B, embedded "Ver2.04 96/01/25" (Sega Saturn sound driver) | 146 union (141 resident + 5 patched-out disc-only); 3 interior | 58 in accepted 7,200-frame window (60 with single-run pause window) | 20 with complete isolated contracts; 2 partial; 124 open |
| XBSND | same bytes as SND | same 146 static entries | not run (XBAND lifetime) | byte-identical; natural lifetime and patching open |
| NLSND | `f3728939…2296`, 23,920 B, embedded "Ver1.31 95/06/20" | not yet inventoried with this tool | not run | earlier isolated handler probes exist (#600–#703) |
| DSP programs | SCSP `DSP.MPROG` hashes | — | SND lifetime: 1 (`b8c82dd4…`, 84 steps); pre-SND program: 1 (`13700781…`, 100 steps) | microcode not decoded |

Other open counts for SND:
- Unclassified resident bytes: 10,826, including the 3,072-byte work area at
  `0x400–0xFFF`. Of these, `0x53E0–0x54DF` is now identified as a zero-filled
  runtime record table (static `lea` witness at `0x5380`, natural writes).
- Unreferenced code-like candidates (unproven): `0x2E8A`, `0x3D0E`, `0x5356`,
  `0x1A46`.
- Runtime code patches: **resolved**. SND's boot routine `0x1768` writes the
  seven NOP sites itself, gated by host byte `0x4E1` (`0x00` in the image).
  `0x141E` is a self-modifying 4-phase counter. The previous "759 work-area
  bytes" at frame 7200 are 684 bytes in `0x416–0xD9F` plus 75 bytes in the
  record table.
- The pre-SND epoch-0 program (frames 52–1280) is a different resident
  program; its loader and identity are open and it is outside the SND count.

Recovered-semantics count (boundaries, ABI, state, callers and behaviour, with a
negative control): **20 of 146 SND entries**. They are `0x1768` (self-patch),
`0x1A60` (executor) and 18 dispatch-table stubs whose whole body is a return or
ignore path (`0x1B6E`, `0x1BAA`, `0x1BBE`–`0x1BEA`, `0x1AEA`, `0x1B06`,
`0x1B0E`, `0x1B12`). There are also 2 partial entries (`0x1B0A`, `0x1B16`),
which reach a device-write guard. The 28 handler-bearing table entries have
verified dispatch but open bodies. See
[the mailbox note](../../research/2026-11-05-snd-command-mailbox.md).

## Tool pins

- Isolated CPU: ABI1 `libneptune_m68k.so` `cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`
  (prepared with `m68k_probe.py`, gcc 14.2.0-19, about 20 s), at
  `$RE_TOOLS_DIR/m68k-probe-abi1-001`.
- Pinned decoder: saturn-recomp `f20de940` (`/home/dev/neptune-tools/saturn-recomp-f20de94`),
  source hashes in `analyze_sound_driver.TOOL_HASHES`; decoder cache is private.
- Reference core: Beetle `01bc063f`, tree `2522acca`, `.so` `c862380e…`;
  USA lock file `eb0d91e0…`.
- Coverage core ABI1: binary `fa0f92ec051dea0df13ea0de435eb4cf9203363f6ca4892b27a0763fbb24787a`.
  Built twice from `tools/saturn_lab/m68k_coverage_core.py` with
  gcc 14.2.0-19; only `m68k.c` is recompiled (~32 s).
- Tool hashes at evidence time are recorded in
  `docs/restart/evidence/2026-11-05-snd-natural-function-inventory.json`.

## Run log

| Run | Result | Notes |
| --- | --- | --- |
| 20261105T0635Z | PR [#840](https://github.com/elgansayer/Neptune-Bomberman/pull/840) | Added the coverage observer, runner and inventory join, with 14 owned tests. Natural cold-boot windows: reference + 2 enabled, 7,200 frames, identical. SND inventory 146 entries; dispatcher map; 8 runtime patches; DSP identities. The first core preparation failed its own smoke (re-armable `begin()`), was fixed before evidence and retained privately as `failed-prepare-001-rearmable-begin`. |
| 20261105T0750Z | PR [#863](https://github.com/elgansayer/Neptune-Bomberman/pull/863) | Added `probe_snd_mailbox.py` with 18 owned tests and no new emulator run. Self-patch `0x1768`: 512 isolated cases, 4 controls; the resident image is derived exactly from disc + isolated writes (`0x4E1 = 0`). Executor `0x1A60`: 9,216 cases over all 256 command bytes, 7 controls, and a natural replay of 89 records. The natural command stream (89 records) matches coverage dispatch counts and the 49,526 vector-26 interrupts exactly; 5 natural-data controls are rejected. Two fresh reports are byte-identical (`2376d1f7…af0`). The first executor contract draft was wrong (offset masked after the add) and was rejected by execution, then corrected from the listing. |

## Frontier (ranked)

1. **SND control handlers with device effects.** Use the natural records as
   inputs. Start with the SCSP-register handlers. `0x80`/`0x81` write
   slot 16/17 byte `0x17`, which ABI7 already admits. `0x82` writes MVOL
   `0x100401`; that needs a common-register extension, not RAM mapping.
   `0x0C` clears DSP MPROG `0x100800–0x100BFF` (ABI8 DSP words). `0x0D` is
   all-off. Then do `0x08` map change and `0x01`/`0x02` sequence start/stop. Each
   needs a full register/memory/device contract and mutation controls.
2. **Sequencer tick timing (prerequisite for sample-timed audio).** The
   tick routine `0x141C` ran 18,127 times, about 240.5 output samples per tick,
   against a nominal 178 samples for the main loop's Timer-A reload of `0x4E`
   (documented SCSP timer layout, a source hypothesis). The
   vector-26 handler `0x1734` writes `0xC0` to SCIRE `0x100422`, clearing both
   Timer-A and Timer-B pending bits; this may drop Timer-A polls. Measure
   per-tick natural timing and decide the tempo base before any PCM comparison.
3. **SH-2 producer of the command slots (#707, SH-2 side).** Find the SH-2
   writer of `0x25A00700` slots (USA kernel/PROGRAM static search, or a bounded
   SH-2 write observer). Tie each of the 89 natural records to its game
   event. The ring already gives the 68000-side timing.
4. **Broaden natural command traces.** Battle mode, items, music changes and
   game over. The history ring holds up to 127 records per snapshot interval,
   so take snapshots often enough; the probe then gives a checked command trace
   with no new observer.
5. **NLSND inventory and DSP decode.** Run `m68k_function_inventory.py` on
   NLSND (Ver1.31) and align it with SND by signature. Decode the 84-step
   SND-lifetime MPROG and its loader (`0x83` effect change → `0x3140` is a
   candidate path).

## Private evidence (never commit)

`$RE_EVIDENCE_DIR` = `/var/lib/repo-factory/saturn-re-lanes/evidence/sound-68k`:
- `sources/`: the three containers, `SND.driver` and `extraction.json`, all
  hash-checked;
- `static/SND.static.lst`: linear listing of the static descent;
- `mailbox/final-{1,2}.json`: the two identical mailbox reports;
  `try-001.json` (rejected executor draft: offset masked after the add) and
  `try-002.json` (resident derivation rejected before the record table was
  declared) are retained failures; `try-003.json` passed before the timing
  field was added; `check.log` is the full tooling-test output;
- `runs/final-{reference-1,enabled-1,enabled-2}`, `runs/final-comparison.json`
  and the exploratory `runs/explore-*` windows;
- `inventory/final-v2-enabled-{1,2}.json`;
- `inputs/route-gameplay-v1.json`;
- `scripts/`.

Tools live in `$RE_TOOLS_DIR/beetle-m68kcov-abi1-00{1,2}` (coverage cores) and
`$RE_TOOLS_DIR/m68k-probe-abi1-001` (isolated Musashi ABI1).

Host notes: `cp`/`rm` are interactive aliases, so use `command cp -f` and
`command rm -f`. `/` had about 6.6 GiB free and all heavy work used the large
volume. Emulation runs at about 70–100 fps here, so a 7,200-frame window takes
100–130 s.
