# Original-code module leads and remaining coverage

The owner's 2 November clarification makes **all original game code** the primary
reverse-engineering target. This census supports #480/#481/#482/#483/#488/#492/
#496/#497/#515. It is a reproducible join of pinned disc-file identities and
specific prior-art module leads, **not new original-code execution or a recovered
function count**.

[`module-candidates.json`](module-candidates.json) contains 15 candidate mapping
identities: 12 USA mappings/artifact leads, the separately identified Japan
kernel, and one system-area bootstrap lead per release. The list is intentionally
incomplete. Other Japan modules are unknown;
they are not filled by copying USA addresses. No whole-program denominator or
code-byte total is inferred from these files.

| Lead | Source / candidate load | Important boundary |
| --- | --- | --- |
| SYSTEM_BOOTSTRAP (USA/Japan) | Track 01 LBA 0 system area / mapping unresolved | Each 32-KiB source extent has a retained hash; bootstrap instructions, metadata and padding are not yet separated. |
| BOOT | USA `0` / `0x06010000` | Boot file identity and IP first-read address are retained; code/data boundaries remain open. |
| TRAMP | Derived from `0+0x3B4B0` / `0x00200000` | Generated upstream artifact; length/hash unknown. Not an original disc file. |
| XS | `NETLINK/XS028000.EXE` / `0x00280000` | Loader/module mapping is an upstream lead. |
| SAMPLEIP | Original `SAMPLEIP.BIN` / unknown | Template bytes have a disc identity; actual unmodified mapping is unresolved. |
| IP_PATCHED | Derived from SAMPLEIP / `0x06002000` | Patched upstream output remains separate from the original template. |
| FLD | `FLD_KNL.BIN` / `0x00200000` | Shares an address with TRAMP; source/lifetime identities must remain separate. |
| H2H | `XBAND/H2HLIBUS.BIN` / `0x06002F00` | Library and dynamic entry/ABI work remain open. |
| XBAND | `XBAND/XBAND.BIN` / `0x06006000` | Reuses the kernel address in another residency lifetime. |
| KRNL USA | `BOMSS/0KRNL.BIN` / `0x06006000` | Existing helper/decompressor evidence is linked separately. |
| SND | `BOMSS/PROGRAM.BIN[0x44:0x6418]` / sound CPU `0` | 25,556-byte source-slice lead, not every byte proved to be 68000 instructions. |
| XBSND | `XBAND/XBAND.DAT[0x11868:0x17C3C]` / sound CPU `0` | Separate sound-driver source and lifetime. |
| NLSND | `NETLINK/SNDDRV.BIN` / sound CPU `0` | Sound CPU address space is separate from the SH-2 physical map. |
| KRNL Japan | `0KRNL.BIN` / `0x0600A000` | This is Japan's first-read and resident kernel; there is no invented separate Japan `0` file. |

