LANE-STATUS: ACTIVE

# Lane ledger: usa-code (USA main SH-2 program)

Scope: the USA MK-81070 V1.003 release's original SH-2 game code. That covers
BOOT (`0` at `0x06010000`), `BOMSS/0KRNL.BIN` (KRNL at `0x06006000`) and every
gameplay/menu overlay they load, on both master and slave SH-2. Japan kernel
execution is Codex's lane; compare with it without extending its probes.
Code-map owns the whole-disc census and `module-candidates.json`, and consumes
the USA ranges recorded here. Sound-68k owns the 68000 drivers.

Issues: #480, #481, #482, #483, #492, #493, #495, #497. All carry `factory-skip`
while this lane works them.

Goal: a reproducible static project for the USA program with validated symbols.
For each function: boundaries, ABI, state read/written, callers/callees,
behaviour and gameplay role. Validate against original bytes in an isolated
CPU interpreter and against natural emulator execution, with negative controls.

## Denominator

All USA SH-2 executable functions, including overlays and dynamic targets,
reconciled with runtime discovery. Measured so far (run 20261105T0632Z):

| Module | Static entries A/B/C | Code / literal / table / unclassified halfwords | Unresolved indirect | Runtime evidence |
| --- | --- | --- | --- | --- |
| KRNL `0x06006000` | 4,868 = 37 / 4,663 / 168 | 284,948 / 54,016 / 83 / 54,169 | 485 | resident at f10200/f10800; 0 code/literal halfwords mutated |
| BOOT `0x06010000` | 1,751 = 959 / 767 / 25 | 150,786 / 21,349 / 945 / 44,568 | 704 | fully resident at f600, replaced by f1200 |

Upstream comparison on identical bytes: KRNL 4,867 shared of 5,098 upstream;
BOOT 1,744 shared of 2,146. There are no code/data contradictions in either
module.

Not yet counted:

- Overlays loaded after KRNL (none mapped yet).
- The BOOT `0x0604B4B0` blob's possible `0x00200000` lifetime.
- XBAND/H2H/FLD/XS (outside this lane unless they run in the USA game path).
- Slave-SH-2 entry points.
- Code behind the unresolved indirect sites and the unclassified bytes.

The function denominator is therefore a measured static lower bound, not a total.

Semantic recovery (boundaries plus ABI plus state plus negative control) remains
limited to the earlier isolated results:

- `0600A4B0`, `0600B934`, `0600A0EC`/`0600A08C`, `06009FA8`.
- Library entries `060958EC`, `06095904`, `06095992`, `06095A84`, `06095AB4`,
  `06095ACE`, `06095E5A`, `060A681A`.
- Natural returns of `060089C8`/`06095B04`.

All 4 natural roots and 12 of 13 probe entries reconcile as inventory entries.

## Tools and identities

- `tools/saturn_lab/sh2_discover.py`: inventory, base-check, reconcile and
  residency. SHA-256 `8795160857be036c2a633d3f777c6d830b515c1fc4648ad9f68a20859093e516`
  at this run.
- `tools/saturn_lab/compare_discovery.py`: SHA-256
  `7129a0da9c2eabe76308ae5a50ae67e4f43f318c668ef74878c3184784a66d75`. It loads
  `saturn-recomp@f20de940` `sh2.py`/`hw.py`/`recomp/discover.py` by hash.
- `tools/saturn_lab/compare_resident_module.py`: reused unchanged.
- Upstream leads: `pc-saturnbomberman@c73bc117` (`game.toml` blob `0ec8d923`,
  `seeds.json` `d1486948`, `coverage-classes.tsv` `30ccb2d4`).
- Reference address sets:
  [usa-krnl-reference-addresses.json](usa-krnl-reference-addresses.json).
- Private inputs:
  - `/home/dev/neptune-research-private/483/0KRNL.BIN`.
  - `$RE_EVIDENCE_DIR/inputs/BOOT-0.bin` (EDC-checked extraction receipt beside it).
  - Checkpoints: f600 `a40ddab1…`, f1200 `5caef9e1…`, f10200 `7049c389…`,
    f10800 `e5bd5164…`.
- No Ghidra/JDK was installed. The stdlib tool plus the pinned upstream
  implementation is the current "equivalent" project. Ghidra 12.2/JDK 25 has a
  factory recipe (`tools/factory/provision_ghidra.py`) that is not installed on
  this VPS.

## Run log

### 20261105T0632Z (merged via this run's PR)

Moved:

- First measured USA KRNL and BOOT function inventories.
- Independent decoder and descent, tested on 16 synthetic cases.
- Cross-implementation comparison, deterministic repeats, and a base/byte-order
  negative control (KRNL passes; BOOT not applicable, recorded).
- First runtime residency for BOOT (exact at f600).
- KRNL code/literal versus runtime-mutation cross-tabulation: 0 code changed.
- Reconciliation of all 199 upstream runtime-learned targets (all inside
  functions) and of prior Neptune entries.
- Five `SYS_SETUINT` interrupt-handler registrations identified statically.
- Note: [2026-11-05 USA function inventory](../../research/2026-11-05-usa-function-inventory.md).
- Receipt: [evidence JSON](../../evidence/2026-11-05-usa-function-inventory.json).

Retained failures and refinements:

- The first base metric (tier-A only) had no power. It was replaced by the
  whole-image `bsr`/literal agreement.
- A stub rule false positive at `060BD924` (a data table) was caught by residency
  and the rule was narrowed.
- The BOOT `bsr`/literal test fails because BOOT has no `bsr` call signal. The
  rule was not changed.

## Frontier (ranked)

1. **#492 VBlank/timing handlers.** Execute original `06006652`
   (word++ at `0x060B2D20`) and `06006368` (long++ at `0x26006038`) in the pinned
   interpreter with mutation controls. Then observe natural calls with the
   existing call-trace tooling and relate `0x060B2D20` to `tick` `0x06006108` and
   game-task cadence. After that: `0600665C` (VDP1 `0x25D00000` stores) and the
   764-instruction SMPC handler `060990AA`.
2. **Scheduler and tasks (#492).** Use the inventory to bound `krnl_setjmp`
   `060061C4`, `krnl_longjmp` `060061E6`, yield `06006D36` and the startup
   scheduler region `06006BE4`–`06006D36`. Enumerate task entry pointers (tier-B
   `argument-pointer` provenance) and the 199 resume points as yield/resume edges.
3. **Overlay loader / later modules (#480, code-map).** Find the KRNL file-load
   calls (CD/BIOS slots in `unresolved_pointer_slots_top`). Determine which
   files load where and when, then inventory each overlay with this tool at its
   observed mapping, with residency.
4. **Shrink the unknowns.** Classify KRNL's 54,169 unclassified halfwords,
   especially the 102 upstream-dead entries and the largest runs, and the 485
   unresolved indirect sites (object update pointers at `+0x30`, RAM function
   pointers `0x060C0FE8`–`0x060C1650`). Resolve BOOT's `0x0604B4B0` /
   `0x00200000` lifetime.
5. **Gameplay core (#493).** Start from upstream symbols that reconcile as tier-B
   entries: `idle_object` `060143D8`, `dino` `0601B5CC`, `core_mechanism`
   `0607466C`, and the hook sites inside `060154A4`, `0605E504` and `0606CF28`.
   Recover bomb/fire/movement functions with isolated original-byte tests.
