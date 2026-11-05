# USA KRNL/BOOT function inventory: static denominator, residency and reconciliation

Run `usa-code` 20261105T0632Z, 5 November 2026, for #480/#481/#482/#497 with
#492 leads. This is the lane's first measured USA function denominator. It
combines four kinds of evidence, labelled throughout:

- **static disassembly**: a new Neptune decoder and recursive descent;
- **second static implementation**: the hash-pinned upstream discovery run on identical bytes;
- **natural emulator observation**: byte identity in captured WorkRAM-H images from earlier cold-boot/menu runs;
- **address reconciliation**: upstream runtime-learned targets and prior Neptune results classified against the inventory.

No instruction was executed in this run. Entries are discovered, not semantically
recovered. Derived measurements, digests and entry addresses are in the
[receipt](../evidence/2026-11-05-usa-function-inventory.json). The lane ledger is
[usa-code.md](../saturn-code/re-lanes/usa-code.md).

## Inputs

| Module | Identity | Bytes | Mapping | Seed |
| --- | --- | --- | --- | --- |
| KRNL | `usa-mk81070-v1003:KRNL:3061382a7457ac03`, SHA-256 `20109f50…c798a7` | 786,432 | `0x06006000` | `0x06006174` (startup cited in VPS-CODE-649/655) |
| BOOT | `usa-mk81070-v1003:BOOT:554fc04ce04132d2`, SHA-256 `5d966992…596827` | 435,296 | `0x06010000` | `0x06010000` (IP first-read address) |

KRNL is the accepted private extraction from #483. BOOT `0` was extracted privately
through the repository's `tools/saturn_disc` reader. All 30 track identities match
the accepted media report, and the 213-sector extent at LBA 33 has no EDC mismatch.
Upstream leads are pinned: `saturn-recomp@f20de940` (`sh2.py`, `hw.py`,
`recomp/discover.py` hashes in the receipt) and
`pc-saturnbomberman@c73bc117` (`game.toml` blob `0ec8d923`, `seeds.json` blob
`d1486948`, `coverage-classes.tsv` blob `30ccb2d4`).

## Method

[`sh2_discover.py`](../../../tools/saturn_lab/sh2_discover.py) is an independent,
standard-library SH-2 decoder (all 65,536 halfwords; SH-2 has no FPU or SH-2A
forms) and fixed-point recursive descent. It classifies every halfword as
instruction, PC-relative literal, switch table or unclassified. Function entries
carry explicit provenance and a tier:

- **A, call-reached:** declared seeds; `bsr` targets; `jsr`/`bsrf` targets from a
  same-line literal or from a callee-saved register written by exactly one literal
  load (epilogue pops excluded); frame-opening far-`jmp` targets; and `SYS_SETUINT`
  handlers. Handlers count when tier-A code loads the BIOS slot `0x06000300` and
  passes the handler in `r5` (slot identity from the Japan system-area evidence).
- **B, pointer-reached hypotheses:** code pointers held in literal pools, passed in
  `r4`–`r7` at a call, or in aligned unclassified words. Each must have a clean
  descent through unclassified bytes and a boundary or frame prologue. Accepted
  shapes: a return; a closed loop of at least 8 instructions (task bodies); or a
  code-loaded `rts; nop` / `rts; mov #imm,r0` stub.
- **C, prologue-only hypotheses:** unreferenced `mov.l r14,@-r15` or
  `sts.l pr,@-r15` at a boundary with a clean 8-instruction descent.
- **R, external leads:** optional, seeded last and only where static tiers left the
  bytes unclassified. Never used to support static claims.

Recognised switches follow SHC `mova`/`braf` relative tables, absolute `jmp`
tables and GCC table-relative jumps. Bounds come from the `cmp/hs|hi|ge|gt` and
`bt`/`bf` edge actually taken. Index scaling comes from the shift chain, so the
stride-16 record dispatch tables found at `060B1220` are not misread as stride-4
code tables. Explicit assumptions:

- PC-relative loads in delay slots use the slot's own address, as the pinned interpreter does.
- Cache-through call targets (`0x2xxxxxxx`) fold onto `0x0xxxxxxx` and are labelled.
- An unresolved call records the absolute pointer slot it loads through, when known.

## KRNL results

| Measure | Value |
| --- | --- |
| Entries (A / B / C) | **4,868** (37 / 4,663 / 168) |
| Instruction / literal / switch-table / unclassified halfwords | 284,948 / 54,016 / 83 / 54,169 of 393,216 |
| Unresolved indirect sites | 485, of which 91 load through a known pointer slot |
| Register-resolved sites; switch tables (unbounded) | 840; 10 (7) |
| Code/literal conflicts; descents with problems | 0; 0 |
| Fresh repeat | byte-identical report, entry-list SHA-256 `9bc8348f…6f2c92` |

