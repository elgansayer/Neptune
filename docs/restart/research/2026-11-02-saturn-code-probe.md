# Saturn code recovery: next original-byte function probe

Update, 2 November 2026: the existing VPS coordinator has now executed the real
kernel under #590. The initial stackless assumption failed on a MACL spill.
An explicit bounded spill/restore contract then passed two 196-case runs and
four altered-original controls. Read the [original result and exact limits](2026-11-02-saturn-table-address-result.md).
The preparation and synthetic interoperability evidence below remains historical;
it must not be confused with the subsequent real-original execution.

This is a bounded continuation of [#483](https://github.com/elgansayer/Neptune-Bomberman/issues/483)
and the [existing original helper result](2026-10-30-saturn-original-kernel-result.md).
It advances code-recovery capability under #480/#482/#515. It does not replace
whole-program accounting or complete those issues. Asset extraction is a separate
coverage axis.

## Exact hypothesis and source

The pinned public reconstruction names a pure arithmetic helper at USA kernel
entry **`0x0600B934`**, file offset **`0x5934`** at load base `0x06006000`:

```text
result = ((10 * n + m) * 152 + 0x00207F74) modulo 2^32
```

Source: [pc-saturnbomberman `decomp/krnl.c`](https://github.com/callumjenkins/pc-saturnbomberman/blob/c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3/decomp/krnl.c),
revision `c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3`, Git blob
`6aba3320e95f988d4424ce5a10c77ee29ed46ab1`. Its C returns
`(10 * n + m) * 152 + 0x00207F74`. The probe makes the low-32-bit arithmetic
explicit, rather than relying on host C signed-overflow behaviour. Whether the
original instructions agree on every selected constructed case is a question
for the original-byte run, not an established fact.

The source describes nine candidate kernel helpers. This one was selected because
its proposed contract needs two register arguments and no device model. Original
execution subsequently required the observed bounded MACL stack spill. Its natural caller, valid table-index domain, pointed-to
record interpretation, complete function boundary and ABI remain unverified.
The arithmetic expression alone does not recover a gameplay system.

## Probe contract

[`probe_table_address.py`](../../../tools/saturn_lab/probe_table_address.py)
reuses the existing `probe_kernel.kernel_bytes` and `probe_kernel.interpreter`:

| Input or boundary | Required identity/behaviour |
| --- | --- |
| Original kernel | USA MK-81070 V1.003 `BOMSS/0KRNL.BIN`, exactly 786,432 bytes |
| SHA-256 | `20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7` |
| SHA-1 | `6fc53e5715d89cae7b4684bb3b65165ac1865736` |
| Interpreter | `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`; all three existing source hashes must match before loading |
| Arguments | `r4 = n`, `r5 = m`, unsigned 32-bit register bit patterns |
| Execution | Fresh poisoned CPU per case; return sentinel; maximum 256 executed instructions |
| Memory | Only the original kernel mapped, read-only; unmapped reads and all writes fail |
| Stack | `r15 = 0x060FFFF0`, deliberately unmapped; unexpected spilling falsifies the current pure-leaf contract |
| Output | Exclusive-create private JSON, mode 0600, complete success or explicit failed phase/class; no overwrite |

There are **196 distinct argument pairs**. One hundred form a Cartesian sample of
the upstream checker's ordinary 0..1000 domain using
`0, 1, 2, 9, 10, 63, 100, 255, 999, 1000`. Ninety-six additional pairs exercise
constructed 16/32-bit sign and wrap boundaries using
`0, 1, 0x7fff, 0x8000, 0xffff, 0x10000, 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff`,
excluding pairs already present. These are neither every pair in 0..1000 nor
exhaustive 64-bit pair space, and none is claimed to be naturally observed.

Every call compares the actual CPU return with the hypothesis. Evidence includes
the arguments/result, instruction count, executed-PC set, observed changed-register
names, return-sentinel completion and zero writes. The wrapper observes the
pinned CPU's `exec`, including its explicit return/branch delay-slot invocation;
observing only outer `step` calls would omit those slots. No original opcode
bytes or memory dumps are emitted. Changed-register observations apply only to
the sampled initial states, not a complete ABI promise. Instruction counts are
not Saturn cycles or game ticks.

The same sampled **original results**, once obtained, must distinguish a stride
of 151, a base increased by 4, and swapped arguments. These wrong-hypothesis
controls do not mutate the original binary and are not an independent CPU oracle.
A later original-instruction mutation and natural caller trace remain separate
verification work.

## Run on the existing original host

The commands below retain the initial strict no-write control, which now has a
known original failure. For the observed stack contract and repeatable original
instruction controls use `--bounded-stack --instruction-controls` as documented
in the linked actual VPS result. Do not map arbitrary data/device RAM.

Use the accepted extracted kernel and exact interpreter sources, retain the
original media unchanged, reconcile host ownership, and choose fresh private
report names. No new model session or full emulator build is needed for this
CPU-only experiment:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_table_address.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/483/code-002-run1.json
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_table_address.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/483/code-002-run2.json
cmp /home/dev/neptune-research-private/483/code-002-run1.json \
    /home/dev/neptune-research-private/483/code-002-run2.json
```

A missing/wrong kernel or changed interpreter fails before execution. A write,
unmapped read, failure to return, instruction-budget overflow or semantic mismatch
fails the experiment. Do not silently map device registers as RAM, allow stack
writes, modify expected arithmetic or replace original instructions merely to
turn that failure into a result. Inspect original disassembly and revise the
explicit hypothesis with evidence instead. Reports identify the failure phase
without copying private paths or instructions into shared metadata.

If both original runs succeed, retain their complete reports, command outcomes,
source/tool identities and independently inspected argument/return observations
before promoting this function's status. Success on constructed inputs still
does not prove its natural role, timing or caller ordering. Continue with
original-emulator callers and further original functions; do not close the parent
mission after a passing child.

## What was actually checked here

Eleven owned synthetic unit tests exercise selection completeness, fixed arithmetic
examples, stride/base/argument-order mismatches, missing/changed inputs, bounded
execution, zero-write/unmapped-access rejection, return completion, delay-slot PC
accounting, fresh CPUs, output preservation and private file permissions:

```sh
python3 -m unittest discover -s tools/saturn_lab/tests \
  -p test_probe_table_address.py -v
```

Separately, the three actual public interpreter source files were fetched at the
accepted revision and verified against the existing exact SHA-256 pins. An owned
SH-2 sequence was placed at the probe entry in an otherwise zero-filled,
kernel-sized **synthetic** buffer. It performs the proposed arithmetic using
register shifts/adds, `mul.l`, `sts macl`, a PC-relative literal and `rts` plus its
delay slot. The actual pinned decoder/interpreter executed all 196 cases, taking
13 instructions per case; observed changed registers were `r0`, `r1` and `macl`.
The results digest was
`5d3bfa5eb6b3fa6f02fb36fdb09cbff21336b9ea69a0e59cf8ec57a1564a80f6`.
Wrong-hypothesis rejection counts were stride 194, base 196 and argument order 174.
Those counts are synthetic interoperability evidence, not expected original
instruction counts, PCs or register clobbers. The [machine-readable smoke receipt](../evidence/2026-11-02-saturn-code-probe-synthetic.json)
explicitly records `original_game_bytes_executed: false` and the source/tool hashes.

Four altered copies of that owned synthetic sequence were also executed by the
actual pinned interpreter: changing its stride to 150 or its base by +4 caused
semantic mismatches; replacing its return with a self-loop hit the instruction
bound; inserting a stack store hit the no-write guard. These are real interpreter
failure-path checks on synthetic code, distinct from mutating an original game
instruction.

To reproduce that optional source-interoperability smoke with an existing
hash-matching source checkout, use this test-owned sequence. Direct `execute`
below deliberately receives synthetic bytes; the original-file CLI would reject
their kernel hash:

```python
import sys
from pathlib import Path
sys.path.insert(0, "tools/saturn_lab")
import probe_kernel as pinned
import probe_table_address as probe

cpu = pinned.interpreter(Path("/PRIVATE/PINNED-SATURN-RECOMP"))
synthetic = bytearray(pinned.SIZE)
owned_code = bytes.fromhex(
    "6043 4008 304c 4000 305c e14c 4100 0017 "
    "001a d102 301c 000b 0009 0009 0020 7f74"
)
offset = probe.ENTRY - pinned.BASE
synthetic[offset:offset + len(owned_code)] = owned_code
result = probe.execute(bytes(synthetic), cpu)
assert result["cases"] == 196
assert result["max_instructions"] == 13
assert result["results_sha256"] == "5d3bfa5eb6b3fa6f02fb36fdb09cbff21336b9ea69a0e59cf8ec57a1564a80f6"
```

No original kernel was executed here. No additional game function is marked
verified by this tooling change. The established original result remains the
earlier `0x0600A4B0` experiment, while original-byte function recovery, code-range
classification, dynamic targets, task resumes, sound CPU/DSP and whole-game
semantics remain part of the active complete-code objective.
