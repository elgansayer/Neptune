# Original signed-index record-state transition

Issue [640](https://github.com/elgansayer/Neptune-Bomberman/issues/640),
[PR641](https://github.com/elgansayer/Neptune-Bomberman/pull/641),
EXP-SAT-CODE-019. **All-original-code programme active, incomplete.**
The original KRNL routine 06006DC8..06006DFE completed 8,256 selected cases,
twice each, with identical complete report pairs. Its natural caller/task role,
valid argument domain, hardware timing and independent-engine agreement remain
unvalidated. This is a selected CPU contract, not whole-module recovery.

## Identity and recovered contract

USA MK-81070 V1.003, resident KRNL, SH-2 mapping 06006000; kernel SHA256
20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7.
Original execution source head 6568c25a9185e8592f3f38e0172cd7b47578ed8f;
probe SHA256 ad5c7bfa0f2ae59ac41e84c1e57b0d252c02ffa5adcdb34cde36679a1ed079a9.
The [derived evidence](../evidence/2026-11-02-original-record-transition.json)
pins all imported adapters and the three historical interpreter sources at
saturn-recomp f20de940e8013fc84103a5b39c4069ed8071b1f9. No game binary or external
CPU implementation is bundled.

R4 is first compared with 18 as a signed 32-bit value. Values at or above 18
return FFFFFFFF without reading the record literal or any record. There is no
lower-bound check. Accepted arguments compute the record pointer as:

```text
060BC190 + signed16(88 * signed16(low16(argument)))   modulo 2^32
```

For example, FFFFFFFF accesses base-88, while FFFF8000 and 80000000 both access
base. Positive 00010000 rejects before any truncation. These constructed
negative-index accesses are observed original CPU effects, not claims that the
game naturally supplies valid negative record indices.

The byte at record+80 is loaded, zero-extended and compared with 1. Only flag 1
succeeds: store flag 2, clear the category byte at +81, return R0=0. Other flag
values return FFFFFFFF without changing the record. The routine pushes MACL and
restores it in either actual RTS delay slot, 6DF6 on success or 6DFC on failure.
SP, PR, MACH, GBR, VBR and all other untouched registers are preserved.

Successful calls finish R1=88, R2=2, R3=0, R4=record pointer and T=1. Accepted
indices with a non-1 flag finish R1=88, R2=record base, R3=18, R4=record pointer
and T=0. Upper-bound rejections preserve input R4 and initial R1/R2, with R3=18
and T=1. The executable [contract](../../../tools/saturn_lab/probe_record_transition.py)
compares all visible registers/SR, exact PC/delay paths, every data transaction
and complete controlled/original canaries. Separate scalar checks validate the
return and record output formula.

## Actual original results

| Partition | Cases/run | Instructions | Data events | SHA256 of either complete report |
| --- | ---: | --- | --- | --- |
|Every category byte|2,048|24|6|45d3b6888c26cffc18271070db75c750e3d19c76c0d30f5dc44ea49696e0d2f0|
|Every flag byte|4,096|18..24|4..6|8714d7bb8a27a5d4fff3517661e96f160b176700c92f238eef846b3dc3b6d0c2|
|Signed/index boundaries|2,112|7..24|2..6|f0eed42ebc82fc4be70b180a4b7859bbe77d3af77d5d5a0786f9b931d95fff07|

Per complete selection: 2,304 successful transitions, 5,280 accepted-index flag
rejections and 672 signed upper-bound rejections. All ordinary indices 0..17,
the bound at 18, larger positive values, signed extremes, low-word/product
truncation boundaries, all 256 flag/category bytes and two register/canary seeds
are covered. The 4,160 negative-index cases use explicit controlled records.
This is not an exhaustive 32-bit machine-state proof.

All ten altered-original controls were detected:

| Mutation | Rejected/tested |
| --- | ---: |
|Unsigned upper bound|19/69|
|Strict greater-than instead of greater-or-equal bound|2/69|
|Missing signed result truncation|7/69|
|Flag 0 comparison instead of 1|12/68|
|Flag 3 store instead of 2|4/68|
|Missing category clear|64/64|
|Missing success result|64/64|
|Zero failure result|57/69|
|Missing success MACL delay restore|4/68|
|Missing failure MACL delay restore|57/69|

The strict-bound and missing-truncation mutations make real undeclared reads
and are rejected by the memory guard; other controls show register/path or
transaction differences. No budget-only failure is counted as semantic proof.
Each control retains its first actual failed comparison, registers, trace and
transactions in the private report; public summaries link the complete report
digest. Explicit witnesses keep successful and signed-bound cases represented
when stride sampling would miss them.

## Isolation and retained evidence

Private immutable pairs and supervisor:
`/home/dev/neptune-research-private/640/record-transition-i6njrr01/`, folders
`categories`, `flags`, `indices`, each with fresh `run1.json`/`run2.json`.
Scripts, logs and CI evidence: `/home/dev/neptune-evidence/code640-20261102/`.
Every original worker passed readonly repository/kernel/interpreter and
broker-hidden namespace checks, then exited 0 without timeout, cancellation or
output truncation. Own execution/derivation leases were released.

Actual shared host limit 3, own leases 180 seconds, commands 60 seconds/nice10,
downward-only 2GiB address-space caps and local 64-instruction call cap remain.
Only a bounded record and stack are writable. Rejected indices map no record.
No aliases, devices or extra executable targets are permitted. Earlier records,
delta, context and strict memory adapters remain unchanged; the shared profile
SHA256 is 26c22576b6398b9f96a1f9b7a2407e4e400c634afcc82d3e916f6b99507087d5.
No provider/model call, scheduler, quota reset, foreign lease change, continuity
activation or paid fallback; #536 stays open. Account/CI spend remains unknown.

269 research tooling tests and 14 catalogue tests passed. Authored-byte tests on
the actual pinned CPU prove this entry profile's literal read, controlled write,
unknown/alias/code-access rejection, 8/64-instruction loop guards and fresh
recovery. Source-only CI
[41480752992](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41480752992)
retains artifact13158987522 and its digest in the derived evidence, explicitly
`original_game_bytes_executed:false`. It is separate from the six original reports.

## Next substantial caller

Selected source 6D36..6DAE calls original61C4 to save the active record's context
and original61E6 to restore the root context. Re-entry at the actually saved
PR=6D86 uses the resumed R0 value; nonzero continues to clear a CPU-indexed
pending word and return, while zero restores the root context again. Wrapper
6DAE..6DC8 returns immediately for a zero pending word or tail-enters 6D36 with
R4=1. This is a static continuation hypothesis, not accepted execution or a
natural scheduler capture.

The next experiment must retain the outbound handoff as incomplete, then feed
the actual original-saved context and memory into a separately declared original
61E6 resume. A nonzero resume should complete the activation through the real
6D36 epilogue; zero should hand off again. Use both VBR-bit10 CPU slots, precise
cache-through RAM permissions and actual delay slots. Do not fake a return from
61C4, replace a saved context with candidate output, execute an unknown root task,
or weaken existing readonly alias guards. A separate bounded handoff profile
must first prove coherent alias writes/reads and unknown-target refusal on
authored bytes. The plan and selected source are retained in the next checkpoint.

Continue full 6BE4 selection, natural callers, loader/slave/overlay/library code,
unresolved 68000 handlers/DSP and regional menu/save/network paths. Whole
executable/function/dynamic-target denominators remain unknown. Neither KRNL nor
the complete original-code programme is finished.
