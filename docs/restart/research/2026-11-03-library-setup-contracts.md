# Original library context setup, indexing and caller continuity

**All-original-code programme active and incomplete.** This continues
[655](https://github.com/elgansayer/Neptune-Bomberman/issues/655) after accepted
status PR669/b161880 and slot PR689/f46ad9d. The
[derived evidence](../evidence/2026-11-03-library-setup-contracts.json) contains
source/report/guard identities and retained original execution. Raw memory,
reports and originals remain private on the VPS.

| Selection | Cases per run | Complete returns | Unfinished handoffs | Original instructions | Controls |
| --- | --- | --- | --- | --- | --- |
| A5EEC initializer with real setters | 1,578 | 1,578 | 0 | 35 | 5 |
| A5F22 field56 setter | 1,628 | 1,628 | 0 | 6 | 4 |
| A5F2E field44 setter | 1,578 | 1,578 | 0 | 2 | 2 |
| A56CA index12 | 2,650 | 2,650 | 0 | 7 | 3 |
| A56D8 index24 | 2,650 | 2,650 | 0 | 8 | 3 |
| 96D74 null-object return | 210 | 210 | 0 | 13 | 2 |
| 96D74 positive prefix through initializer | 210 | 0 | 210 | 53 | 4 |
| Total | 10,504 | 10,294 | 210 | explicit64 budget | 23 |

All seven families run twice in fresh original CPU states. Each pair's full
report files match byte-for-byte. The original is unchanged USA MK-81070 V1.003
KRNL at06006000, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
The pinned f20de940 interpreter and all three source hashes are checked. Counts
are actual original instruction executions, not native observer hooks or cycles.

## Recovered contracts

A5EEC initializes a60-byte object at input R4 through the **actual original**
A5F2E and A5F22 calls. Fields0,4,8,12,16,24,28,32,36,40 and52 become zero;
20 and44 become1;56 becomes3. Field48 is untouched. It returns the object
address in R0, restores R13/R14/PR/SP through the real RTS delay and preserves
SR/MAC. Input R5 is overwritten and ends zero. The wider purpose of this
structure is still under library/caller investigation.

A5F22 returns the previous word56 in R0, stores input R5 there, sets R5 to zero
and clears words36/40. The word40 store is the actual RTS delay. A5F2E is a
two-instruction function storing R5 at word44 in its RTS delay; R0/SR and the
other registers are preserved. The tests distinguish previously zero words,
high-bit values and arbitrary canaries instead of assuming cleared input.

A56CA returns `(12*R4+R5)mod2^32`; A56D8 returns `(24*R4+R5)mod2^32`.
Both leave R3 equal to input R4 and preserve the remaining visible state except
R0/SR.T. For index12, final T is input R4's bit31; for index24 it is bit31 of
`12*inputR4 mod2^32`. The final base addition is in each real RTS delay and
does not replace that T result. Ordinary indices, wrap/sign boundaries, zero/
canonical/high-bit/all-ones bases and both initial SR variants are checked.

96D74 stores R5/R6 in its own frame before testing the next path. R4=0 returns
zero through the actual null RTS/restore delay, with SR.T=1 and saved linkage
restored. For nonzero R4, original A5EEC and both setters initialize the final
60 bytes at slot+108 within the168-byte constructed slot; the first108 bytes
and the nested initializer's field48 remain untouched. It then reloads the
original R5/R6 and executes JSR/delay toA681A with R4=slot+12, PR=96DA2,
SP=before-16, R14=slot and R0=slot+108.

The positive experiment stops at **non-executable A681A**. Its pending frame and
real call arguments are retained; no A681A instruction or fabricated return is
executed. This is a true original caller prefix and complete nested initializer,
not a complete positive96D74 or95E5A return contract.

## Comparison and controls

Every case checks all23 visible registers, full SR/PR/MAC, exact original PC/
delay trace, ordered data transactions, complete object/slot/stack bytes,
readonly canaries and every other mapped original byte against an independent
expected model. Separate scalar checks cover field results, untouched bytes,
saved-frame layout and modulo index formulas. The public derivation rechecks
each private result against the frozen model, including every region digest and
the positive handoff's argument/link/stack continuity.

The corpus crosses ordinary byte values and selected32-bit boundaries, two
register/stack variants, three canary patterns, old/new field words and original
caller argument combinations. Duplicate case tuples are removed. It is not
exhaustive over all32-bit inputs and does not establish natural interior caller
traffic or hardware/gameplay timing.

All23 family/control combinations have semantic non-budget rejections. Original
copies lose/change field/default stores, prior-field reads, multiplier/addend
operations, return/store/restore delays, caller offsets, descriptor reload and
saved PR. Controls include nonzero bases and boundary inputs. Source files stay
unchanged; accepted128 guard9d73ab34 and its permissions are unchanged. The
chosen64 budget is stricter than that maximum; no aliases/devices are added.

## Provenance, preserved admission and continuation

Sourcea5a38d7cd9bb94b9dadc610202f0e0427d5730b7 was tested/pushed before original
work. Ten owned tests and431 research tests pass. Owned fixtures also verify
retention of completed records when later cases/controls fail; they are tooling
checks and are not counted as original execution. Frozen76-file adapter:
`/home/dev/neptune-research-private/655/adapter-f1f824ec77452c13cf98a87dd6b53ae92d57532654be041a792986ad25a34542`.
Private batch:`/home/dev/neptune-research-private/655/setup-batch-y19gol2c/batch.json`.
Actual outputs are under the private volume655 directory; source/test/runner/
derivation receipts remain in`/home/dev/neptune-evidence/code655-20261102/`.

Two55-second waits initially deferred at index0. A live foreign factory daemon's
exclusive reservation was preserved. Once it legitimately released exclusivity,
the same manifest resumed with two foreign shared owners still present. Fourteen
jobs each acquired their own normal shared3/180-second lease and retained
60-second/nice10/downward2GiB, offline/read-only and hidden-authority guards.
All own leases released. No provider dispatch, native build, scheduler, allowance
change or reference repin occurred. Historical deferrals remain in the checkpoint;
they are not relabeled as CPU failures or counted as runs.

Next recover A681A's real9410C division,94268 remainder,A6DA6 format,A6FE0
context and A7F4E service dependencies, then compose actual complete96D74/95E5A
behavior. Independent ISA/math development has separate owned-only evidence;
it has not yet executed those original functions.95CBC,A6790,969E0/BIOS,
293A4, root/task cycles and other modules remain open. Whole module/function/
dynamic-target denominators and hardware/gameplay/Godot parity remain unresolved.
