# Can we extract whole Saturn Bomberman sprite sheets?

**Yes, whole character/effect sheets are a credible extraction goal.** There is
game-specific firsthand evidence of successful VRAM/memory-editing rips. The
remaining work is recovering source patterns, palettes, frame associations and
coverage from our own identified originals. We have not newly extracted a whole
Saturn sheet in this investigation. This extends #525 S06–S09 and #485/#487/#512.

Source inventory: [12 primary/firsthand records](whole-spritesheet-sources-2026-10-30.json).
The [serializer smoke receipt](../evidence/2026-10-30-state-serializer-smoke.json)
records a constructed-data interoperability check, explicitly not a game rip.

## What a whole sheet actually means

The game need not store the tidy PNG layout we want to export. Sega's original
[VDP1 manual, chapter 5](https://antime.kapsi.fi/sega/files/ST-013-R3-061694.pdf)
describes character patterns referenced by drawing commands. Their width, height
and colour mode determine the byte count; boundaries have alignment constraints.
A sheet can be assembled losslessly from those individually stored patterns.

There are three different deliverables:

| Deliverable | What it proves |
| --- | --- |
| Observed-pattern sheet | A stated set of original patterns was extracted and assembled. Does not prove every animation is present. |
| Character animation sheet | Frames are assigned to named sequences with ordering, duration, origin and palette interpretation. May have explicitly missing sequences. |
| Complete character resource set | All entries of identified frame/sequence tables for a stated build/mode set are accounted for, including unused or shared entries. Requires a measured denominator. |

A useful first sheet can be the first two deliverables. Do not wait for all
characters, worlds or production integration. Do not label an observed sheet
complete because a replay stopped finding new pixels.

## Evidence specific to this game

The firsthand ripper's [Saturn Bomberman section](https://randomhoohaas.flyingomelette.com/spr/bomberman.html)
lists character, enemy and boss sheets and says VRAM and memory editing were used
to display animations. It explicitly flags missing Normal Game-exclusive
animations in the Bomberman/Tirra sheets. This is strong evidence of feasibility
and a valuable coverage warning; it is not an extraction receipt for our build.
The indexed page was available in search; repeated direct fetches returned 502,
so its current download set and every sheet's completeness were not inspected.

A [2013 firsthand discussion](https://archive.vg-resource.com/archive/index.php/thread-15341-55.html)
describes the exact Saturn Bomberman problem of linear patterns looking wrong
when the viewer width is changed, and difficulty finding palettes. A responder
supplies a specific historical Yabause palette offset. That offset belongs to an
unspecified old state layout; do not transplant it into Beetle or modern Yabause.
For our captures, take dimensions from commands/frame tables and use the matching
palette context. A four-bit texture index does not imply a four-bit palette entry.

The [current project disc inventory](../evidence/2026-10-30-gemini-saturn-disc-inventory.md)
identifies 236 USA PROGRAM.BIN banks and 240 Japan banks, with 11 pointer slots
and bank names in each header. That is an archive map, **not** a decoded sprite
table. Graphics could be in resident banks, compressed subresources or other
sections; labels alone do not establish their meaning. Keep #484's existing
base1/normal2 experiment with its owner.

## Best route: use runtime evidence to unlock archive-wide extraction

Use a hybrid approach. Capture one known animation to identify its original
resource descriptors, then enumerate those descriptors and decode the complete
resource set offline. This avoids relying on long gameplay to reveal everything,
without guessing the bank format from raw image-like bytes.

1. Restore an accepted post-load USA checkpoint and obtain coherent VDP1 VRAM,
   VDP2 registers/CRAM and work RAM. The new
   [state adapter](../../../tools/saturn_lab/STATE_GRAPHICS.md) implements the
   bounded acquisition step. Its original mode verifies a code-span witness
   against the already hash-locked USA kernel; real checkpoint validation is due
   on the VPS. Retain captures privately.
2. Identify the player's observed commands and export their native pattern bytes,
   dimensions, colour mode and original source orientation. Resolve indexed colour
   using actual VDP2 sprite type, CRAM mode and offset. Transparent black must
   remain distinguishable from opaque black; do not colour-key a screenshot.
3. Observe a frame change. Record whether CMDSRCA changes, the bytes at the same
   address change, or only palette/placement changes. These distinguish resident
   frames, streamed frames and palette/transformation animation.
4. Trace the frame selection and texture upload back to the original descriptor
   and source range. Recover record stride, source pointer/offset, dimensions,
   palette reference, part offsets, frame durations and sequence termination.
   Each interpretation needs several different real examples plus a deliberate
   wrong-stride/length/order comparison.
5. Follow that validated table to enumerate entries, decode each bounded resource
   and correlate at least one member back to resident VRAM. If a resource is
   compressed, compare output against the actual resident original bytes, not
   merely our encoder/decoder round trip. Record unused and duplicate entries.
6. Assemble deterministic PNG sheets and JSON animation maps. Regenerate into a
   fresh directory, compare native bytes/decompressed pixels, and publish the
   first verified derived sheet to the authorised private asset repository.

This is a proposed experiment sequence, not proof that Saturn Bomberman's table
layout has already been recovered. The upstream research's dino pattern-base
observation (`0x80 + 34 * eggs_eaten`) is a concrete search lead, **not** a licence
to assume every character has 34 frames. Its warning that changing only the egg
count fails to update animation pointers reinforces the need to recover the
actual selection path.

## Alternate route: deterministic multi-frame capture

If the bank descriptor is slow to identify, extract one bounded sheet from a
scripted animation sequence now. Capture on state/frame changes and record
sequence boundaries. Walk all four directions, then add a small named group such
as idle, placement and death. Expand later to carry/throw/kick, status effects,
riding/dismounting, victories, introductions and mode-specific variants where
the actual build uses them. Keep Battle, Normal and Master coverage separate.

Capture should distinguish two hardware usage patterns. The author of
[The Rockin'-B's Saturn tutorial](https://segaxtreme.net/content/satdev/tutorial/SaturnGameTutorial.htm)
demonstrates both selecting resident textures and overwriting a VRAM texture
with work-RAM animation frames. This is Saturn homebrew evidence of the two
mechanisms, not proof that Bomberman uses either for a particular animation.
Measure which happens instead of deduplicating by VRAM address.

For streamed frames, capture bytes at the upload/draw boundary so two uploads to
the same slot in one VBlank are not silently collapsed. For resident resources,
a checkpoint may hold unreferenced frames, but VRAM bytes alone may lack their
dimensions and association. Enumerating current draw commands cannot prove that
all resident or archive frames were visited.

Use a content identity containing native bytes, dimensions and interpretation,
with separate palette identities. Preserve logical frame occurrences and timing
even when their pixels are duplicates. Keep flips in metadata; do not report a
mirrored reuse as newly recovered source art. A blank logical frame can still
carry duration/events and must not be deleted from a sequence.

## Reconstructing characters made from several parts

Some Saturn graphics are drawn as several commands. Determine grouping through
object/frame records or an observed original draw routine, rather than screen
proximity alone. Retain component source ID, local offset, order, flip/transform,
palette and transparency semantics. Subtract camera/world placement to recover
a stable frame origin; otherwise the assembled animation jitters.

Export both the original components and a composed character frame when the
observed draw modes are supported. For distorted/scaled/mesh/shaded pieces,
preserve transform/effect metadata and label any reconstruction limits. Do not
fill missing pixels with image generation or interpolation. A native-pattern
atlas and a composed animation sheet are useful distinct artifacts.

## Tools checked beyond their feature lists

### Yabause: real per-command export, not one-click complete sheets

Inspected source pin: `7e38821dbac265490f115e163c523a939acda759`.

- [UIDebugVDP1.cpp](https://github.com/Yabause/yabause/blob/7e38821dbac265490f115e163c523a939acda759/yabause/src/qt/ui/UIDebugVDP1.cpp)
  enumerates commands, calls `Vdp1DebugTexture` for a selected command, wraps the
  returned native dimensions in QImage, and saves it. The viewport is fitted for
  display, but the save path uses the original dimensions. Do not copy the scaled
  viewer image as source pixels.
- [vdp1.c](https://github.com/Yabause/yabause/blob/7e38821dbac265490f115e163c523a939acda759/yabause/src/vdp1.c)
  contains the debug command walker and texture decoder, including palette/SPD/
  end-code handling. A bounded external GPL-compatible batch helper could iterate
  current textured commands and save originals. It would still cover the selected
  state/list, not every character animation or all unused resources.
- The [official Qt documentation](https://wiki.yabause.org/index.php5?title=Readme_QT)
  confirms VDP1 texture export and VDP2 raw-map viewing. Actual original-game
  compatibility, palette correctness and a batch adapter still need testing.

This can be a useful independent comparison with Beetle. Keep its build/profile
separate and cap enumeration; do not let a corrupt/cyclic command list generate
an unlimited image dump. Do not copy the GPL implementation into Neptune game
code. The separately pinned decoder can remain an external research tool.

### GPU texture interception: fallback and cross-check

A firsthand [Sprite Database tutorial](https://spritedatabase.net/tutorial/saturn)
demonstrates Yabause-rr plus GLIntercept capturing a renderer atlas with many
sprite pieces at once. Its examples are Guardian Heroes/Princess Crown, not our
accepted Bomberman build. This shows a batch-capture technique, not completeness.
The [GLIntercept project's own README](https://github.com/dtrebilco/glintercept)
identifies it as a Windows OpenGL interceptor. Do not treat the historical DLL
instructions as a native headless Debian recipe. The accepted Beetle software
renderer is not an OpenGL texture-upload source.

Renderer atlases may contain padding, filtered/scaled copies, palette-expanded
pixels, cached stale images or only what was drawn. Use API capture as a visual
comparison or discovery aid, preserving pipeline settings and source correlation.
It does not replace archive provenance, original dimensions or coverage analysis.

### Existing upstream dump helper: useful but incomplete

At game pin `c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3`,
[`research/dump.py`](https://github.com/callumjenkins/pc-saturnbomberman/blob/c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3/src/bomberman/research/dump.py)
reads that recompiler's custom graphics dump. Its sprite helper lists normal
sprite placements and follows next/assign links. It is not a general full VDP1
call/return walker or native-pattern sheet exporter. Its absolute dump offsets
belong to that producer, not Beetle save states. Reuse only after validating the
actual producer layout and missing command-flow cases.

## Completion and deliverable contract

Use a coverage ledger keyed by build, bank/resource, character, mode, sequence,
direction, variant and frame. Keep these counts distinct:

```text
descriptor entries identified / entries decoded / entries independently checked
sequences identified / sequences observed / sequences with timing and anchors
unknown table boundaries / unresolved palettes / missing modes or variants
```

Until a denominator is recovered, report counts and explicit gaps, not a percentage
or “all sprites”. A defensible complete sheet accounts for every entry of a stated
table/scope and documents shared, unused, blank, duplicate and transformed frames.

The first useful output should include `sheet.png`, an enlarged labelled preview,
`frames.json` with rectangles/origins/native source identities, `animations.json`
with frame order/durations/timebase, and a provenance/regeneration manifest.
Use readable labels in the preview but keep the underlying sheet unscaled and
lossless. Publish derived output under a private Saturn/build namespace, preserving
existing content and history. Raw state/VRAM/discs/BIOS remain host-private.

Priority: one genuine White Bomberman walk/idle sheet with declared mode coverage,
then Normal-only Bomberman/Tirra gaps, then additional characters/effects. Full
archive extraction and a complete catalogue remain the long-term target; neither
blocks sharing the first verified sheet promptly.
