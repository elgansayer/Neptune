LANE-STATUS: ACTIVE

# Lane ledger: code-map (module map, splitter, byte-identical build)

Scope: the decomp project's infrastructure and the whole-program denominator in
the private `elgansayer/saturn-bomberman-decomp` repository:

- the module map (every code-bearing file/range with load address, CPU, lifetime
  and compression);
- a config-driven splitter and a `make` build that rebuilds every module and
  verifies SHA-256 (`make check`);
- library identification (SBL/SGL/BIOS/CD-block);
- progress tooling (`docs/PROGRESS.md`).

Issues: #480, #497, #515, #496 (all `factory-skip`). usa-code and sound-68k
build on the splitter and build.

Denominator: every byte of every code-bearing file classified and covered by the
byte-identical build, and every module in the build.

## Status (run 20261105T1122Z)

Private repo commit: `8827e3b` (build, configs, docs), on top of `211da81`
(splitter). This PR adds a public copy of the generic SH-2 formatter.

| Measure | Value |
| --- | --- |
| Modules in the build | 14 (USA 11, Japan 3) |
| Modules rebuilt byte-identically by `make check` | **14/14** (2,971,194 bytes) |
| Disassembled modules (SH-2 mnemonics) | USA KRNL, USA BOOT, Japan KRNL |
| Data-only modules (rebuilt from data directives) | USA IP, SND, XBSND, NLSND, XS, FLD, SAMPLEIP, H2H, XBAND; Japan IP, SND |
| Functions MATCHING / NONMATCHING-verified / asm-only | 0 / 0 / 11,454 (static entries: USA KRNL 4,868, USA BOOT 1,751, Japan KRNL 4,835) |
| Instructions emitted as mnemonics | USA KRNL 283,288 (+1,660 cross-file `bsr` as raw words), USA BOOT 150,786, Japan KRNL 285,427 (+1,664) |
| Assembly files | USA KRNL 1,166, USA BOOT 1,744, Japan KRNL 1,203 (cut at function entries no PC-relative reference crosses) |

The function counts are `sh2_discover.py` static entries (a measured lower
bound). They are not source-level totals. Function counts of data-only modules
are unknown. No C exists yet because the original compiler is not identified.

USA code-bearing modules (load address, CPU):

| Module | Load | CPU |
| --- | --- | --- |
| KRNL | `0x06006000` | SH-2 |
| BOOT | `0x06010000` | SH-2 |
| IP | `0x06002000` (IP size `0x1000`) | SH-2 |
| SND | `PROGRAM.BIN[0x44:0x6418]` → sound RAM `0` | 68000 |
| XBSND | `XBAND.DAT[0x11868:+25,556]` (same bytes as SND) | 68000 |
| NLSND | `NETLINK/SNDDRV.BIN` | 68000 |
| XS | `0x00280000` (lead) | SH-2 |
| FLD | `0x00200000` (lead) | SH-2 |
| SAMPLEIP | template | SH-2 |
| H2H | `0x06002F00` (lead) | SH-2 |
| XBAND | `0x06006000` (lead) | SH-2 |

Embedded copies:

- BOOT `+0x3B53C` holds a byte-identical NLSND copy.
- BOOT `+0x3B4B0` holds the TRAMP payload.

Japan: KRNL `0x0600A000` (IP first read; 4,835 static entries), IP (`0x1800`
bytes), SND (byte-identical to USA SND).

Census basis (run 20261105T0801Z, private evidence): 457 sources and 138
PROGRAM.BIN entries screened for SH-2/68000 signals. Only bank 0 (`s_init`,
the SND driver) of PROGRAM.BIN carries code; no code signal was found in any
decoded bank stream.

## Tools and identities

- Toolchain: GNU binutils 2.44 (Debian `binutils-sh4-linux-gnu`/`binutils-m68k-linux-gnu`
  2.44-3), unpacked without root into `$RE_TOOLS_DIR/cross-binutils-2.44-3`. Deb SHA-256:
  sh4 `9ae1397e431be6b07e63287799d07e791454820bd03406f88fc6f3adee1fbd8c`,
  m68k `195f98f2c4fa751481d6c10eab3b1d8995a67d6452ab5de99fc15686550dc552`.
  The assembler runs as `as -big --isa=sh2` / `as -m68000`, the linker as `ld -EB --no-relax`.
- `tools/saturn_lab/sh2_gas.py` (this PR) is the SH-2 → GNU as formatter used by the
  private splitter (`tools/split/sh2_gas.py`, identical bytes). Synthetic tests:
  - accept/reject agreement with `sh2_discover.decode` on all 65,536 words;
  - PC-relative target agreement;
  - known encodings;
  - an optional exhaustive GNU as round trip (53,752/53,752 accepted words
    reassemble identically, and the accept set equals objdump `-m sh2`'s decode).
- Code maps: `sh2_discover.py inventory` reports (tool SHA-256 `87951608…e516`).
  - USA KRNL and BOOT entry lists reproduce usa-code's receipt
    (`9bc8348f…`, `76ee15fe…`).
  - Japan KRNL (seed `0600A000`) has entry list `f36a46f7f00d61be86d209ef1493da4ff106b0a32c3ad5a5dd5de690a6aed61d`.
- Private inputs: EDC-checked extraction under `$RE_EVIDENCE_DIR/inputs/<release>/`
  (receipt `extraction.json`). It is never committed.

Hard constraint found: GNU as cannot relocate SH fixed-width PC-relative forms
(`bra`/`bsr`/`bt`/`bf` and `mov.l`/`mov.w`/`mova` literals) to symbols in another
file. Errors seen: "displacement to undefined symbol overflows", "pcrel too far".
So the splitter:

- cuts files only where no branch or literal load crosses;
- emits cross-file `bsr` as a raw word;
- starts files on 4-byte boundaries, because `mov.l`/`mova` alignment is
  resolved against the section start.

## Run log

### 20261105T0801Z, 0847Z, 0922Z, 1027Z (no result)

- 0801Z built the whole-disc census (`disc_code_census.py` in its worktree;
  2 private census reports kept in evidence).
- 0801Z then hit the account usage limit before committing. The worktree, and
  with it the census tool, was cleaned up.
- 0847Z, 0922Z and 1027Z exited immediately on the same limit.
- The census JSON survives in private evidence and is used by this run's
  module map.

### 20261105T1122Z (this run)

Moved:

- Splitter, build, checker and progress generator in the private repo.
- 14/14 modules byte-identical.
- USA/Japan module map (`docs/MODULE_MAP.md`, private).
- Public formatter and tests (this PR).

Next frontier:

1. Put 68000 disassembly in the build (SND/XBSND/NLSND, code map from
   sound-68k's inventory). Then split BOOT's embedded NLSND/TRAMP into their
   own segments.
2. Inventories and disassembly for the data-only SH-2 modules (IP, XS, FLD,
   H2H, XBAND).
3. Compiler identification. KRNL has 3,383 `bsr` targets and literal-pool words
   equal to many of them, which is consistent with linker relaxation. Then the
   C path.
4. SBL/SGL/BIOS library signatures.
5. Runtime overlay load map (heavy lock).
6. Recreate the census tool in `tools/saturn_lab` (lost with the 0801Z
   worktree) so the module map's census is reproducible from the public repo.
