# Original full32-record NetLink consumer

Issue [#606](https://github.com/elgansayer/Neptune-Bomberman/issues/606), under
#483/#488/#480/#464, continues [the packed-byte writer](2026-11-02-original-netlink-command.md).
Original sound68000 entry `0x4B1C` now passes **1,476 constructed cases twice**,
including all32 active matching records and nested original4C2A calls. Complete
reports are byte-identical, SHA256
`a8ff36c55da66247aea86f2e638cfb608168d8cc2328e43bc0a2410210184b0a`.
The maximum observed path has **1,572 instructions,967 data events and32 emitted
records**. This is full declared32-record execution, not an at-most-two-active
subset. Natural sound/SCSP/DSP/hardware behavior and whole-program coverage remain
unvalidated. [Derived evidence](../evidence/2026-11-02-original-netlink-consumer.json).

## Source and recovered caller/callee behavior

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`,23,920bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, NetLink driver lifetime. Whole-source identity is
checked before loading. Executed ranges are original `[0x4B1C,0x4B6E)` and
`[0x4C2A,0x4C9A)`; both hashes are retained. Other drivers/regions and SH2 mappings
remain distinct. No original file or executed instruction is patched on positive
runs; data slots and registers are explicitly initialized controlled inputs.

The original scans32 twelve-byte records starting at initial A5, in ascending
order. For each record:

1. If bit7 of byte0 is clear, skip it without reading its pointer or payload.
2. Otherwise compare its big-endian pointer at+8 with A6. Skip mismatches.
3. For an active match, clear bit7 only when **D7.low8** is nonzero; its other
   low flag bits remain. Nonzero high D7 bits with a zero low byte do not clear it.
4. Read bytes+1/+2/+3 and byte0. Build status`0x80 | (byte1 & 15)`, payload
   bytes2/3 and flag`byte0 & 1`, then call the unchanged original4C2A writer.

Consequently emitted status80..8F excludes4C2A's90-class subtract/clamp path in
this caller. Each match writes one four-byte record in the format established by
#604, with first byte0, second byte `(record.byte1 & 15) | ((record.byte0 & 1)<<4)
| ((tag<<5)&255)`, then record bytes2/3. `tag` is read from the shared descriptor
at A6+1. The counter at `b+1840` advances modulo256 for each emission, and the
selected four-byte output position is `b+1A00+4*old_counter`, where b=read32(450).
All output order, wraps and unaffected bytes are independently compared.

The original BSR at4B5A pushes4B5E. Each actual writer return reaches4B5E, after
which the record pointer advances12 and DBRA counts all32 positions. Outer
D6/A5 are saved/restored; the loop's low16-bit D6 counter is distinguished from
its preserved upper bits. D5/D7 and A6 remain preserved in tested states. D0-D3
and A0-A2 retain the last writer's specified results when there is an emission;
without emissions their initialized values remain. RTS returns through the
explicit outer sentinel and SP increases4. Every visible D/A register, PC and SR
is checked, not just a final counter or byte count.

Final CCR depends on the last predicates/writer, not a blanket preservation rule.
A writer restores its intermediate saved Z/X state. Later inactive tests change
Z only; pointer mismatches compare unequal larger positive pointers in the
constructed cases and can leave N/C set. Empty/all-inactive and active-but-all-
mismatched cases are separately tested. Initial supervisor SR/mask bits, both X
states, sparse/dense matches and zero-low-byte clearing controls are explicit.
No natural meaning is assigned to those status flags without caller evidence.

Only six declared data regions exist: pointer450, one descriptor tag byte,
384 record bytes, one counter byte,1024 output bytes, and30 stack/return bytes.
Every other access fails. Exact per-case read/write addresses,widths,values and
order, all executed PCs, registers and every mapped byte are compared; the full
source instruction buffer remains unchanged. There is no device or SCSP RAM.
The lower stack holds actual nested save/SR/return values; unused stack bytes and
all untouched record/output bytes retain their canaries.

## Scope and negative controls

The1,476-case selection combines empty, each one-of32 active positions, all active,
and alternating active masks; five additional all-active pointer-match patterns;
D7 variants0/1/100/FF; counters0/250/255; and three tag/SR variants. It includes
zero matches, mismatches, multiple matches, full32 emission, flag-clearing and
nonclearing cases, and wrap through255. It is not all possible32-record/RAM/
register combinations or naturally captured data. Observed calls span132..1,572
instructions and39..967 events. Each stays below its explicit2048/1024 bounds.

| Altered original instruction | Rejected /48 |
| --- | --- |
| reverse pointer-match branch |48|
| remove flag-bit clear |12|
| process31 instead of32 records |48|
| test full D7 longword instead of low byte |24|
| widen flag mask1 to3 |36|

Mutations fail actual bytes, registers/SR or access/path comparisons; unaffected
cases remain recorded. Original sources stay unchanged and altered hashes remain
separate. These controls do not create an independent CPU/hardware oracle.

## Real capacity failure and separate prepared generation

The accepted short-call ABI1 was first run on the original all32-active case.
It correctly stopped after206 instructions at128 events with `event-budget` at
address20031. Its receipt explicitly says `completed_original_call:false`; it is
not counted as a successful consumer call. The source remained unchanged. The
short rejection and report hash are retained with the derived evidence.

A new **separate ABI2 profile** uses the accepted hash-pinned owned shim with
exactly three substitutions: instruction capacity256→2048, event capacity128→1024
and ABI tag1→2. An exact-source-hash check and reversible substitution test guard
those edits. No CPU instruction implementation, memory guard, region allowance,
clock model or original game byte changes. The accepted short C/Python adapter,
source lock and prepared generation remain unchanged; its binary still hashes to
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.

ABI2 reuses all19 pinned Musashi source files at
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`. Its source-only guarded
preparation hid originals/broker authority, verified all source hashes, used one
compiler process,2GiB address-space cap and60-second compiler deadline, and
retained diagnostics. Initial build and reuse each passed owned positive,
read/write/PC/loop controls, a real2048-step overflow, a real1024-event overflow,
and fresh-state recovery afterward. Those smokes use owned synthetic bytes and
explicitly record original execution false. The prepared ABI2 binary SHA256 is
`abd26a109c1e854925625e11c924b39829d2921d07a249d5c782b08d4eb6aa63`.
The generation is `.factory-tools/code606-001/prepared`; ABI/receipt/native hash
checks precede original calls. ABI1 cannot be loaded as ABI2 accidentally.

This increases a **separate function-local trace profile**, not host/provider
budgets. Existing shared host admission was read as3, unchanged; own180-second
leases were released. Other manual sessions, coordinator#597 and Gemini#487 stay
untouched. No provider/model call, paid fallback, scheduler, new allowance or
continuity activation occurred. Account/CI spend is unknown. Source/original/
prepared mounts stayed read-only and broker authority hidden in the real jobs.
Preparation took about21seconds; the short proof and two original runs about
10seconds total, with60-second per-command deadlines.

Preparation source head `d839a862527d36b12a8852519297594f69feb5de`; original
execution head `0d24f6b740cfed7b21d92b5b12d6af46569d90c2`. Original reports are
`/home/dev/neptune-research-private/606/nlsnd-consumer-001/`, including
`short-proof.json` and `run{1,2}.json`. Private supervisors/logs are
`/home/dev/neptune-evidence/code606-20261102/` and the prepared-generation parent.
Nine new synthetic tests and all197 input-tooling tests pass; generated owned C
also passes warning-as-error syntax checks. Native/original execution is separate
host evidence. Publication still requires exact-head/current-base CI.

## Reproduction and next code

After existing admission, prepare a separate generation without original inputs:

```sh
python3 tools/saturn_lab/m68k_consumer_native.py \
  --sources /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --cache /home/dev/neptune-code-recovery-20261102/.factory-tools/NEW-consumer-prepared
```

Mount it read-only into original jobs, choose two fresh reports and compare files:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_consumer.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code606-001/prepared \
  --report /home/dev/neptune-research-private/606/NEW-consumer-run1.json
python3 tools/saturn_lab/check.py
```

Next inspect the original queue-read/parser path beginning241A. Selected static
instructions use counters1842/1841, the four-byte area1A00 and another output area
1F00 before dispatching further. Derive those roles and device boundaries from
actual accesses; do not infer sounds from field names or flatten SCSP registers
into RAM. The prepared next-source inspector is in code606's checkpoint. Natural
calls, original reset, SCSP/DSP/audio, hidden/network/region paths, boot/loaders,
overlays/slave/gameplay/RNG and whole-program denominators remain open.
