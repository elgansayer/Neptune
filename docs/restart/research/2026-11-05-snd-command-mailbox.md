# SND host-command mailbox: natural command stream, executor and boot self-patch

Lane `sound-68k`, run `20261105T0750Z`, toward
[#488](https://github.com/elgansayer/Neptune-Bomberman/issues/488) (parent),
[#665](https://github.com/elgansayer/Neptune-Bomberman/issues/665) (dispatcher and
control handlers, here for SND rather than NLSND) and the 68000 side of
[#707](https://github.com/elgansayer/Neptune-Bomberman/issues/707) (natural
command traffic). This builds on the
[natural SND inventory](2026-11-05-snd-natural-function-inventory.md) and
reuses its private natural runs. No new emulator run or native generation was
needed. The isolated CPU work uses the unchanged ABI1 Musashi adapter
(`m68k_probe.py`).

Derived evidence (counts, contracts, hashes and the decoded command records):
[`2026-11-05-snd-command-mailbox.json`](../evidence/2026-11-05-snd-command-mailbox.json).
Original bytes, states, raw rings and listings stay private.

## Results at a glance

| Claim | Evidence class |
| --- | --- |
| SND patches its own code at boot. Routine `0x1768` writes `NOP NOP` over seven call/test sites, each gated by a bit of host byte `0x4E1`. The disc image's own `0x4E1` is `0x00`, which patches all seven. | static + isolated original-byte execution (512 cases, 4 controls) + natural observation |
| The eighth "patch" (`0x141E`) is a self-modifying 4-phase counter, and its phase at frame 7200 is predicted by the natural store count. | static + natural observation |
| 75 runtime bytes at `0x53E1`–`0x54D7` belong to a zero-filled 256-byte record table inside the image, not to the low work area. | static + natural observation |
| Executor `0x1A60` contract for all 256 command bytes, including the masked ring offset, the stamp handoff and every dispatch class. | isolated original-byte execution (9,216 cases, 7 controls) + natural replay |
| Natural command stream for the accepted route: 89 records with inter-command timing, read from SND's own history ring. | natural observation, checked against the independent coverage observer |
| Sega driver command names (`0x01` sequence start, `0x82` master volume, …) | source hypothesis only, with static first-instruction readings |

These results correct two statements in the earlier note and ledger. "Runtime
code patches: 8 sites. Their SH-2 writer is unknown" becomes: no SH-2 code
write is needed. SND's own boot code produces all seven NOP sites from the
image's default configuration byte, and the eighth is its counter. "759 further
bytes change in work areas (`0x416`–`0x9xx`)" becomes: at frame 7200 those are
684 bytes in `0x416`–`0xD9F` plus 75 bytes in the record table at `0x53E0`.

## Identity

| Item | Value |
| --- | --- |
| Module | SND, USA MK-81070 V1.003 `BOMSS/PROGRAM.BIN[0x44:0x6418]`, loaded at sound-CPU address 0 |
| Driver bytes | 25,556 B, SHA-256 `c8842cc9…bd04` (container `f5154d4a…96d5`) |
| Lifetime | the second 68000 reset epoch of the accepted route (frames 1284–7199) |
| Natural runs | `final-enabled-1` and `-2` from the previous run: coverage `012dd380…d3d3`, final state `b4b25540…a635`, snapshots at 1800/4300/7200 |
| Native | ABI1 `libneptune_m68k.so` `cc059d3a…c83c` (Musashi from saturn-recomp `f20de940`, source lock `641b45f1…`, backend `1ae72479…`); owned smoke passed |
| Probe | `probe_snd_mailbox.py` `67642fe7…3939`; two fresh reports are byte-identical, `2376d1f7…af0` |

## Boot self-patch: `0x1768`

The reset code calls `0x1768` once, through `bsr` at `0x10BA`, before it
enables interrupts. Its contract, stated independently and then checked
against original execution for all 256 values × 2 register/CCR variants:

```text
self_patch():                      ; entry SP -> return address 0x10BE
  D1 = 0x4E714E71                  ; two NOP opcodes
  v  = byte[0x4E1]                 ; host configuration byte
  if !(v & 0x80): long[0x10E4] = D1; long[0x10E8] = D1   ; main-loop 0x4E0 gate removed
  if !(v & 0x40): long[0x2BE6] = D1                      ; bsr 0x2C3C removed
  if !(v & 0x20): long[0x1AAE] = D1                      ; executor's bsr 0x1B20 removed (static: builds a 0x47…0xF7 message from slot nibbles)
  if !(v & 0x10): long[0x116C] = D1                      ; bsr 0x1202 removed
  if !(v & 0x08): long[0x1168] = D1                      ; bsr 0x11AA removed
  if !(v & 0x02): long[0x1170] = D1                      ; bsr 0x11D2 removed
  D0.b = byte[0x4E1] & 0x7F        ; D0 upper 24 bits preserved
  ; A0 = last patched address (0x10EC after the pair) or unchanged
  ; CCR: N=V=C=0, Z=(v&0x7F)==0, X=bit 2 of v (from the shift chain); bits 0 and 2 select nothing
```

The reads are `0x4E1` twice and the return address once. The writes are only
the selected longwords, in the order above. No other memory is touched.
Controls: changing the NOP constant (31/31 rejected), shifting the `0x2BE6`
site (15/31, by the forbidden-write guard), replacing one shift with `NOP`
(23/31) and inverting the first branch (31/31).

Natural observations tie the isolated contract to the real lifetime:

- the disc image and every SND snapshot hold `0x4E1 = 0x00`;
- coverage shows `0x1768` executed exactly once (frame 1285). Every edge of
  the isolated 30-instruction path for `v = 0`, including the call from `0x10BA` and
  the return to `0x10BE`, occurs once;
- disc bytes plus the isolated writes for `v = 0` equal the natural resident
  image at frames 1800, 4300 and 7200 over the vector table and
  `0x1000`–`0x63D3`. Only the counter word and the record table below differ.
  Every executed opcode word in the epoch also matches the derived image.

So the resident image is SND's own derivation from its default configuration.
Whether the SH-2 also writes `0x4E1` (with the same value) is not observed;
no SH-2 write is required. The companion boot routine `0x17BA` checks a
`CR LF CR LF` sequence at `0x17F8` and sets bit 4 of `0x421` on mismatch,
which looks like an image-transfer integrity flag. In this run that branch
was not executed. It also writes `((byte[0x4E2] − 1) & 7) << 5` into data
byte `0x2981`; with `0x4E2 = 0` that is `0xE0`, the disc value. This routine
has static and coverage evidence only.

The self-modifying counter at `0x141C`/`0x1428` is
`imm16[0x141E] := (imm16[0x141E] + 0x100) & 0x300` on each sequencer tick.
The disc value is `0x0300`. Natural coverage executes the store 18,127 times, and
`(3 + 18127) mod 4 = 2` predicts the observed `0x0200` at frame 7200. The other
snapshots hold `0x0100` and `0x0300`.

The record table `[0x53E0, 0x54E0)` is a 256-byte zero run in the disc image.
`lea ($5E,PC,D1.w),A1` at `0x5380` addresses it, and its users read a pointer at `+0`,
a loop pointer at `+8` and a counter at `+0x18`. It holds 0/24/75 non-zero
bytes at frames 1800/4300/7200 and is never executed. The 8 × 32-byte layout
and the "per-track" meaning are hypotheses until the sequencer is recovered.

## Command executor: `0x1A60`

Natural entry state (main loop `0x10C6`, `bsr` at `0x10FE`): `A0` = slot address
`0x700 + 16k`, `D0.b` = command byte, `A6 = 0x7000`, `A5 = 0x100000`, `A2 = 0x9000`.
The stack holds return address `0x1102`, then the saved `D7`/`A0` and the slot's first
longword.

```text
execute(slot):
  A0 = slot + 2; push D0
  off = word[0x883A] & 0x7F0                       ; read offset is masked first
  rec = 0x800 + off
  rec[0..13] = slot[0..13]                         ; word, long, long, long
  word[0x883A] = word[0x41A] = off + 16            ; 0x010..0x800, never carries
  rec[14..15] = word[0x8838]; word[0x8838] = 0     ; ticks since previous command
  fill 0x800 + ((off + 16) & 0x7F0) with 16 x 0xFF ; end marker, wraps to 0x800
  ; resident image: NOP NOP here (disc: bsr 0x1B20, slot-nibble message builder)
  pop D0; c = D0 & 0xFF
  if c < 0x80:
      if c >= 0x20: CCR from D0.w; return             ; ignored
      A4 = A6; push A5, A6; jsr table 0x1B6E + 4c     ; returns via 0x1B64 (pop A5/A6)
  else:
      if c >= 0x91: CCR from D0.w; return             ; ignored
      jsr table 0x1ADA + 4(c & 0xF); then CCR from D0.w; return
```

| Commands | Isolated outcome |
| --- | --- |
| `00` | `rts` stub, completes with `Z = 1` |
| `01`–`0E`, `10`–`13` | stop at handler entry (`01→2364`, `02→2396`, `03→23FE`, `04→242E`, `05→2466`, `06→1BEE`, `07→1BF6`, `08→18FE`, `09→1C04`, `0A→1C2A`, `0B→1C32`, `0C→1C3A`, `0D→1C4C`, `0E→1C88`, `10→20DC`, `11→20CA`, `12→20C0`, `13→20D6`); `A4 = A6`, `A5`/`A6` and return `0x1B64` stacked |
| `0F`, `14`–`1F` | ignore stub (`jmp 0x1B6A`) and return |
| `20`–`7F`, `91`–`FF` | ignored without dispatch |
| `80`–`83`, `85`–`8A`, `90` | stop at handler entry (`80/90→1D10`, `81→1D54`, `82→1D98`, `83→1DA4`, `85→1DAE`, `86→2056`, `87→17FC`, `88→20A2`, `89→2162`, `8A→1FA0`); return `0x1AD6` stacked; `90` aliases `80` |
| `84` | `jmp 0x1DAC` (`rts`) and return |
| `8B`, `8E` | `jmp 0x1B6A.l` and return |
| `8D` | executes a misaligned `ori.b #$6A,D0`, then returns |
| `8C`, `8F` | execute misaligned table bytes as `move.b ($4EF9/$4EFA,A2),($0/$50,A5)`: one byte is read through `A2`, then a byte write goes to SCSP slot registers `0x100000` / `0x100050`. The isolated run stops at that device write (status forbidden-write) |

The 9,216 cases (256 commands × 6 ring offsets × 3 slots × 2 register
variants) compare the complete PC path, every ordered access, all 18
registers including CCR and stack pointer, and every mapped region. Results
digest: `0b4d7676…4b33`. Controls on original copies: ring mask `0x7F0→0x3F0`
(1,229/1,844 rejected), end marker `0xFF→0x00` (1,844/1,844), stamp left at 1
(1,844/1,844), host offset `0x41A→0x41C` (1,844/1,844), high bound
`0x91→0x92` (8/1,844: exactly the `0x91` cases), low bound `0x20→0x21`
(7/1,844: the `0x20` cases) and low table displacement shift (231/1,844).

The first contract draft assumed the offset was masked after the add. The
original code masks it before the add, so the stored value never exceeds
`0x800`. The comparison rejected that draft. The contract was corrected from the
listing, not from the execution output.

Natural replay: each of the 89 natural records was fed through original
`0x1A60` with its natural offset (`16 × index`) and stamp. Each reached the
handler that the natural dispatch edges name, and the rebuilt ring equals the
natural ring at frame 7200.

## Natural command stream (accepted route)

`0x1A60` keeps a history of every command it executes. Each 16-byte record is
the slot's first 14 bytes plus the number of vector-26 interrupts since the
previous command. The host-visible offset is at `0x41A`. Decoding the ring from
the three SND snapshots gives 19, 67 and 89 records. Each earlier ring is a
strict prefix of the later one, the end marker sits at the published offset,
and the untouched tail is zero, so the history is complete and unwrapped.

Independent cross-checks against the coverage observer (natural, both runs):

| Check | Ring | Coverage |
| --- | --- | --- |
| executor entries | 89 records | `0x10FE→0x1A60` × 89; `0x1A60` hits 89 |
| per-command dispatch | `01`×23, `02`×1, `08`×6, `0C`×3, `0D`×3, `80`×10, `81`×10, `82`×16, `83`×3, `85`×4, `86`×4, `87`×6 | identical counts on the table edges from `0x1B60`/`0x1AD2` |
| low/high path | 36 / 53 | `0x1B4E` hits 36, `0x1AC2` hits 53 |
| timing | stamps 34,851 + live counter 14,675 = 49,526 | vector-26 interrupts 49,526 = hits of the increment at `0x175A` |

Five data controls are each rejected by the intended check: a dropped record,
one stamp off by one, two swapped records in the middle snapshot, a wrong
configuration byte (`0x80`) and one extra counter store.

**Tick length.** The vector-26 handler `0x1734` reloads SCSP `0x10041A` with
`0x01D4` and increments `0x8838`. Under the documented SCSP timer layout this
would be Timer B, prescale 2, 44 counts, i.e. 88 samples; that reading is a
source hypothesis. Measured naturally, the emulator output averages
88.038–88.053 samples per interrupt (4,360,162–4,360,899 samples over 49,526
interrupts). So one stamp tick is about 2.0 ms at 44.1 kHz. As a consistency
check, records 37, 38 and 39 each follow the previous record by 2,513 ticks, about 300.1 frames
at the measured 737.13 samples per frame. That matches the route's 300-frame
Start period. This is emulator output-rate timing, not hardware timing.

Byte 1 is always `0x00` and bytes 9–13 are always zero in this window. Bytes
past a command's parameters keep stale values from the previous command in
the same slot: the SH-2 side writes only the bytes it needs. Records:

| # | Cmd | Bytes 2–8 | Stamp (ticks) | Cumulative | Snapshot window |
| ---: | --- | --- | ---: | ---: | --- |
| 0 | `82` | `00 00 00 00 00 00 00` | 1657 | 1657 | < 1800 |
| 1 | `0D` | `00 00 00 00 00 00 00` | 0 | 1657 | < 1800 |
| 2 | `0C` | `00 00 00 00 00 00 00` | 1 | 1658 | < 1800 |
| 3 | `08` | `00 00 00 00 00 00 00` | 0 | 1658 | < 1800 |
| 4 | `08` | `00 00 00 00 00 00 00` | 3 | 1661 | < 1800 |
| 5 | `87` | `05 00 00 00 00 00 00` | 160 | 1821 | < 1800 |
| 6 | `83` | `00 00 00 00 00 00 00` | 0 | 1821 | < 1800 |
| 7 | `87` | `00 00 00 00 00 00 00` | 0 | 1821 | < 1800 |
| 8 | `82` | `0d 00 00 00 00 00 00` | 0 | 1821 | < 1800 |
| 9 | `80` | `e0 e0 00 00 00 00 00` | 21 | 1842 | < 1800 |
| 10 | `81` | `1f 0f 00 00 00 00 00` | 0 | 1842 | < 1800 |
| 11 | `82` | `0d 00 00 00 00 00 00` | 0 | 1842 | < 1800 |
| 12 | `80` | `e0 e0 00 00 00 00 00` | 176 | 2018 | < 1800 |
| 13 | `81` | `1f 0f 00 00 00 00 00` | 0 | 2018 | < 1800 |
| 14 | `82` | `0d 00 00 00 00 00 00` | 0 | 2018 | < 1800 |
| 15 | `80` | `e0 e0 00 00 00 00 00` | 142 | 2160 | < 1800 |
| 16 | `81` | `1f 0f 00 00 00 00 00` | 0 | 2160 | < 1800 |
| 17 | `82` | `0d 00 00 00 00 00 00` | 0 | 2160 | < 1800 |
| 18 | `85` | `90 e0 20 00 00 00 78` | 325 | 2485 | < 1800 |
| 19 | `86` | `00 e0 20 00 00 00 78` | 2667 | 5152 | 1800–4300 |
| 20 | `82` | `00 e0 20 00 00 00 78` | 6 | 5158 | 1800–4300 |
| 21 | `0D` | `1f 0f 00 00 00 00 00` | 0 | 5158 | 1800–4300 |
| 22 | `0C` | `0d 00 00 00 00 00 00` | 1 | 5159 | 1800–4300 |
| 23 | `08` | `00 00 00 00 00 00 00` | 0 | 5159 | 1800–4300 |
| 24 | `08` | `00 e0 20 00 00 00 78` | 3 | 5162 | 1800–4300 |
| 25 | `87` | `05 00 20 00 00 00 78` | 160 | 5322 | 1800–4300 |
| 26 | `83` | `00 0f 00 00 00 00 00` | 0 | 5322 | 1800–4300 |
| 27 | `87` | `00 00 00 00 00 00 00` | 1 | 5323 | 1800–4300 |
| 28 | `82` | `0d 00 00 00 00 00 00` | 0 | 5323 | 1800–4300 |
| 29 | `80` | `e0 e0 20 00 00 00 78` | 40 | 5363 | 1800–4300 |
| 30 | `81` | `1f 0f 00 00 00 00 00` | 0 | 5363 | 1800–4300 |
| 31 | `82` | `0d 00 00 00 00 00 00` | 0 | 5363 | 1800–4300 |
| 32 | `82` | `0d e0 20 00 00 00 78` | 124 | 5487 | 1800–4300 |
| 33 | `80` | `e0 e0 00 00 00 00 00` | 0 | 5487 | 1800–4300 |
| 34 | `81` | `1f 0f 00 00 00 00 00` | 0 | 5487 | 1800–4300 |
| 35 | `01` | `01 00 05 03 00 00 78` | 2079 | 7566 | 1800–4300 |
| 36 | `01` | `06 00 03 03 00 00 78` | 2605 | 10171 | 1800–4300 |
| 37 | `01` | `06 00 03 03 00 00 78` | 2513 | 12684 | 1800–4300 |
| 38 | `01` | `06 00 03 03 00 00 78` | 2513 | 15197 | 1800–4300 |
| 39 | `01` | `06 00 03 03 00 00 78` | 2513 | 17710 | 1800–4300 |
| 40 | `80` | `e0 e0 03 03 00 00 78` | 310 | 18020 | 1800–4300 |
| 41 | `81` | `1f 0f 00 00 00 00 00` | 0 | 18020 | 1800–4300 |
| 42 | `82` | `0d 0f 00 00 00 00 00` | 0 | 18020 | 1800–4300 |
| 43 | `85` | `90 e0 20 00 00 00 78` | 382 | 18402 | 1800–4300 |
| 44 | `86` | `00 e0 20 00 00 00 78` | 1830 | 20232 | 1800–4300 |
| 45 | `82` | `00 e0 20 00 00 00 78` | 841 | 21073 | 1800–4300 |
| 46 | `0D` | `1f 0f 00 00 00 00 00` | 0 | 21073 | 1800–4300 |
| 47 | `0C` | `0d 0f 00 00 00 00 00` | 1 | 21074 | 1800–4300 |
| 48 | `08` | `02 00 00 00 00 00 00` | 0 | 21074 | 1800–4300 |
| 49 | `08` | `02 e0 20 00 00 00 78` | 3 | 21077 | 1800–4300 |
| 50 | `87` | `05 00 20 00 00 00 78` | 135 | 21212 | 1800–4300 |
| 51 | `83` | `00 0f 00 00 00 00 00` | 0 | 21212 | 1800–4300 |
| 52 | `87` | `00 00 00 00 00 00 00` | 0 | 21212 | 1800–4300 |
| 53 | `82` | `0d 00 00 00 00 00 00` | 0 | 21212 | 1800–4300 |
| 54 | `80` | `e0 e0 20 00 00 00 78` | 1024 | 22236 | 1800–4300 |
| 55 | `81` | `1f 0f 00 00 00 00 00` | 0 | 22236 | 1800–4300 |
| 56 | `82` | `0d 00 00 00 00 00 00` | 0 | 22236 | 1800–4300 |
| 57 | `01` | `06 00 16 03 00 00 78` | 1231 | 23467 | 1800–4300 |
| 58 | `01` | `06 00 16 03 00 00 78` | 134 | 23601 | 1800–4300 |
| 59 | `01` | `06 00 16 03 00 00 78` | 134 | 23735 | 1800–4300 |
| 60 | `01` | `06 00 16 03 00 00 78` | 134 | 23869 | 1800–4300 |
| 61 | `01` | `06 00 16 03 00 00 78` | 134 | 24003 | 1800–4300 |
| 62 | `01` | `06 00 16 03 00 00 78` | 134 | 24137 | 1800–4300 |
| 63 | `01` | `06 00 16 03 00 00 78` | 134 | 24271 | 1800–4300 |
| 64 | `01` | `06 00 16 03 00 00 78` | 134 | 24405 | 1800–4300 |
| 65 | `01` | `06 00 16 03 00 00 78` | 134 | 24539 | 1800–4300 |
| 66 | `01` | `06 00 16 03 00 00 78` | 134 | 24673 | 1800–4300 |
| 67 | `01` | `00 01 04 03 00 00 78` | 671 | 25344 | 4300–7200 |
| 68 | `85` | `91 e0 7c 00 20 00 78` | 118 | 25462 | 4300–7200 |
| 69 | `01` | `07 00 28 03 00 00 78` | 1465 | 26927 | 4300–7200 |
| 70 | `86` | `01 00 00 00 00 00 00` | 436 | 27363 | 4300–7200 |
| 71 | `82` | `0d 00 28 03 00 00 78` | 0 | 27363 | 4300–7200 |
| 72 | `80` | `e0 e0 00 00 00 00 00` | 0 | 27363 | 4300–7200 |
| 73 | `81` | `1f 0f 00 00 00 00 00` | 0 | 27363 | 4300–7200 |
| 74 | `01` | `05 01 03 06 00 00 78` | 377 | 27740 | 4300–7200 |
| 75 | `01` | `03 00 0c 04 00 00 78` | 854 | 28594 | 4300–7200 |
| 76 | `01` | `01 00 0d 03 00 00 78` | 1248 | 29842 | 4300–7200 |
| 77 | `01` | `07 00 0b 03 00 00 78` | 8 | 29850 | 4300–7200 |
| 78 | `02` | `05 00 0b 03 00 00 78` | 1659 | 31509 | 4300–7200 |
| 79 | `80` | `e0 e0 0b 03 00 00 78` | 33 | 31542 | 4300–7200 |
| 80 | `81` | `1f 0f 00 00 00 00 00` | 0 | 31542 | 4300–7200 |
| 81 | `82` | `0d 0f 00 00 00 00 00` | 0 | 31542 | 4300–7200 |
| 82 | `85` | `91 e0 7c 00 20 00 78` | 1007 | 32549 | 4300–7200 |
| 83 | `01` | `07 00 28 03 00 00 78` | 1407 | 33956 | 4300–7200 |
| 84 | `86` | `01 00 00 00 00 00 00` | 518 | 34474 | 4300–7200 |
| 85 | `82` | `0d 00 28 03 00 00 78` | 1 | 34475 | 4300–7200 |
| 86 | `80` | `e0 e0 00 00 00 00 00` | 0 | 34475 | 4300–7200 |
| 87 | `81` | `1f 0f 00 00 00 00 00` | 0 | 34475 | 4300–7200 |
| 88 | `01` | `05 01 03 06 00 00 78` | 376 | 34851 | 4300–7200 |

### Command meanings (source hypothesis)

The embedded "Ver2.04 96/01/25" text identifies Sega's Saturn sound driver.
The names below come from that driver family's published host interface.
They are **hypotheses** until each handler is executed and checked. The
right-hand column is only a static reading of the handler's first
instructions.

| Code | Hypothesised name | Static first-instruction reading |
| --- | --- | --- |
| `01` | sequence start (P1 control no., P2 bank, P3 song, P4 priority) | handler `0x2364` |
| `02` | sequence stop (P1 control no.) | handler `0x2396` |
| `08` | sound area map change (P1 map) | handler `0x18FE` |
| `0C` | DSP stop | `0x1C3A` clears `0x100800`–`0x100BFF` (SCSP DSP MPROG, 128 steps) |
| `0D` | all sound off | `0x1C4C` masks interrupts, saves and later restores `0x883A`/`0x8838` around its work |
| `80` | CD-DA level (P1 left, P2 right) | `0x1D10` merges `P & 0xE0` with shadow pan bits at `0x888E`/`0x888F`, writes slot 16/17 byte `0x17` (EFSDL/EFPAN) |
| `81` | CD-DA pan | `0x1D54` merges `P & 0x1F` with the shadow level bits, same registers |
| `82` | master volume (P1) | `0x1D98` writes `P1 & 0x0F` to SCSP `0x100401` (MVOL) |
| `83` | effect change (P1) | `0x1DA4` loads `P1` into `D3` and jumps to `0x3140` |
| `85`, `86` | PCM start / stop | handlers `0x1DAE`, `0x2056` |
| `87` | mixer change | handler `0x17FC` |

## Denominator after this slice

Of the 146 SND entries:

- **20 have complete isolated contracts with controls and natural ties**:
  `0x1768`, `0x1A60` and 18 dispatch-table stubs whose whole body is a
  return or ignore path (`0x1B6E`, `0x1BAA`, `0x1BBE`–`0x1BEA`, `0x1AEA`,
  `0x1B06`, `0x1B0E`, `0x1B12`).
- **2 are partially executed to a device-write guard**: `0x1B0A` and `0x1B16`.
- **28 handler-bearing table entries are open.** Their dispatch is verified,
  but their bodies are not.
- **The other 96 entries are open.**

The vector-26 handler `0x1734`, the counter prologue of `0x141C` and the
companion routine `0x17BA` have natural evidence only. They are not counted.
NLSND, XBSND and the DSP programs are unchanged by this slice.

## Limitations

- The isolated contracts are CPU-only (ABI1). They model no SCSP device,
  interrupts or bus timing. The executor contract stops at handler entry.
- Natural evidence comes from one Beetle/Mednafen lineage, one route, one
  release and one SND lifetime (two identical runs).
- The command stream comes from the driver's own ring, not from an SH-2 write
  observer. The SH-2 producer of each command is not identified here.
- The slot index of each natural record is not stored in the ring. The replay
  declares slot 0.

## Reproduce (private inputs, fresh report)

```sh
python3 tools/saturn_lab/m68k_probe.py --sources /PRIVATE/saturn-recomp-f20de94 --cache /PRIVATE/tools/m68k-probe-abi1
python3 tools/saturn_lab/probe_snd_mailbox.py --source-file /PRIVATE/SND.container \
  --prepared /PRIVATE/tools/m68k-probe-abi1 --run /PRIVATE/runs/final-enabled-1 \
  --run /PRIVATE/runs/final-enabled-2 --report /PRIVATE/mailbox/NEW.json
```

The runs are the accepted natural coverage windows from
`run_m68k_coverage.py`, with snapshots at 1800, 4300 and 7200. The probe
verifies each run's coverage file, observations and snapshot states against
the run's own digests before it uses them.
