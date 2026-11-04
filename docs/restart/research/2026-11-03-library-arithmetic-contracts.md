# Original library division, remainder and format selection

**All-original-code programme active and incomplete.** Following accepted
[setup PR691](https://github.com/elgansayer/Neptune-Bomberman/pull/691), original
9410C,94268 andA6DA6 now complete17,136 constructed cases per run, twice.
All three full report pairs are byte-identical. The
[derived evidence](../evidence/2026-11-03-library-arithmetic-contracts.json)
records original/source/range/interpreter identities, actual results and controls.
Originals, raw reports and memory remain private on the VPS.

| Original function | Cases per run | Instructions per call | Mutation controls |
| --- | ---: | --- | ---: |
| 0609410C signed quotient | 7,032 | 9 or79 | 4 |
| 06094268 signed remainder | 7,032 | 9,86 or89 | 5 |
| 060A6DA6 format selection | 3,072 | 8,13,14 or15 | 4 |
| Total, all complete returns | 17,136 | unchanged128 maximum | 13 |

The source is unchanged USA MK-81070 V1.003 KRNL, resident at06006000,
SHA256`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`.
The pinned f20de940 interpreter and all three source hashes are verified before
execution. These counts are original instructions, not cycles or observer hooks.

## Recovered contracts

Both division entries take divisor inR0 and numerator inR1. For a nonzero
divisor,9410C returns the signed quotient truncated toward zero in bothR0/R1.
94268 returns `numerator-quotient*divisor` inR0, with the numerator's sign for
nonzero remainder. Machine values wrap modulo2^32; INT_MIN/-1 produces quotient
80000000 and remainder0. This describes the original routine's machine result,
without attributing host-language signed-overflow behavior to it.

9410C saves/restoresR2/R3 and executes32 DIV1 operations plus33 ROTCL operations.
94268 saves/restoresR2/R3/R4, executes32 DIV1 operations and follows the actual
optional sign-correction path, including another DIV1. ItsR1 retains intermediate
quotient bits. With `adjust=signbit(numerator XOR divisor)` and
`pre=(quotient-adjust)mod2^32`, that value is
`(adjust<<31)|(pre>>1)`. All other register effects, full SR includingM/Q/T,
stack writes and restores are compared against the independent instruction model.

For nonzero divisors, quotient finalM is the divisor sign; finalQ is that sign
XOR the inverse ofpre's low bit. FinalT is1 exactly when the quotient is zero
and the operand signs differ. Other SR bits are preserved. The remainder's full
flags follow its tested original DIV0S/sign-correction sequence; no unspecified
flags are masked during comparison.

Each family includes600 zero-divisor cases per run. Both original zero paths
returnR0=0, setR1=060FA8B4 and store0000044E at that explicit high-RAM error
cell. They preserve priorM/Q, setT=1 and restoreR2 in the actual RTS delay.
They execute nine instructions, with no callback or device access.

A6DA6 selects from inputR4 using bits64,16 and8. Bit64 returns2352 regardless
of the other bits. Otherwise bit16+bit8 returns0, bit16 alone returns2324,
and all remaining combinations return2048. The full path-specific clobbers of
R2/R3/R4/R5/R6 andT are checked. No writable region is needed. Its literal island
A6DB2..A6DC4 is excluded from executable ranges; only the three verified16-bit
literals are readable data regions.

## Independent expectation, corpus and controls

The expected DIV1 flags use an independently derived carry/borrow expression
from the primary [Renesas SH-1/SH-2/SH-DSP Software Manual](https://www.renesas.com/en/document/mah/sh-1sh-2sh-dsp-software-manual),
REJ09B0171-0500O, sections6.1.17–19. The pinned vendor DIV1 implementation was
neither read/copied into the expected model nor changed. A separate signed scalar
model uses absolute integer division andn-q*d, checking the result independently
of the bit iteration. The earlier552 model-only pairs remain owned development
evidence and are excluded from the original counts.

The division corpus combines all256 signed-byte numerators, twelve wider
boundary/bit patterns, thirteen divisors including0/±1/±2/±3/±8/±2048/INT_MIN/
INT_MAX, two register/stack variants and extra zero-divisor cases crossing all
eight initialM/Q/T combinations. Format cases cover all256 low bytes with six
upper-word patterns and two variants. Duplicate case tuples are removed. These
selections do not exhaust all32-bit argument pairs.

Every case compares all23 visible registers, full SR/PR/MAC, exact PC/delay trace,
ordered reads/writes, every mapped output/stack/canary byte and unaffected original
bytes. The derivation independently rechecks every retained row against the frozen
model and separate scalar results. All13 family/control combinations reject
without counting budget failures: lost DIV1/carry/sign-adjust operations, error
stores, register restores, real return delays, bit masks and format/result delays.
All mutations use disposable original copies; the supplied kernel stays unchanged.

## Provenance, storage and continuation

Source6705403 was tested/pushed before original execution. Nine owned tests and
440 research tests passed; the later current-base merge preserved those exact
production/test bytes. Execution source head7860d2a212f63e37b51beecda134d33dcc03ebdc
is frozen in77 files under
`/home/dev/neptune-research-private/655/adapter-1928ddc4ca2d102474c4e2bae9fe5fdf954bee235c1e3d37170f5f31157f9ee0`.
Completed batch:
`/home/dev/neptune-research-private/655/arithmetic-batch-ay2cbb78/batch.json`.
Reports and immutable prior failures remain private. Runner/derivation/check
receipts are in`/home/dev/neptune-evidence/code655-20261102/`.

The first batch87zatfsj refused storage preflight before admission or original
execution. Lossless recovery hard-linked76 byte-identical completed own reports/
states, preserving every path and hash, and omitted verified clean addon/font
binaries from this research worktree. The exclusion/dedup receipts and restore
command are retained. Fresh output moved to the root filesystem with the same
5GiB+64MiB preflight reserve; the constrained evidence volume was left intact.
No other owner's data, reservation or worktree was changed.

All six admitted jobs released their own normal shared3/180-second leases and
kept60-second/nice10/downward2GiB, offline/read-only and hidden-authority guards.
The accepted128 guard and original/interpreter hashes are unchanged. No provider
call, native build, device model, scheduler or allowance change was introduced.

Next inspect/recoverA6FE0 andA7F4E, then execute actualA681A/96D74/95E5A calls
without substituted services. Natural arithmetic arguments/interior execution,
95CBC,A6790,969E0/BIOS,293A4, complete89C8 semantics and root/task cycles remain
open. Other SH-2/overlay/68000/DSP/regional modules and executable/function/
dynamic-target denominators remain unresolved. This CPU evidence does not prove
physical Saturn timing, gameplay or Godot parity.
