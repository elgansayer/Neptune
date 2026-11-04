# Original bounded name comparison, table search and lookup

**All-original-code programme active and incomplete.** Eight actual guarded jobs
complete4,316 returns per run, twice. Four full raw/archive pairs are identical;
all16 semantic mutation-control combinations reject. Read the
[derived evidence](../evidence/2026-11-03-library-name-contracts.json).

| Entry/selection | Cases/run | Original instructions | Controls |
| --- | ---: | ---: | ---: |
| 95158 bounded byte comparison | 1,452 | 5–593 | 3 |
| A5676 flagged-record search | 464 | 25–698 | 4 |
| 95CBC complete lookup/status returns | 2,320 | 77–760 | 6 |
| 95CBC invalid mode/null table | 80 | 42–52 | 3 |

Original identity is USA MK-81070 V1.003 KRNL, resident06006000, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
Every job checks the pinned f20de940 interpreter and its three source hashes.
Counts here are original instructions, separate from cycles/native observer hooks.

95158 receives byte strings inR4/R5 and an unsigned bound inR6. Bound0 returns0
through the actual MOV delay without reading either string. Otherwise it stops
at the first unequal bytes, common NUL or bound, then returns the **unsigned**
byte difference modulo32. Tests cover all256 selected first-byte values, both
subtraction signs, lengths0..16/32/48, late differences and early common NULs.
All scratch-register, pointer, flag and ordered-read effects are compared.

A5676 receives tableR4, queryR5 and signed capacityR6. It scans24-byte records,
calling real95158 on the query and record+12 with bound12. Equality returns the
current zero-based index **before** checking the record's end flag. After a
mismatch, recordbyte11 bit0 stops search; otherwise it advances24 bytes, including
the actual branch delay. Nonpositive capacity, exhaustion or a terminating
mismatch returnsFFFFFFFF. Selected capacities0/1/2/4/8/-1/INT_MIN, match positions,
early/final end flags and common prefixes exercise these distinctions. The tested
limits describe this corpus, not a universal record capacity.

95CBC receives the query pointer inR4, obtains the library through060FA8BC and
uses its header at library+98. The table at header+8 must be nonnull and mode at
header+0 must equal1. Otherwise it restores its frame and tail-calls original
96C60(-8), returning the effective error. A valid header passes **header+4
capacity** to realA5676. Not found tail-calls96C60(-9). A found index calls
96C60(0); a negative effective status is returned, otherwise the saved index is
returned. Global060FC080 values-16/-14/-13 map to-25/-2/-23; other selected words
preserve the input status. The effective code is stored at library+C0. Callback
+B8 is explicitly null; no callback or service result is substituted.

The resource-slot word at library+0, search capacity at header+4 and populated
file count at header+12 are separate. Earlier95E5A uses that populated count for
its index check. Its tested nonzero-mode indexing rule must not be generalized
to every neighboring entry.

The first frozen comparison job stopped on a missing negative-control rejection:
the sampled controls omitted bound0, so the changed zero-return delay was never
executed. Its report/archive/supervisor and terminal manifest remain private and
are not counted as completed evidence. Corrected source explicitly includes
bound0 in control selection and retains completed rows on later control failures.
The supplied original and CPU/permissions/limits were unchanged. Source
`70b90ef1423cd5e634ae06c35444eeb194560351` passed8 focused/477 research tests before
these eight jobs. Frozen81-file adapter:
`.../655/adapter-597238043d2b5864a893b4a39cb6008cb8015023af2c9bc1f7ddf5bd0febf9de`.
Completed manifest:`/home/dev/neptune-research-private/655/name-batch-qt7qpih_/batch.json`.

Every case compares all23 registers/fullSR/PR/MAC, exact PC/delay trace, ordered
transactions, every mapped byte/canary and unaffected source. Independent scalar
byte/search/status calculations are rechecked against retained results. All actual
original-copy controls have non-budget semantic rejections. The original128 guard
is unchanged, with actual refusals retained for comparison/search/lookup. The
already accepted separate1024 profile uses budget1024, maximum observed760.
Literal islands and neighboring functions are excluded from executable ranges.

A separate read-only analysis revalidates all12 previously accepted PR667 final
states and both enabled89C8 traces. Their frame1264 native95CBC boundaries enter
withR4=060B1AB8 and return index25. The captured header is[1,32,060BF198,26], with
16 resource slots. The identical frame1800 final-state table has its sole tested
name match and end flag at index25. Source spans for all three functions and the
query match the original kernel in those final states. **These table/query bytes
are from the later final state**, not an interior call-time memory observer; the
projection does not establish unchanged table contents during the call or the
intervening frames. It executes zero new original frames/instructions. Retained
projection:`.../655/natural-name-projection-79nb7dyv/projection.json`.

Raw reports remain private lossless archives, with source/raw/archive hashes and
`gzip -dk report.json.gz` restore. Derivation and worker receipts remain under
`/home/dev/neptune-evidence/code655-20261102/`. All own leases released. Shared3,
180-second leases,60-second/nice10/2GiB/64MiB/offline/read-only guards and5GiB+64MiB
storage reserve remain. No provider, native build, scheduler or allowance change.

Next recover95D34 record-name pointers and95D9C descriptor copies through real
A56CA/A56D8/949E0/96C60, then successful95E5A/context services, callbacks and further
root/task/modules. Complete89C8, hardware timing, gameplay and Godot parity, and
whole-program/module/function/dynamic-target denominators remain unresolved.
