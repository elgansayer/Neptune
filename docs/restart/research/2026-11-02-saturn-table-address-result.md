# Original USA table-address helper: observed stack contract and sampled result

Executed on the existing research VPS on 2 November 2026 under #590/#483.
This is **real original-byte CPU-interpreter evidence**, separate from #589's
synthetic smoke. It is not natural emulator/caller validation or complete code
recovery. [Derived measurements and hashes](../evidence/2026-11-02-saturn-table-address-original.json)
retain both the initial rejected hypothesis and the successful revised experiment.

## What the original did

The accepted USA MK-81070 V1.003 kernel is 786,432 bytes, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
mapped at `0x06006000` for this isolated experiment. The unchanged interpreter
is `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`; all three
existing source hashes were checked before loading. Source media stayed read-only.

The first strict probe **failed** on a four-byte write at `0x060fffec`. Inspection
of the original at entry `0x0600b934` found a MACL push, followed by arithmetic,
`rts` at `0x0600b94c` and MACL restore in its `0x0600b94e` delay slot.
Mathematical purity did not imply a stackless implementation. The first failure
report is preserved; default no-write mode still rejects the original.

The new explicit `--bounded-stack` mode supplies an 80-byte constructed stack
around initial SP `0x060ffff0`. It permits exactly one four-byte MACL write and
one matching read at SP-4 per case. Other stack bytes must remain unchanged;
the entire mapped kernel remains read-only and unchanged. SP, poisoned MACL and
all sampled registers except the observed scratch/result registers are checked.
No hardware/device registers or arbitrary data RAM are mapped to make a call pass.
This stack is a controlled input, not a captured native caller stack.

Two fresh runs passed **196 distinct argument pairs each**, producing identical
complete report bytes. Every call executed 14 instructions, including the return
delay slot. The sampled arithmetic matches the pinned upstream hypothesis:

```text
r0 = ((10 * r4 + r5) * 152 + 0x00207f74) modulo 2^32
```

The original reads its stride literal at `0x0600b96c` and base literal at
`0x0600b984`. It restores SP and MACL. Observed changed registers were `r0`,
`r2`, `r3`, `r6` and SR's T bit; all other sampled register values were preserved.
The bounded mode also checks the T bit from the original SHLL of `5*r4`.
These observations cover the declared initial states and entry, not every ABI
context. Fourteen instructions are not fourteen Saturn cycles or game ticks.

Report SHA-256:
`8b543e26e1c84df6a1c1734794e4776cc62c6502b9e9031fac21b649ec3c621c`.
Results SHA-256:
`9d82d210644407796b87db6e3009c4067873fc17240c2f9c94422811007dd8c6`.
The source harness commit is `01c9d5a04b1dfbe136a0dfd16b0a52c79ce7148c`;
the receipt records exact adapter/probe and executed-range hashes. Subsequent
documentation commits do not change those tested source bytes.

## Negative controls and caller leads

The original results distinguish a wrong stride in 194 cases, a wrong base in
196, and swapped arguments in 174. Separately, four private altered copies of
the original were actually executed: stride 150, base +4, removing the MACL
spill, and removing its restore delay slot. Every altered copy failed the
arithmetic or exact memory/restore contract. The original file hash was checked
unchanged afterwards. Altered copies are never reference inputs.

Static original-word scanning found BSR candidates at `0x0600baea` and
`0x0600bc28`, with delay slots at +2. These are **leads**, not naturally
observed callers: bytes in data can resemble instructions. The function's table
meaning, valid natural argument domain, CPU role and caller ordering remain
unverified. No RNG or gameplay purpose is inferred from names or arithmetic.
The same interpreter lineage supplies the execution oracle; independent emulator
or hardware validation remains outstanding.

## Reproduce without changing originals

Use fresh private report paths and the existing bounded resource admission and
unprivileged guarded execution. The original kernel/interpreter mounts must stay
read-only, and coordinator/provider credentials and the private signing authority
must remain hidden. No provider inference or continuous scheduler is needed.

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_table_address.py \
  --kernel /PRIVATE/accepted-usa/0KRNL.BIN \
  --saturn-recomp /PINNED/saturn-recomp-f20de94 \
  --bounded-stack --instruction-controls --report /PRIVATE/code002-new-run1.json
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_table_address.py \
  --kernel /PRIVATE/accepted-usa/0KRNL.BIN \
  --saturn-recomp /PINNED/saturn-recomp-f20de94 \
  --bounded-stack --instruction-controls --report /PRIVATE/code002-new-run2.json
cmp /PRIVATE/code002-new-run1.json /PRIVATE/code002-new-run2.json
python3 tools/saturn_lab/check.py
```

Each original command also executes the four fixed altered-copy controls through
the checked-in `--instruction-controls` experiment. Timeouts do not qualify as
semantic rejection. The last command runs synthetic tooling regressions, including extra/escaped
writes, missing/extra/mirrored reads, bad restore/SP/register/condition state and
changed unaffected memory. It does not rerun the private original on CI.

Keep #483 and the complete-code mission open. Next observe a real caller/return
under bounded original tracing, then recover the adjacent table helpers and
their callers with separate source/mapping/lifetime identities. Module/function
denominators remain unknown; this helper does not close whole-program recovery.
