# Two original USA split-halfword accumulators

Issue [#594](https://github.com/elgansayer/Neptune-Bomberman/issues/594), under
#483/#480/#482/#464, continues the [position-helper/caller result](2026-11-02-original-position-bounds.md).
Two fresh original-kernel runs passed **1,120 constructed cases each**, 560 per
entry. Complete private reports are byte-identical, SHA-256
`73d9c6a90cc4821c35c76c4d990854d74a66b12cab4b978a1eb5da81dd712d06`.
The [derived receipt](../evidence/2026-11-02-original-split-add.json) preserves
source/tool/range identities and ten original-instruction controls. This adds
two isolated-tested entries, not natural gameplay or whole-program completion.

## Identities and exact contracts

Original USA MK-81070 V1.003 `BOMSS/0KRNL.BIN`, 786,432 bytes, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
resident-kernel candidate mapping `0x06006000`, SH-2 address space. CPU
master/slave role and natural residency are unvalidated. SHA-1 and all three
source files of `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`
are checked before execution. These functions share that interpreter lineage;
an independent CPU oracle remains absent.

| Original entry | File range, exclusive end | Low/high record offsets | Code SHA-256 |
| --- | --- | --- | --- |
| `0x0600A25E` | `[0x425E,0x428C)` | +12 / +16 | `c6c000de72bf54e136efbc7e9c725909a83b69a902bce405091c51a2239feb22` |
| `0x0600A2D8` | `[0x42D8,0x4306)` | +14 / +18 | `0a36318628fd7f5a1256fb131cfe022ad6847199e06fbd2d6e8d7fce731597e7` |

Each executes 23 original instructions, including the RTS delay slot restoring
MACL. Literal range `0x0600A358..0x0600A360` contains the record base
`0x060C381C` and index pointer `0x060C1AA8`; its SHA-256 is
`bf4608b39f41bb52bc9eccbab2896fe9e4eefc697df3598e9e3d76de69443c24`.
These eight bytes are literals, not counted as instructions.

Both routines accept the 32-bit delta in r4 and read a halfword index from the
fixed index pointer. The original instructions multiply its low 16 bits by 84,
truncate that product to 16 bits, then add the record base. For each entry's
low/high field pair:

```text
record = 0x060C381C + ((u16(memory[0x060C1AA8:]) * 84) & 0xFFFF)
value = (u16(record[high:]) << 16) | u16(record[low:])
result = (value + r4) modulo 2^32
record[high:] = u16(result >> 16)
record[low:] = u16(result)
```

The actual high load is signed, followed by SHLL16; its low-32-bit result is the
same high-half bit pattern above. The low load is explicitly zero-extended.
The independent oracle uses scalar modulo arithmetic and separately splits the
result; it does not run the original load/shift/add sequence.

Each original call reads the index, both data halfwords, both four-byte literals,
and its four-byte stack save exactly once, besides instruction fetches. Each
writes exactly the high halfword, low halfword and one four-byte MACL spill slot
at SP-4. Every other mapped byte must remain unchanged. All reads/writes carry
address/width evidence; any undeclared read or store fails. The stack slot holds
the saved MACL afterward; only its pointer/value restoration is promised.
Sampled changed registers are r0/r1/r2/r3/r5/r6. r4/r7–r15, SR, MACL/MACH, PR,
GBR/VBR are preserved for these initialized states. No return-value interpretation
is assigned to r0. Instruction counts do not establish cycles, speeds or ticks.

## Actual experiment and controls

Each entry tests the full 10×8×7 product. Index halfwords are
0/1/127/255/780/781/0x7FFF/0x8000/0xFFFE/0xFFFF. Combined initial values are
0/1/0xFFFF/0x10000/0x7FFFFFFF/0x80000000/0xFFFF0000/0xFFFFFFFF. Deltas are
0/1/0xFFFF/0x10000/0x7FFFFFFF/0x80000000/0xFFFFFFFF. These exercise carry,
signed loads, wrap, zero and identity, not a measured gameplay input domain.

Fresh CPU/memory copies use explicit initialized index/84-byte record/four-byte
stack regions, carved out of the original file mapping where necessary without
ambiguous overlaps. Untouched original code/literals remain original. There is
no device RAM, natural captured game state or runtime patch. All record bytes are
compared to the independent result plus unchanged-field canaries; every other
mapped byte outside exact store destinations is compared with its pre-call
baseline. Execution is restricted to the inspected entry range, at most
128 instructions, with sentinel return and delay-slot accounting.

Each of five mutations per function runs 63 constructed cases covering all
indices and delta values:

| Altered original instruction | A25E rejected / 63 | A2D8 rejected / 63 |
| --- | --- | --- |
| delta addition → subtraction | 45 | 45 |
| high-half store → NOP | 63 | 63 |
| low-half store → NOP | 63 | 63 |
| delay-slot MACL restore → NOP | 63 | 63 |
| index-product truncation → NOP | 31 | 31 |

Changed arithmetic fails the independent output contract. Missing stores fail
exact store accounting, missing restore fails register/SP preservation, and wrong
record selection fails the declared-read guard. Mutated copies/hashes remain
distinct from the original. Zero/unchanged-result cases are not disguised as
mutation rejections.

Private evidence: `/home/dev/neptune-research-private/594/split-add-001/`,
including `run1.json`, `run2.json`, supervisor and stdout/stderr. Supervisor source
is `/home/dev/neptune-evidence/code594-20261102/run-original.py`. Execution source
head `3a69ec867fd8806fb3c58d11f03bd05fb56dc052`; source/original mounts were
read-only and the installed process guard hid broker authority. Existing host
admission read configured shared limit 3 without changing it; lease 180 seconds,
60-second timeout per command. Both runs finished within the bounds, around six
seconds each. The supervisor released its own host lease. No new provider call,
manual-session change, daemon, purchase or allowance; account/CI spend is unknown.

To repeat after existing admission, choose two fresh reports and compare them:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_split_add.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/594/NEW-split-run1.json
# Repeat with NEW-split-run2.json, then cmp both complete files.
python3 -m unittest discover -s tools/saturn_lab/tests -p test_probe_split_add.py -v
python3 tools/saturn_lab/check.py
```

Seven synthetic tests cover carry/wrap, selection, nonoverlapping memory mapping,
private immutable failure reports and false-success rejection. The full
160-test input-tooling suite passed after incorporating current main. Synthetic
checks do not replace the original host runs; exact-head/current-base CI remains
the publication gate.

Static neighboring tail-call leads at `0x0600A2AC`, `0x0600A2D4`,
`0x0600A326`, `0x0600A350` and their scale/sign-extension wrappers remain separate
untested functions. Natural callers, gameplay role, timing, independent CPU and
Godot state/pixel/audio parity remain open. Next examine the task/entry helpers
`0x06006B38`/`0x0600940A`/`0x0600942E`, then expand loader/dispatch and sound
module work; unknown whole-program denominators stay unknown.
