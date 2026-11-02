# Original SND and XBSND table-byte setters

Issue [#619](https://github.com/elgansayer/Neptune-Bomberman/issues/619), under
#483/#488/#480/#464. Complete original leaves51F0 and520E now pass **9,136 cases
twice per module**, separately loading SND and XBSND from their pinned containers.
All four reports succeed; each module's two reports are byte-identical. The
modules' result rows also match. This validates two leaf semantics across two
source identities; it does not imply recovery of either full module.
[Derived evidence](../evidence/2026-11-02-original-shared-setters.json).

## Sources and recovered behavior

USA MK-81070 V1.003 SND is the accepted sound slice of `BOMSS/PROGRAM.BIN`,
container offsets44..6418hex. XBSND is the slice of `XBAND/XBAND.DAT` at
11868..17C3Chex. Full containers are independently hash-checked before slicing;
identities are retained in the reports. Both25,556-byte driver slices hash to
`c8842cc957bf82693ddd72d996353c9cb92feb34fe5f2834c0651aebacb4bd04`.
Execution uses each original slice directly, at sound68000 mapping0 candidate,
with distinct shared/XBand lifetimes. No instruction is relocated or patched
on positive runs. NLSND is a different driver and is not assigned these entries.

The complete even-lane leaf `[51F0,520E)`:

1. Save D0/D2/A0 with MOVEM.L on the original caller stack.
2. Set A0=0780, read byte A6+2 into D0.low8, clear D2 and load byte A6+1 into it.
3. Double D2 as a word and write exactly one byte at0780+2*index.
4. Restore D0/D2/A0 and return through the real sentinel.

The complete odd-lane leaf `[520E,522C)` has the same sequence with A0=0781 and
payload read at **A6+3**. Thus adjacent bytes of each indexed two-byte table
entry are written by different input payload fields. Every index0..255 stays
within0780..097F; no word/longword table write occurs. Their calling protocol and
the natural table meaning remain unknown.

All D/A registers are preserved, apart from SP advancing4 through RTS. Final
CCR has N from payload bit7 and Z iff payload0, with V/C/X clear: the word index
double clears X, and the final MOVE.B changes N/Z/V/C. MOVEM and RTS do not
restore incoming CCR. Initial supervisor/mask bits remain. The probe checks all
registers and SR, actual nine-instruction paths and all13 data events, including
predecrement MOVEM's low-word/high-word transactions and longword restores.

Only three RAM regions exist: a four-byte descriptor,512-byte table and16-byte
stack/sentinel area. The unused payload byte is the complement of the selected
payload, so choosing the wrong field cannot silently pass. All untouched table
bytes, the opposite lane and descriptor bytes retain their canaries. Original
code buffers remain unchanged. Other accesses fail; there is no SCSP/device RAM.

## Tests and retained evidence

Each module's9,136 cases are the union of all256 indices with five payload
boundaries and both lane/SR variants, plus all256 payload values at four index
boundaries and both lane/SR variants. Both low-level functions complete through
RTS in every positive case. The selection is not all possible CPU/RAM states.

For **each** module and lane, swapping the output lane rejects18/18 mutation
cases, swapping the payload field rejects18/18, and removing the index double
rejects15/18. The latter leaves some index0/initial-X0 cases unaffected, which
remain recorded. These six altered-original controls are separate copies with
separate hashes. Four owned tests cover fixed offset/flag/stack examples and
private/exclusive failure reports; they do not replace original execution.

| Module | SHA256 of either complete private report |
| --- | --- |
| SND | `83957b2669bc6f2b9f61996d14f72d1ce3db00bf1b24fb36e3d3aa1a05d5defc` |
| XBSND | `e7d8092817e5c0160a9cfcd52926a04402248731375f29e7a7a1575681206074` |

Common result-row hash:
`550e7e9776b7444a68d8b140802b1c878fbb811e95e7a61ecdb06afe00964d59`.
Report hashes differ because module/source/lifetime metadata differs. Each
original module is actually loaded and executed; static byte equality alone is
not counted as an execution result.

Original execution head `bc4a80caa75bb171500f632422efd9a615429d7e`.
Private reports `/home/dev/neptune-research-private/619/nlsnd-setters-001/`, named
`SND-run{1,2}.json` and `XBSND-run{1,2}.json` (directory name is historical).
Supervisors `/home/dev/neptune-evidence/code619-20261102/`.
The existing prepared ABI1 is unchanged, binary SHA256
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.
No new tool/device/native generation is needed.

Guarded original jobs mounted repository, original containers and prepared tool
read-only and hid broker authority. Actual configured host limit3 and own180-
second admission leases stayed unchanged; own leases were released. Each command
had60-second timeout and nice10. No provider/model call, scheduler, paid fallback,
allowance reset or continuity activation. Preserve other VPS/Gemini owners and
#536. Account/CI spend remains unknown.

## Reproduction and continuation

After existing admission and read-only mounting, run both modules with two
fresh report paths each; compare complete reports within each module:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_shared_setters.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/SND.container \
  --module SND \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/619/NEW-SND-run1.json
```

For XBSND choose its container and module explicitly. Continue callers of these
setters and the original SND/XBand command paths. The private selected inspector
also records failed exact NLSND-helper searches and a rejected weak byte-similarity
candidate; these are not equivalence evidence. Continue unresolved NLSND17F2
dispatch/table targets and active scan completion from#617, then further kernel/
slave/overlays/DSP/regional/network/save paths. Boot, natural calls, audio/timing,
independent-engine/hardware checks and whole-program/function/dynamic-target
denominators remain open. All-original-code recovery remains active, incomplete.
