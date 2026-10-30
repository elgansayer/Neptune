# One captured texture: lossless native export

This is the bounded decoder slice of #485. It consumes an existing 512 KiB VDP1
VRAM snapshot in CPU address order and one explicit command offset. It does not
capture emulator memory or walk the command list. A host-side adapter must first
produce a coherent snapshot with the matching VDP2 state and input/core identity.
Neither this tool nor its synthetic tests establishes a newly extracted game
spritesheet. Keep #485, #487 and #512 open.

## What is implemented

- Native 4-bit, 8-bit and 16-bit texels for all six defined colour modes.
- Packed source bytes, original 32-byte command, native samples as big-endian
  uint16 values, and pre-composition colour words. The full 8-bit samples are
  retained in 64/128-colour modes so end codes are not lost through masking.
- The original lookup table when used, command fields, source spans, dimensions
  and flip flags. Output stays in source orientation. No transform is baked in.
- An RGBA source-pattern PNG for RGB lookup/direct textures with end codes
  disabled, provided every visible word has RGB interpretation. Bank-mode or
  unresolved lookup colours produce lossless data and an explicit unavailable
  preview reason. They never get an invented palette.
- Input, exporter, metadata and output digests; declared game/build/frame/core,
  runtime versions and synthetic status. Fresh output directories prevent reruns
  from replacing accepted evidence. Failed writes remove their own partial output.

PNG transparency here covers the source zero-sample rule and SPD. This is not a
VDP1 rasterizer: end-code drawing, mesh, shading, priority, clipping, local
coordinates, scaling/distortion and VDP2 composition remain unimplemented. Even a
valid source-pattern PNG is not the game's final rendered region or an animation.
Command fields and native samples remain available for those later adapters.

## Capture input contract

On the private host, record `vram.bin` and the matching VDP2 registers/CRAM outside
Git. Use the accepted pinned core in a separate instrumented build or a tested
debugger adapter. Do not reinterpret the register range as VRAM. The snapshot
must contain exactly the VDP1 VRAM range `0x05C00000..0x05C7FFFF`, increasing CPU
address order, with big-endian words. Emulator-internal swapped memory is not this
format and must first be converted by a tested adapter.

Create a small `capture.json` containing:

```json
{
  "schema": "neptune.vdp1-capture.v1",
  "game": "Saturn Bomberman",
  "build": "USA MK-81070 V1.003",
  "capture_id": "YOUR-UNIQUE-EXPERIMENT-ID",
  "frame": 1234,
  "synthetic": false,
  "byte_order": "big",
  "input_lock_sha256": "REPLACE-WITH-64-LOWERCASE-HEX-DIGITS",
  "core_sha256": "REPLACE-WITH-64-LOWERCASE-HEX-DIGITS",
  "vram_sha256": "REPLACE-WITH-64-LOWERCASE-HEX-DIGITS",
  "vdp2_state_sha256": "REPLACE-WITH-64-LOWERCASE-HEX-DIGITS"
}
```

The frame and capture ID above are placeholders, not an observed checkpoint.
Hash actual files; never paste placeholder digests or label a fixture original.
The decoder verifies VRAM identity against this declaration. It does not have the
other private inputs and cannot authenticate the declared core, game or frame.
The host receipt must verify those identities and link the actual snapshot,
checkpoint/input recording and VDP2 state. Do not infer trust from manifest shape.

Run from the repository checkout with inspected private paths and a fresh output:

```sh
python3 tools/saturn_lab/export_vdp1.py \
  --vram /PRIVATE-CAPTURE/vram.bin \
  --capture /PRIVATE-CAPTURE/capture.json \
  --command-offset 0xYOUR-OFFSET \
  --output /PRIVATE-EVIDENCE/UNIQUE-TEXTURE-001
```

The offset is the command's byte offset from the VRAM base, aligned to 32 bytes;
it is not a command ordinal or a CMDSRCA value. Select it from a verified draw
command observation. The tool rejects draw-end, skipped and non-textured commands,
prohibited colour modes, invalid sizes/alignment and out-of-range source spans.
Wrapping patterns are unsupported and rejected. Sources remain unchanged.

Successful execution reports `native-decoded`; inspect `manifest.json` for preview
availability and limitations. This status alone is not an original-game research
receipt. A missing PNG is an unresolved preview, not successful colour recovery.
PNG file hashes are tied to the recorded runtime; compare decompressed pixels
when independently checking a different compressor/runtime.

## Next actual experiment

1. Coordinate the existing host lease; preserve Gemini's #484 work and accepted
   core/checkpoints. Capture one observed player/effect command with its coherent
   source VRAM, VDP2 state, source build and input timeline.
2. Export the selected command twice to fresh directories. Compare native bytes,
   metadata and output hashes. Keep raw snapshots host-private.
3. Compare a supported RGB preview with a separate debugger/exporter using the
   same command and native source orientation. For bank colours, implement and
   test the VDP2 resolver before claiming a colour preview. Do not silently switch
   to greyscale, a guessed palette or a screenshot crop.
4. Deliberately change a palette entry, source stride or nibble order and require
   the comparison to detect it. Retain the failing control and restored result.
5. Publish only a verified derived batch under the private asset repository's
   game/build namespace with provenance and regeneration instructions (#512).
   Keep discs, BIOS, full VRAM/CRAM dumps and save states outside Git. Link the
   real evidence from a PR promptly if it meets the first-result alert condition.

## Validation and primary source

Run `python3 tools/saturn_lab/check.py`; the ordinary merge gate discovers the
new tests through the existing input-tooling check. Hand-calculated fixtures cover
packing, bank masks, RGB channels, zero/SPD, lookup dependencies, dimensions,
malformed inputs, PNG CRC/scanline parsing, deterministic export and write failure.
No original game bytes, copied emulator implementation or extracted art is bundled.

Format basis: [Sega VDP1 User's Manual ST-013-R3-061694](https://antime.kapsi.fi/sega/files/ST-013-R3-061694.pdf),
sections 6.3–6.6. This source documents the format; it is not a hardware accuracy
test. Actual original-game extraction and independent runtime checks remain due.
