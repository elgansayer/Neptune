# Original paired table-helper caller prefix

[Issue630](https://github.com/elgansayer/Neptune-Bomberman/issues/630), under
#483/#482/#492/#464. The [derived receipt](../evidence/2026-11-02-paired-table-caller.json)
records the original-byte experiment, source hashes, complete declared input
coverage, repeatability, altered-copy controls and its limits. This extends
[the naturally observed helper pair](2026-11-02-original-call-observer.md).
It does not establish whole-program recovery or Saturn/Godot parity.

## Recovered prefix contract

The original USA kernel entry `0600BAC4` saves five registers and PR, then reads
unsigned bytes at `060C029C` and `060C029D`. If the first byte is at least nine,
it writes zero to both. It passes the resulting pair to the complete original
helpers `0600B934` and `0600B950`, executing their actual calls, returns and delay
slots. With resulting bytes `n,m`, the computed addresses are:

```text
first  = 0x00207f74 + 152 * (10*n + m)
second = 0x060b30c4 +  16 * (10*n + m)
```

The prefix stops at `0600BAFA`, immediately after the second helper returns and
before that instruction executes. This is deliberately **not a caller return**:
SP remains 24 bytes below its initial value, PR is `0600BAFA`, `r14` holds the
first pointer, and `r0` the second. `r13` still holds the first global's address;
the next original instruction would replace it with the second pointer. The
remaining caller and its external dependencies are unexecuted here.

All 65,536 constructed byte pairs passed in each of two fresh interpreter
processes. There are 2,304 paths of 50 instructions and 63,232 reset paths of 52,
for 3,403,264 executed instructions per run. Those counts include every executed
delay slot; they are not Saturn cycles or video frames. The second byte is not
clamped to nine in this prefix. Its valid natural domain and the table meanings
remain unknown. Neither pointer is dereferenced before the declared stop.

The comparison checks all declared registers/SR/PR/MACL, the seven exact stack
writes and MACL read, conditional global writes, five global reads, actual callee
arguments/return contexts and complete ordered PC paths. The stack and 32-byte
global-data window are explicit constructed writable overlays. The latter is
carved out of the kernel image without overlapping memory regions. Other mapped
original code/literals and unaffected data/stack bytes remain unchanged.

## Original execution and negative controls

The kernel is the accepted 786,432-byte USA MK-81070 V1.003 file, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
All three files of `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`
were hash-checked before loading. Both reports are byte-identical, SHA256
`19624979a396ffb235e31f5401f3c3e4557759fe4d950a91655dcf6d45630620`;
full observation digest is
`4a5805a83eccfafc5b59582d7babe3509a67b2d7194364022377d28348310ec7`.

Each run also executed five private altered copies: threshold ten, reversed
reset branch, missing second-byte reset, changed first-call delay action and
second-table base plus four. Each reached a terminal comparison and failed the
register contract. Budget/timeout/isolation failures cannot pass these controls.
The original input was read-only and was never replaced with an altered copy.

The guarded processes ran offline with read-only input/code/dependency mounts
and hidden provider credentials, broker and signing authority. Bounds were 1GiB
address space, 150 CPU seconds, 180 wall seconds and 2MiB output-file size per
process. Observed run durations were 43.292 and 44.420 seconds. No model call or
new allowance was used. This shared interpreter lineage is not an independent
emulator or hardware oracle.

## Relation to the prior natural call

A separate derived cross-check reloads the accepted #597 trace with SHA256
`c8dda8b2cb04166b8ad96f54fd916299364bf046c25dd9ae3034a0ecac937194`.
Its frame34213 master entry has arguments `(0,0)`, PR `0600BAEE`, and return
`00207F74`, agreeing with this prefix's first helper contract. The original
caller's static BSR lead is at `0600BAEA`.

This is no new natural capture. The old trace does not observe the second helper
or the whole prefix and does not reveal whether the initial global bytes were
zero or were reset. The scene, table purpose, full caller ordering and natural
argument distribution remain unverified. Do not label this campaign/battle
identification or a gameplay implementation result.

## Reproduce and continue

```sh
python3 tools/saturn_lab/probe_table_caller.py \
  --kernel /PRIVATE/accepted-usa/0KRNL.BIN \
  --saturn-recomp /PINNED/saturn-recomp-f20de94 \
  --report /PRIVATE/new-original-caller-report.json
python3 tools/saturn_lab/check.py
```

Use the existing shared host admission and guarded offline execution for the
first command. It refuses to overwrite an existing report. The second runs owned
input/contract-fence tests and does not rerun the private original. Match the
executed probe/source hashes in the receipt, use two fresh report paths, and
compare the complete reports.

Private evidence is under `neptune-research-private/630/original-002` and
`neptune-evidence/caller-prefix-20261102`. `original-001` remains a real failed
180-second admission wait, before any original execution. A bounded read-only
wait later observed empty admission and dispatched exactly one fresh guarded
attempt; no live reservation was cleared or declared stale. That wait exposed
separate recovery issue#632. Keep manual enrolment/restart#536 and the complete
code programme open. Next cover the caller's remaining original dependencies,
additional natural contexts and its table/state role, preserving other owners.
