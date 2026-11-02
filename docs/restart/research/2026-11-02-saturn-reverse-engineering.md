# Saturn Bomberman reverse engineering: evidence and next experiments

Checked 2 November 2026 against local source and committed receipts. Primary
reference: USA MK-81070 V1.003; Japan T-14302G V1.000 remains a separate profile.
The programme has recovered useful bank structure, decoded real resources,
reproduced a small original function and published one verified source image.
Complete code recovery, complete asset extraction and whole-game behavioural
reconstruction remain open. Their total denominators are not yet known.

This report reconciles the earlier [deep dive](2026-10-30-deep-dive.md),
[VPS playbook](2026-10-30-saturn-vps-playbook.md),
[whole-sheet investigation](2026-10-30-whole-spritesheets.md) and later accepted
results. It adds no new original-emulator execution. Follow
[research execution](../RESEARCH_EXECUTION.md),
[the factory/Saturn priority](../FACTORY_FIRST_GOAL.md) and
[exact fidelity acceptance](../SATURN_FIDELITY.md). Preserve active #487 work;
this investigation does not restart its owner or duplicate that extraction.

## 1. What the accepted evidence establishes

### Original inputs and repeatable control

The [input receipt](../evidence/2026-10-29-real-saturn-inputs.json) and
[disc inventories](../saturn-disc/README.md) identify complete USA and Japan
30-track images, matching regional firmware, hashes and separate configuration
profiles. Each contains 29 CD-DA tracks. No accepted PAL input profile is recorded.

The [bounded bridge result](../evidence/2026-10-29-libretro-bridge.md) records a
3,240-frame USA run, checkpoint after frame 3,000 and three fresh-process replays
of the remaining 240 frames. Video, audio sample counts/hashes, controller masks
and absolute frame observations match. Japan has a separate 300-frame smoke run;
its equivalent three-process replay remains unverified. Independent callback
delivery to ports is not yet proof of identified players moving in a battle.

The accepted Beetle source revision is
`01bc063fdd0fb5fc208850c9ecc658834df762ab`, core SHA-256
`c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e`.
Actual locks additionally bind BIOS, all tracks, settings, frontend, support
modules, interpreter and log adapter. The queried output rates are
59.82650314089141 Hz and 44,100 audio samples per second. These are the pinned
core's reported rates, not hardware measurements or permission to assume every
game task updates at one tick per video frame.

### Filesystem and live bank directory

Static inventory records 430 USA and 25 Japan ISO-9660 files, validated Track 01
EDC and complete sector accounting. Structural classification of a container
does not recover the behaviour of its contents. In particular, the original
236/240 `PROGRAM.BIN` header counts are not live bank, level or actor counts.

The [kernel-directory receipts](../saturn-archive/README.md) resolve the scanned
headers against the directory actually indexed by the original kernel:

| Accounted structure | USA | Japan |
| --- | ---: | ---: |
| Live directory entries | 72 | 66 |
| Named headers at active entry starts | 68 | 66 |
| Headerless active entries | 4 | 0 |
| Residual headers within live slots | 43 | 8 |
| Headers in the unreferenced tail | 125 | 166 |
| Referenced 2,048-byte sectors | 5,277 | 4,905 |
| Referenced bytes | 10,807,296 | 10,045,440 |
| Unreferenced tail bytes | 2,169,666 | 2,931,522 |

Both complete `PROGRAM.BIN` files are 12,976,962 bytes. All live directory
destinations fit Low Work RAM through `0x00300000`; there are no inter-entry
sector gaps in these receipts. Earlier apparent out-of-RAM voice banks belong
to residual/tail data. Unreferenced data remain a discovery target for unused
content; absence from this directory alone does not establish unreachability
through every code path.

USA directory arrays are at `0x06093ECC`, `0x06093F5C`, `0x06093FEC`; Japan's
are at `0x06095018`, `0x0609509C`, `0x06095120`. The four USA-only headerless
entries, including ID 23 at `0x002DA000` and IDs 41–43 at `0x002FB000`, have
bounded source spans but unresolved runtime purpose.

### Real bank decoding and resident comparisons

The [archive result and receipts](../saturn-archive/README.md) establish
verbatim staging of two banks into Low Work RAM. USA `base1`, ID 1, starts at
sector 16 and occupies 344,064 bytes at `0x00200000`. `normal2`, ID 5, starts
at sector 912 and occupies 573,440 bytes at `0x00254000`; it is byte-identical
between the supplied USA and Japan discs. The compared resident bank bytes and
headers remain unchanged, rather than undergoing the hypothesised load-time
pointer relocation.

The retained decoder produces these scoped resource counts:

