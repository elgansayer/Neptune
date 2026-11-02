# Original library status handling and callback registration

**Programme active and incomplete; [655](https://github.com/elgansayer/Neptune-Bomberman/issues/655)
remains open.** [Derived evidence](../evidence/2026-11-02-library-status-contracts.json)
retains identities, counters, source/control hashes and private original reports.
This follows the accepted [natural initialization result](2026-11-02-first-task-natural-init.md)
in PR667, mergedb6a8e253b558b925439acb3225937a91d782f124. The bounded observer
issue660 is closed; whole library semantics are not complete.

## Actual original-byte results

USA MK-81070 V1.003 KRNL at06006000, unchanged SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
executes on the pinned f20de940 interpreter with all three source hashes checked.
Each family runs twice on fresh CPUs; full reports match byte-for-byte.

| Selection | Cases per run | Complete root returns | Unfinished callback handoffs | Instruction counts | Controls |
| --- | --- | --- | --- | --- | --- |
| 96C60 status/error | 4,256 | 3,156 | 1,100 | 24,26,27,28,29,31,33 | 8 |
| 9696C setter through real96C60 | 256 | 208 | 48 | 33,35,36,37,38,40 | 11 |
| Total | 4,512 | 3,364 | 1,148 | bounded by unchanged128 | 19 family/control combinations |

The status selection covers all256 sign-extended byte values, four wider status
words, zero/-5 arguments, additional32-bit argument boundaries, null/original
callback pointers, two register/stack variants and varied canaries/userdata.
The setter selection crosses eight status classes, both callback choices, four
userdata words and both register/stack/canary variants. These are constructed
high-RAM cases. They do not replace natural or hardware evidence.

Every case compares all23 visible registers, PC/SR/PR/MAC, each original executed
PC and delay marker, exact reads/writes, output bytes, readonly canaries, saved
stack and every other mapped original byte against an independent model. A
separate scalar model checks memory results. Complete returns include original
RTS/restore delay and SP/R13/R14/PR restoration, with MAC registers preserved.
Handoffs retain the actual saved stack and live call link instead.

## Recovered interface and unfinished callback body

96C60 reads the32-bit status word060FC080. Status-16 overrides input R4 with-25;
-14 overrides it with-2; -13 overrides it with-23. Other status values preserve
R4 modulo2^32, including status0. It stores the effective value at library+C0,
where library is read from060FA8BC. Zero suppresses notification. A nonzero value
loads callback+B8; a null pointer suppresses it too. Otherwise the actual JSR at
96CA2 passes R4=library+BC userdata and R5=effective value, PR=96CA6.

9696C stores input R4/R5 at library+B8/+BC, then BRA's into original96C60 with
R4=0 in the actual tail delay. A mapped global status can therefore trigger the
new callback immediately; registration does not imply notification is suppressed.

The naturally registered callback060089C2 is a trampoline: it loads060293A4 from
the original8BF4 literal, executes JMP at89C4 and NOP delay89C6. Nonzero callback
cases stop at the explicit **non-executable293A4 handoff**. No293A4 instructions
or fabricated return execute. At that boundary R3=293A4, PR=96CA6, R4=userdata,
R5=effective value, with the real twelve-byte saved root stack still present.
The293A4 body and other callback targets remain unresolved. Null and zero-value
paths have genuinely complete root returns; non-null notifications do not.

The first source incorrectly treated89C2 as return-only. Actual execution stopped
at its undeclared literal read in
`/home/dev/neptune-research-private/655/status-contracts-status-ut54_sdh/`.
Report SHA256e8eb01ef2e93e17f120b37e6578564a078ae5b82bae2fe926924231a8d5f90e3,
source5472a4f and the immutable defa0101 adapter remain retained. Disassembly
established the real trampoline; the correction declares its original literal,
three instructions and unfinished terminal. The accepted128 guard is unchanged.
This corrects an erroneous semantic assumption without claiming callback completion.

All nineteen family/control combinations reject at least one semantic mutation
without a budget failure. Controls change the three mappings, input/error-store
delays, callback userdata/tail delay, root restoration and setter stores/tail
argument. Originals remain unchanged. These tests do not certify arbitrary
callback or device behavior.

## Provenance and continuation

Corrected sourcefd70b1a91c2b78521455b6e9fb8e6073d3e39858 was tested and pushed
before the accepted jobs. Six owned tests and328 research tests pass. Owned
fixtures are tool tests, not original-game evidence. Frozen74-file adapter:
`/home/dev/neptune-research-private/655/adapter-4e70144aae913108299c69616b9be096b4655f2e206ff5f93a17c5f66c6f83fe`.
Private batch:`/home/dev/neptune-research-private/655/status-batch-60tks8xc/batch.json`.
Supervisors/workers and logs:`/home/dev/neptune-evidence/code655-20261102/`.

Each original job uses normal shared3 admission, its own180-second lease,
60-second/nice10/downward2GiB limits, offline networking, read-only sources/
originals/dependencies and hidden broker/credentials/authority. All own leases
are released. No native build, provider dispatch, scheduler or allowance change.

Next continue the positive95E5A path: real96B9C slot selection,
then A56CA/A56D8 and other measured callees; retain its full error/callback
dependencies.95CBC, A6790,969E0 and BIOS behavior also need semantic recovery.
293A4 remains a separate error-path target. Then continue623A/root cycles and
other modules. Whole function/module/dynamic-target denominators and hardware,
gameplay and Godot parity remain unknown; no programme completion follows.
