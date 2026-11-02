# Original first-task and library initialization: natural returning paths

**All-original-code programme active and incomplete.** Issue [660](https://github.com/elgansayer/Neptune-Bomberman/issues/660)
now has actual original execution through both named returning boundaries. Full
library semantics remain under [655](https://github.com/elgansayer/Neptune-Bomberman/issues/655).
The [derived evidence](../evidence/2026-11-02-first-task-natural-init.json) contains
identities, selected boundary scalars, hashes, comparisons and control results.
Raw states, records, BIOS and discs remain private on the VPS.

## Actual original execution

USA MK-81070 V1.003 KRNL, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
loads at06006000. Twelve fresh600-frame windows resume the same verified original
frame1200 boot checkpoint, with no Start pulse: two reference, two disabled and
two enabled runs for each profile. No callee returns, devices, ticks or RAM are
substituted. Each enabled run observes one complete root.

| Profile | Original entry and link | Actual entry/return frames | Records | Returned R0 | Pending native hooks |
| --- | --- | --- | --- | --- | --- |
| 1 | 89C8 from623A, PR6240 | 1247 /1264 | 44 | 0000001A | 4,012,829 |
| 2 | 95B04 from89C8, PR8A18 | 1247 /1264 | 24 | 0000001A | 4,007,492 |

Native hooks include fused-NOP delay hooks; these are neither original instruction
counts nor Saturn hardware cycles. Both traces remain within the unchanged
4,194,304-hook,120-pending-frame,128-record and depth16 limits. There are no
source mismatches, dropped records or observer errors. Complete named calls,
actual delay slots, callee entries/returns and the root RTS/stack restore delay
are validated, including original SP/R14/PR linkage.

The independently parsed imported/final state, every frame's native video and
audio, input polls/masks and source identities match exactly across all six runs
of each profile. Enabled trace files also match byte-for-byte within each pair:

- Profile1: `2719dde90a65dfe5020d4b93cd9ee9ce7774e820d5dfd1f5b489f36b8c050b3f`.
- Profile2: `fc09ea64cfa44689bb4957fc64378a65c27b0e1935139c95f13f56ab0712cae5`.
- Final state, all twelve: `54af2c95d530b7d34349406da8a37806d6472ac6caf27ac78b1b0ebc9fc4c799`.

Host wall observations are retained with two-run medians, without inferring a
performance improvement or hardware timing from their variation.

## Measured path and semantic limits

Natural95B04 receives R4=16, R5=060BD92C and descriptor060BF00C containing
`[1,32,060BF198]`. Its real BIOS06000344 vector resolves to060007C0; the call
receives R4=FFFFF7FF and R5=0 and returns R0=25FE00A0. Named original callees
96AC0, A6790,969E0 and96C60 all return.969E0 spans frames1247–1264 and returns
R0=1A;96C60 receives zero and returns zero.95B04 then returns1A to8A18.
These are observations of this path, not a recovered BIOS/device implementation.

The natural96AC0 snapshot agrees with the earlier independent scalar contract:
count16, the four original callback addresses, seven cleared header fields,
two cleared five-word tables and sixteen cleared marker positions. Other sampled
header words are preserved. Several fields were already zero, so this natural
sample cannot detect lost clears by itself; the prior constructed original-byte
cases supply those controls. The observer samples24 possible marker positions;
only the first16 are active slots here. Later positions can contain neighboring
data, including the descriptor, and are not mislabeled as extra active slots.

Natural89C8 calls89AC and the above95B04, then9696C with R4=060089C2/R5=0.
The sampled library callback field at+B8 becomes060089C2.95CBC returns19;
95E5A receives19 and returns060BE58C, which89C8 stores at060BF498.89C8's real
RTS at8A66 and restore delay return1A to6240. The numeric results do not yet
establish the complete roles or all possible behavior of these functions.

Twenty-one corruptions of each actual trace copy are rejected: target/link,
delay pipeline/opcode/PC, callee/return SP/PR, root restore stack/R14, record
order, frame order, dropped/partial/error status, false completion and an
independent source-witness mutation. All42 retain unchanged budgets. These
controls validate boundary evidence, not arbitrary internal data semantics.
Original inputs and accepted actual trace files remain unchanged.

Separately, the [one-state96C60 result](../evidence/2026-11-02-library-status-preliminary.json)
executes original callback-null status-16/input-5 twice:24 instructions and13
events each, returning/storing-25. An original-copy MOV-24 control changes the
semantic result on the same returning path. This is not broad callback coverage.

## Tool provenance and retained failures

Native observer PR663 merged `fed7932eaedd9728e6c06d877f37fd319d6356d6` after
all ten exact-head checks passed at44328ce, against current base8e30293. All six
real native preparation children passed. CI run41526580031/job125556000422
produced artifact13180950020, verified ZIP SHA256
`d42913ad21dc91e38c9a175fc9035556c32cdbfa00249550f1b87926b5d3e7f6`.
The native binary is083127e15f1d4844b774da83cff8403920706ebd520040ab4e68115000e7df2f;
recipe0a848d81731e35e6e2fa2bcdcd605b271c7fd4eed7a60df0c2fbac571e4085d2.
Corresponding GPL source/notices were verified. Two actual guarded local cache
reuse checks passed with a callback that refuses compilation. No VPS native
build occurred below the retained6GiB compilation reserve.

Driver source828beed was pushed after10 focused and322 research tests passed.
The frozen73-file adapter is
`/home/dev/neptune-research-private/660/adapter-9df9cab6045ea9a1bd31573b8ea35888582afe34656f42b29ce6feced37da6e7`.
Original runs use shared3, separate own180-second leases,60-second/nice10/
downward2GiB bounds, offline networking, read-only sources/media/tool and hidden
broker/authority key. All own leases are released; foreign owners are preserved.

The first strict driver failed before core loading: frame1200 has2426/2572
witness words, with the final146 A6790 words not yet loaded. A read-only audit
finds all2572 at1800. The correction permits only the verified preloader boot
checkpoint to have an incomplete initial witness. The original loader supplies
the code; native entry, every snapshot and final state still require every word.
The failed run and old frozen adapter remain retained. Earlier Xvfb/base-change
CI failures and admission deferrals also remain historical evidence.

Private resumable evidence:

- Batch:`/home/dev/neptune-research-private/660/natural-batch-ux_1k7qf/batch.json`.
- Validation:`/home/dev/neptune-research-private/660/natural-analysis-oanuuapm/validation.json`.
- Actual states/captures:`/mnt/HC_Volume_106574422/repo-factory/neptune-integration/neptune-research-private/660/`.
- Supervisors, source/test/CI proofs:`/home/dev/neptune-evidence/code660-20261102/`.

Next recover broader96C60/9696C contracts and the positive95B04 dependencies,
including BIOS/A6790/969E0 and95CBC/95E5A, using these natural arguments and
independent original-byte models. Keep655 open. Then continue623A/root cycles,
17F2, both SH-2s, loaders/overlays, sound/DSP and regional network/menu/save code.
Function/module/dynamic-target denominators and gameplay/hardware/Godot parity
remain unresolved; this observational slice does not complete the programme.
