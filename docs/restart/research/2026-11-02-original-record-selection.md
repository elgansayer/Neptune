# Original record selection, delta polls and bounded waits

Issue [646](https://github.com/elgansayer/Neptune-Bomberman/issues/646),
[PR648](https://github.com/elgansayer/Neptune-Bomberman/pull/648),
EXP-SAT-CODE-021. **All-original-code programme active, incomplete.**
Original6BE4..6D36 was exercised on7,736 constructed cases per run, twice.
All seven complete report pairs are identical:5,340 selected-task handoffs and
2,396 bounded incomplete waits per selection. No case is a normal function
return. Wait executions retain their actual failed status and instruction-cap
error; matching the selected contract does not turn them into completed code.
Natural scheduler/task roles, valid argument domains, simultaneous CPUs,
hardware timing and independent-engine validation remain open.

## Identity and recovered control flow

USA MK-81070 V1.003 resident KRNL, SH-2 mapping06006000; kernel SHA256
20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7.
Original execution source head3da95dc94ff07411fb2ef37ba3e0f2acaf80807a.
[Derived evidence](../evidence/2026-11-02-original-record-selection.json) pins
all nine imported sources and the three historical CPU sources at saturn-recomp
f20de940e8013fc84103a5b39c4069ed8071b1f9. No original binary or external CPU
implementation is bundled. Previously accepted61C4/61E6 and6B9C are real
callees here, reused rather than counted as new functions.

The original saves R14..R8, PR and MACL, allocates eight local bytes and calls
61C4 on the root context060BD020. Actual saved PR is6C00 and saved SP is
entrySP-44. The48-byte context duplicates R8 at+0/+4. A nested6B9C poll uses
another four stack bytes; the experiment compares64 controlled stack bytes.

Slot=(VBR>>10)&1 selects two-word arrays060B2D2C/060B2D34 and the current-index
header at26006018+4*slot. Array values initialize live26006040/26006044. The
index domain sampled here is FFFFFFFF or0..17. Search starts at0 forFFFFFFFF,
otherwise the next index with18 wrapping to0.

A word1 record with flag1 or3 is eligible. Flag2 is eligible regardless of its
word: copy record+12 to saved PR at+68, copy+16 to context+0 at record+32 and
the resume local, then store flag3. Other records advance the scan. The actual
6CB4 delay slot advances the pointer; wrap resets the index in6CBA and calls
the full original6B9C. Reaching the previous index ends that inner scan and
may invoke a second poll at6CC6. The previous record is then reconsidered.
For previous0/sole eligible0, the observed path examines18 records and polls
twice before selecting0. This is not a simple scan which permanently skips
the previous record.

On selection, write the selected index through26006018+4*slot and record pointer
through26006020+4*slot. Write the old live26006044 back to the selected word of
060B2D34, then load live values from record+20/+28. The array writeback is a
real transaction even where its value is unchanged. Reload record+0 from+4,
restore the original frame and tail-jump to61E6 with record+32 and resume value1
or the flag2 argument. The actual6D34 delay slot restores R14 before the context
restore loads the selected saved registers/SP/PR. Selected PR transfers to an
explicit non-executable task boundary; no unknown task code executes.

The [probe](../../../tools/saturn_lab/probe_record_selection.py) compares all
visible registers/SR/PR/MAC, exact PCs/delay slots, every transaction, full table,
root context, stack, readonly neighbors and unaffected original bytes. A separate
scalar search/delta/initialization model checks selection and table outputs.
The derivation reconstructs every actual root context from the original write
events and verifies its bytes/digest and saved PR6C00 in all7,736 cases.

## Actual results and retained incomplete executions

| Partition | Cases | Handoffs | Bounded waits | Handoff instructions/events |
| --- | ---: | ---: | ---: | --- |
|All positions/previous indices, slot0|2,052|2,052|0|168..481 /77..134|
|All positions/previous indices, slot1|2,052|2,052|0|168..481 /77..134|
|Field/initialization boundaries|576|288|288|168..188 /77..86|
|Every flag byte|1,024|12|1,012|172..192 /78..87|
|Delta/poll boundaries, slot0|864|468|396|611..885 /142..185|
|Delta/poll boundaries, slot1|864|468|396|611..885 /142..185|
|Stable no-eligible layouts|304|0|304|incomplete|

Each complete report has an identical repeat. SHA256 digests:

- positions0: e6575e00cf25e337d385969667bdcb7b2bf54430ca05dc09602221d735bc8922
- positions1: 907dc0673cb50527c785befa428eabff52a0471ee433c76864711366ab377da4
- fields: f98d9866aec4933ee58d11884f4ef40ac5ae9e7c8a9faf0a0a2d6d7175395346
- flag-bytes: 18ef4902a30cb5ab8491ab08e1d68e22d216debc6d69cac5d7f04ade64d844eb
- polls0: 99784f638888f58d4de000fc2bf0b535f74b657cf027055700002965727567a2
- polls1: 04403edcd11e529891cf7f20a19bcc3a0a203353054abe7d8d0549fc78f5f5b6
- waits: 4124bcc50d355cd99bc370965799b6d2057686ce2464c344702e35eab2ea3424

All18 positions, previous indices-1/0..17, both VBR slot values, all256 flag
bytes, words0/1/high unsigned values, argument boundaries and wrapping sample
deltas are covered. A real6B9C call can reduce a nontrivial word to1 and make
a record eligible after a full scan; selected cases examine up to36 records.
The sample is immutable during each constructed case. When no future delta or
eligible flag can arise, the original keeps polling. All2,396 wait cases retain
1,024 executed instructions,1,025 attempted steps, their actual guard error,
exact partial registers/transactions and unchanged canaries. No tick is injected,
no callee stubbed, and no wait dropped. This does not imply a deadlock in the
natural game, whose sample producer/interleaving is not modeled here.

The original128-instruction request is separately retained: case slot0,
previous-1, target17/flag1 fails after128 executed/129 attempted instructions,
with root PR6C00 and no completed return. The same declared case reaches its
task boundary under the explicit1024 selection profile. Counts are interpreted
instructions/data events, not Saturn cycles or a timing-parity result.

## Mutation controls and profile limits

All15 altered-original controls have semantic, transaction or permission
rejections independent of budget-only refusals:

| Mutation | Rejections/tested | Budget-only refusals excluded |
| --- | ---: | ---: |
|Wrong next-index increment|55/55|0|
|Missing initial wrap|9/55|0|
|Flag3 comparison becomes4|1/53|1|
|Flag2 comparison becomes4|1/53|1|
|Missing initialized PR store|2/55|0|
|Missing initialized argument store|16/48|0|
|Initialization stores flag4|2/55|0|
|Missing scan-pointer delay update|8/55|42|
|Missing wrap-index delay update|49/51|0|
|Missing selected-index store|55/55|0|
|Missing current-pointer store|55/55|0|
|Missing array writeback|55/55|0|
|Missing word reload|24/48|0|
|Missing R14 tail delay restore|55/55|0|
|Delta addition wraps a wait into ready|1/52|12|

The last mutation changes FFFFFFFF+2 into1 instead of subtracting, producing a
handoff where the unchanged original waits. First semantic/permission failures
and separate budget-only refusals retain actual traces/state/errors privately.
Unknown target/read guards are not converted into successful task transfers.

The new [selection profile](../../../tools/saturn_lab/sh2_selection_profile.py)
hash-checks accepted guard9d73ab349e27bc476700e111cf454f70b3ee2305ff354c82040ff0d39c5f4169,
changes only `MAX_STEPS=128` to1024 in a fresh namespace, and retains all of its
permission/CPU checks. Derived guard SHA256 is
d744a4235e5df6709adaf66a272abdc56b8ee2bd0413f2980aac5ae5fba11c21.
Older sources/globals/defaults remain unchanged; their129-instruction request
still rejects. Only explicit selected header views and known canonical RAM are
writable. Sample, other slot and array A are readonly; only the selected array B
word is writable. No device RAM or extra executable target is invented.

283 tooling tests,14 catalogue tests and actual pinned CPU authored-byte
coherence/25 guard/recovery checks passed. Source-only CI
[41488833293](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41488833293)
retains artifact13163266758 and digest in the derived evidence, explicitly
`original_game_bytes_executed:false`. It is separate from the14 original reports.
Private pairs/supervisor:
`/home/dev/neptune-research-private/646/record-selection-1c570c8y/`, under the
seven partition names above. Scripts/logs/CI receipts:
`/home/dev/neptune-evidence/code646-20261102/`.

All seven admitted families passed readonly repository/kernel/interpreter and
broker-hidden namespace checks;14 original workers exited0 without timeout,
cancellation or output truncation. Shared host limit3, own leases180seconds,
commands60seconds/nice10 and downward-only2GiB AS caps were retained. Own leases
released. No provider/model dispatch, foreign lease change, scheduler, quota reset,
continuity activation or paid fallback; #536 and other active owners stay open.
Account/CI spend is independently unknown.

## Next: actual natural context observations

An actual guarded no-media ABI probe checked the existing prepared observer
core0f14356da70ac8b88a8a1727e25acf6137be4ace453c37b1819d82222346faca,
recipe54cfecd0f16c98e1523854c8d293da4beb6a731dd09a9374c5cf0c43318ea2a2.
ABI2/128-record/4096-dispatch observer rejects6BE4,6D36,61E6 and leaves status
unchanged, while known B934 begin/stop works. It executes zero emulated frames
and is explicitly **not original-game evidence**. Retained proof:
`.../646/observer-capability-0ff501zo/`, digest
b287d1ac437315d705284e7ea14e96ad383faadb0fd237a873fb2a49c5cc11ce.

[Issue649](https://github.com/elgansayer/Neptune-Bomberman/issues/649) owns a
separate bounded context observer through the existing trusted provisioner and
matched core, preserving historical B934 tools/generations. First prove pipeline,
delay-slot, nonmutation and bound semantics on owned fixtures. Then prepare an
isolated generation and run actual reference/disabled/enabled original windows
twice, with identical source witnesses, inputs, canonical state and native
video/audio. Empty/overflow/incomplete windows must fail. Preserve master/slave,
clock/interleaving and scenario-identification limits; VBR slot is not physical
CPU identity. Natural contexts can then validate these contracts and expand
dynamic-target/module recovery.

Continue the larger root/task cycle, loader/slave/overlay/library, unresolved
68000/DSP and regional menu/save/network code. Whole executable/function/dynamic-
target denominators remain unknown. Neither this selection result nor the
complete original-code programme is finished.
