# Saturn lab: inputs and bounded libretro experiments

Python 3.11+, standard library only. The optional Linux libretro frontend also
requires a C compiler for its small log adapter and a separately built core.
Run commands from the repository root.
These tools operate locally; no files are sent to an AI service.

## Inspect supplied CUE media and firmware

```sh
python3 tools/saturn_lab/media.py inspect --root /private/supplied-inputs \
  --disc 'usa/game.cue' --region usa --output /private/evidence/usa.media.json
python3 tools/saturn_lab/media.py verify --root /private/supplied-inputs \
  --report /private/evidence/usa.media.json
```

`media.py` reuses the existing safe CUE dependency and SHA-256 readers. It reads
TRACK 01/INDEX 01 in MODE1/2352 or MODE1/2048, checks the raw sync/mode and Saturn
IP signature, and records product/revision, area and title. Field layout follows
the pinned Beetle `disc.c` reader; this is header identity, not full-disc EDC/ECC,
pressed-disc provenance or an emulator-boot guarantee. CHD header inspection is
not implemented. Every referenced audio/data file must exist.

Top-level `.bin`/`.rom`/`.bios` candidates are fingerprinted. Firmware selection
requires 512 KiB and the [Beetle compatibility-catalogue MD5](https://docs.libretro.com/library/beetle_saturn/#bios);
SHA-256 remains the research identity. Names never select firmware. Identical
aliases are preserved and selected stably; differing SHA identities under the
same expected MD5 fail. `--bios <relative-name>` requires that exact candidate to
match, useful for testing incorrect firmware. Reports include all candidate hashes.

The deterministic `neptune.saturn-media.v1` report is separate from the complete
core/configuration lock below. Verification re-reads header, firmware and files;
missing, tampered, wrong-region or incompatible firmware fail nonzero. Original
media are never changed. Test mutations belong in ordinary disposable copies.
Output cannot overwrite an input. Synthetic header/firmware tests validate these
tools only; real input acceptance must retain its own commands and reports.

## Inventory an existing asset checkout

```sh
python3 tools/saturn_lab/cli.py inventory /srv/neptune/repos/SaturnBomberman-Assets \
  --output /srv/neptune/private/manifests/assets.inventory.json
```

Reports sorted relative paths, byte sizes, streaming SHA-256 hashes and groups of
byte-identical files. PNG header dimensions are reported when readable; this is
not complete image validation or provenance certification. `.git`, `.godot`,
`__pycache__` and `.venv` directories are excluded. Symlinks and unreadable files
cause failure; they are not silently followed/skipped. An existing output file is
excluded from the inventory to keep repeat runs stable.

## Lock a reference input set

Place the actual inputs below a private root. In this example their relative paths
are `disc/game.cue`, `bios/saturn.bin`, `emulator/core.so` and
`settings/reference.json`. Substitute actual filenames and the correct region.
The settings file must contain a non-empty JSON object describing the actual
configuration intended for the future emulator bridge; this tool does not apply it.

```sh
python3 tools/saturn_lab/cli.py lock \
  --root /srv/neptune/private \
  --disc disc/game.cue \
  --bios bios/saturn.bin \
  --emulator emulator/core.so \
  --settings settings/reference.json \
  --region usa \
  --output /srv/neptune/private/manifests/reference.lock.json
```

The CUE and every referenced BINARY track are included. CUE references must use
portable relative paths within the CUE's directory (or its subdirectories).
Parent traversal, absolute paths, Windows separators and symlinks are rejected.
CHD is accepted as a single opaque input file; the tool does not decompress or
validate its container. WAV/MP3 track declarations, bare BIN and ISO inputs are
currently unsupported. Preserve the original complete disc separately.

```sh
python3 tools/saturn_lab/cli.py verify \
  --root /srv/neptune/private \
  --lock /srv/neptune/private/manifests/reference.lock.json
```

Verification re-hashes every input, validates the manifest and requires complete
coverage of the selected CUE tracks. Changing a track, BIOS, core or settings
causes a non-zero exit. Locks contain relative paths and can move with the input
root. They are not signatures: protect the lock itself in research evidence storage.

Output JSON is atomically replaced. Existing output must be a JSON document with
the same schema; unrelated files and symlinks are refused. Use a dedicated output
path. The lock command also explicitly refuses to overwrite selected inputs.

## Noninteractive original-game experiments

`frontend.py` runs one software libretro core in a fresh bounded subprocess.
It is currently a Linux, little-endian XRGB8888 research driver, not a game
dependency or a browser transport. Core binaries retain their upstream licences.
Only the independent driver, log adapter and synthetic test core are in this repo.

First build/pin the actual Beetle core and inspect actual media as above. Configure
ordinary private copies in a separate root; original files are never overwritten:

```sh
python3 tools/saturn_lab/frontend.py configure \
  --media-root /private/supplied-inputs --media-report /private/evidence/usa.media.json \
  --core /private/build/mednafen_saturn_libretro.so \
  --root /private/staged-inputs --output /private/evidence/configure-001 --timeout 120
```

The result gives the real generated lock path. Settings pin every option actually
declared by the core, region, twelve joypads across two multitaps, interpreter/host
identity, frontend/support modules and compiled log adapter. These last executable
components are transitively pinned by the locked settings and verified by this
driver before loading the core. `cli.py verify` alone verifies only the base input
lock. These are identity checks, not signatures or a native-code sandbox. Load
only a trusted pinned core; this command does not isolate host credentials.

Each run gets new private save data, seeded with valid Saturn SMPC RTC/NV bytes
for 2000-01-01 00:00:00, with host-clock auto-RTC disabled. Japan uses the Japanese
language setting. Pin the core when interpreting this NV layout. Settings changes
produce new content-addressed bundles/locks; old checkpoints fail identity checks.

An actions file is a JSON list, for example:

```json
[{"start":0,"end":15,"port":0,"buttons":["start"]},
 {"start":100,"end":115,"port":1,"buttons":["a"]}]
```

Ports and frames are zero-based; `end` is exclusive. Overlapping actions combine
button masks. Hold the same mask at every poll within that frame. Offsets are
relative to this run, including after a restore. Twelve exposed devices do not
prove the original game supports twelve players. Names are libretro joypad IDs,
not Saturn button labels: this pinned Beetle pad mapping uses `b` for Saturn A,
`a` for Saturn B and `r` for Saturn C. Preserve the mapping with the core version.

```sh
python3 tools/saturn_lab/frontend.py run --root /private/staged-inputs \
  --lock /private/staged-inputs/locks/ACTUAL.json \
  --output /private/evidence/boot-001 --frames 3240 --checkpoint-at 3000 \
  --actions /private/inputs/full.json --capture 2999 --capture 3239 --timeout 120
python3 tools/saturn_lab/frontend.py run --root /private/staged-inputs \
  --lock /private/staged-inputs/locks/ACTUAL.json \
  --output /private/evidence/replay-001 --frames 240 \
  --restore /private/evidence/boot-001/checkpoint.json \
  --actions /private/inputs/continuation-relative.json --timeout 120
python3 tools/saturn_lab/frontend.py compare --root /private/staged-inputs \
  --output /private/evidence/comparison-001 \
  --reference /private/evidence/boot-001/observations.json --reference-start 3000 \
  --candidate /private/evidence/replay-001/observations.json
```

For this example the replay actions must equal the full actions after frame 3000,
with 3000 subtracted from their start/end. `--checkpoint` saves at the end instead.
Compare an uninterrupted suffix against at least three fresh restored processes.
Comparison requires matching component/timing identities, nonempty matching frame
counts and exact video/audio/input/frame observations. It fails at the first
divergence. It does not derive game coordinates or certify capture authenticity.

Video hashes omit row padding and invisible X bits; optional private PPM captures
contain visible RGB. PCM audio hashes include sample counts. Actual core timing is
recorded as binary64 plus its exact hexadecimal representation, never assumed to
be exactly 60 Hz. This is the core-reported rate, not a measured hardware clock.
Callback errors, core error-level logs, missing video, rejected states, timeout,
oversized logs and missing/mismatched result receipts fail. Limits are 1–60,000
frames, 32 selected captures, 64 MiB states/files, 2 GiB address space and a
5–600 second subprocess wall bound; the CPU bound adds five seconds. Use smaller
scenarios when the resource bound is insufficient. The separate `configure` file
bound is 2 GiB so verified disc tracks can be staged. These bounds are not isolation.

Private PPMs, states, saves, discs and BIOS remain outside Git and model prompts.
Give other agents compact hashes/derived measurements and an explicit capture
handoff. Standard libretro does not expose VDP1/VDP2 texture, palette or tracing
hooks: those still require #28's separately pinned/instrumented core.

## Optional lossless audio retention

`frontend.py run --capture-audio` retains exact interleaved signed 16-bit stereo
callback bytes in private `audio.s16le`, with an observations-bound `audio.json`
manifest containing per-emulated-frame sample offsets/counts/hashes, exact reported
sample rate and the capture/checkpoint origin. Existing observation and checkpoint
schemas remain unchanged. Successful enabled runs include an `audio_capture`
result. Use a newly configured pinned frontend bundle; preserve older bundles and
locks for their accepted evidence.

```sh
python3 tools/saturn_lab/compare_pcm.py \
  /private/evidence/audio-boot/audio.json \
  /private/evidence/audio-restored/audio.json --reference-start 3000
```

The explicit reference index selects a video-frame suffix for a restored replay.
The comparator validates retained observations and all raw PCM hashes/counts,
requires matching component/AV identities, absolute frames and controller masks,
and reports the first sample/channel or frame-boundary divergence. It never
resamples, normalizes or infers alignment. Limits include 64 MiB of PCM and
65,536 stereo sample frames per emulated frame. A wholly empty stream fails;
nonempty digital silence is valid. Failed runs never publish a successful audio
manifest. Raw PCM remains private alongside original captures.

See [PCM_FORMAT.md](PCM_FORMAT.md) for the format, lifecycle, limits and exit codes.
This is same-core replay tooling with synthetic validation only; real Saturn
execution, trusted source authentication and production Godot audio parity remain
separate, unverified work under #488/#511. The callback-output rate does not prove
the original sound chip's internal rate or hardware accuracy.

## Tests and scope

```sh
python3 tools/saturn_lab/check.py
```

Tests use synthetic bytes in temporary directories, including multitrack input,
tampering, omitted dependencies, unsafe paths and failure exits. No test requires
or includes a disc or BIOS. A tiny C fixture tests the real libretro callback ABI,
controller delivery, serialization and failure paths; it is not a Saturn emulator.
A missing compiler is a test failure. The check fails if no tests are discovered.

Real-media boot/repeatability acceptance is separate private host evidence, never
inferred from synthetic CI. Graphics extraction, archive decoding, animation
reconstruction, gameplay parity and a live AI factory remain separate milestones
in `docs/restart/BACKLOG.md`.
# Behaviour trace comparisons

`python3 tools/saturn_lab/compare_trace.py reference.json candidate.json` compares
canonical observations and reports the first differing frame/field. See
[TRACE_FORMAT.md](TRACE_FORMAT.md) and the
[Saturn execution plan](../../docs/restart/SATURN_RECONSTRUCTION.md).
The comparator's synthetic tests do not establish reference-game fidelity.

## Bounded original kernel probe

The [first real-original result](../../docs/restart/research/2026-10-30-saturn-original-kernel-result.md)
records two identical 256-case USA kernel runs and an actual altered-return
negative control. This is partial CPU-only evidence; independent emulator/caller,
timing and graphics validation remain open.

`probe_kernel.py` prepares EXP-SAT-CODE-001 for the USA `0600A4B0` helper.
It verifies the accepted kernel SHA-256 and upstream SHA-1 plus three pinned
interpreter source files, checks 256 inputs with instruction limits, and writes
one new JSON report. It does not fetch dependencies or contain original bytes.
See [the source investigation and exact host recipe](../../docs/restart/research/2026-10-30-deep-dive.md).
Run it under the existing unprivileged research environment with private inputs
and a fresh private report path. A pass is CPU-only evidence for this bounded
hypothesis, not hardware/timing, whole-game or graphics parity.

## Native VDP1 texture decoder

`export_vdp1.py` unpacks one explicitly selected command from an existing private
VRAM snapshot, preserving native samples, lookup data and provenance. Supported
RGB source patterns get a PNG; unresolved palette/end-code previews are reported.
See [VDP1_EXPORT.md](VDP1_EXPORT.md) for the strict capture format, CLI and remaining
original-game experiment. Synthetic checks establish decoder tooling only.

## Coherent graphics inputs and whole sprite sheets

[`state_graphics.py`](STATE_GRAPHICS.md) adapts a bounded raw checkpoint from the
pinned Beetle serializer into VDP1/VDP2 capture inputs without modifying or running
the core. Original mode requires the hash-verified USA kernel as a word-order and
residency witness. It is not command discovery, palette resolution or a completed
sheet extraction. The optional pinned-source serializer smoke uses constructed
arrays; ordinary tests remain synthetic tooling checks.

The [whole-sheet investigation](../../docs/restart/research/2026-10-30-whole-spritesheets.md)
sets out archive-table and multi-frame paths, actual Yabause export capabilities,
Normal Game coverage gaps, composite frame assembly and completeness criteria.