Addresses, seeds and sound slices come from pinned
[`game.toml`](https://github.com/callumjenkins/pc-saturnbomberman/blob/c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3/game.toml),
Git blob `0ec8d923776c90935d415f4e9209612e55c401a9`. Original file sizes/hashes
come from the accepted [USA/Japan inventories](../saturn-disc/README.md).
The census pins the exact receipt bytes. These are retained identity declarations;
this command does not rehash private original media or authenticate earlier host
execution. Candidate mappings and entry seeds are not runtime-validated by this
join. SH-2 master/slave roles remain unresolved rather than silently assigned.
The system-area candidates instead use each receipt's `ip_bin.system_area_sha256`
and 16-sector extent, outside the ISO file namespace. Their synthetic locator
`@track01-system-area` is explicitly typed as a disc-system-area reference, not
an actual filename or an instruction-range declaration.

Each ID binds release, complete source-file hash/path, source slice, processor,
candidate mapping, residency lifetime and original/derived status. A bare address
must never be the key: `0x06006000` can refer to KRNL or XBAND, while sound CPU
address zero belongs to several driver lifetimes. Derived outputs have no invented
output hash or length. Whole files include data, literals, padding and possibly
several executable ranges; source sizes are not code coverage.

## Reproduce the metadata join

```sh
python3 tools/saturn_lab/code_inventory.py verify \
  --census docs/restart/saturn-code/module-candidates.json
python3 tools/saturn_lab/code_inventory.py generate \
  --census /PRIVATE/NEW-module-candidates.json
python3 tools/saturn_lab/check.py
```

Generation requires a fresh output with an existing parent. Input JSON is bounded,
duplicate keys/paths and unsafe source paths are rejected, source spans and entry
seeds are checked against file/mapping bounds, and changed disc-receipt identities
fail until explicitly reconciled. Verification regenerates the expected result;
dropped overlays, changed source/mapping fields or false completion claims fail.
The tests use metadata and owned synthetic records, not original instruction bytes.

## Code recovery still required

For every module, establish original loaded ranges, code/data/literal boundaries,
function entries/ABIs, direct/indirect call targets and task yield/resume edges.
Account for master/slave SH-2 execution, system-area bootstrap code, runtime
copy/relocation/patching, code-bearing bank contents, self-modifying 68000 drivers,
DSP programs, regional variants and hidden/network paths. Preserve SDK/library
code in the accounting even when it has a recognizable public implementation.

For each newly recovered routine, record original source/mapping identity,
arguments, touched state, return/side effects, execution bounds, tested cases and
meaningful instruction/semantic mutations. Original-byte interpreter tests and
natural emulator callers establish different evidence. Disassembly, successful
translation, a matching function name or an asset count cannot establish semantic
equivalence or complete code recovery.

Existing [selector samples](../research/2026-10-30-saturn-original-kernel-result.md)
and [resident decompression comparisons](../evidence/2026-10-30-gemini-program-bin-archive-002.md)
remain useful accepted evidence. They do not increase this census into a verified
whole-program function total. Unknown denominators remain `null`.

The [2 November original memory-helper/caller result](../research/2026-11-02-original-position-bounds.md) adds two isolated-tested USA kernel entries and their explicit controlled-memory limits. It does not establish natural gameplay validation or a whole-program function denominator.

The [natural first-task/library result](../research/2026-11-02-first-task-natural-init.md)
observes complete89C8/95B04 returns through twelve repeated original windows with
exact state/video/audio/input equality. [Status/registration contracts](../research/2026-11-02-library-status-contracts.md)
then distinguish3,364 complete returns from1,148 unfinished callback handoffs per
run. The [slot selection/release result](../research/2026-11-03-library-slot-contracts.md)
adds3,918 complete constructed calls twice with seven mutation-control
combinations and the old128 refusal retained. Internal library/device semantics,
full655 and whole-program coverage remain open; resume the
[current checkpoint](VPS-CODE-655-CHECKPOINT.md).

The [3 November NLSND state/command11 result](../research/2026-11-03-original-nlsnd-state.md)
compares36,127 constructed complete calls across five entry modes, repeated in
fresh pinned CPU/frozen-SCSP processes with44 terminal mutation rejections. Natural
sound roles/traffic, command10, audio timing and the whole-code denominator remain
open. These isolated calls do not establish campaign/battle Godot fidelity.

The [command10 trace-capacity dependency](../research/2026-11-03-command10-trace-capacity.md)
adds a separately qualified ABI6 profile. Two fresh paired128-case experiments
preserve96 non-capacity results exactly and advance32 event-limited scans to the
same explicit unsupported device read. This is tooling/diagnostic progress;
parent665's complete device/command10 semantics remain open.

The [original slot-reset result](../research/2026-11-03-original-slot-effects.md)
adds639 complete constructed3540/355A/356E calls repeated in fresh processes,
24 terminal mutation rejections and a qualified frozen slot-byte profile. The
128-case command10 continuation now reaches32 diagnostic returns and precise
low0780/longword-DSP guards; full command10, natural timing/audio and whole-code
coverage remain open.

The subsequent [fixed-data clear result](../research/2026-11-03-original-low-reset.md)
qualifies294 complete constructed3530 calls in each of two fresh processes with12
terminal mutation rejections. Direct original writers establish only the bounded
NLSND0780..078F data profile. All prior680 observations are reproduced; the new
command10 matrix has64 diagnostic returns and64 explicit DSP longword guards.
Natural code/data lifetime, full command10 semantics and whole-code coverage remain open.

The [DSP reset helper result](../research/2026-11-03-original-dsp-reset.md)
adds414 complete original calls repeated in fresh processes and60 terminal
mutation rejections, with a separate qualified frozen DSP longword/TEMP profile.
All128 command10 scenarios now return diagnostically;64 prior CPU/RAM/common-device
outcomes and64 prior guarded prefixes are preserved. This removes the measured
width dependency, not the remaining independent command/natural/audio/Godot proof.
