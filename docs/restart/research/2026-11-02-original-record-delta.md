# Original kernel18-record delta update

Issue [635](https://github.com/elgansayer/Neptune-Bomberman/issues/635),
EXP-SAT-CODE-017. **All-original-code programme active, incomplete.**
The original USA KRNL routine06006B9C..06006BE4 returned correctly on7,568
constructed cases, twice each, using unchanged original instructions. This is a
complete selected CPU routine contract; its natural clock/task/gameplay role,
hardware timing and independent-engine agreement remain unvalidated.

## Identity and recovered contract

USA MK-81070 V1.003, resident KRNL, SH-2 mapping06006000; kernel SHA256
20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7.
Original execution source head7b0302efc781211d3780fa281e588ccad85d7731.
The [derived evidence](../evidence/2026-11-02-original-record-delta.json) pins
each imported source and all three historical interpreter files at
saturn-recomp f20de940e8013fc84103a5b39c4069ed8071b1f9. No third-party CPU source
or original binary is bundled here.

The routine reads current through26006038, with canonical RAM backing06006038,
and previous at060BD050. Equal samples return without reading the table or
storing previous. Otherwise delta=(current-previous) modulo2^32, and all18
stride88 records at060BC190 are visited. A zero byte at+80 skips the word read.
For nonzero flags, words0/1 remain unchanged. Words greater than1, compared
unsigned, become max(1,old-delta), with delta also unsigned. Finally previous
becomes current, even when all flags are zero. Both comparisons are unsigned;
e.g. current1/previousFFFFFFFF gives delta2, and active word80000000 becomes
7FFFFFFE. Delta80000000 with that word instead clamps to1.

R14 is pushed atentry and restored in the RTS delay slot6BE2. PR, MACL, MACH,
GBR, VBR, SP and other untouched registers are preserved; final T=1. Equal
samples leave R2=previous address, R3=raw sample address, R4=previous value.
Changed samples finish R0=80, R3=previous address, R4=table+18*88, R5=1, R6=0,
R7=delta. R1/R2 retain the last path's intermediate values. The executable
[contract](../../../tools/saturn_lab/probe_record_delta.py) checks every visible
register, exact transaction and PC/delay slot, alongside a separately evaluated
scalar output formula. The original routine makes no substituted calls.

## Actual execution evidence

| Partition | Cases/run | Instructions | Data events | SHA256 of either complete report |
| --- | ---: | --- | --- | --- |
| Sample boundaries |576|9..315|6..87|c7eddafc57b7ba29db78f3a9667258ed51dbc65326b72ee67502622f8e3042b1|
| All18 records/masks/word patterns |6,480|9..343|6..99|65e91af528b202e99e096cb746d3910908f5f5dc0f220142b302a935d09ea9a0|
| Every flag byte, two register seeds |512|163..343|27..99|274f2c3e252be54b06fb4ab94860e7d691704bbd80a10a107fcd9bd610fdb2d7|

Every report pair is byte-identical. Per complete selection,1,128 cases take
the real equality return, and6,440 execute all18 iterations. Inputs cover
32-bit sample/wrap/sign boundaries, unsigned deltas0/1/2/7FFFFFFF/80000000/
FFFFFFFF, words0/1 and high unsigned values, every individual active position,
all-active/all-inactive tables, all256 flag bytes and two register seeds.
These are selected cases, not an exhaustive32-bit machine-state proof.

All nine mutated-original controls were detected across193 selected cases each:
addition107, missingR14 delay restore193, missing equality skip17, missing
subtraction delay store110, seventeen-record loop176, signed delta comparison108,
signed first comparison110, adjacent undeclared alias193, zero floor/threshold176.
Eight detect semantic/path/transaction differences; the adjacent alias control
proves the explicit access guard. No instruction-budget failure is counted as
a semantic rejection. Unchanged bytes in all controlled records, saved stack
canaries and all other mapped original segments were compared exactly.

## Alias boundary, isolation and retained history

The new [profile](../../../tools/saturn_lab/sh2_profile.py) declares only the
four-byte readonly logical26006038→canonical06006038 read alias. Translation
is performed by the unchanged pinned Memory implementation, after permission
checking. The canonical sample is an explicit four-byte controlled input overlay
inside the mapped kernel header. It is readonly during original execution;
table, previous and bounded stack are the only writable regions. No device
register is represented as RAM. Original executed code and literals cannot be
overlaid. Accepted629 probe SHA256 remains
33f929226175dc00195ea0609c3e2658f70b27c659922d6b9f802e61d78034d3;
its older alias guards and defaults were not changed.

Authored-byte tests run on the actual pinned CPU prove canonical-write/alias-read/
canonical-read coherence in a separate writable fixture, then reject readonly
sample writes, alias writes, adjacent/overrunning aliases, code reads/writes,
alias instruction fetch and invalid alias configuration. Loops stop at8/1024
executed instructions, followed by a fresh successful run. Source-only CI run
[41476199167](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41476199167)
retains artifact13156818200, SHA256
548a376f9186ed1f98fc25add66be1bdfaeb7eaeaeb7b0786931bfc9ab52bccc,
explicitly `original_game_bytes_executed:false`. It is separate from the six
actual original reports. Local checks passed259 research tests and14 catalogue
tests; these are tooling/metadata checks, not game parity.

Private boundary reports and the retained partial admission timeout:
`/home/dev/neptune-research-private/635/record-delta-5a_rh8lu/`.
After the boundary pair, another owner acquired exclusive host capacity; the
finite120-second wait stopped without running the remaining cases or touching
that owner. After normal release, only missing partitions resumed in
`.../635/record-delta-5t5n2gh0/`. Supervisors and stdout/stderr receipts retain
both stages. Scripts and CI artifact live in
`/home/dev/neptune-evidence/code635-20261102/`.

Shared host limit3, own leases180seconds, each command60seconds/nice10,
downward-only2GiB address-space caps and1024 instructions per call were retained.
Actual namespace checks proved repository/kernel/interpreter readonly and broker
storage hidden. All six workers exited0 without timeout, cancellation or output
truncation; own leases were released. No provider/model call, scheduler, foreign
lease change, quota reset, continuity activation or paid fallback. Account/CI
spend remains independently unknown; #536 stays open.

## Continue original code

Static selected instructions in6BE4..6D36 call6B9C at6CB8 and6CC6, and reference
context save61C4 and restore61E6. The caller selects records using VBR bit10,
cache-through RAM views and a tail context restore. This is a source lead, not a
natural capture or a complete caller contract. Its write aliases and context
targets need their own bounded profiles; do not broaden this readonly profile
to execute it blindly.

Selected61C4..61E6 appears to save a48-byte context with duplicatedR8 at+0/+4;
61E6..620A restores saved SP/PR/MACH/MACL and returns R5 in the RTS delay slot.
Validate those original routines next before the caller. Also selected6DC8..
6DFE appears to accept signed indices below18, change flag1→2 and clear+81,
preserving MACL. Its missing lower bound and signed16-bit product truncation
need explicit negative/high-index contracts. Neither lead is accepted execution.

Keep unresolved sound handlers/DSP, natural callers, loader/slave/overlay/library,
menu/save/network/Japan code and unknown executable/function/dynamic-target
denominators open. This result completes neither KRNL nor the whole programme.
