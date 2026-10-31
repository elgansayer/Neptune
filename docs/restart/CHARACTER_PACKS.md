# Local data-only character visuals

Work branch: `feature/data-only-character-packs`. This PACK-007/PACK-006 slice
extends the existing `neptune.pack.v1` manifest and session registry. It reuses
Robin Hood's SpriteFrames/TexturePacker authoring workflow and the existing
GameView animation vocabulary. Network avatar selection, automatic sharing,
archive installation and palette/voice metadata remain separate work.

## Character definition contract

`neptune.character.v1` definitions describe a name, sprite offset, centering,
a named fallback animation, source provenance and named animation sequences.
Each animation declares FPS, looping and ordered frames with relative duration.
Every frame references hash-bound RGBA8 bytes plus explicit width and height.
Trim margins are baked into the rendered frame pixels; the sprite anchor is
retained independently. This preserves the authored presentation without shipping
scene resources, scripts or TexturePacker importer code.

The runtime accepts declared JSON and fixed-layout RGBA8 payloads only. It checks
paths, hashes, exact byte lengths, dimensions, aggregate pixel budgets, timings,
fields and fallback availability before constructing script-free native visual
objects. RGBA8 avoids calling a codec on untrusted compressed images. Authoring
still uses ordinary imported PNG/atlas resources in a trusted isolated process.

This is cosmetic data. It cannot define physics, hitboxes, abilities or native
extensions. Different namespaced characters coexist through the existing session
registry. An explicit local GameView selection applies to one participant before
its visual is created; default and other participant visuals remain unchanged.
