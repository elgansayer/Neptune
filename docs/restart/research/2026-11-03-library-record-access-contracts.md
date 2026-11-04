# Original record access and overlap-aware byte move

**All-original-code programme active and incomplete.** Six guarded original jobs
complete13,936 returns/run twice, with three identical full raw/archive pairs and
11 non-budget semantic mutation-control combinations. Read the
[derived evidence](../evidence/2026-11-03-library-record-access-contracts.json).

| Entry/selection | Cases/run | Original instructions | Controls |
| --- | ---: | ---: | ---: |
| 949E0 byte move | 4,896 | 4–302 | 3 |
| 95D34 record-name pointer | 3,400 | 41–69 | 4 |
| 95D9C descriptor copy | 5,640 | 40–157 | 4 |

Original identity is unchanged USA MK-81070 V1.003 KRNL at06006000, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
The pinned f20de940 interpreter and its three source hashes are checked per job.
Counts are original instructions, separate from physical cycles/native hooks.

949E0 receives destinationR4, sourceR5 and unsigned byte countR6. Equal pointers
skip every copy, returning the destination through the actual MOV return delay.
Otherwise unsigned destination<source selects forward bytes; destination>source
selects backward bytes. The chosen direction preserves the sampled overlapping
input as a snapshot copy would. Zero count reads/writes no source/destination
bytes, including the unequal-pointer paths. Selected counts0..32/48, four byte
alignments, negative/positive relative offsets and identical pointers exercise
both directions, zero lengths and signed source-byte loads. Scratch pointer/
register/fullSR effects, every ordered transaction and untouched bytes are checked.

95D34 receives a signed record index inR4. It obtains the library through060FA8BC
and header at library+98. Nonnull table and mode **exactly1** are required;
otherwise original96C60(-8) executes and the root returns0. A nonnegative signed
index below the populated count at header+12 is required; otherwise96C60(-9)
executes and the root returns0. A valid index calls realA56D8 for24-byte indexing,
saves the actual record pointer and calls96C60(0). Negative effective status
returns0; otherwise the result is recordpointer+12. Actual linkage restores and
root restore delays execute on every selected return.

95D9C receives indexR4 and destinationR5. Null table or invalid signed index tail-
calls96C60(-10), returning its effective error. A valid index uses realA56D8's
24-byte stride only when mode equals1; tested other modes0/2/FFFFFFFF use real
A56CA's12-byte stride. It passes the actual selected record to real949E0, copying
its **first12 bytes**, then tail-calls96C60(0) and returns that effective status.
Those bytes are the record prefix, distinct from the24-byte record's name field.

The valid copy completes before status reporting, including when global060FC080
maps to a negative result. Status-16/-14/-13 maps to-25/-2/-23; other selected
words preserve the input. Effective code is stored at library+C0.95D34 returns0
for such negative status, while95D9C returns the effective negative word. Callback
+B8 is explicitly null. This mode rule is **different from95E5A**: its earlier
selected mode0 used12 bytes and tested nonzero modes used24. No common SDK/API
rule is inferred from adjacent entries.

Record cases cover constructed counts0/1/4/24/26/-1/INT_MIN, valid/last/outside/
negative indices, five mode/null-table selections, five status words, two register/
stack variants and two canary seeds. Descriptor destinations are separate or
at offsets-4/0/4/12 from the selected source, with explicit writable bounds.
Whole source/destination/library/stack bytes and unaffected neighbors are checked;
independent scalar snapshot/index/status calculations are rechecked against every
retained row. Input tables remain unchanged outside the precise copied12 bytes.
All23 registers/fullSR/PR/MAC, exact PC/delay trace and ordered accesses match.
No service or callee return is substituted, and no original native frames are added.

Source6fc5954 passed7 focused/484 full research tests before originals; normal
accepted-main integration preserves all82 source files in execution head
`dab7e591f01a6a8431c2dc33f66fc1afbf391bfd`. Frozen adapter:
`.../655/adapter-73d6ea9d9c05d97d9119f15a695d9b38f394a0c4fd73c912f1c08a10023429ae`.
Completed manifest:`/home/dev/neptune-research-private/655/record-access-batch-zsy5mro9/batch.json`.
Actual old128 refusals remain for move/descriptor copy. The original128 guard and
accepted separate1024 profile are unchanged; chosen budget512, actual maximum302.
Data/literal islands and unrelated functions are excluded from executable ranges.

Raw reports and supervisor/isolation receipts remain private lossless archives,
with raw/archive/source hashes and`gzip -dk report.json.gz` restore. The derivation
is`/home/dev/neptune-evidence/code655-20261102/derive-record-access-contracts.py`.
Owned sizing reads no original kernel and executes no original instructions;
positive lists plus6MiB allowance stay below64MiB. All six actual jobs pass the
existing shared3/180-second/60-second/nice10/2GiB/64MiB/offline/read-only guards,
5GiB+64MiB storage reserve and hidden authority checks. All own leases released.
No provider, native build, scheduler or allowance changes; preserve active owners.

Next inspectA780A cleanup, A7BB0 request fields, A7C20 polling andA81FE deadline
stores. The newly retained static windows identify furtherA85E4/A805C/service
calls; they are not executed evidence or substituted success. Successful95E5A/
context services, callbacks, complete89C8/root cycles, further modules and all-code
denominators remain open. No hardware timing, gameplay or Godot parity claim.
