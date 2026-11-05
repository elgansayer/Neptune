# Saturn Bomberman: full source code and all assets

**Owner direction, 5 November 2026 (binding; supersedes narrower wording in
older documents):** the reverse-engineering goal is the **complete source code
and every asset** of Sega Saturn Bomberman, not only selected timings or
behaviour measurements. Once the full source and assets exist, every timing,
gameplay rule, AI policy and presentation detail can be read straight from
them. Behaviour measurement remains valuable as a **verification method** for
the reconstruction, not as the deliverable.

## What "done" means

1. **Full source code.** Every original executable has been reconstructed and
   rebuilds with a documented toolchain into binaries that are **byte-identical**
   to the originals. That covers the SH-2 boot program, resident kernel,
   overlays and libraries on both master and slave CPUs, the 68000 sound drivers
   and the observed SCSP DSP programs.
   - A function is **MATCHING** when its recompiled bytes equal the original.
   - **NONMATCHING-verified** means it's decompiled to C and proven equivalent
     by differential tests against the original bytes in an isolated CPU
     interpreter, including a negative control. This is temporary, not done.
   - **asm-only** means split and reassembling byte-identically, but not yet
     decompiled.
   - Progress is reported as these three counts per module, against a measured
     function denominator. Never round up. A census, an instruction
     translation, a static recompilation or a disassembly is *not* source
     recovery.
2. **All assets.** Every asset is extracted by a deterministic recipe from the
   original disc, with a manifest (source file, offset, hash → output hash).
   That covers VDP1 sprites/textures and palettes, animation tables, VDP2
   tiles/maps/backgrounds, stage/map/item/enemy data, fonts, text and
   encodings, UI layouts, FILM movies, SCSP samples, sequences, sound-effect
   tables and CD audio. Progress is extracted / total per category, plus a count
   of unclassified data that must reach zero.

USA (MK-81070) is the primary target. Japan is reconstructed where it differs.

## Where things live

| What | Where | Why |
| --- | --- | --- |
| Reconstructed source, disassembly, split/symbol config, build/compare/extract tools, recipes, extracted assets, per-lane progress | **Private** repository `elgansayer/saturn-bomberman-decomp` (GitHub Actions disabled) | Derived from copyrighted Sega/Hudson material, so it must **never** be public or copied into this repository |
| Generic, content-free tools with synthetic tests; research notes with no copyrighted content; lane ledgers (`docs/restart/saturn-code/re-lanes/`); implementation issues | This public repository | Open-source engine work; see `OPEN_SOURCE_AND_CONTENT.md` |
| Original disc/BIOS images | Local host only | Never committed anywhere |

Implementation work in Neptune/Godot is driven from the recovered source:
issues cite private repository paths and describe the behaviour in their own
words, without pasting decompiled code.

## Who is working on it

Continuous Claude "RE lanes" (cron-supervised, `~/saturn-re` on the VPS)
run `usa-code` (decompile the USA SH-2 program), `sound-68k` (sound driver
source and all audio), `code-map` (module map, splitter, byte-identical build,
progress tooling) and `assets` (all graphics, text, stage and movie assets).
Their ledgers are in `docs/restart/saturn-code/re-lanes/`, and their issues
carry `factory-skip` so the Repo Factory doesn't duplicate them. The Factory
implements the resulting unlabelled implementation issues. Codex's Japan
kernel execution probes (`tools/saturn_lab/probe_japan_*`) remain Codex's.

Any agent working in this area, now or in future, works toward this goal:
choose work that increases the matching-function count or the extracted-asset
count, or that unblocks one of those.
