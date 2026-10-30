# First verified original RGB source pattern

Issue #529 follows the [real checkpoint acquisition repair](2026-10-30-saturn-state-host-proof.md).
One actual USA MK-81070 V1.003 texture was decoded twice and published in the
existing private assets repository. The [derived receipt](../evidence/2026-10-30-saturn-first-rgb-pattern.json)
records the native/PNG/pixel digests, mutation control, exact publication commits,
CI identities and remote byte readback. The image itself remains private.

[Private image and provenance](https://github.com/elgansayer/SaturnBomberman-Assets/tree/e1e31236e5288f6181f411bf4d2feca04f022ad2/saturn/usa-mk81070-v1003/runtime-captures/SATURN-GFX-REAL-001/frame-003000-command-000060)
are in a separate Saturn/release/capture namespace. Existing content/history were
preserved. The repository was verified private before publication. Original
Hudson/SEGA rights remain separate; this grants no public redistribution licence.

## Actual source and result

The preserved original-game frame 3000 checkpoint contains a distorted-sprite
command (type 2) at VDP1 VRAM byte 96. It points at byte 32,768, with 320x160 RGB555
source pixels, no source flips and end-code processing disabled. The recorded
coordinates are (0,32), (319,32), (319,191), (0,191); they were not baked into the
source image. No palette was guessed: this command uses direct RGB words.

The existing exporter consumed the verified normalized snapshot/capture metadata.
Two fresh offline processes produced identical outputs, including their manifests.
The private PNG is 8,518 bytes, SHA-256
`41007b8fceb7a4e6b7e1f4666fe7c6383e14341b895da7d6c1c5bfbbae019667`.
The 102,400-byte native pattern digest is
`6eddba01c06f5dd7bde97b67072a753aa71d14346d1a53604065efd17dff9cdd`.

A separate stdlib PNG reader checked signature, chunk CRCs, dimensions, stream
length and source RGBA pixels. All 51,200 pixels matched a separately expressed
RGB555 interpretation with bit-replicated five-bit channels and the observed
zero-source transparency rule. Decoding the PNG back to native RGB555 recovered
every original word, including the distinction between transparent zero and
opaque black. A deliberately changed source colour bit produced a mismatch.
Comparisons used source/native words, not a tolerance against final display RGB.

The underlying graphics arrays had already matched a direct memory read from the
same accepted restored core in PR #528. This is independent acquisition and pixel
interpretation, not a second emulator implementation or hardware oracle.

## Publication gate

Private asset PR #1 added only this decoded PNG/provenance/recipe plus a bounded
stdlib validator and read-only CI. The validator checks every PNG pixel and native
word digest. Deliberately broken PNG CRC and stale native digest controls fail.
It validates bytes; it cannot authenticate arbitrary future source declarations.
Full discs, BIOS, checkpoints, full VRAM/CRAM buffers and credentials were omitted.

Both exact-head capture checks succeeded under GitHub Actions app 15368. The
coordinator re-read private visibility, candidate head, current base, ancestry and
literal checks, then performed a normal expected-head merge without administrator
bypass or branch deletion. Merge parents are exactly the tested base/head.
Remote PNG bytes fetched at the immutable merge match the locally validated hash.
This is a verified private asset publication, not a live factory job.

## Reproduction and limits

From the preserved capture produced in PR #528, run the existing exporter twice into
fresh private directories:

```sh
python3 tools/saturn_lab/export_vdp1.py \
  --vram /PRIVATE-CAPTURE/vram.bin --capture /PRIVATE-CAPTURE/capture.json \
  --command-offset 0x60 --output /PRIVATE/NEW-PATTERN-OUTPUT
```

Keep the actual accepted checkpoint/core/input-lock and adapter identities from
the host receipt; an arbitrary VRAM image does not establish provenance. The
private assets repository's `tools/validate_saturn_captures.py` reproduces the PNG
and native-word checks against the published derived hashes. Full host pixel
comparison recipe is retained at
`/home/dev/neptune-evidence/issue485/pattern-validation.py`, with its digest in
the receipt. It compares the exporter output directly with the actual captured
VRAM source span and runs the colour mutation control.

The image looks like an intro image; its subject and source file/resource mapping
remain unidentified. It is not a player animation, effect sequence, atlas or
complete sheet. Final draw composition, source-bank/animation correlation and
campaign/battle/Neptune parity remain open. Continue #485/#487 with an identified
player/effect in a verified playable scene, preserving Gemini #484. No provider
session, service setting, budget or notification automation changed in this slice.
