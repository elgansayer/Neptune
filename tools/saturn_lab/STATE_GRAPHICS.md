# Read a private Beetle checkpoint into graphics inputs

This implements the bounded acquisition adapter from #525 S06. It reads the
existing bridge's `checkpoint.json` and raw `checkpoint.state`; it does not restore
or run an emulator. Existing binaries, profiles, frontend modules and checkpoints
are unchanged. Original USA kernel execution remains the #524 result.

## Scope and safeguards

Supported declaration: Beetle source `01bc063fdd0fb5fc208850c9ecc658834df762ab`,
raw `MDFNSVST` serializer version `0x00103201`. Reject wrappers/compression,
unknown versions, invalid lengths, nonzero trailing padding, duplicate sections
or fields, excessive records and missing/wrong-sized graphics/context fields.
The 64 MiB input limit matches the bridge. Bounded unknown fields are indexed,
not interpreted. This is not a general Mednafen/RetroArch save-state converter.

The framing's lengths are little endian. Numeric arrays at the accepted source
pin are native host bytes. `--producer-byte-order` is mandatory; no guess based
on the file header or current parser host is made. For a real capture the adapter
also requires the already extracted USA `0KRNL.BIN`, verifies its accepted size,
SHA-256 and SHA-1 using `probe_kernel.kernel_bytes`, and compares 64 bytes at
kernel offset `0x44B0` with normalized `MAIN.WorkRAMH` at offset `0xA4B0`.
That separately identified code span checks word order and kernel residency.
A pre-load, patched or other-region checkpoint fails rather than being repaired.
Japan support needs its own validated witness; it is not silently accepted.

The checkpoint state bytes/size/digest and five component identity digests are
checked. Component hashes and source revision remain sidecar/operator declarations;
the adapter does not possess every locked component or authenticate host execution.
Use the accepted host's verified input-lock/profile and retain its receipt. The
kernel witness is not proof that all labels, graphics or media are authentic.

## Host command

Choose an existing accepted post-load checkpoint and a fresh private output path:

```sh
python3 tools/saturn_lab/state_graphics.py \
  --checkpoint "$CHECKPOINT_JSON" \
  --producer-byte-order little \
  --core-source-revision 01bc063fdd0fb5fc208850c9ecc658834df762ab \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --capture-id SATURN-GFX-REAL-001 \
  --output "$NEW_PRIVATE_GRAPHICS_DIRECTORY"
```

The variables are host-resolved paths, not observed new captures. `little` is
appropriate only for a known little-endian producer; the original code witness
must match. Use `--synthetic` exclusively for constructed states; it bypasses the
original witness but labels every generated capture synthetic. Never use it to
turn a rejected original checkpoint into success.

Outputs, all **host-private**:

| File | Meaning |
| --- | --- |
| `vram.bin` | 512 KiB VDP1 VRAM, CPU address order, big-endian uint16s. |
| `vdp2-vram.bin` | 512 KiB VDP2 VRAM, same normalization. |
| `vdp2-cram.bin` | 4096-byte original palette storage, normalized uint16s. |
| `vdp2-registers.bin` | 512-byte raw register array, normalized uint16s. |
| `vdp2-state.bin` | Exact framed `VDP2` section from this state, in **producer payload order**, including context; not a new canonical graphics format. |
| `context.json` | Draw phase, current command word index and its byte offset, return slot, framebuffer selection and selected VDP2 mode state. |
| `capture.json` | Existing `neptune.vdp1-capture.v1` exporter metadata, bound to output hashes. |
| `manifest.json` | Source/sidecar/adapter identities, field locations/digests, witness result, outputs and limitations. |

Fresh directories prevent overwrite; failed writes clean only their own output.
The raw VDP2 section is preserved as coherent context and is **not** directly a
palette-resolved preview. The normalized files have their own hashes. The capture
metadata's `vdp2_state_sha256` hashes the exact `vdp2-state.bin` above.

Next use [export_vdp1.py](VDP1_EXPORT.md) with a verified observed command **byte
offset** and the generated `vram.bin` / `capture.json`. The adapter converts
`CurCommandAddr` from word index to bytes for inspection, but that current command
may be mid-draw, clipped, non-textured or draw-end. It is not automatically the
player sprite or the start of a complete command list. Indexed palette resolution,
command traversal, animation association and sheet packing remain separate work.

## Tests and pinned-source interoperability

`python3 tools/saturn_lab/check.py` includes nine new synthetic contract tests:
framing failures, duplicates/names/bounds, both producer orders, required layouts,
kernel-witness comparison, sidecar/path/digest controls, deterministic exporter
input, word-to-byte conversion and failure cleanup. Existing tests retain the
real original-kernel hash rejection contract. Mock witness tests are explicitly
synthetic; no original bytes are bundled.

An additional optional smoke compiles the **actual pinned `mednafen/state.c`**
writer against a Neptune-owned synthetic producer. It verifies all 526592 uint16
elements, signed context and command-index conversion, and detects wrong order.
It supplies only the logging declaration used by the writer; no emulator is
implemented by the fixture. The upstream GPL source is compiled temporarily,
not vendored or linked into Neptune game code. The optional check downloads
nothing and fails if sources/compiler are missing or modified.

Obtain these files at the exact accepted core revision in a separate directory:

```text
mednafen/state.c                       -> state.c
mednafen/state.h                       -> state.h
mednafen/general.h                     -> general.h
libretro-common/include/boolean.h      -> boolean.h
libretro-common/include/retro_inline.h -> retro_inline.h
```

Then run:

```sh
python3 tools/saturn_lab/check_state_serializer.py --sources "$PINNED_SOURCE_DIRECTORY"
```

All five source SHA-256 values are enforced by the script. On this investigation's
little-endian host the actual source-writer smoke passed, emitting synthetic state
SHA-256 `82fb3aad96d69c9ee6548b61b1a5596c72b0fd816b3012e26690b56f055f52c3`.
An appended-byte source mutation was rejected before compilation. This establishes
serializer/adapter interoperability for constructed arrays, not compatibility
with a complete running core or extraction from an original-game checkpoint.

## Remaining original-host check

Run the command on one accepted real checkpoint, retain the original kernel
witness, compare selected VRAM/CRAM spans with another independently obtained
memory/export view, and regenerate a selected pattern. Record mid-draw phase,
core/settings/input lock, checkpoint/frame and output hashes. Do not publish raw
states or memory dumps. A real sheet is a later derived artifact with its own
preview and reproducible frame/palette/source mapping; see the
[whole-sheet research](../../docs/restart/research/2026-10-30-whole-spritesheets.md).
