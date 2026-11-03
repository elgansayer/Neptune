# Original byte copy, resource pools and context setup

**All-original-code programme active and incomplete.** This continues655 after
the [division/format evidence](2026-11-03-library-arithmetic-contracts.md).
Twelve actual original jobs pass, with byte-identical full reports for every
family pair. The [derived evidence](../evidence/2026-11-03-library-pool-contracts.json)
records source/range/guard/interpreter identities, report hashes, controls and
retained resource deferrals. Originals and raw memory/reports remain private.

| Selection | Cases per run | Complete returns | Unfinished handoffs | Instructions | Controls |
| --- | ---: | ---: | ---: | --- | ---: |
| 945B4 forward byte copy | 3,752 | 3,752 | 0 | 9–147 | 3 |
| A77E0 first24-byte pool | 5,076 | 5,076 | 0 | 13–177 | 4 |
| A777E second24-byte pool | 5,076 | 5,076 | 0 | 17–225 | 4 |
| A77B0 indexed second-pool release | 12,324 | 12,324 | 0 | 4,7,14,20 | 3 |
| A6FE0 first-pool exhaustion | 1,536 | 1,536 | 0 | 270 | 5 |
| A6FE0 successful-first-allocation prefix | 1,296 | 0 | 1,296 | 105–266 | 4 |
| Total | 29,060 | 27,764 | 1,296 | explicit bounds | 23 |

Source is unchanged USA MK-81070 V1.003 KRNL resident at06006000, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
The f20de940 interpreter and its three source hashes are checked before every
job. Counts are original instructions, distinct from cycles or native hooks.

## Recovered contracts

945B4 takes count inR0, destination inR1 and source inR2. It copies bytes
forward, including the observed propagation when destination overlaps later
source bytes. Zero count performs no byte copy, returnsR0=0 and leavesT=1.
For tested nonzero counts,R0 ends as the sign-extended final copied byte andT=0.
R1 advances four bytes after each complete four-byte group, including an exact
multiple-of-four ending; a final partial group does not advance it. The original
restoresR2/R3/R4/PR/SP, including the R2 pop in the RTS delay. Other flags/MAC
remain unchanged. This specialized ABI is not relabeled as a standard C API.

Counts0..32, eight relative source/destination positions, both register variants
and all256 selected initial byte seeds are exercised. Small negative count words
FFFFFFFF/FFFFFFFE/FFFFFFE0 make the wrapped end pointer lower than the canonical
source; those cases copy exactly one byte. No general negative-count or arbitrary
address behavior is inferred. Every unaffected arena/canary byte is compared.

A77E0 scans24 bytes starting at the pointer stored in060FC084. A777E scans the
next24 bytes at that same pointer+24. The first zero byte becomes1, its index is
stored through inputR4, andR0 returns0. Every tested nonzero marker, including
80/FF sign-extended reads, is used. Exhaustion storesFFFFFFFF throughR4 and
returns-4 for the first pool or-3 for the second. The other pool and neighbors
remain unchanged. The corpus covers every first-free/full boundary, all256
eight-byte masks with the remaining entries used, alternating masks and three
old output values. Duplicate case tuples are removed.

A77B0 takes a signed index inR4. Values outside0..23 return-6 before any data
read. In-range entries in the second pool must equal **exactly1**; all other byte
values return-7 unchanged. Success clears that one byte and returns0. Every byte
value is tested at every valid index, plus signed/upper-bound adversarial inputs.
All path-specific register andT effects are retained rather than masked.

A6FE0 now executes its actual945B4 six-byte copy and original first-pool allocator.
For all24 first-pool markers used, it returns0 through its actual saved-register/
PR/SP restore. The partial96-byte object keeps its other bytes, but sets offsets
28=0,52=1,56=FFFFFFFF and60/64/68/72=0. Bytes44..49 become input object byte14
followed by five zeros. The local allocation output containsFFFFFFFF. This is a
complete exhausted-pool return, with270 executed instructions.

If the first pool has a free entry, that actual allocation marks it1 and the
index is additionally stored at object+32. The experiment then follows the real
JSR/NOP to **non-executable A777E**: PR=060A7054, SP=before-28,
R4=beforeSP-28, R14=object+28. The pending original frame and every register,
transaction and output byte are retained. This is an unfinished success prefix;
no second allocation, cleanup service or fabricated return executes in it.

## Comparison, controls and bounds

Each case compares all23 visible registers, full SR/PR/MAC, exact PC/delay trace,
ordered transactions, complete declared output/stack bytes, readonly neighbors
and every unaffected original byte against an independent expected model.
Separate scalar models check forward overlap, output indices/error codes,
unchanged pool bytes and context fields. The derivation rechecks every retained
row and verifies exact corpus membership, isolation receipts and both report bytes.

All23 family/control combinations reject without counting budget failures.
Disposable original copies lose/change stores, copy progression, loop limits,
pool offsets, the exact valid release marker, copied flags, allocated indices,
context defaults and real return/restore delays. The supplied original stays
unchanged. Owned tooling tests and static/model development are not counted as
additional original executions.

Accepted128 guard9d73ab34 remains unchanged. Release uses budget128; copy and
allocations use256 and context uses512 under the separate already accepted
1024 profile. Actual old128 refusals are retained for both complete pool scans
and the context exhaustion path. The evidence distinguishes128 recorded executed
instructions from the CPU step-attempt counter. No aliases, device RAM, external
callee substitutions or vendor interpreter changes are added.

## Provenance, resource history and next calls

Source84c8499f27f6d95509ee19c881154f5e5a126abb was tested/pushed before original
jobs:8 owned and448 research tests pass. Later checkpoint changes preserve the
exact tested production/test bytes. Frozen78-file adapter:
`.../655/adapter-5823f81ce329a8f17cd42c1b6461d1c12405492ff8b445afbc2e8b2ab3c5a5b4`.
Completed continuation:
`/home/dev/neptune-research-private/655/pools-batch-continue-2fdcc4ck/batch.json`.
Source/runner/derivation/resource receipts remain under
`/home/dev/neptune-evidence/code655-20261102/`.

The initial index0 admission deferral preserved a verified live foreign exclusive
reservation. After legitimate release, five jobs passed; root storage preflight
then refused index5 before any worker/CPU execution. That terminal parent
manifest/stderr remain unchanged. A derived continuation retains its hashes,
completed paths and attempts, runs only missing selections, and chooses between
the two approved private output filesystems under the same5GiB+64MiB reserve.
Further gate/storage deferrals at indices9/11 are retained. Lossless references
to existing identical completed own captures preserve all old readable paths and
decompressed bytes. No foreign file, reservation or configured limit was changed.

Every admitted job acquired/released its own shared3/180-second lease and kept
60-second/nice10/downward2GiB, offline/read-only and hidden-authority limits.
No provider calls, native build, scheduler or allowance change occurred.

The composed nonnullA681A/96D74 exhaustion batch subsequently completed3,344
returns per run twice through real division/remainder/format/context/copy/pool
calls, with12 controls and byte-identical raw/archive pairs. Its source29d7bdb
has7 owned/455 research tests; dependent [PR699](https://github.com/elgansayer/Neptune-Bomberman/pull/699)
retains that additional original evidence. Null record/A7F4E, successfulA6FE0 services, positive95E5A/full89C8,
BIOS/callbacks, root/task cycles and further modules remain unresolved. Unknown
executable/function/dynamic-target denominators stay unknown. These CPU contracts
do not establish natural interior traffic, physical timing, gameplay or Godot parity.
