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

## Measured denominator (2026-11-05)

| Driver | Identity | Function entries | Executed naturally | Status |
| --- | --- | --- | --- | --- |
| SND | `c8842cc9…bd04`, 25,556 B, embedded "Ver2.04 96/01/25" (Sega Saturn sound driver) | 146 union (141 resident + 5 patched-out disc-only); 3 interior | 58 in accepted 7,200-frame window (60 with single-run pause window) | inventory measured; semantics open for all 146 |
| XBSND | same bytes as SND | same 146 static entries | not run (XBAND lifetime) | byte-identical; natural lifetime and patching open |
| NLSND | `f3728939…2296`, 23,920 B, embedded "Ver1.31 95/06/20" | not yet inventoried with this tool | not run | earlier isolated handler probes exist (#600–#703) |
| DSP programs | SCSP `DSP.MPROG` hashes | — | SND lifetime: 1 (`b8c82dd4…`, 84 steps); pre-SND program: 1 (`13700781…`, 100 steps) | microcode not decoded |

Other open counts for SND:
- Unclassified resident bytes: 10,826, including the 3,072-byte work area at
  `0x400–0xFFF`.
- Unreferenced code-like candidates (unproven): `0x2E8A`, `0x3D0E`, `0x5356`,
  `0x1A46`.
- Runtime code patches: 8 sites. Their SH-2 writer is unknown.
- The pre-SND epoch-0 program (frames 52–1280) is a different resident
  program; its loader and identity are open and it is outside the SND count.

Recovered-semantics count (boundaries, ABI, state, callers and behaviour, with a
negative control): **0 of 146 SND entries**. The inventory gives entries and
boundaries, not semantics.

## Tool pins

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

## Frontier (ranked)

1. **SND command handlers (#665-style, priority 2).** Execute executor
   `0x1A60` and the twelve naturally used handler families in isolation:
   `0x01`, `0x02`, `0x08`, `0x0C`, `0x0D`, `0x80`–`0x83`, `0x85`–`0x87`
   (handler entries in the research note). Reuse the Musashi ABIs and SCSP
   register models (`m68k_scsp_*`). Record full register/memory/device
   contracts with mutation controls. Start with `0x1A60` + `0x1B6E` (no-op)
   + `0x01`.
2. **Natural mailbox traffic (#707, 68000 side).** Extend the observer, or add a
   separate ABI2, to log the 16-byte slot contents at `0x700` when `0x1A60`
   is entered: the frame plus the 14 copied bytes, from the instruction's own
   reads. This gives the real command/argument stream for the accepted route.
   Correlate it with the history ring at `0x800`/`0x41A`.
3. **Who patches SND?** Find the SH-2 writer of the eight resident patches.
   Statically search the USA kernel/PROGRAM.BIN code for stores to
   `0x25A010E4`-class addresses or NOP words, or use a bounded SH-2
   write observer. Check whether XBSND/NetLink lifetimes are patched alike.
   This decides whether the disc or resident image is canonical per lifetime.
4. **Broaden natural coverage.** Battle mode, item pickups and kicks, music
   changes, game over/continue and options. Run each as its own repeated
   window, targeting the 83 static-only resident entries and the
   unreferenced candidates.
5. **NLSND inventory and DSP decode.** Run `m68k_function_inventory.py`
   statically on NLSND (Ver1.31) and align it with SND (Ver2.04) by function
   signature, not byte offset. Separately decode the 84-step SND-lifetime
   MPROG and identify its loader path.

## Private evidence (never commit)

`$RE_EVIDENCE_DIR` = `/var/lib/repo-factory/saturn-re-lanes/evidence/sound-68k`:
- `sources/`: the three containers, `SND.driver` and `extraction.json`, all
  hash-checked;
- `static/SND.static.lst`: linear listing of the static descent;
- `runs/final-{reference-1,enabled-1,enabled-2}`, `runs/final-comparison.json`
  and the exploratory `runs/explore-*` windows;
- `inventory/final-v2-enabled-{1,2}.json`;
- `inputs/route-gameplay-v1.json`;
- `scripts/`.

Tools live in `$RE_TOOLS_DIR/beetle-m68kcov-abi1-00{1,2}`.

Host notes: `cp`/`rm` are interactive aliases, so use `command cp -f` and
`command rm -f`. `/` had about 6.6 GiB free and all heavy work used the large
volume. Emulation runs at about 70–100 fps here, so a 7,200-frame window takes
100–130 s.