Tier A is small because startup quickly hands control to tasks, callbacks and
interrupt handlers through pointers. The startup function's far `jmp` reaches the
`krnl_setjmp`-guarded scheduler region; its return point `06006C00` is a resume
target inside that function, not a separate entry. Calls through BIOS slots
(`0x06000300`, `0x06000310`, `0x06000344`, `0x0600026C` …), the H2H library table
at `0x06002F3C`–`0x06002F78` and RAM function-pointer variables at
`0x060C0FE8`–`0x060C1650` remain unresolved by design.

**Second static implementation.** The pinned upstream discovery, given the same
bytes and seed, finds 5,098 entries. **4,867 are shared**; 231 are upstream-only
(53 inside Neptune functions, 178 in Neptune-unclassified bytes) and 1 is
Neptune-only. At halfword level there are **zero code/data contradictions**.
Upstream classifies 6,167 more halfwords as code where Neptune leaves them
unclassified. Neptune's tier-B/C rules follow the same published SHC heuristics, so
this shows implementation consistency, not independent validation of those rules.

**Natural residency.** At frame 10,800 (menu) and frame 10,200, earlier natural
cold-boot runs hold KRNL at `0x06006000` with 770,452 and 769,693 of 786,432 bytes
identical at halfword granularity. The wrong mappings `0x06006002` and `0x06007000`
match only 39,184 and 34,061 bytes. Cross-tabulated with the inventory:

| Class | Identical | Changed (f10800 / f10200) |
| --- | --- | --- |
| Instruction | 284,948 | **0 / 0** |
| Literal | 54,016 | 0 / 0 |
| Switch table | 83 | 0 / 0 |
| Unclassified | 45,299 / 44,936 | 8,870 / 9,233 |

Every byte the game mutates by these frames lies outside the static code and literal
classes. The check also caught a defect in this run. An earlier stub rule accepted
`060BD924`, a sequential halfword table whose `0x000B` word decodes as `rts`. That
location changed at runtime, so the rule was narrowed to `rts; nop` /
`rts; mov #imm,r0` and the run repeated. The clean table above therefore does not
independently validate the stub rule itself. Identity in a captured image does not
prove that the bytes executed.

**Base and byte-order negative control.** Whole-image agreement between PC-relative
`bsr` targets (base-independent) and absolute literal values (base-dependent)
is **0.1829** at `0x06006000`: 4,207 of 23,000 in-module literals land on `bsr`
targets. Ten wrong bases (±2, ±4, ±0x10, ±0x1000, +0xA000, −0x6000) give at most
0.0190. Byte-swapping gives 0.0351, from only 4 of 114 values. The rule fixed before
any data was seen (≥0.1, ≥5× every control, strictly greatest) passes. The
byte-swap margin is narrow (5.2×) because its denominator is tiny.

**Reconciliation** (static inventory only; adding the leads as tier R changes nothing):

| Reference set | Result |
| --- | --- |
| 199 upstream runtime-learned KRNL targets | **all 199 inside discovered functions** (resume/return points), none unclassified |
| 7 upstream code symbols | 6 entries; `06006C00` inside the startup function (the setjmp return) |
| 3 upstream hook points | all inside functions, as declared mid-function |
| Neptune natural roots `06006174`, `06006372`, `060089C8`, `06095B04` | all entries (A, A, B, B) |
| 13 prior Neptune probe entries | 12 entries; `060958EC` is a second entry 2 bytes after entry `060958EA` |
| Upstream coverage classes online/cut/dead | 67/67 and 3/3 entries; dead: 179 entries, 6 inside functions, **102 unclassified** |

**Interrupt handlers (static disassembly only).** Five `SYS_SETUINT` registrations
name tier-A handlers. Startup `06006372` first calls `060064E0`, which registers:

- `0x40` → `06006652`, which increments the word at `0x060B2D20`;
- `0x41` → `0600665C`, which stores to the VDP1 registers at `0x25D00000`.

Startup then re-registers `0x41` → `06006368`, which increments a longword through
cache-through `0x26006038`. Separately, `06098C6C` registers `0x47` → `060990AA`, a
764-instruction body.

This order was corrected after the first publication; the
[lineage samples](2026-11-05-usa-vblank-counter-lineage.md) confirm `06006368`'s
counter advancing once per frame. The SCU vector names (V-Blank-IN/OUT, System
Manager) are labels to verify. These are #492 timing leads, not executed or
natural-caller evidence.

## BOOT results

