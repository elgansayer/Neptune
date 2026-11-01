# Retained libretro callback PCM v1

Child task [#555](https://github.com/elgansayer/Neptune-Bomberman/issues/555)
adds optional lossless callback retention and exact **same-core replay** checks
under #488/#511. Tests use synthetic data and a synthetic libretro ABI fixture.
Real Saturn media execution, trusted private-receipt authentication, sound-driver
recovery and production Godot audio parity are separate, unverified results.

## Capture

Add `--capture-audio` to a bounded `frontend.py run` using a newly configured,
transitively pinned frontend bundle. The flag applies only to `run`. Default runs
retain the existing observations and result shape. A successful enabled run adds
`audio_capture` to its result, identifying `audio.json`, `audio.s16le`, their hashes,
the stereo sample-frame count and the limited comparison scope.

```sh
python3 tools/saturn_lab/frontend.py run --root /private/staged-inputs \
  --lock /private/staged-inputs/locks/ACTUAL.json \
  --output /private/evidence/audio-boot --frames 3240 --checkpoint-at 3000 \
  --actions /private/inputs/full.json --capture-audio --timeout 120
python3 tools/saturn_lab/frontend.py run --root /private/staged-inputs \
  --lock /private/staged-inputs/locks/ACTUAL.json \
  --output /private/evidence/audio-restored --frames 240 \
  --restore /private/evidence/audio-boot/checkpoint.json \
  --actions /private/inputs/continuation-relative.json --capture-audio --timeout 120
```

`ACTUAL.json` must be the generated lock for the actual inputs and current bundled
frontend. Adding `pcm.py` changes frontend/support-module identity. Create a new
bundle/profile alongside accepted ones. Do not edit old locks, staged scripts or
checkpoint identities to make them appear compatible.

`audio.s16le` contains the callback stream without headers, added silence,
normalization, compression or resampling. Each stereo sample frame consists of
signed 16-bit little-endian left then right values, exactly four bytes. Both single
and batch callbacks feed the same stream in delivered order. The rate is the
loaded core's reported callback-output rate. It does not identify the sound chip's
internal rate, a source instrument's rate or an independently measured hardware
clock. Enabled retention rejects callbacks outside a running frame and unsupported
dynamic AV changes rather than silently mislabelling the stream.

One emulated frame may emit zero stereo sample frames. A nonempty stream of zero
sample values is valid digital silence. An entire capture with no delivered audio
sample frames cannot produce a successful manifest.

## Manifest and bounds

The `neptune.libretro-pcm.v1` manifest has these exact top-level fields:

| Field | Meaning |
| --- | --- |
| `schema` | `neptune.libretro-pcm.v1` |
| `scope` | Supplied-file equality only; authenticity, hardware accuracy and Godot/game fidelity are not certified |
| `format` | `s16le`, two channels, left/right order, reported sample rate as exact binary64 hex and a numerator/denominator pair |
| `origin` | Absolute starting emulated frame, local `sample_frame: 0`, and restored checkpoint SHA-256 or `null` for a fresh load |
| `observations` | Confined relative observations path and SHA-256 of the retained file |
| `pcm` | Confined relative stream path, SHA-256, byte length and stereo `sample_frames` count |
| `frames` | One segment per retained emulated frame: absolute `frame`, local `sample_offset`, `sample_frames` count and SHA-256 of those exact bytes |

Sample offsets begin at zero and remain contiguous, including zero-length segments.
Absolute emulated frames must also remain contiguous. Existing
`neptune.libretro-observations.v1` files remain unchanged and retain the component
identities, core AV values, controller masks, video observations and per-frame
audio counts/hashes. The manifest must agree with that file and with the actual
raw stream. The observations file is a distinct artifact, never the manifest or
raw stream itself.

Limits are 65,536 stereo sample frames per emulated frame, 60,000 emulated frames,
64 MiB of PCM, 16 MiB of manifest JSON and 64 MiB of observations JSON. Existing
frontend process, wall-time, CPU and file limits still apply. Stop and split an
experiment when any bound is insufficient. Neither callbacks nor retention may
silently truncate audio to fit. A frame holds at most 256 KiB of retained audio;
the writer and validator stream the complete capture rather than holding it all
in memory.

The writer refuses existing raw/manifest outputs, unsafe paths and symlinks.
`append()` checks the frame count/hash against the bytes before writing.
`close()` seals the raw stream and is safe to repeat. `finish()` works after close,
checks the retained observations and stream, and publishes `audio.json` only on
success. The frontend invokes finish after successful core closure and writing
observations. A failed run may leave private partial files for diagnosis but has
no successful audio manifest/result. Do not treat those partial bytes as evidence
of a completed capture.

## Exact replay comparison

```sh
python3 tools/saturn_lab/compare_pcm.py \
  /private/evidence/audio-boot/audio.json \
  /private/evidence/audio-restored/audio.json --reference-start 3000
```

`--reference-start` is an explicit zero-based **video-frame list index** selecting
the complete reference suffix. Its default is zero. It is neither an absolute
emulator frame number nor a sample offset. The selected reference starting
absolute frame must equal the candidate's starting frame. No search for a matching
section, inferred alignment, masking, resampling or tolerance is performed. The
origin checkpoint hashes may differ: an uninterrupted capture and its restored
suffix naturally have different origins. The hashes remain recorded for replay.

Before comparison, both complete captures are checked against their actual raw
files and observations, including all per-frame hashes and sample accounting.
Component identities and the complete core AV configuration must agree. The
selected controller masks must also agree. This command cannot compare separate
engine implementations with different component identities.

Valid comparisons check both stream bytes and frame-to-sample boundaries. Equal
concatenated PCM with different frame boundaries diverges. A different number of
captured frames also diverges. A sample mismatch reports its absolute emulated
`first_frame`, zero-based stereo `sample_frame` relative to the selected comparison
start, and `channel` (`0` left, `1` right). Frame-boundary/count mismatches report
the relevant frame/sample position. Reports contain no original sample values.

Exit codes follow the trace comparator:

- `0`: supplied captures agree at the declared replay boundary.
- `1`: individually valid, compatible captures diverge.
- `2`: missing, malformed, inconsistent, changed or incompatible evidence, including
  differing source identities, rates, origins or controller timelines.

Hashes detect inconsistent supplied files. They are not signatures, and a complete
fabricated capture can contain internally consistent hashes. A trusted source
receipt, original-media execution and equivalent initial conditions still require
their own evidence. Future reference-versus-Godot audio comparison needs explicit
scenario/ruleset/input/clock contracts; this same-core tool does not provide it.
