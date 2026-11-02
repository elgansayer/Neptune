# Original context handoff and saved-context resume

Issue [643](https://github.com/elgansayer/Neptune-Bomberman/issues/643),
[PR644](https://github.com/elgansayer/Neptune-Bomberman/pull/644),
EXP-SAT-CODE-020. **All-original-code programme active, incomplete.**
Original 6D36 and its pending wrapper 6DAE were exercised in 2,400 staged cases
per run, twice, with identical complete report pairs. Each selection contains
2,016 complete activation returns and 384 repeated incomplete handoffs.
Constructed context/resume inputs are not natural scheduler captures, unknown
task execution, simultaneous master/slave execution or timing validation.

## Identity and original effects

USA MK-81070 V1.003 resident KRNL, SH-2 mapping 06006000; kernel SHA256
20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7.
Original execution source head f519dbc4b4872f9a8996acc34b9b34b2b9e3b785.
The [derived evidence](../evidence/2026-11-02-original-context-handoff.json)
pins each imported adapter and all three historical CPU sources at saturn-recomp
f20de940e8013fc84103a5b39c4069ed8071b1f9. No game binary or external CPU
implementation is bundled. Accepted context61C4/61E6 are real callees here;
their prior recovery is reused, not counted as new code.

For slot=(VBR>>10)&1, original6D36 reads the current record pointer through
26006020+4*slot. It stores input R4 at record+0 and +4, reads live26006044 and
stores it at record+28. It then calls original61C4 with record+32 in the actual
6D84 delay slot. The saved context contains real PR=6D86, SP=entrySP-16,
R13=26006020, R14=1, the preserved R8..R12 and MACH/MACL. The stack contains
the original caller PR/R13/R14 and input argument.

The real save returns zero.6D36 then loads the saved argument into R5 and calls
original61E6 on the root context at060BD020. That restore transfers to the
declared external root target. This is an **incomplete outbound handoff**, never
a completed function return. No root task code is executed by the experiment.

A separate declared resume enters original61E6 with R4=the actual saved context
and controlled R5. The original restore consumes the context written in the
first phase and transfers to its real saved PR=6D86. Nonzero R5 becomes R0 in
the restore's RTS delay slot, so6D36 continues at6D94: clear pending26006028+
4*slot, restore original stack/PR/R13/R14, then return to the caller. The actual
6DAC RTS delay slot restores R14. Final R0=26006028, R1=26006044, R2=4*slot,
R3=0, R4=original R8, R5=resume value and T=0. R8..R15, PR, MACH/MACL, GBR/VBR
and other untouched state match the recovered contract.

Zero resume instead reloads the original argument from the saved stack and
restores the root context again. Pending stays unchanged and the activation
remains incomplete. The outbound R0 is the original effective argument, which
need not be zero. Wrapper6DAE reads the selected pending word; zero returns
directly, while nonzero tail-enters6D36 with R4=1 in the real6DC2 delay slot.

## Actual staged evidence

| Partition | Cases/run | First phase instructions/events | Resume instructions/events | Final outcome counts |
| --- | ---: | --- | --- | --- |
|6D36 argument/live/resume boundaries|1,152|82/42|33..43 /17..27|864 resumed returns;288 repeat handoffs|
|6DAE pending wrapper|384|11..93 /2..44|33..43 /17..27|96 immediate returns;192 resumed returns;96 repeat handoffs|
|Every record position|864|82/42|33/17|864 resumed returns|

All three full report pairs are byte-identical:

- yield: c0e93f5f9f7864cabd3de5622cfd1b6b39fc6dce6b766c6e3136335664a27bb0
- wrapper: db329ed067f447053c71404feabf66fbc613edb8654fe53941844c3e11a597d5
- records: d0bf1a1095596d1502aeb80f304738be4b231d40072f8f1b4701c8a87adc33be

Every selection has 96 immediate wrapper returns, 2,304 initial incomplete
handoffs, 1,920 complete resumed returns and 384 repeated incomplete handoffs.
Both VBR bit10 values, all18 record positions, 12 argument boundaries, high
unsigned live/resume/pending values and two register/canary seeds are covered.
Counts are interpreted SH-2 instructions/data transactions, not hardware cycles.
The two phases have separate bounded entries; no arbitrary intermediate
instruction is treated as a completed return.

Actual saved-context continuity is checked in all2,304 resumed cases. The
derivation reconstructs all12 context words from the original first-phase
write events, compares their bytes/digest with the retained saved context, and
checks every second-phase restore read against those bytes. Saved PR is6D86.
The executable [probe](../../../tools/saturn_lab/probe_context_handoff.py) builds
resume inputs from actual first-phase registers/memory, never expected-model
buffers. Independent scalar checks validate the record fields and saved layout.
Every visible register/SR, PC/delay path, transaction, readonly neighbor, record,
stack and unaffected original byte is compared. No native callee is stubbed and
no return result is injected into an executing routine.

## Negative controls and permissions

All ten altered-original controls were detected:

| Mutation | Rejected/tested |
| --- | ---: |
|Missing record+4 argument store|66/66|
|Missing record+0 store|66/66|
|Missing record+28 live word|66/66|
|Missing context+32 delay argument|66/66|
|Wrapper supplies argument0|50/66|
|Wrapper inverts pending skip|66/66|
|Missing pending clear|68/68|
|Missing epilogue R14 delay restore|68/68|
|Missing context PR restore|68/68|
|Missing context result delay|68/68|

Omitting PR restoration enters an invalid caller continuation with root context
state and triggers an undeclared alias/read guard. Other controls produce exact
transaction, register or boundary differences. Each first rejection retains its
actual phase, trace, registers, error and transaction evidence privately. No
instruction-budget failure is counted as semantic proof.

A separate [handoff profile](../../../tools/saturn_lab/sh2_handoff_profile.py)
permits only the selected slot's current-pointer read, the live-word read and
the selected pending-word read/write alias. All have explicit canonical high-RAM
backing; the native pinned Memory performs the fold after permission checking.
The other slot is readonly and compared. Root context is readonly; only the
selected record, pending word and bounded stack are writable. Root SP is loaded
as data and left unmapped. Original instructions/literals are readonly; only
61C4..620A and6D36..6DC8 execute. The external outbound stop is non-executable
data, distinct from the fixed return sentinel. Previous profiles remain
byte-identical, including the readonly alias guard.

Authored-byte pinned CPU tests prove coherent alias-write/canonical-read/alias-
read for both slots,25 access/configuration/8-or-128-instruction guard controls,
non-executable handoff classification and fresh recovery. Source-only CI
[41484021707](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41484021707)
retains artifact13161765639, SHA256
4b19623292162733f05c7a20f71d0f7fce4aa6225e85066cd23d53b5099afa83,
explicitly no original game execution.275 research tests and14 catalogue tests
passed; they are separate from the six original reports.

## Isolation, receipts and continuation

Private report pairs/supervisor:
`/home/dev/neptune-research-private/643/context-handoff-wmqkij6q/`, folders
`yield`, `wrapper`, `records`, each `run1.json`/`run2.json`.
Scripts/logs/CI receipts: `/home/dev/neptune-evidence/code643-20261102/`.
All six final original workers passed readonly repository/kernel/interpreter and
broker-hidden namespace checks, then exited0 without timeout, cancellation or
output truncation. Own execution/derivation leases released. Actual host shared3,
own leases180seconds, commands60seconds/nice10 and downward-only2GiB AS caps
retained. The new target has a local128 instructions per phase; prior target
profiles/caps are unchanged. No provider/model call, foreign lease change,
scheduler, quota reset, continuity activation or paid fallback. #536/642 and
account/CI spend remain open/unknown as applicable.

Next is original6BE4 selection: root context save with real PR6C00, round-robin
18-record search, flag2 initialization, selected context restore, header/array
views and actual6B9C polls. Retain a bounded no-eligible/equal-sample wait as
incomplete. Never inject a clock tick, stub the delta call or weaken the existing
128-instruction handoff profile. Derive an explicit new selected-function profile
within current research limits. Actual saved root data may then support a larger
constructed selector/yield cycle; it still cannot establish natural task code or
hardware timing. See the next checkpoint's retained selected source and plan.

Continue natural runtime callers, loader/slave/overlay/library code, unresolved
68000 handlers/DSP and regional menu/save/network paths. Whole executable,
function and dynamic-target denominators remain unknown. Neither these context
paths nor all original game code are complete.
