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

The [context/helper and caller-prefix result](../research/2026-11-03-library-setup-contracts.md)
adds10,504 original cases twice:10,294 complete returns and210 explicit A681A
handoffs per run, with23 mutation-control combinations. Initializer/field/index
helpers and the actual96D74 null path/positive nested-call prefix are distinct
from the still-unrecovered A681A body and full95E5A semantics.

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

The [NLSND reset-marker phase result](../research/2026-11-03-original-boot-gate.md) independently compares the bounded `0x1000..0x1080` handoff in two fresh original CPU processes. Each has eight complete phase transfers, 8,192 explicitly unfinished marker waits and 48 completed-handoff mutation rejections; the embedded data gap stays non-executable. Natural loading and the remaining reset body, header-global lifetimes and whole-code denominators remain open.

The [Japan kernel result](../research/2026-11-03-japan-kernel-residency.md)
verifies exact Japanese `0KRNL.BIN` residency at candidate mapping `0x0600A000`
in original boot states through frame 2400 and isolates two Japanese startup
buffer helpers (`0x0600A58E`/`0x0600A5A2`) across 48 repeated constructed case
pairs with two wrong-opcode controls. Residency is not a complete executable
range map or proof that every matching instruction ran; the helpers are not
natural-caller validation, and Japan startup/device semantics and the all-module
denominator remain open.

The subsequent [Japanese record-address helper result](../research/2026-11-03-japan-record-address.md)
executes the original 18-byte helper at `0x0600AEF2` over 34 inputs twice per
run, with paired reports identical and two instruction mutation controls. A
follow-up composes the helper with its original `0x0600CC5C` indirect callsite
for all 18 record indices twice per run, checking the exact call argument,
return path, and callback store at record `+12`, with three mutations. The
constructed caller continuation does not prove natural runtime reachability or
the preceding `0x0600A946` producer.

The same [Japanese record result](../research/2026-11-03-japan-record-address.md)
also executes original `0x0600AACC` over all 18 record indices with both
activity states, twice in each of two identical reports, and two instruction
mutations. It checks the `+80` flag read, conditional longword `1` write, exact
stack MACL restore, and return delay slot. The `AA34` producer still has
unresolved cache-through/VBR dependencies; no natural reachability or gameplay
is claimed.

The same [Japanese record result](../research/2026-11-03-japan-record-address.md)
also executes the `0x0600AAEA` 18-slot tag scan composed with `AACC`: matching
tags at `+81` are cleared, and active records are latched. Thirty-nine cases
run twice in each of two identical reports, with two instruction mutations.
Natural callers and record lifetime remain open.

Static follow-through from `AB78` found original `0x0600A186`, a 48-byte
context restore. Its 31-pattern constructed probe executes all 18 original
instructions twice per case in paired reports, checks R8–R15/MACH/MACL/PR/R4
restoration and the R5-to-R0 return delay slot, and detects two mutations.
Natural task-switch reachability remains unresolved.

The [Japanese record result](../research/2026-11-03-japan-record-address.md)
now also covers original `0x0600ADB0`: 360 constructed valid-record cases in
two byte-identical reports, with exact memory transaction/stack checks and
three original-instruction mutation controls. It is a Japan-mapped helper
contract; signed-negative index memory behavior and natural callers remain
open. The original all-code programme remains active and incomplete.

The same Japanese startup study adds 520 original calls to the `0x0600A5E4`
16-bit counter helper, including wrap boundaries and three mutation controls.
The larger `A312` startup path crosses SR, BIOS, VDP2, SCU and cache-through
polling state; its static decode does not count as execution or establish those
device contracts.

It also adds original `0x0600A164` context save over 31 constructed register
patterns twice per case in paired reports. The exact 48-byte write order
preserves the source's duplicate R8 at offsets 0 and 4. The existing A186
restore slice remains separate; natural task-switch reachability is unresolved.
The A7D0 literal/JSR/delay-slot caller is now composed with A164 across 31
patterns and two original instruction controls; execution stops at its actual
callee return boundary. Natural boot reachability and task-frame lifetime
remain unresolved.
The AB78 caller path now composes its exact stack prologue and A164 call across
31 additional constructed patterns, checking the frame at `0x060BDD7C`, its
40-byte saved stack, and the A164 return boundary. Neither caller establishes
natural task-switch behavior.

Static follow-through also found a third caller at `0x0600AD26`: it derives a
two-entry cache-through slot index from VBR, loads that frame pointer, and calls
A164 with a 32-byte delay-slot advance. The bounded composed probe covers 31
register patterns for each of two constructed VBR values, twice per case in
paired reports, with two instruction mutation controls. The reports match at
SHA-256 `573494700d714b29edbe46e31e19bd3ae54e3a5f9211a5fe7e2bb8e7feb16827`.
The table contents, VBR values, task identity, and frame lifetime are
constructed; natural task scheduling remains unproven. Failed harness attempts
are retained in `execution-026` and `execution-027`.
