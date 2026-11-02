# Bounded Sega FILM movie and PCM recovery

This dependency-free parser supports the **observed FILM 1.04 subset**: one
32-byte FDSC, one STAB, 24-bit Cinepak video and mono/stereo uncompressed signed
8-bit PCM. Other versions, codecs, extensions, gaps, overlaps, malformed tables,
truncated payloads, noncontiguous video timing and trailing bytes fail explicitly.
The supported subset does not imply general Sega FILM compatibility.

STAB records identify source byte ranges, video PTS/duration/keyframe flags and
audio packet boundaries. Stereo PCM is planar **within each packet**. Recovery
interleaves channels independently for each packet, preserving all signed samples.
`audio.s8` retains signed bytes; `audio.wav` uses the reversible XOR-128 conversion
required for unsigned 8-bit RIFF PCM. It does not resample, normalize or compress.

```sh
python3 tools/saturn_film/check.py
python3 tools/saturn_film/cli.py inspect --input /PRIVATE/BOMSS1.CPK
python3 tools/saturn_film/cli.py extract \
  --input /PRIVATE/BOMSS1.CPK --output /PRIVATE/FRESH-BOMSS1
```

Extraction creates `audio.s8`, `audio.wav`, `sample-table.json` and `report.json`.
The table preserves packet indices, source ranges/hashes, original video clock
ticks and cumulative audio sample-frame offsets. The report carries exact rational
durations, pixel dimensions, complete byte accounting and hashes. New directories
prevent overwriting evidence; parser/extraction failures cannot become success.
Keep media outputs under ignored `research-private/` or other private storage.

The parser caps files at 256 MiB, headers at 4 MiB, tables at 100,000 packets,
packets at 8 MiB, decoded audio at 128 MiB, and dimensions at 4096 pixels. Input
and output symlinks are rejected. Inputs are read only. This tool inspects
compressed Cinepak packets; it does not implement Cinepak pixel decoding.

## Optional independent media check

Installed `ffmpeg` and `ffprobe` can cross-check **all** recovered PCM bytes,
WAV roundtrip, every packet PTS/duration/keyframe flag, complete video frame
count and two full decoded RGB framehash runs. Missing tools, process failures,
timeouts, mismatches and ineffective mutation controls fail. Nothing downloads.

```sh
python3 tools/saturn_film/validate_real.py \
  --input /PRIVATE/BOMSS1.CPK --input /PRIVATE/BOMSS2.CPK \
  --input /PRIVATE/BOMSS3.CPK \
  --output /PRIVATE/FRESH-FILM-VALIDATION \
  --timeout-seconds 120 > /PRIVATE/film-receipt.json
```

Use an existing private parent directory. This optional validation accepts at
most eight uniquely named inputs totaling 512 MiB and limits each child process
to at most 120 seconds. Commands use one codec thread. Outputs include decoded
audio, packet tables and framehash files, not video image dumps. The shareable
receipt records source/tool/executable hashes, versions and tokenized command
arguments without absolute source/output paths. Failed runs retain an
`INCOMPLETE.txt` marker and must not be published as successful evidence.

Timing comes from STAB, never ffprobe's aggregate video stream duration. On the
three existing assets, ffprobe reports correct packet timing but reports video
stream duration as frame-count/600, omitting each frame's 24-tick duration. The
native STAB times are 25 fps and 100.16 / 113.8 / 132.76 seconds. Audio has its
own 22,050-Hz sample clock; retain the exact small audio/video duration difference.

## Evidence scope

Synthetic tests bundle only owned fake packets. They prove parser/rejection and
PCM mechanics; they are not valid Cinepak movies or original-game extraction.
The optional original-container experiment supplies external decoder evidence.

All reports deliberately label inputs `prior-assets-unresolved-release`: the
existing asset-repository BOMSS movies differ from supplied USA/Japan disc files.
Their 25-fps timing supports the existing PAL hypothesis, not an authenticated
PAL release identity. No report from this tool establishes emulator correctness,
game trigger mapping, campaign/battle parity or whole-game asset completeness.
Publish permitted decoded derivatives separately from raw originals and keep
reference content provenance separate from the Neptune engine licence.
