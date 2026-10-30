# Saturn Bomberman: source investigation and VPS experiment playbook

Research date: 30 October 2026. Scope: **original Sega Saturn Bomberman**, initially
USA MK-81070 V1.003, with Japan T-14302G V1.000 as a separately identified comparison.
Owner/dispatch: [#464](https://github.com/elgansayer/Neptune-Bomberman/issues/464),
[#477](https://github.com/elgansayer/Neptune-Bomberman/issues/477), existing Elgl factory.
This extends the [earlier investigation](2026-10-30-deep-dive.md), rather than replacing
its source registry. The accompanying [experiment queue](saturn-vps-experiments-2026-10-30.json)
and [source receipts](saturn-vps-sources-2026-10-30.json) make the handoff machine-readable.

**Status:** source inspection and proposed next experiments, reconciled with the
newly merged [original Saturn result, PR #524](https://github.com/elgansayer/Neptune-Bomberman/pull/524).
The VPS has reproduced one original kernel helper; this report did not run private
originals itself. Its [analysis](2026-10-30-saturn-original-kernel-result.md),
[numeric report](../evidence/2026-10-30-saturn-original-kernel-probe.json) and
[host receipt](../evidence/2026-10-30-saturn-original-kernel-host.json) were read
before finalizing this handoff. No newly extracted Saturn sheet is established.
Upstream work still supplies hypotheses, not automatic Neptune validation.
No Power Bomberman work is on this queue.

## Dispatch this first

Do not start by building another emulator or completing all of Ghidra. Reconcile
the current lease and #33/#464/#483 evidence; preserve the Gemini workspace and
EXP-SAT-ARCHIVE-002 reservation on #484. Use an isolated checkout of current main.
The first three bounded outputs should be:

1. Reuse #524's **completed original-kernel probe** and retain its CPU-only scope.
   Continue with an independent original-emulator caller/return observation;
   do not rerun an unchanged probe merely to generate activity.
2. Prove a read-only **named-section save-state adapter** against one accepted
   bridge checkpoint, exposing VDP1 VRAM plus coherent VDP2 CRAM/registers.
3. Recover one observed player/effect pattern, then publish a small verified
   **real sheet** with provenance, extraction recipe and preview in the private
   asset repository. One useful sheet is sufficient; do not wait for the atlas.

The first probe already passed on the VPS: two fresh 256-case runs match, and an
altered original return produced 128 mismatches. The reports share the upstream
interpreter and are not independent emulation. Continue towards a more substantial
gameplay routine and spritesheet rather than inflating that scope. The existing
first-success mail automation has its own durable delivery
state; this research handoff neither resets it nor authorises another email.

## New findings that change the approach

| Finding from inspected source | Consequence for the worker |
| --- | --- |
| Accepted Beetle serializes named `VDP1` and `VDP2` sections containing their graphics arrays. | Try parsing the bridge's raw serialization before modifying the core for VRAM access. |
| Its state framing uses little-endian lengths, but this revision writes numeric payloads as native host bytes. | A little-endian file header does **not** make the exported VRAM CPU-address-order big endian. Record and convert the producer's word order. |
| VDP2 keeps both raw registers and CRAM; the renderer uses sprite type and CRAM address offsets. | A bank number and a guessed RGB555 palette are insufficient for a credible colour sheet. |
| Ymir headless currently has protocol definitions/tests but a configuration-only `main()`. | Do not make this purported command server a prerequisite or report it as functioning. |
| The upstream Bomberman lab already records memory, events and write streams, and discloses missing DMA writes. | Reuse narrowly scoped adapters and compare event order; do not equate a CPU store log with every memory mutation. |
| Upstream object documentation crosses its declared stride and disagrees about bombs. | Validate structure fields and allocation behaviour before adopting a schema. |
| A firsthand prototype analysis identifies a debug menu and says a related menu exists in retail. | Find the homologous retail dispatcher via strings/control flow; prototype addresses are not retail patches. |
| The static recompilation toolkit lists several desirable extractors and fingerprinting as future work. | Treat the feature table's “still to do” column as missing capability, not an installed exporter. |

## Source and build anchors

Source IDs below refer to exact files and Git blob receipts in the source JSON.
These pins are inspection inputs, not attestations of a locally built executable.

| Component | Inspected revision | Useful source IDs |
| --- | --- | --- |
| Accepted Beetle Saturn | `01bc063fdd0fb5fc208850c9ecc658834df762ab` | `core-libretro`, `core-state`, `core-state-h`, `core-ss`, `core-vdp1`, `core-vdp2`, `core-vdp2render` |
| pc-saturnbomberman | `c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3` | `gameconfig`, `gamestate`, `game-lab`, `gameresearch`, `memorynotes` |
| Its saturn-recomp submodule | `f20de940e8013fc84103a5b39c4069ed8071b1f9` | `recomp-readme`, `recomp-config`, `recomp-match`, `disc` |
| Ymir headless | `023d351aa172213c7a320817214368f47ac14125` | `headless-main`, `headless-config`, `headless-command`, `headless-protocol`, `headless-types` |
| Headless repository's Ymir gitlink | `7283a89888470d974e512222e796815b69ba2eb5` | Dependency pin observed in its recursive Git tree; not a tested integration. |
| Ghidra Saturn loader | `c489a190a79d2634b9ecf82e2c0dcec8fd999cf5` | `loader` |

The first original-file input is `/BOMSS/0KRNL.BIN`, 786432 bytes, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
SHA-1 `6fc53e5715d89cae7b4684bb3b65165ac1865736`, loaded at `0x06006000`.
Verify it against the accepted input lock; do not infer release identity from a
filename. The accepted USA cue is under
`/home/dev/Sega-Saturn-BIOS/Saturn-Bomberman-EN/`; reuse #473's validated file
extraction instead of concatenating tracks. Keep original cue/BINs unchanged.

## A. Recover original code with the smallest useful experiment

### S01 — extend the reproduced kernel probe with original callers (#483)

**Baseline achieved in #524**, commit `77e78f02e30e098390a0b033aa8120aad83bde3e`.
The result digest is `76c3b831d03cbe47a27db58ca6321e5b9f788396b3a8fc70119a69a8f6fa047b`.
The host receipt records two exit-zero, byte-identical reports and an actual
in-memory original-instruction mutation rejected by the comparator. Review those
receipts first; the commands below describe regeneration, not unfinished work.
The next new output is a bounded original-emulator trace of arguments, returns,
caller identity and the executed instruction regions. Keep graphics work moving
independently if that requires a separate instrumentation recipe.

`tools/saturn_lab/probe_kernel.py` targets entry `0x0600A4B0` in the pinned USA
kernel, corresponding to file offset `0x44B0`. Its hypothesis is a priority
selector: bit `0x4000` wins and returns 3, otherwise `0x2000` returns 2,
`0x8000` returns 1, `0x1000` returns 4, otherwise 0. The original instructions,
not a fixture substituting this expression, must execute in the pinned interpreter.

After resolving the actual extracted file and pinned tool checkout on the host:

```sh
python3 tools/saturn_lab/probe_kernel.py \
  --kernel "$SATURN_USA_KERNEL" \
  --saturn-recomp "$SATURN_RECOMP_PINNED_CHECKOUT" \
  --report "$NEW_PRIVATE_KERNEL_REPORT"
```

The variables are host-resolved paths, not values supplied by this report. The
script verifies the exact kernel and three interpreter source hashes. Preserve
the report, process exit status, command, source revisions and input-lock digest.
The 256 samples exercise combinations of the relevant bits plus selected other
patterns; they are not exhaustive across all 32-bit arguments. Its negative
controls must reject changed result/priority semantics. Report the instruction
range actually executed, registers consumed/clobbered and termination condition.
Do not invent its gameplay meaning from the bit pattern. A subsequent caller
trace can establish whether these bits represent direction, mode or another tag.
The first CPU-only result is useful even before that caller is understood.

### S02 — recover the RNG transition and bounded-draw rule (#483/#492)

Upstream source names `random_index=0x060BF4F4`, a 55-entry state table following
it, and the call `f_0600A0EC(10)` in illness selection. This is a **candidate**,
not a fully specified recurrence. Determine element width, taps, modulo/bounding
logic, signedness and seed routine from original instructions and real state.

Capture entry/exit for 1, 2, 10 and representative larger bounds. Exercise the
index-wrap boundary and zero/high-bit table values in isolated execution; label
those states constructed. Separately record at least one unmodified natural
caller sequence. Compare every touched state word and output, not just a histogram.
An intentionally wrong tap or signed comparison must fail. This could produce a
compact meaningful routine with direct use in deterministic CPU/mechanics tests.
Do not claim that matching RNG values makes two entire runs deterministic: the
number and timing of calls also matter, especially with free-running CPUs.

### S03 — recover the actual bank decompressor (#484/#483)

The upstream research file identifies `0x06033E0C` as an instruction storing into
a 256-byte decompression ring at `0x060C1260`, with a file-loader path through
`0x06009470`. Those are trace anchors, not established function boundaries or a
format specification. Do not assume generic LZSS constants because a ring exists.

With #484's current owner, capture an actual loader call for one base1/normal2
resource. Record source file offset/extent, destination and expected output length,
registers, prior ring contents and the complete bounded writes. Try verbatim load
and relocation checks first; only claim compression where input/output prove it.
Then recover flag-bit order, literal/reference distinction, length/distance
encoding, ring initialization, overlapping-copy semantics and termination.
Test truncation, impossible reference and exact-output-length boundaries against
the real routine where feasible. Prove the decoded bytes match a **resident
original-game range**, not only a decoder/encoder round trip. Correlate one decoded
pattern to S06/S07 rather than labelling a bank “sprites” solely from its name.

### S04 — recover one sprite-sort list operation (#483/#485)

`memorynotes` names 500 head/tail buckets at `0x060EBA80`, their pointer at
`0x060FBFA4`, append code `0x060AA50C`, and traversal/reset code `0x060AA57C`.
Use these as original-code entry candidates. A minimal harness can test an empty
bucket, repeated appends, two buckets, equal-key order and traversal/reset. First
recover node/index widths and sentinel values from bytes; do not seed them from
an assumed C linked-list layout. Verify returned command ordering in one original
frame. A missing head reset or reversed equal-key ordering must be detected.
Unreferenced stale tail words may legitimately differ, but demonstrate that they
are unread before excluding them from comparison. This result links game logic
to the graphics pipeline without requiring the full renderer.

### S05 — explain one scoring/growth transition (#483/#493)

The upstream `Code and RAM worth knowing` table points at `0x06021604` for
points/scoring and dino growth. Its config identifies score `0x060C0690` and growth
data `0x060D82DC`; thresholds 5000 and 15000 are upstream observations to test.
Recover the original call contract and arithmetic first. Compare a natural pickup
without a rider, a pickup while riding, threshold crossings and a second player.
Use constructed overflow/negative tests only after establishing signedness and
width. Record whether display score, extra-life accounting and growth are separate
updates. Do not infer all scoring rules from one increment.

## B. Make save states a graphics acquisition route

### S06 — parse named state records before adding a new core API (#485/#482)

This is the highest-value new tooling idea from this investigation. `core-libretro`
calls `MDFNSS_SaveSM` from `retro_serialize`; `core-state` shows the framing.
The raw core buffer begins with `MDFNSVST`, not an unspecified emulator dump.
RetroArch or another frontend may wrap/compress its saved file; inspect the bridge's
actual bytes and retain both the wrapper identity and the unwrapped payload hash.
Do not scan arbitrarily for magic and silently treat the first occurrence as valid.

For the **pinned revision only**, implement this strict read-only parser contract:

| Structure | Encoding / check |
| --- | --- |
| Header | 32 bytes; first 8 bytes `MDFNSVST`; version at byte 16 and recorded length at byte 20, both u32 little endian. |
| Length boundary | Require `32 <= recorded_length <= actual_buffer_length`; constrain all parsing to it; retain/hash any frontend padding separately. |
| Section | 32-byte zero-padded name followed by u32 little-endian payload byte length. Bound before entering. |
| Field | u8 name length, that many name bytes, u32 little-endian data byte length, then the data. Validate every bound before reading. |
| Identity | Use `(section, field)`, not just `VRAM`; reject duplicate required identities. Unknown bounded fields can be indexed and skipped. |
| Numeric data | `SubWrite` copies numeric arrays directly at this pin. Payload word order is the producer's native order; the framing's LE lengths do not establish it. |

The source header's `RLSB16` names are not proof that this implementation performs
normalization: inspect the writer actually called. On the expected little-endian
VPS, serialized uint16 arrays need adjacent-byte swapping to produce the existing
exporter's **big-endian CPU address order**. Record architecture/order and establish
this using an independent CPU-memory read or inspected command words. Reject an
unknown producer layout rather than guessing. Never swap byte-oriented fields or
assume every section consists of 16-bit words.

Required fields from `core-vdp1` / `core-vdp2` / `core-ss`:

| Section.field | Expected payload at this pin | Purpose |
| --- | --- | --- |
| `VDP1.VRAM` | 524288 bytes (262144 uint16s) | Command records, source patterns and lookup tables. |
| `VDP2.VRAM` | 524288 bytes | Background maps/pattern data; not the whole mirrored CPU address aperture. |
| `VDP2.CRAM` | 4096 bytes (2048 uint16s) | Original palette state. |
| `VDP2.RawRegs` | 512 bytes (256 uint16s) | Palette, sprite type, background configuration context. |
| `MAIN.WorkRAML` / `MAIN.WorkRAMH` | 1048576 bytes each | Distinct low/high work RAM; convert uint16 backing order before CPU byte addressing. |

Also retain VDP1 draw phase, `CurCommandAddr`, `RetCommandAddr`, `FBDrawWhich`,
`TVMR`, `FBCR`, `PTMR`, `EDSR`, and VDP2 CRAM/resolution/interlace context. Field
widths come from their declarations; do not apply the VRAM conversion to scalars.
`CurCommandAddr` is a **uint16 index**; the source advances it by `0x10` per command.
The existing exporter takes a **byte offset**, so the conversion factor is two.

Acceptance: parse the same real checkpoint twice; recover identical arrays and
metadata; compare at least a command and a palette span against a separate memory
read/export. Test truncated header/section/field, duplicate VRAM, wrong lengths,
swapped payload and oversized recorded length. A synthetic state validates the
parser only. A save state can be internally consistent while captured midway
through a draw; freeze at the bridge boundary and disclose the observed phase.
Do not wait for `retro_get_memory_data(RETRO_MEMORY_VIDEO_RAM)`: this core's
implemented memory API exposes work RAM/backup, not this graphics contract.

### S07 — select commands and resolve genuine colours (#485/#487)

Feed S06's normalized snapshot into the existing
[`export_vdp1.py` contract](../../../tools/saturn_lab/VDP1_EXPORT.md).
First inventory observed colour modes and pattern extents. Prefer an actually
observed supported RGB pattern for the first preview; do not force the game into
a synthetic RGB case simply to obtain a green result.

For indexed data, implement only the observed sprite type/CRAM mode first, with
explicit rejection of unsupported cases. `core-vdp2render` is a concrete reference:
`SPCTL` is handled at register offset `0xE0`, sprite CRAM offset at `0xE6` bits
4–6. The sprite type's dot-code mask separates palette index from priority/colour
calculation bits; its selected offset is shifted by eight before palette lookup.
`CacheCRE` shows that 1024/2048 RGB555 and 1024 RGB888 modes have different layouts.
These are source observations to compare with Sega's VDP2 manual, not a shortcut
that assumes every colour word is a direct CRAM index.

Keep native sample, pre-composition colour word, palette lookup and final preview
as distinct products. Disclose zero transparency, SPD, end-code, shadow, mesh,
shading and priority support. A source-pattern sheet need not reproduce final
scanline composition, but must state that scope. The current RGB exporter expands
five-bit colours for an image; the core's colour cache uses top-bit expansion.
Define a comparison domain (native words or a documented expansion) before calling
small RGB differences a palette failure or silently accepting them.

For validation, deliberately alter one used palette entry, nibble order, CRAM
offset and sprite type. Each applicable comparison must detect the change.
Preserve unmodified output. Use a second debugger/exporter or a separately
implemented manual-based resolver for the same native data; the same renderer
used twice is repeatability, not independent validation.

### S08 — walk the actual command flow (#485)

Do not linearly export every 32-byte-aligned blob as a sprite. `core-vdp1`'s
`DoDrawing` has next, assign, call and return flow, skipped commands and draw-end.
Preserve clipping/local coordinates even when exporting source orientation.
At this pin the runtime uses a single return slot, not an invented unbounded call
stack. Recover byte-address translation from the original link field and the
core's word-index operations; test it against one actual list. Bound visits and
detect cycles/out-of-range targets. Separate a list reconstructed from start from
the remaining work at a mid-draw checkpoint. Compare visited command IDs with a
bounded instrumented trace before using list discovery as provenance.

### S09 — turn recovered patterns into one useful animation sheet (#487/#512)

Capture a short deterministic sequence: idle, one walk direction, bomb placement,
or one effect. Associate object/update identity with command, source pattern,
dimensions, palette state and frame/tick. Dedupe with **native bytes + dimensions
+ interpretation + palette identity**, not source address alone: memory is reused
and palette animation changes an otherwise identical pattern. Keep source flips
as metadata; do not count mirrored images as newly recovered art.

Pack the verified frames with explicit rectangles, origin/anchor, duration and
ordering into one PNG plus JSON. Deterministic row packing is adequate; no texture
optimiser or Godot integration is required. Save a preview at a concrete private
repository path under a Saturn/build namespace. Link source revision, capture and
command IDs, tool revision, hashes and exact regeneration command. Original
captures stay private on the host. Reproduce into a fresh directory and compare
native output and decompressed pixels. A contact sheet of screenshot crops is a
different product and must not be labelled VRAM extraction.

### S10 — recover a background as cells rather than one flat screenshot (#486)

Use S06's matching VDP2 VRAM/registers/CRAM. Choose an enabled simple cell plane,
then derive character size, bit depth, pattern-name size, plane/map base, palette
selection and flips from the actual register values. Decode one cell and a small
map patch before the entire level. Explicitly reject rotation/line-scroll/bitmap
modes until implemented. Compare an unscrolled patch with the original output and
mutate a pattern-name entry/palette index. Distinguish visual tiles from the
logical collision grid; changing one does not imply the other changed.

## C. Turn reference memory into measured mechanics

### S11 — validate the object/map schema before exporting it (#480/#493)

Candidates from `gameconfig` and `gamestate`:

| Candidate | Address/layout | First falsification experiment |
| --- | --- | --- |
| Logical map | `0x060EC8B0`, 64×64 uint16 cells; upstream masks solid `0x80`, item `0x40`, soft `0x10`, bomb `0x20`, fire low three bits. | Observe a natural bomb placement, flame and block destruction; pair each bit change with original writer PC. |
| Objects | `0x060D5F00`, claimed stride `0x7C`; update +`0x30`, flags +`0x34`, cell +`0x44`, x/y +`0x48`/+`0x4C` 16.16. | Follow player 1, player 2 and one enemy through spawn/movement/death; recover allocation stride from code. |
| Item indirection | Hidden-item map `0x060F08B0`; slots `0x060DFB96`, eight bytes each, kind at +5. | Break one ordinary item-bearing block and trace lookup to spawned pickup. |
| Stage | `0x060C179A`, `0x060C029C`, `0x060C029E`, `0x060C17A0`. | Compare load, restart and continue; distinguish requested, active and saved state. |

**Two upstream contradictions deserve explicit resolution.** The config describes
fields at +`0x7C`, +`0x7E` and +`0x80` while declaring stride `0x7C`; those offsets
cross a nominal record boundary. They may describe related storage or mistaken
notes. Do not generate a C struct or write them automatically. Also `gamestate`
describes bombs among object slots while `gameresearch` says bombs are not objects;
`game-lab.bombs()` uses map flags instead. Determine whether there are separate bomb
pools, transient slot use, or stale documentation by observing creation/destruction.
Use address/PC evidence to resolve it rather than voting between comments.

### S12 — distinguish the timebases (#492/#513)

Record at least: bridge frame/VBlank index, game poll counter at `0x06006108`,
stage update count, and relevant timer words. The upstream notes show the poll
counter can stop during disc loads while another VBlank counter continues.
Run a small sequence across a load, menu, pause, active match and restart. Determine
which counter advances and which game routine consumes it. Measure intervals by
event endpoints and count convention; label PAL/NTSC, interlace, speed hacks and
clock settings. Do not turn upstream “about 575” or an old European TAS observation
into an exact USA constant. A comparison that aligns solely by wall clock can
misclassify a loading offset as a mechanics discrepancy.

### S13 — learn original CPU decisions without replacing them (#490/#493)

Use ordinary original CPU play first. Sample player/CPU positions, nearby map
bits, available bombs, action transitions and RNG calls. Identify the actual CPU
update function via an object callback and its caller; the player update
`0x06015358` is only a lead, not proof of a shared AI routine.

Then construct paired checkpoints differing in one factor: escape corridor,
blast range, remaining fuse, soft-block reward, opponent distance, or CPU level.
Log all forced writes and validate each field through S11. Repeat the same seed
and separately sweep seeds; separate deterministic branch rules from randomized
choices. Recover one decision branch and its constants with an original trace,
then an independent implementation and a deliberately wrong danger test. Keep
faithful Saturn policy measurements separate from stronger Neptune bot design.

### S14 — measure interactions as a matrix (#493)

Start with plain/remote/spike/rubber/power/line bombs and one mobility ability.
For each bounded pair record setup, stimulus, affected logical cells, object
states, damage and timings. Prioritize counterexamples: spike through soft blocks,
kick into a wall, thrown versus placed bombs, illness versus capacity upgrades,
invincibility expiry on a flame boundary, and timer expiry while paused/frozen.
Use a naturally reached example to anchor each forced setup. A route with
invincibility or manually struck enemies can expose animations but cannot prove
ordinary damage, difficulty or legal clear behaviour. Preserve failing cases and
unknown item functions rather than assigning familiar Bomberman names by analogy.

## D. Other high-value routes, with honest capability checks

### S15 — find the retail test menu through cross-references (#480/#488/#489)

Bo's firsthand [prototype investigation](https://32bits.substack.com/p/the-longest-fuse)
shows TEST OPTION with media/sound and save-data functions; it reports a related
menu in the final game. Its flag `0x060C1464` and instruction patches apply to the
Flash Sega Saturn prototype studied there, not automatically our USA kernel.
Start by locating retail menu strings and their pointer/control-flow references,
then compare homologous routines between accepted USA and Japan builds. Recover
the retail guard and dispatcher before any patch. Keep an instrumented menu
profile separate from ordinary boot; back up a separate test save directory.

This could expose sound IDs, resource numbers and ending playback with much less
autoplay, but it is still a hypothesis for the supplied builds. Success is a
documented retail entry path and one selected resource reproduced from its source;
seeing a menu alone is not a code/spritesheet milestone.

### S16 — isolate sound driver and samples, not the whole archive as PCM (#488)

`gameconfig` identifies a 68000 sound-driver slice in PROGRAM.BIN starting `0x44`,
length `0x63D4` (exclusive end `0x6418`), loaded at sound RAM start. `gameresearch`
also reports runtime self-patching of driver instructions. Verify that slice on
our original and capture the resident driver before interpreting its disassembly.
Driver bytes are not PCM and unknown bank bytes are not automatically samples.

Choose one original SE TEST/game event; pair its command with SCSP slot start,
loop/end, bit depth, pitch and sample address. Export only that bounded sample,
then regenerate against the same source range. Preserve raw sample rate/pitch and
distinguish source sample from the emulated output mix. Trace addresses around
`0x1000` carefully: the BIOS's prior sound program can occupy the same RAM before
the game's driver loads. Label generic Sega driver code separately from game
content; a library identification is not original game-logic recovery.

### S17 — use Ghidra and signatures to remove distractions (#481/#480)

The Saturn loader's own README says its ISO route loads only the first file.
Importing the disc successfully can therefore leave the real kernel absent.
Import the verified raw kernel at its established base, or a correctly identified
state format into mapped RAM. The loader supports Mednafen/Yabause states, but
that does not establish compatibility with this modified Beetle serializer.
Validate the magic/section parser first; do not rename a file to fake support.

The loader recommends ApplySig and CyberWarriorX Sega library signatures. Check
their actual compatibility, licence and signature scope before applying them.
Use matches to tag candidate SDK/CRI/BIOS routines, retaining confidence and byte
evidence. A signature match is classification, not proof that the neighbouring
game routine has the same prototype. Cross-region `recomp.match` can help find
homologous functions, but duplicated tiny helpers and relocated literals require
caller/CFG checks. Compare USA/JP names only after hash/build and module mapping.

For a recovered function, export disassembly with resolved literal pools, inferred
control flow, argument/register contract, memory effects, readable pseudocode and
an executable original-byte comparison. Preserve uncertainty in names/types. An
SH-2 instruction in a delay slot must execute with the correct branch semantics;
“looks like C” is not validation. Setjmp/longjmp task resumes and shared tails
also defeat naive function-boundary assumptions.

### S18 — capability test Ymir before spending a build cycle (#479)

At the pinned headless revision, `main.cpp` calls `LoadConfig`, `ValidateConfig`,
prints paths/slave configuration and returns 0. `debug_command.hpp` names
`mem.peek`, `regs.read`, `exec.stepi`, breakpoints and other methods, but names,
JSON adapters and unit tests are not a running emulation/debugging service.
Do not fabricate JSON-RPC invocation examples or claim a successful process exit
means a BIOS/game ran. Recheck implementation changes if adopting a newer pin.

The useful future experiment is narrowly scoped: prove an emulator loop, request
transport, pause/step semantics and real memory reads on a private original before
building a capture adapter. Prefer the accepted Beetle state route for the
immediate result. An independent Ymir capture can later increase confidence; two
Mednafen-derived render paths share ancestry and should be described accordingly.

## Experiment discipline and handoff format

Use configured factory budgets and shared provider limits. The queue's attempt
bounds are proposed stopping points, not new spending/concurrency authorisation.
Run one owned bounded slice at a time; scripts perform repetitive frame/byte
loops, while the worker inspects compact summaries. If a proposed path needs a
new capability, produce a small failing capability receipt and switch to an
already runnable experiment rather than silently expanding the prerequisite.

Every result should contain:

```text
experiment ID; owner/lease; status (hypothesis / falsified / reproduced / verified)
game + product/version/region; original input lock and file hash
source revision + original address/range or resource offset/length
tool revision/executable hash + settings + command + exit status
checkpoint/input timeline; frame/tick/timebase; natural versus forced writes
output paths and SHA-256; independent comparator and shared ancestry
negative control and observed failure; readable analysis; remaining uncertainty
PR + private derived artifact/preview link; trusted host receipt when available
```

Use a fresh output directory. A real, partial verified result should be reviewable
immediately, without requiring full-game integration or a merged PR. Keep full
discs, BIOS, states, raw memory and credentials outside Git. Derived sheets belong
in the authorised private `elgansayer/SaturnBomberman-Assets` namespace with build
provenance. Preserve root Apache-2.0 and upstream/component notices; do not copy
GPL renderer implementations into Neptune simply because their behaviour was
useful for this analysis. Do not transmit raw private inputs to model providers.

## What to reject as completion

Installer success, emulator boot, another inventory, synthetic PNGs, copied
upstream screenshots, an untranslated routine list, a decoder that only round
trips itself, unsupported palette guesses, a protocol schema without a server,
and a folder called “sprites” without original offsets/recipes are not the desired
result. A failed hypothesis with a reproducible receipt is useful research, but
must stay labelled failed. Tool CI verifies tooling and metadata; only the
original-input experiment can establish original-game recovery.
