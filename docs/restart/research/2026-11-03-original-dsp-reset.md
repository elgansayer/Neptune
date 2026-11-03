# Original NLSND DSP reset helpers

[#683](https://github.com/elgansayer/Neptune-Bomberman/issues/683) adds a separate
ABI8 reference profile and four complete constructed original helper contracts.
[Evidence](../evidence/2026-11-03-original-dsp-reset.json) binds sources, preparation,
actual commands, repeated reports and retained failures. Parent665 remains open:
returning from command10 does not establish its independently recovered semantics.

## Reference effects and two distinct traces

The pinned Beetle source retains the complete affected DSP declarations and
selected word register/work-buffer branches, sign-extension macro and normal
`Write_u32` function. Additional exact hashes cover `sound.c`, `math_ops.h`,
`m68k_private.h`, the addressing-mode helper and MOVE dispatcher. The normal
reference helper dispatches the high word at A before the low word at A+2.
Predecrement uses a separate reverse-order path. The adapter's minimal callback
view is explicitly not the complete reference CPU or its structure layout.

The new trace records those frozen reference16-bit dispatches separately from
the pinned Musashi CPU's operand records. It does not measure physical Saturn
bus transactions or clocks. SoundCPU address/timing wrappers are source evidence;
the whole SoundCPU/SCSP clock, DSP, envelope and audio engines are not run.
The two components share emulator lineage; no independent hardware proof follows.

Normal aligned MOVE.L stores are admitted in the bounded700..DFF register view.
CPU absolute and postincrement modes receive direct tests; the pinned dispatcher
establishes normal versus predecrement bus ordering. Long reads, non-MOVE and
predecrement CPU long stores, bytes, odd words and unaligned/cross-boundary longs
remain explicit guards. Some physically possible operations are deliberately
outside this profile. No device range is mapped as flat RAM.

| State | Independently compared effect |
| --- | --- |
| COEF700..77F | Each16-bit word contributes its high13 bits. |
| MADRS780..7BF | Full16-bit entries;7C0..7FF gap writes leave state unchanged and gap reads remain unsupported. |
| MPROG800..BFF | Four ordered16-bit lanes per64-bit entry; every write invalidates the decoded program, even an identical write. |
| TEMPC00..DFF |128 signed24-bit values. First word supplies bits0..7; second supplies bits8..23. Sign extends after each insert. |

For example, long12345678 atC00 produces TEMP00567834, not00123456 or00345678.
The larger snapshot exposes all128 TEMP values and masks them out of the separate
untouched-byte capture. Initial TEMP values are normalised to24-bit signed state.
This is a declared fixture difference from ABI7, whose hidden TEMP bytes remained
inside its untouched capture. All old ABIs, source identities and caches remain.

Native fresh preparation and reuse pass26,880 full-state raw writes,1,536
identical program-word invalidations,2,688 CPU long stores,26 raw/CPU access
guards and a separate predecrement guard. The8,192-word bus trace rejects overflow
without partial effects and recovers. Inherited98,304 slot-byte values,1,024 slot
CPU calls,96 RMW calls, latch/pan effects, actual16-range/region calls, native
17th-count rejection and8,192-instruction/4,096-event fences also pass.

## Complete original helper contracts

All calls use unmodified pinned USA MK81070 V1.003 NLSND source, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
The sound68000 load-zero lifetime is separate from SND/XBSND and SH-2 modules.
A5 is the declared100000 device base; each helper zeros D0 before writing.

| Entry | Long writes | Effect | Instructions |
| --- | ---: | --- | ---: |
|3592|256|Clear all128 MPROG entries and invalidate program decode.|517|
|359C|32|Clear32 MADRS words plus32 no-op gap words.|69|
|35A4|32|Clear64 COEF words.|69|
|35AC|128|Clear128 TEMP values.|260|

A1 ends immediately after each span; D0 ends zero. D7.low16 endsFFFF.
3592 preserves its incoming D7 upper word because it initialises the counter with
MOVE.W; the other entries initialise with MOVEQ and end0000FFFF. Other registers
remain unchanged apart from SP advancing4 through RTS. Final SR preserves X and
upper bits, sets Z and clears N/V/C. All18 visible registers, every PC, instruction
count, ordered operands, reference word-bus events, RAM/stack bytes, full device
effects, untouched bytes and original code buffer are compared. Model cycles are
retained for repeatability only, not claimed hardware timing.

Two fresh processes pass414 cases each:40 per COEF/MADRS/program helper and294
TEMP cases. The selection covers all TEMP byte seeds, wider seeds, four SRs and
two register variants. Fifteen changed-value/count/destination/branch families
each return normally in four cases and all60 fail independent comparison.
Early guards never count as successful semantic mutation controls.
Both complete reports hash to
`10a22a79aaae176f5897759caad5cd5fd4f7492aaf4edd5f5a0a174c64a9637f`.

## Wider command10 diagnostic

All128 constructed scenarios now return.64 prior complete CPU/RAM/common-device
outcomes are identical and64 previous DSP-width prefixes are preserved/extended.
Previously untouched bytes remain unchanged within each profile; common device
fields are compared directly. The new TEMP fixture and masking difference above
is disclosed rather than pretending the two full initial snapshots are identical.
Low0780 neighbours and all original code buffers remain unchanged.

This removes the observed width blocker; it is not an independent complete
command10 specification. Command payload domains, natural callers, boot/traffic,
timing, PCM, production Godot campaign/battle/state/pixel/audio comparisons and
the whole-original-code denominator remain unresolved.

## Reproduction and operational evidence

Qualified original source head is9ed8b8f829da1c72f8a21955514b4aab3ac69993.
Native preparation source isf0284c5bc625dad1d1f1252116f5a06c79fa9868; executable
preparation dependencies are unchanged between those heads. Native005 passed
fresh/reuse in105.238s and produced binary SHA256
`82291cfcc35cbf6f24e326eb49f2fa01720e43bf62fc8c9a79ea89eb0e97e21f`.
The private host copies all eight prepared files into a proper home directory
and verifies every hash before read-only mounting. A symlink resolving outside
home was correctly rejected before any child; the guard was not relaxed.
Original results are under `/home/dev/neptune-research-private/683/original-002/`;
native receipts/stages under the existing secondary volume's
`repo-factory/neptune/research-683/` and coordinator logs under
`/home/dev/neptune-evidence/dsp-long-20261103/`.

Retain the failed preparation attempts: the raw sweeps exposed an inherited
16-bit mask truncating nonzero CPU operand records, then split predecrement word
callbacks bypassing the first width-only guard. Both repairs affect ABI8 only.
A queued own attempt was interrupted before admission/children to correct the
new native-count fixture's ctypes layout; its owner was independently absent.
The first actual CI preparation failed because its upstream sparse checkout
omitted a newly pinned addressing helper; all five required wrapper/helper files
are now selected. These failures are not passing or substituted results.

399 research-tooling tests pass separately from emulator, Godot and factory
health. Final exact-head required CI must still qualify publication; fresh/reuse
is part of the existing mandatory preparation job, with source/receipt/library
artifact and explicit applicability. Missing/skipped/failed applicable work blocks
merging. Pure tests establish tooling, not natural original-game behaviour.

```sh
python3 tools/saturn_lab/m68k_scsp_long.py \
  --sources "$NEPTUNE_PINNED_CPU_SOURCE" \
  --scsp-sources "$NEPTUNE_PINNED_SCSP_SOURCE" \
  --cache "$NEPTUNE_NEW_ABI8_PREPARED"
python3 tools/saturn_lab/probe_netlink_dsp_reset.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI8_PREPARED" \
  --previous-prepared "$NEPTUNE_ABI7_PREPARED" \
  --report "$NEPTUNE_NEW_PRIVATE_REPORT"
```

Use the existing guarded, credential-free, offline runner and shared admission.
Source, upstream tools, original inputs and native libraries are read-only;
broker/auth/signing authority are hidden. Shared limit3, guard5s and5GiB reserves
remain. Preparation has no original input,2GiB address space,400s CPU,420s wall
and600s host lease. Original runs use512MiB,40s CPU,45s wall,4MiB files,300s host
lease and600/8192 instruction limits for helpers/command diagnostics. All accepted
guardians are terminal, without timeout, cancellation or truncation. No service,
provider cap/circuit, allowance, scheduler or continuity changes. Model calls by
tests0; account/review/CI spend unknown. Preserve669 and Gemini487.
