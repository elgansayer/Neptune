# Real libretro boot and replay evidence — 29 October 2026

Scope: #27's bounded noninteractive bridge and #462's remaining complete input
locks. Source base `da944c0aa4a68ddaf5e2d84badf752e0846f556c`. Exact PR head,
current-base CI and merge identity belong in the linked issue/PR evidence after
publication. [Machine-readable measurements](2026-10-29-libretro-bridge.json)
contain component identities, actual results and explicit unknowns. No reference
binary, frame, save or state is committed.

## Implemented

`tools/saturn_lab/frontend.py` stages ordinary private copies, configures the real
core's declared options, verifies executable identities, advances exact libretro
frames, delivers per-port masks at every poll, records video/audio observations,
saves/restores checkpoints and compares canonical output. One core runs per
bounded fresh process. The small independent C adapter safely bridges variadic
core logging; error-level messages fail the experiment.

The complete base lock includes CUE, all thirty referenced tracks, selected BIOS,
real core and actual settings: 34 files per region. Settings additionally pin the
frontend, support modules, compiled adapter, interpreter/host, region, both
multitaps, twelve joypads and valid fixed RTC/NV seed. The driver verifies these
transitive components before loading native code. This is identity verification,
not a security sandbox or a signature. Original media remain separate/unchanged.

## Actually executed

- Source core `01bc063fdd0fb5fc208850c9ecc658834df762ab`, built with
  `make -j2 platform=unix LTO=0 HAVE_OPENGL=0 HAVE_CHD=1`.
  Binary SHA-256 `c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e`.
- Final driver SHA-256
  `84b29f26338d31a0a4f546e75ecca88460f457f5463ae20dbb4a135ca7f1c8da`.
- USA `MK-81070 V1.003`: 3,240 frames, checkpoint after 3,000, then an
  uninterrupted 240-frame suffix. Three fresh processes restored the same state
  and reproduced that suffix exactly, including absolute frame indices,
  canonical video, PCM hashes/sample counts and input masks.
- The three suffix canonical digests are
  `7d1a2635f580d9181fd4f2d0cfbd920e0db591d8a13cc9854a50e89a8e070a63`.
  Each actual port was polled 480 times during 240 frames. Ports 1 and 2 received
  different masks independently; this is callback-level controller evidence,
  not a claim that two identified characters moved in battle.
- The same restored suffix without input produced different video and audio.
  An earlier 600-frame checkpoint did not show that response; its limitations
  and evidence are preserved. Inputs are libretro button IDs, not Saturn labels.
- All 34 configured options were actually requested with the pinned values.
  Auto-RTC was disabled. The used SMPC output remained valid in year 2000 and
  advanced to 00:00:54 after 3,240 emulated frames. Unused shared NV stayed at
  the initial seed. No error-level core logs occurred.
- Japan `T-14302G V1.000`: separate complete lock/copies, matching Japan firmware,
  Japanese region/language, and 300 actual frames with no error-level core logs.
  This is a smoke run, not three Japanese replay comparisons.
- Actual core timebase: 59.82650314089141 Hz,
  binary64 `0x1.de9cadadc15bfp+5`, 44,100 Hz audio. This is queried core timing;
  no exact 60 Hz or measured hardware-clock claim is made.

## Rejections and a discovered defect

Eleven actual negative cases failed: changed core/settings/BIOS/frontend/support
module/log adapter, missing referenced track, actual wrong-region BIOS, checkpoint
identity/state digest mismatches, and an overlong real emulator run. The latter
was terminated at its five-second wall bound and returned failure. After restoring
all disposable copies, the control run passed. Every mutation is limited to
private staged copies and restored in `finally`; source media were not mutated.

Changing the candidate video hash at suffix index 10 caused comparison failure
at absolute frame 3010. This verifies observation regression detection, not a
deliberate Neptune movement/fuse regression. Reference fixtures were not changed.

Japan's first staging attempt found that the capture file-size limit also applied
to large disc copies. Its `EFBIG` failure and partial copy are retained. Configure
now has a separate two-GiB file bound; run/compare retain 64 MiB. A synthetic
65-MiB track-copy regression exercises the actual child-process limits. Both real
regions were then staged and all final-revision experiments rerun.

## Reproduce and inspect

Use [the frontend commands](../../../tools/saturn_lab/README.md#noninteractive-original-game-experiments).
Private evidence root: `/home/dev/neptune-research-private/27/`.
`configure-release` and `configure-japan-release` give actual lock paths;
`continuation-release`, `replay-release-{1,2,3}`, `compare-release-{1,2,3}`,
`replay-release-no-input`, `compare-release-regression`, `japan-release-smoke`
and `negative-release-*` retain commands, process exit/timeout receipts, logs and
results. `release-experiments.py` and `negative-release.py` preserve the actual
bounded orchestration commands. Their supervisor logs retain exit assertions.
Prior failed/initial experiments remain available; no report was overwritten.

`python3 tools/saturn_lab/check.py`: 50 passing tooling/ABI tests, with a clearly
synthetic C core and no original media. Catalogue 14, factory 27 and merge-gate 17
tests also passed. Those are tool/metadata tests, not Godot/runtime/factory health.
The aggregate CI must separately validate this exact PR/current base before merge.

## Not established

No identified campaign room/battle arena, original per-character movement/bomb
measurements, VDP1/VDP2 extraction/tracing, reconstructed animation, Neptune parity,
hardware/cross-host determinism, browser netplay or live factory recovery is claimed.
The late-frame/menu exploration is separate exploratory evidence. #28/#29/#38 and
Gemini's #464 programme retain those scopes. Local OCR produced inconclusive menu
text; raw images were not uploaded to a model.

No new provider job was launched for this bridge work. Account-wide spend remains
unknown; paid fallback was not enabled. This is manually coordinated bounded
research, not a continuously operating development factory.
