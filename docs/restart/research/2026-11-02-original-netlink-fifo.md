# Original NetLink software queue to SCSP FIFO

Issue [#614](https://github.com/elgansayer/Neptune-Bomberman/issues/614), under
#483/#488/#480/#464. Original sound68000 prefix `[0x10B2,0x10DE)` passes
**15,872 constructed cases twice** with byte-identical complete reports, SHA256
`5edf9f0dfce4fc2bc8ba61a389c1309bc7dfbc3abe1b721a801804671230d0f5`.
The probe stops **before** the original JSR130E; it does not complete the main
loop. [Derived evidence](../evidence/2026-11-02-original-netlink-fifo.json).

## Source and recovered behavior

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`, 23,920 bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, NetLink lifetime. Whole-source identity is checked
before slicing/execution. Positive runs never patch original instructions.
Controlled A6 is software base b; A5 is100000, consistent with selected reset
setup at107A, which this experiment does not execute.

1. Read absolute byte4E1. Continue only if either bit5 or bit6 is set.
2. Read software output cursor at b+1843 and compare with writer cursor b+1841.
   Equal means empty; skip the device entirely.
3. Otherwise read the actual reference SCSP FIFO flags at100404. If bit4 is set,
   the FIFO is full; preserve the software cursor, payload and device state.
4. Otherwise write exactly one byte from b+1F00+old_read_cursor to100407, then
   increment the software read cursor modulo256. D4 keeps the old cursor.

This connects the [parser's optional output buffer](2026-11-02-original-netlink-parser.md)
to the device boundary without assigning a natural sound/protocol meaning.
The parser tests bit6; this output path accepts bit5 **or** bit6. Counters1840/1842
belong to the four-byte command ring, whereas1841/1843 index this byte ring.

Every visible register, SR, PC, mapped RAM byte, instruction path and data access
address/width/value/order is compared with an independent Python contract. There
are only three RAM regions:4E1, the three cursor/canary bytes1841..1843 and the
256-byte output buffer. No generic device RAM exists. The two supported device
lanes are read8 at100404 and write8 at100407; other addresses/widths fail.

Final flags depend on the exit: disabled uses AND's Z, empty uses CMP's Z, full
preserves CMP's N/V/C/X while BTST changes Z, and a successful transfer ends with
the byte ADDQ flags. In particular FF→00 sets X/C/Z and7F→80 sets N/V. The probe
checks these outcomes instead of assuming incoming CCR preservation. SP remains
unchanged because execution stops before the following JSR.

## Device evidence and limits

A separate ABI3 native generation extracts **verbatim** MIDI reset/output and
sound/main interrupt-recalculation definitions from
`libretro/beetle-saturn-libretro@01bc063fdd0fb5fc208850c9ecc658834df762ab`.
The full scsp.h/scsp.inc/COPYING hashes, exact extracted component hash and the
19-file Musashi lock are pinned. Preparation preserves the upstream license
notice and COPYING. No third-party implementation or original media is added
to the repository. The narrow structure includes every field those functions
access; no interrupt clearing or recalculation is stubbed out.

The serial clock is frozen and interrupt enables are zero. A successful push
advances the four-entry ring, clears OUTPUT_EMPTY, sets OUTPUT_FULL at count4,
clears SCIPD/MCIPD bit200 and calls both actual recalculations. No drain, serial
bit timing, audio sample, DSP or complete SCSP is claimed. The reference's direct
write-when-full behavior remains its upstream hardware TODO; the positive
original path never writes a full FIFO. This is reference-component evidence,
not Saturn hardware validation. It shares the existing interpreter lineage.

Source-only guarded preparation hid original inputs and broker authority, used
one compiler, a2GiB address-space cap and60-second compile deadline. Build and
reuse passed40 owned FIFO cases spanning all five fill counts, four ring read
positions and two pending-bit states, plus CPU guards, unsupported MMIO widths/
lanes and recovery after failures. Those synthetic smokes explicitly record no
original execution. The prepared binary SHA256 is
`9d7a5257262cc8f6f017201a0180c4964424e203f0ea02f927d3e51052208772`.
Existing ABI1/ABI2 source, capacities and caches remain unchanged. A dedicated
source-only CI job builds this adapter and exercises actual FIFO effects/reuse;
its logs/receipts are retained even on failure. Factory tool provisioning remains
governed by its separate exact-path aggregate.

## Coverage, controls and custody

The selection has all256 gate values with indices0/127/255, counts0/3/4,
ring positions0/3 and pending0/200; seven selected gate values with all256
software indices in empty-queue states; and four enabled gates with all256
indices across FIFO counts0/3/4. It is not the Cartesian space of all machine
states. Outcomes:3,328 disabled,2,560 software-empty,3,328 device-full and6,656
one-byte transfers. Observed paths span3..12 instructions and1..8 data events.

| Altered original instruction | Rejected /90 |
| --- | --- |
| accept bit6 only instead of bits5/6 |54|
| test OUTPUT_EMPTY instead of OUTPUT_FULL |24|
| remove software cursor increment |24|
| write unsupported even device lane406 |24|
| reverse full-FIFO branch |36|

Unchanged controls remain in the report. Mutation copies/hashes stay separate
from positive original input. Nine new synthetic tests and all214 then-current
research tooling tests passed; native/original execution is separate evidence.

Original execution head: `40554d69cbff27683566ea311216c65861f23ff6`.
Private immutable reports: `/home/dev/neptune-research-private/614/nlsnd-fifo-001/`.
Preparation receipt/diagnostics: `.factory-tools/code614-001/prepared` and parent.
Supervisors: `/home/dev/neptune-evidence/code614-20261102/`.
Actual host admission read shared limit3, unchanged; own180-second leases were
released. Original/code/prepared sources were read-only in original jobs and
broker authority hidden. No provider call, scheduler, paid fallback, allowance
reset or continuity activation occurred. Other active owners remain untouched;
account/CI spend is unknown.

## Resume

After existing host admission, prepare without original inputs:

```sh
python3 tools/saturn_lab/m68k_scsp_fifo.py \
  --sources /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --scsp-sources /home/dev/neptune-research-private/462/beetle-saturn-source \
  --cache /home/dev/neptune-code-recovery-20261102/.factory-tools/NEW-fifo-prepared
```

Mount the prepared generation read-only. Use fresh report paths for each run:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_fifo.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code614-001/prepared \
  --report /home/dev/neptune-research-private/614/NEW-run1.json
```

Next recover original130E and its1326 command-processing path. The main-loop
successor also touches SCSP420/418/422; those accesses require further actual
device modeling, not expansion of the FIFO adapter into flat RAM. Parser targets
3248/2BFC/24EA/1762/2B08 remain open. Natural sound/reset/gameplay, timers/DSP/audio,
boot/loaders, overlays/slave, RNG/save/network/Japan and whole-program/function/
dynamic-target denominators remain incomplete. This result closes no programme.
