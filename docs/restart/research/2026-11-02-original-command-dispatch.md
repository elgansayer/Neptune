# Original NetLink command classifier and indexed calls

Issue [#623](https://github.com/elgansayer/Neptune-Bomberman/issues/623), under
#483/#488/#480/#464, continues the original130E capture work. Two complete
18,432-case reports match byte for byte, SHA256
`42aa5a4fd379ec94fe0f16e3975b697a970af65089016bd34fe07f8986ff9fbb`.
They contain **16,128 complete returns**, **2,160 prefixes stopped before
unresolved handlers**, and **144 actual illegal-landing failures**. Those144
are not successful completed calls. All six original-copy controls reject.
[Derived evidence](../evidence/2026-11-02-original-command-dispatch.json).

## Source, classification and returns

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`,23,920 bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, NetLink driver lifetime. Full-source identity
precedes execution. Entry17F2 executes within17F2..18F2; original positive
instructions are unchanged. Only a28-byte explicit stack/sentinel region is
mapped. No device or generic RAM model is added. The accepted ABI1/native
generation remains unchanged.

The original ANDI.W00FF normalizes D7's low word to its command byte, preserving
upper16 bits. MOVE.B D7,D7 tests the command's bit7. The actual classification is:

| Command bytes | Actual bounded behavior |
| --- | --- |
| 20..7F and91..FF | OR.W D0,D0 at186E, then RTS1870 |
| 00..1F | Scale command by4, set A4=A6, save A5/A6, indexed JSR at1864 into1872+4*command |
| 80..90 inclusive | Mask command with0F, scale by4, indexed JSR at1808 into180E+4*index |

90 therefore selects the same high-table entry as80. The high path pushes180C;
the low path pushes1868 beneath actual MOVEM saves. All saved words, return
longwords, restores and SP outcomes are compared transaction by transaction.
Neither table is replaced with a Python callback or substituted handler.

Low command00 lands on RTS1872 and completes through1868/186C. Low0F and14..1F
land on original jumps to186E, execute OR.W D0,D0, and return through the same
restore path. Their indexed doubles clear X. Direct skip classes retain incoming
X; OR.W sets N/Z from D0.low16 and clears V/C. A4 remains A6 after low-class calls;
A5/A6 are restored. The probe checks all visible registers and SR, not just PC.

High8B and8E land on six-byte absolute JMP186E instructions, complete the nested
return to180C, branch to186E again, and return to the caller. High8D lands in
an encoded operand: the actual instruction there is **ORI.B006E,D0 at1842**,
followed by JMP1846. It really ORs6E into D0.low8 before those returns. Both OR.W
operations, changed D0 and final flags are checked. Treating all four-byte table
landings as independent JMP instructions would miss this behavior.

The remaining30 command bytes reach29 distinct nontrivial handler entries, where
this experiment stops before execution. Their actual indexed JSR, table jump,
D7 value, A4 setup, stack contents and CCR are verified. The target addresses are
retained in derived evidence. Handler semantics and their eventual returns are
not claimed here. The original range contains variable-width entries; no uniform
function-boundary assumption is used.

## Illegal landings and retained correction

Commands8C and8F actually execute illegal words at183E and184A. In this pinned
68000 interpreter each pushes the offending original PC and current SR after
the existing180C return address, then attempts the illegal-instruction vector4
read at absolute10. That vector is deliberately unmapped. All144 attempts stop
with `unmapped-data-read`, address10,width4. Their exact ten executed PCs,
three stack writes, every register and untouched stack byte are retained and
compared. No exception handler, natural command validity or hardware outcome is
inferred; the native failing status and `completed_original_call:false` remain
in each report row.

The first full attempt failed at its first8C case after10,080 preceding states:
the predicted stopped PC was1840. Actual accesses, stack/SR and executed PCs
already matched. Inspection of the pinned `m68ki_jump_vector` shows it assigns
REG_PC=vector*4 **before** the vector load. A rejected vector read therefore
leaves visible PC10. The contract was corrected to that source-backed stopped
state. No instruction, CPU source, register/vector mapping, guard, bound or
expected completion status was changed. The initial failed report and private
diagnostic remain immutable; their hashes are retained in derived evidence.

An intervening original-job attempt was denied by a foreign exclusive host
lease and executed no original code. Its admission record is preserved. The
foreign process then ended and the gate became empty; a fresh admitted report
directory was used. No foreign lease was removed or reset.

## Selection, controls and custody

The product covers all256 command bytes, nine D0.low16 boundary words,
two D7 upper-bit patterns, two supervisor SR/X states and two A6 bases. It does
not cover all machine states or naturally captured commands. Observed paths
span7..16 instructions and1..9 events. All registers, exact instruction paths,
read/write widths/order/values, entire mapped stack and unchanged code buffers
are checked. Model cycles are not Saturn hardware timing.

| Altered instruction | Rejected /96 |
| --- | --- |
| high limit91 changed to90 |8|
| low limit20 changed to1F |8|
| high mask0F changed to07 |24|
| remove second low index double |16|
| remove return OR.W flag operation |52|
| remove middle-entry ORI.B |8|

Unchanged mutation cases remain recorded. Altered source copies/hashes are
separate from unchanged positive inputs. Six owned tests cover classification,
stack/flag examples, unsupported-call rejection and immutable private failures.
Tooling tests are distinct from real original-code execution evidence.

Corrected original execution head `0fe8e9c64757116d6700450e244857900a2d84fe`.
Two full evidence reports: `/home/dev/neptune-research-private/623/nlsnd-command-dispatch-003/`.
Initial failure: sibling `nlsnd-command-dispatch-001/`; diagnostic `diagnostic-001/`;
denied admission `nlsnd-command-dispatch-002/`. Supervisors/commands are in
`/home/dev/neptune-evidence/code623-20261102/`.

The accepted prepared ABI1 is `.factory-tools/code600-001/prepared`, binary
SHA256 `cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.
Actual configured shared host limit3 and180-second own leases were unchanged
and released. Original/code/prepared sources were read-only and broker authority
hidden in guarded original jobs. Every command had60-second timeout and nice10.
No provider/model call, scheduler, allowance reset, continuity activation or
paid fallback. Preserve VPS coordinator#613/#621 and Gemini#487; spend unknown.

## Reproduce and continue

After existing admission and read-only mounting, choose fresh report paths:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_command_dispatch.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/623/NEW-run1.json
```

Next connect these complete skip/no-op returns to original139A..13B0, including
139E slot selection, actual word clear at13A4, eight-slot rescan and130E handshake
acknowledgement. Exercise full active scans with real nested dispatcher calls,
not just one capture prefix. Then continue the unresolved nontrivial handlers,
their real device effects and further SH-2 scheduler/slave/overlay/common sound/
DSP/save/network/Japan code. Natural callers, boot/audio/hardware validation and
whole-program/function/dynamic-target denominators remain open. The all-code
programme remains active and incomplete.