| Measure | Value |
| --- | --- |
| Entries (A / B / C) | **1,751** (959 / 767 / 25) |
| Instruction / literal / switch-table / unclassified halfwords | 150,786 / 21,349 / 945 / 44,568 of 217,648 |
| Unresolved indirect sites | 704 (275 through known slots, mostly `0x0608D390`–`0x0608D3A8` and BIOS `0x06000330`/`0x06000334`) |
| Switch tables (unbounded); descents into literal data | 74 (3); 4 (upstream also reports 4 problem functions) |
| Fresh repeat | byte-identical report, entry-list SHA-256 `76ee15fe…f2e70` |
| Upstream comparison | 1,744 shared; 402 upstream-only (400 Neptune-unclassified); 7 Neptune-only; 0 code/data contradictions |

**Residency** makes the BOOT mapping a natural observation. All 435,296 bytes are
identical at `0x06010000` in the frame-600 cold-boot state; wrong mappings
`0x06010002`/`0x06011000` match 13,610/5,486 bytes. At frame 1,200 no 16-byte run
matches: the kernel load has replaced it. The frame-600 image has no mutated BOOT
bytes yet, so it cannot test the BOOT code/data split.

The **bsr/literal base test does not pass for BOOT and is not applicable.** BOOT
reaches its call graph almost entirely through `jsr` literals (one `bsr`-reached
entry of 1,751). Linear-scan `bsr` halfwords are therefore data noise, and literal
pools create a +2 artifact (209 coincidences). The rule was not changed after seeing
this result; the BOOT mapping rests on exact residency.

BOOT calls directly into its own `0x0605xxxx`/`0x0607xxxx` range, so code past file
offset `0x3B4B0` mostly executes in place. The pointer argument `0x0604B4B0` is the
candidate source of upstream's derived `0x00200000` TRAMP lead. That second lifetime
is unresolved and is not analysed at `0x00200000` here.

## What this does not establish

- Execution, callers, arguments or semantics for any discovered entry.
- Source-level function boundaries; the inventory lists reachable instruction sets.
- Master/slave SH-2 role.
- Overlays loaded later.
- XBAND/H2H/FLD/XS modules or the `0x00200000` lifetime.
- The true function denominator. The open remainder is the 54,169 KRNL and 44,568
  BOOT unclassified halfwords, 485 + 704 unresolved indirect sites, the 102
  upstream-dead KRNL entries Neptune leaves unclassified, and every not-yet-loaded
  overlay.

## Reproduce

Private inputs stay outside Git. Each report path must be new.

```sh
python3 tools/saturn_lab/sh2_discover.py inventory --module PRIVATE/0KRNL.BIN \
  --base 06006000 --seed 06006174 --name KRNL --release usa-mk81070-v1003 \
  --expected-sha256 20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7 \
  --report PRIVATE/krnl-inventory.json
(cd tools/saturn_lab && python3 compare_discovery.py --module PRIVATE/0KRNL.BIN \
  --base 06006000 --seed 06006174 --inventory PRIVATE/krnl-inventory.json \
  --saturn-recomp PRIVATE/saturn-recomp-f20de94 --report PRIVATE/krnl-compare.json)
python3 tools/saturn_lab/sh2_discover.py reconcile --module PRIVATE/0KRNL.BIN --base 06006000 \
  --inventory PRIVATE/krnl-inventory.json \
  --references docs/restart/saturn-code/re-lanes/usa-krnl-reference-addresses.json \
  --report PRIVATE/krnl-reconcile.json
python3 tools/saturn_lab/compare_resident_module.py --source PRIVATE/0KRNL.BIN \
  --expected-source-sha256 20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7 \
  --checkpoint PRIVATE/menu-release/checkpoint.json --mapping 0x06006000 --minimum-range 2 \
  --report PRIVATE/krnl-res2-f10800.json
python3 tools/saturn_lab/sh2_discover.py residency --module PRIVATE/0KRNL.BIN --base 06006000 \
  --inventory PRIVATE/krnl-inventory.json --resident PRIVATE/krnl-res2-f10800.json \
  --report PRIVATE/krnl-residency.json
python3 tools/saturn_lab/sh2_discover.py base-check --module PRIVATE/0KRNL.BIN --base 06006000 \
  --wrong-delta=2 --wrong-delta=-2 --wrong-delta=4 --wrong-delta=-4 --wrong-delta=10 \
  --wrong-delta=-10 --wrong-delta=1000 --wrong-delta=-1000 --wrong-delta=A000 \
  --wrong-delta=-6000 --report PRIVATE/krnl-base-check.json
```

BOOT uses the same commands with `--base 06010000 --seed 06010000`, its digest
and the frame-600 cold-boot checkpoint. Inventory takes about 35 s for KRNL and
6 s for BOOT; the upstream comparison takes about 22 s. Sixteen synthetic tests in
`tools/saturn_lab/tests/test_sh2_discover.py` cover the decoder, tiers, bounds, the
data-as-`rts` rejection, register resolution, BIOS handlers, leads, base controls,
residency flagging, exclusive reports and pinned-source refusal. They validate the
tool only.