| Decoded structure | base1 | normal2 |
| --- | ---: | ---: |
| Slot 8 descriptor-pointer entries | 1,062 | 873 |
| Unique pixel blocks within the bank | 841 | 566 |
| Compressed pixel blocks | 838 | 566 |
| Raw format-code-5 blocks | 3 | 0 |
| Decoded pixel bytes | 235,232 | 270,272 |
| Slot 0 pattern blocks | 3 | 3 |
| Slot 0 decoded bytes | 36,032 | 276,416 |
| Slot 1 palette records / bytes | 36 / 1,856 | 18 / 2,752 |
| Slot 7 grids / bytes | absent | 9 / 73,728 |

These are [base1](../saturn-archive/usa-mk81070-v1003.base1-decode.json) and
[normal2](../saturn-archive/cross-region.normal2-decode.json) receipt counts.
They are not all characters, all animation frames or globally unique art: shared
blocks, null descriptors, cross-bank duplicates and logical repeated frames
require separate accounting. All recorded pixel blocks decode without the
reported stream/predictor failures, while original resident confirmation covers
a subset: 623 base1 blocks (155,200 bytes) and 150 normal2 blocks (70,144 bytes).
Three normal2 8,192-byte grids and selected VDP2 resources also match resident
bytes. Palette searches find matching byte spans in CRAM/shadow memory; they do
not by themselves prove destination offsets, colour interpretation or assignment
to a particular sprite.

The two fresh `normal2` runs retain identical frame-30,360 checkpoints after
20,160 frames from an earlier checkpoint. This is useful original repeatability
and residency evidence. The recorded route uses an attract/demo scene; it does
not prove a user-controlled campaign route, normal damage rules or a legal clear.

