# First original Saturn kernel result

EXP-SAT-CODE-001 now has a real-original partial result on the VPS. Two fresh
processes executed the accepted USA MK-81070 V1.003 kernel helper at `0x0600A4B0`
for 256 inputs each. Both passed and produced byte-identical reports. This advances
[#483](https://github.com/elgansayer/Neptune-Bomberman/issues/483), which stays open
for independent emulator/caller validation and further functions.

The [complete numeric input/output report](../evidence/2026-10-30-saturn-original-kernel-probe.json)
and [host/extraction receipt](../evidence/2026-10-30-saturn-original-kernel-host.json)
contain derived evidence, with no original binary or raw memory dump. The original
kernel, detailed instruction trace and deliberately modified copy remain private.

## Inputs and execution

| Input | Identity |
| --- | --- |
| Original file | `BOMSS/0KRNL.BIN`, 786432 bytes, USA MK-81070 V1.003 |
| Kernel SHA-256 | `20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7` |
| Kernel SHA-1 | `6fc53e5715d89cae7b4684bb3b65165ac1865736` |
| ISO extent | Track 01 INDEX 01 relative LBA 3854, 384 logical sectors |
| Interpreter | [`saturn-recomp`](https://github.com/callumjenkins/saturn-recomp/tree/f20de940e8013fc84103a5b39c4069ed8071b1f9), `f20de940e8013fc84103a5b39c4069ed8071b1f9` |
| Neptune probe | `049f46b987489440b3d925fc6ca1b413b8021a9a917bd246bae14011b43e8f38` |
| Neptune base | `b4cc6de97976ac247ca3f77d73acaa6c4380257f` |

The accepted disc reader re-read the ISO directory and selected exactly that
extent. All 384 kernel sectors passed EDC validation; all 30 track identities
matched the accepted #462 media report. No source media was changed. A first
extraction wrapper mistakenly expected an enriched summary field from the raw
directory parser and stopped before writing output. The corrected wrapper used
the actual extent records; that setup failure log is retained.

The probe checked the kernel's size and both hashes, then verified all three
interpreter source hashes before loading those files. It skipped the dependency's
package initializer. The source hashes and extraction modules are recorded in the
receipts. The dependency is MIT-licensed; its implementation is not vendored here.

Each call used a new CPU, `r4` as the argument, initial registers `0xA5A5A5A5`,
stack pointer `0x060FFFF0`, and a return sentinel instead of the original caller.
Only the original kernel was mapped. Writes or unmapped reads failed; each call
had a 256-instruction bound. Each process had a 60-second external deadline.
No emulator boot, BIOS, device memory, provider request or game build was needed.

## Recovered logic and instruction annotations

The observed function selects one result by bit precedence:

```c
unsigned select_bits(unsigned input) {
    if (input & 0x4000u) return 3;
    if (input & 0x2000u) return 2;
    if (input & 0x8000u) return 1;
    if (input & 0x1000u) return 4;
    return 0;
}
```

This reproduces the earlier upstream hypothesis on the executed original samples.
It is a reconstruction of this helper, not recovered original source names or a
new game implementation. Physical direction names remain unverified until callers
and input mapping are observed.

The separate instrumented CPU run observed these original instruction regions:

| PCs | Observed operation and interpretation |
| --- | --- |
| `0600A4B0` to `0600A4B8` | Load the halfword at `0600A4CE`, test argument against `0x4000`; return 3 through the return delay slot when set |
| `0600A4BA` to `0600A4C2` | Load the halfword at `0600A4D0`, test `0x2000`; return 2 through the delay slot when set |
| `0600A4C4` to `0600A4CC` | Load the longword at `0600A4D8`, test `0x8000`; return 1 through the delay slot when set |
| `0600A4DC` to `0600A4E4` | Load the halfword at `0600A5B8`, test `0x1000`; return 4 through the delay slot when set |
| `0600A4E6` to `0600A4EA` | Return zero when none is set; the final return has a no-op delay slot |

All 23 visited instructions were inside those regions. Literal data between code
regions must not be counted as instructions. The longword load for `0x8000` also
matters when interpreting sign extension. The instrumented run observed no writes,
all calls reached the return sentinel, and `r4` and the stack pointer were
preserved. This does not establish a complete ABI/register preservation contract.

## Coverage, repeatability and regression detection

The 256 unique inputs combine all sixteen selected-bit combinations with four
low-bit and four upper-word patterns. They cover simultaneous/opposed selected
bits, but do not exhaust all 32-bit arguments or initial CPU states. Return values
matched for every sample. Observed instruction counts were 5, 8, 11, 14 and 15;
these are interpreter instruction counts, not Saturn cycles or frame durations.

Both independently started processes produced complete reports with SHA-256
`12e4e02aa382172f5aa77c56534cd339ae8eb486a464f9eac082c9f98250fa6a`.
The ordered `[argument, result, instructions]` result digest was
`76c3b831d03cbe47a27db58ca6321e5b9f788396b3a8fc70119a69a8f6fa047b`.

Three distinctions matter for negative controls:

- The existing probe's changed-return hypothesis disagreed with 128 original
  sample results; prioritising `0x8000` first disagreed with 96. These controls
  change expected semantics, not the original binary or a second emulator.
- A separate controlled experiment changed the return immediate at `0600A4B8`
  from 3 to 5 in a private in-memory copy of the original kernel. Running the same
  CPU inputs gave 128 mismatches; `probe.execute` failed at input `00004000` with
  `expected 3, got 5`. The accepted original file and its hash remained unchanged.
- Existing synthetic tooling tests cover missing/wrong-sized/wrong-hash kernels,
  bad source hashes, empty samples, non-returning calls, writes and report
  overwrite prevention. Those tests validate failure handling, not original-game
  equivalence.

## Regeneration

Use private local media, the existing accepted disc decoder and the exact pinned
dependency. All commands run as the unprivileged research user; a hash is not an
OS sandbox. Supply a new private directory and do not expose these inputs to a
provider. The private extraction recipe/receipt are saved under experiment 483.

To reproduce extraction with the existing decoder, parse the supplied CUE using
`saturn_disc.cue.parse_cue_sheet(root, cue_relative_path)` and validate track
identities against #462. Open `DataTrackReader(sheet.tracks[0])`, parse its sector
16 with `parse_primary_volume_descriptor`, and call `_walk_directory_tree` with
the PVD root extent/length. Require exactly one `BOMSS/0KRNL.BIN` entry with the
extent above. Read it using `read_logical_bytes(3854, 786432, verify_edc=True)`,
check both kernel hashes and exclusive-create the private output. No full-disc
export or new filesystem parser is necessary.

From the recorded Neptune base, the actual repeated probe commands were:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_kernel.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/483/code-001-run1.json
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_kernel.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/483/code-001-run2.json
cmp /home/dev/neptune-research-private/483/code-001-run1.json \
  /home/dev/neptune-research-private/483/code-001-run2.json
sha256sum /home/dev/neptune-research-private/483/code-001-run1.json
```

Choose new report names when repeating: overwriting evidence is deliberately
rejected. For the actual mutation control, use `probe.kernel_bytes` and
`probe.interpreter` to verify the inputs, alter only bytes at kernel offset
`0x44B8` from `e003` to `e005` in a copied buffer, and invoke `probe.execute`.
It must fail with the mismatch above. Do not bypass `kernel_bytes` on accepted
inputs; the buffer alteration is an explicitly instrumented negative experiment.

## Remaining work

The same upstream decoder/interpreter is used throughout, so this is not an
independent oracle. No original caller, interrupt state, device effects, clock
timing, movement/fuse behaviour, Neptune parity or graphics extraction is proved.
Next, observe calls/returns in a pinned original emulator and compare argument,
result and instruction identities, then capture a real player/effect through
#482/#485. Preserve Gemini #484 ownership and the accepted core/state evidence.
The broad #483 and first campaign/battle milestone remain incomplete.
