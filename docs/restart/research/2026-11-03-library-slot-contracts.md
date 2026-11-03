# Original library slot selection and marker release

**All-original-code programme active and incomplete.** This continues
[655](https://github.com/elgansayer/Neptune-Bomberman/issues/655)'s positive95E5A
dependencies after status/callback PR669 mergedb161880. The
[derived evidence](../evidence/2026-11-03-library-slot-contracts.json) records
source identities, paired private reports, controls and execution bounds.

| Original entry | Cases per run | Complete returns per run | Executed instructions | Controls |
| --- | --- | --- | --- | --- |
| 06096B9C selection | 3,486 | 3,486 | 17–233 | 5 |
| 06096BCE release | 432 | 432 | 3 | 2 |
| Total | 3,918 | 3,918 | bounded per function | 7 |

Each family executes twice against unchanged USA MK-81070 V1.003 KRNL, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
mapped at06006000, using the pinned f20de940 interpreter and verified three
source hashes. Full original reports match byte-for-byte within both pairs.
These are constructed high-RAM cases, separate from natural runtime validation.

## Recovered contract

96B9C reads the library pointer from060FA8BC and its signed32-bit count at+0.
Marker words begin at+C60, strideA8. For positive counts, it scans in ascending
order until a zero marker is found; it writes1 there and returns that marker's
address. Nonzero marker words are occupied, including80000000 andFFFFFFFF.
A full table or zero count returns0 without a marker write. The actual RTS at
96BCA returns the pointer/zero through MOV R4,R0 in its delay at96BCC.

The initial comparison is signed, while the final exhaustion comparison uses
equality. The54 adversarial cases with counts-1,-2 or INT_MIN skip the scan but
still write1 at the first marker and return its address, regardless of its
previous value. This is measured behavior outside the earlier95B04 valid-count
contract, not a claim that the natural library initializes with a negative count.

96BCE sets R3=0, executes RTS and stores0 at the pointer in R4 in its actual
96BD2 delay. It preserves R0/SR/PR/SP/MAC and other visible registers exceptR3.
Neither function calls a callback, BIOS service or device. No substitute callee,
MMIO mapping, alias or tick is introduced.

Selection cases cover every count0..24, every first-free position and full
outcome, all256 occupancy masks for eight slots, three tested negative counts,
three nonzero marker representations and two register/data/stack variants.
Duplicate tuples are removed. Release covers all24 positions, three prior word
values, both register variants and three data/canary seeds. Larger positive
counts and all possible32-bit words/bitmaps are not executed exhaustively.

Every actual case matches an independent full register/SR/PR/MAC/PC model,
exact original PC/delay trace, ordered reads/writes, full7,036-byte block output,
readonly neighbors/stack and all other mapped original bytes. A separate scalar
first-zero/store model checks the block and return value. Both routines preserve
the untouched stack and original file.

All seven original-copy controls have non-budget rejections: missing/wrong marker
store, wrong stride, lost full-table null delay, lost return-value delay, wrong
release clear value and missing release store delay. Budgets and guards remain
unchanged. Mutated private copies never replace the original source file.

## Execution bounds and natural projection

Selection uses the accepted separate1024 profile with a smaller explicit256
budget. Release uses the unchanged128 guard. The24-occupied-slot original call
also runs under the old128 guard: it retains128 recorded instruction executions,
CPU step-attempt field129, last recorded PC96BAA and interrupted PC96BAC, with
the actual budget refusal. This failure is retained in both selection reports;
it is not a failed full return or permission to weaken the old guard.

Accepted PR667's natural95E5A entry/return snapshots provide a separate matching
projection: library060BD92C, count16, sixteen zero active markers before the
call, returned pointer060BE58C (=library+C60), and only marker0 changing0→1.
The other fifteen active markers remain zero. The observer's extra positions
beyond count16 are neighboring samples, not additional active slots. This agrees
with selection semantics; the internal96B9C entry itself was not directly traced.

## Provenance, admission and continuation

Source6d1b20a9505345180110f85e9f2aef43920792ca was tested/pushed before original
execution. Six owned tests and411 research tests pass; owned fixtures do not
execute original game instructions. Frozen75-file source adapter:
`/home/dev/neptune-research-private/655/adapter-3e7e4952c0614649ee575d6865fdbd0c994b860d365498d9e72b8cd726cb7be9`.
Private batch:`/home/dev/neptune-research-private/655/slot-batch-hfgeci8y/batch.json`.
Reports reside outside Git on the volume under
`/mnt/HC_Volume_106574422/repo-factory/neptune-integration/neptune-research-private/655/`.
Worker/supervisor/test/source proofs remain in`/home/dev/neptune-evidence/code655-20261102/`.

The first08:10:14 request was deferred with all three foreign slots occupied.
Its receipt is retained in`slot-contracts-select-0kqyhzfc/`. Normal admission
opened during a bounded55-second wait; no foreign claim was cleared/adopted.
All four actual jobs used shared3, own180-second leases,60-second/nice10/
downward2GiB limits, offline networking, readonly sources/originals/dependencies
and hidden broker/credentials/authority. Own leases were released in finally.
No native build, provider dispatch, scheduler or allowance change occurred.

PR669's exact13-check acceptance and seven non-applicability receipts are retained
in`.../code655-20261102/pr669-acceptance-verified.json`; its merge tree/base match
the tested head/current main. Preserve other coordinator686/PR687 and all newer
owners. Keep655 open:96D74 calls real A5EEC and A681A, while95E5A also depends
on A56CA/A56D8 and96C60. Next recover those contracts and the composed95E5A
return without stubs.95CBC,A6790,969E0/BIOS and293A4 still need semantics;
continue root/task cycles and all other modules. Whole-function/module/dynamic-
target denominators and hardware/gameplay/Godot parity remain unresolved.