**Read the [2 November correction](../evidence/2026-10-30-gemini-program-bin-archive-002.md#correction-and-supersession--2-november-2026)
before using the historical archive narrative as a format specification.** Its
codec bit order, predictor/ring descriptions, slot layouts and CUE hashes conflict
with merged code or corroborated metadata. The correction preserves receipt
identities, identifies those conflicts and separates source inspection from a
new original-host validation. New extractors must use the implemented interfaces
and confirm remaining semantics against original consumers.

Slot 8 currently follows a descriptor pixel pointer at `+16` and requires 20
readable bytes; this is not a proven stride. Dimensions, anchors, palette,
part-grouping and animation fields remain open. Slot 2 is polymorphic: base1
tilemaps and normal2 SCSP/DSP command data must not share one guessed parser.
Slots 3–6/9 are bounded pointer tables with unresolved inner semantics.

### Original function recovery

[EXP-SAT-CODE-001](2026-10-30-saturn-original-kernel-result.md) executes unchanged
USA kernel instructions at `0x0600A4B0` in the pinned upstream SH-2 interpreter.
Two fresh runs agree for 256 constructed arguments, and a changed original return
instruction is detected. Its recovered rule is:

```c
if (input & 0x4000u) return 3;
if (input & 0x2000u) return 2;
if (input & 0x8000u) return 1;
if (input & 0x1000u) return 4;
return 0;
```

The sampled original bytes support this bounded rule. They do not establish its
physical direction names, natural callers, full ABI, device/interrupt effects or
Saturn cycles. Original-emulator call/return observations and further substantial
functions remain open. Do not count the 23 visited instructions as 23 recovered
functions or as a whole-program coverage denominator.

### Coherent graphics and one published pattern

The [state acquisition result](2026-10-30-saturn-state-host-proof.md) verifies
normalization of VDP1/VDP2 VRAM, VDP2 CRAM and raw registers against a separate
direct-memory read of the same accepted restored core. All 1,053,184 bytes match
in both fresh processes; wrong-order and changed-byte controls are detected.
This is independent acquisition from the state parser, with shared emulator
lineage. It does not independently certify Saturn hardware behaviour.

The [first RGB result](2026-10-30-saturn-first-rgb-pattern.md) exports one actual
320×160 RGB555 source pattern at frame 3,000, VDP1 command byte offset `0x60`,
source byte offset 32,768. Its 102,400 native bytes and 51,200 pixels were checked
through a separate PNG/native interpretation; repeated exports and a colour-bit
mutation were retained. The private artifact was published and read back at an
immutable assets commit. It appears to be intro art; source-file/resource mapping
and subject remain unresolved. This is one source pattern, not an identified
Bomberman sheet or the final composed Saturn frame.

## 2. Whole-game accounting and what remains open

The 50,407-file [existing asset audit](../evidence/2026-10-29-gemini-asset-audit-463.md)
includes substantial GameMaker export data and 26,785 redundant duplicate files.
Filenames and existing rips cannot become a Saturn denominator. Preserve their
provenance, aliases and history. The measured disc, bank, pixel-block and logical
animation inventories answer different questions and must remain separate.

| Domain | Current evidence boundary | Next missing contract / existing task |
| --- | --- | --- |
| SH-2 kernel, slave tasks, overlays and dynamic targets | Two releases' directory maps and one bounded helper execution; decoded bytes also contain data/literals | Validated executable ranges, function boundaries, callers, dynamic targets and substantial original-byte tests; #480–#483/#497 |
| VDP1 resources | Two banks' pixel blocks, selected resident matches and one RGB pattern | Actual command flow, palette-bank colour semantics, descriptor fields, part composition, animation order and native durations; active #487 with #485 |
| VDP2 resources and maps | Selected pattern/tilemap/grid bytes decoded and matched | Register-derived plane layout, cells/palette/flips, scene-specific destinations, collision meaning and event/spawn consumers; #486/#395 |
| Audio and movies | 29 CD-DA tracks per release, structurally identified FILM/AIFF resources, selected SCSP transfer bytes | Driver/68000 and DSP interpretation, PCM/sequence layout, trigger/loop/priority/pan/pitch and exact game presentation timeline; #488/#489 |
| Navigation and persistence | Bounded bridge and attract routes | Input-only normal/co-op/Master/Battle routes, state identity, save/continue/checkpoint flags, menus/fonts/text/camera and endings; #490/#494/#495 |
| Rules, actors and CPU | Source leads and reproducible original control | Typed state, fixed-point units, clocks/RNG/call ordering, movement/collision/fuse/flame/items, enemy/boss phases, original CPU and simultaneous-event boundaries; #491–#493/#396–#398/#407 |
| Regional, hidden and network paths | USA/Japan differences and bounded unidentified support files | Measured mode/topology limits, hidden/unused reachability, USA headerless resources and offline NetLink/XBAND semantics; #394/#397/#496/#497 |
| Production Godot comparison | Trace/PCM tools and factory verification interfaces | Equivalent campaign room and battle arena with independently retained exact state/pixel/audio output and mutation controls; #29/#76/#511/#513 |

The total counts of functions, rooms, route transitions, characters/variants,
logical animation sequences, enemy/boss phases, sound events and meaningful
interactions remain unknown. A nine-grid table is not necessarily nine reachable
rooms; a pixel-block count is not an animation-frame count. No percentage of the
whole game is supported by current evidence. The
[coverage ledger](../asset-audit/saturn-coverage-ledger.json) is useful but lags
some later results; zero aggregate entries must not erase accepted partial
recovery, and missing denominators must not be filled by guesswork.

The [36-entry starter catalogue](../../../tools/research_catalog/README.md)
and [418-feature backlog](../backlog/catalogue.json) have different purposes.
Their metadata checks do not execute the evidence or certify game completion.
Use stable discovered resource/route/actor IDs through #410/#515, keeping
discovered, decoded, executed, semantically validated, published, implemented and
exactly compared states distinct. Original names/comments may be irrecoverable
even when behaviour is understood.

## 3. Current FILM recovery result

A new [FILM parser/PCM extractor](../../../tools/saturn_film/README.md) now
recovers the three actual `audio/rips/BOMSS*.CPK` streams from assets commit
`445114300594db707c1085d8b6b33d50218cd582`. The
[complete derived receipt](../evidence/2026-11-02-film-recovery.json) records source,
tool and external executable hashes, tokenized commands, packet timing, decoded
sample/frame counts, repeated results and seven negative controls per movie.
All source containers remained unchanged.

| Existing container | Source SHA-256 | Video frames | Video duration | Stereo PCM sample frames |
| --- | --- | ---: | ---: | ---: |
| BOMSS1.CPK | `c070db915f55f821e5ff3e7d008723a5eebdd018a9faa26d7a60f7f0efdb35a3` | 2,504 | 100.16 s | 2,208,528 |
| BOMSS2.CPK | `10f6edcdb39593c7c859f4faf564e4f66b5c0600567f79a9d81a570cd2634bf8` | 2,845 | 113.8 s | 2,509,292 |
| BOMSS3.CPK | `d5325c7a00562ed494b1349a5452fa33da7ec442ed0dea28a7ba52fd3f0894ba` | 3,319 | 132.76 s | 2,927,360 |

All three use FILM 1.04, 320×160 Cinepak, a 600-Hz video clock and 24 ticks
per frame: exactly 25 fps. Their uncompressed stereo signed 8-bit PCM is planar
within each audio packet at 22,050 sample frames per second. The new extractor
interleaves each packet independently and converts signed bytes reversibly to
unsigned 8-bit WAV, with no resampling, normalization or discarded samples. Packet
tables retain every source span/hash, PTS, duration, keyframe flag and cumulative
audio sample offset. All header/table/payload bytes are accounted for.

The complete **15,290,360 PCM bytes** match FFmpeg 7.1.5 byte for byte; decoding
the exported WAVs returns those same bytes. A separate struct reader and channel
interleaver also matches all three streams. Every STAB video timestamp, duration
and keyframe flag agrees with FFprobe's packet output. Two complete FFmpeg RGB
framehash runs per movie agree for all **8,668 decoded frames**. This is full
container PCM recovery and repeated external Cinepak decoding, not two independent
video codecs or a newly implemented Cinepak decoder.

The installed FFprobe reports aggregate video-stream durations of 4.173333,
4.741667 and 5.531667 seconds: frame-count/600 rather than the actual
frame-count×24/600. Its packet timing is correct. The new tool uses STAB clock
ticks as the timing source instead of accepting this misleading duration field.
BOMSS2 and BOMSS3 audio each extend exactly **two sample frames** beyond video
(`1/11025` second); BOMSS1 ends exactly with video. Those differences are retained,
not trimmed to manufacture synchronization. Container timestamps do not establish
actual game trigger or Saturn presentation timing.

Malformed/truncated/overlapping streams, unsupported versions and noncontiguous
timing are rejected. Real negative controls reject truncation, overlapping packet
ranges, one-tick duration drift and unsupported version, and distinguish wrong
planar passthrough, an audio bit change and a changed packet timestamp. Fourteen
owned synthetic tests cover boundaries, exact signed channel samples, rational
timing, WAV reversal, missing tools, output preservation and private permissions.
The required aggregate now includes these FILM contracts without changing native
path classification or removing any existing check.

These files are explicitly labelled **prior-assets-unresolved-release**. They
are not identical to the supplied NTSC disc movies: the regional comparison
finds 3,414 BOMSS2 frames on both accepted discs versus 2,845 here. The 5/6 ratio
and 25-fps timing support the existing PAL hypothesis; they do not identify a PAL
disc. The derived WAVs, packet tables and recorded decoded-frame hashes belong in
`saturn/unresolved-release/film/` in the authorised private assets repository.
Do not adopt them as USA/Japan parity fixtures or close #489: original CD-DA,
stream selection, trigger/loop timing and runtime A/V comparison remain open.

Regenerate to a fresh private directory with installed FFmpeg/FFprobe:

```sh
python3 tools/saturn_film/validate_real.py \
  --input ../SaturnBomberman-Assets/audio/rips/BOMSS1.CPK \
  --input ../SaturnBomberman-Assets/audio/rips/BOMSS2.CPK \
  --input ../SaturnBomberman-Assets/audio/rips/BOMSS3.CPK \
  --output research-private/FRESH-MOVIE-VALIDATION \
  --timeout-seconds 120
```

## 4. Factory progress and execution access

Current source includes #576/#578's named supplied-trace contract and
#579/#580's [trusted original experiment recorder](../../../tools/factory/REFERENCE_RECEIPTS.md).
The recorder executes three bounded original replays and two comparisons through
the existing sandbox/shared host gate, with Ed25519 certificate verification and
task/head/base/policy/artifact bindings. Its implementation is meaningful progress
beyond plausible worker-authored hashes. Supplied-trace equality alone remains a
consistency check; an authority selected by the candidate is not trusted capture
provenance. Preserve the key/policy boundary and applicable negative controls.

The receipt tool does not automatically join authenticated originals to a new
Godot capture, integrate every live adapter selection, or prove continuous
issue-to-merge/restart recovery. These remain separate #76/#511 and #33/#536
acceptance. Read current service/lease evidence before scheduling providers;
reuse the shared control plane, account limits and manual sessions. The same
original core reached twice is repeatability, not an independent emulator oracle.

Historical media, accepted cores, checkpoints and orchestration recipes are
recorded under `/home/dev/Sega-Saturn-BIOS/` and the private research directories.
That VPS filesystem is not mounted in this cloud workspace; `/home/dev` is absent.
No configured VPS execution channel was available for this investigation.
Existing asset-repository files are available, which permits bounded static/media
work. No new BIOS boot, gameplay measurement, state rehash or private original
regeneration is claimed here. Do not ask for already-supplied discs again or
replace accepted reference identities merely to make a local experiment run.

## 5. Next bounded experiments

Select the first unowned eligible result after reconciling live issues/PRs/leases.
These extend accepted interfaces and active extraction rather than introducing
another programme or scheduler.

1. **Finish one useful sheet with active #487.** Its owner should join an
   identified scene/object to actual commands, native block IDs and coherent
   palette/register state, then record a short named idle/walk/effect sequence.
   Preserve source orientation, origins, logical repeated/blank frames, native
   durations and composite parts. Correlate several descriptors with original
   consumer reads before inferring dimensions or anchors. Regenerate a partial
   sheet/JSON map, compare native pixels and detect a changed palette/stride/frame
   order. Publish its exact covered modes/directions and remaining gaps.
2. **Unblock indexed VDP1 extraction through #485.** The existing
   [exporter](../../../tools/saturn_lab/VDP1_EXPORT.md) decodes six native texel
   modes but previews only supported RGB/LUT cases. Add one observed VDP2 sprite
   type/CRAM mode/offset resolver, or bounded next/assign/call/return command
   traversal with skip/end/cycle/range controls. Reuse
   [coherent state inputs](../../../tools/saturn_lab/STATE_GRAPHICS.md). Synthetic
   tests prove tool handling; an original command/palette comparison is still
   required before claiming new recovered colours or draw coverage.
3. **Recover one VDP2 patch through #486.** Decode an enabled simple cell plane
   from actual registers, pattern names, VRAM and CRAM. Compare one cell and a
   small unscrolled patch, then detect a palette/pattern-name mutation. Keep
   unsupported rotation/line-scroll modes explicit and the visual plane separate
   from the Slot 7 logical grid/event meaning.
4. **Advance original code and rules with a measured caller.** Through
   #482/#483/#491/#492, capture natural callers/returns of `0x0600A4B0`, or a
   bounded RNG transition around candidate `0x0600A0EC` and state `0x060BF4F4`.
   Pin touched state, argument/return width, order and units; test a wrong branch
   or RNG tap. Distinguish constructed isolated CPU inputs from natural execution.
   Then measure one movement/bomb boundary for #493, rather than repeatedly
   rerunning the already accepted selector samples.
5. **Connect the first production comparison.** Use #29/#76/#511 to bind an
   independently authenticated original capture and current Godot scenario to
   exact release/content/build/input/adapter identities. Record the first state,
   pixel and sample divergence in native units. One tick/order, palette/pixel and
   sample/trigger mutation must each fail its applicable check. Do not generate
   reference output from the candidate or relax an exact claim into a tolerance.

Once a slice is measured, expand through the same existing per-entity tasks.
Reachability, rare interactions, alternate modes and regional differences must
be reconciled with code/resource inventories before a whole-release completion
dossier is possible. All discovered entries passing is still insufficient when
discovery itself is incomplete.

## Sources and reproduction boundaries

The linked repository receipts identify commands, source ranges, hashes,
negative controls and private reproduction locations. Offline
`tools/saturn_disc/cli.py verify` and `tools/saturn_archive/cli.py verify` check
committed receipt structure/consistency; the corresponding `inspect`,
`decode-bank` and `compare-resident` commands need their actual private sources.
Do not confuse the two operations.

Primary source anchors retained from the earlier investigation:

- [Pinned pc-saturnbomberman](https://github.com/callumjenkins/pc-saturnbomberman/tree/c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3)
  and its [saturn-recomp dependency](https://github.com/callumjenkins/saturn-recomp/tree/f20de940e8013fc84103a5b39c4069ed8071b1f9):
  useful hypotheses/tools with disclosed forced routes and known divergences;
  upstream demonstrations are not accepted Neptune parity.
- [Sega VDP1 manual](https://antime.kapsi.fi/sega/files/ST-013-R3-061694.pdf),
  [Beetle core documentation](https://docs.libretro.com/library/beetle_saturn/) and
  [Mednafen Saturn documentation](https://mednafen.github.io/documentation/ss.html):
  format/control references, with actual capabilities and producer layouts tested
  against the pinned implementation.
- [Firsthand Saturn ripping notes](https://randomhoohaas.flyingomelette.com/spr/bomberman.html):
  evidence that useful sheets can be recovered and a warning about missing Normal
  Game animations; not a completeness receipt for our selected release.
- [Pinned source registry](saturn-vps-sources-2026-10-30.json) and
  [whole-sheet sources](whole-spritesheet-sources-2026-10-30.json): exact inspected
  source identities and availability limits. The existing Ghidra/Ymir leads must
  pass real capability tests; a loader import or schema is not a working debugger.

Keep discs, BIOS, full states and raw memory host-private. Publish verified
derived assets with provenance to the authorised private repository under #512;
engine licensing, reference content and public distribution remain separate.
