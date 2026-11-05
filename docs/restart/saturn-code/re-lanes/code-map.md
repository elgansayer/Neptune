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

Private repo commit: `3bc8b5a` (all modules disassembled), on top of
`7765c40` (verified 68000 path), `8827e3b` (Japan, docs, progress) and
`211da81` (splitter). This PR adds a public copy of the generic SH-2 formatter.

| Measure | Value |
| --- | --- |
| Modules in the build | 14 (USA 11, Japan 3) |
| Modules rebuilt byte-identically by `make check` | **14/14** (2,971,194 bytes) |
| Modules disassembled | **14/14**; 1,988,942 code bytes emitted as instructions, the rest as data |
| Functions MATCHING / NONMATCHING-verified / asm-only | 0 / 0 / 19,022 static entries (USA 14,026 incl. the duplicate XBSND; Japan 4,996) |
| SH-2 instructions as mnemonics | USA: KRNL 283,487, BOOT 150,786, XBAND 225,221, XS 13,224, H2H 3,009, FLD 1,652, IP 703, SAMPLEIP 719. Japan: KRNL 285,623, IP 719 |
| Cross-file `bsr` kept as raw words | KRNL 1,461; Japan KRNL 1,468; IP/SAMPLEIP 12 each |
| 68000 instructions as verified mnemonics | SND/XBSND/Japan SND 4,050 of 4,051; NLSND 3,746 of 3,747 |
| Assembly files | USA KRNL 1,166, BOOT 1,746, XBAND 6,509, XS 307, H2H 71, FLD 11, IP 11; Japan KRNL 1,203 |

The function counts are static entries from `sh2_discover.py` (SH-2) and the
pinned Musashi descent (68000). They are a measured lower bound, not
source-level totals. Bytes that no inventory classifies are built as data.
No C exists yet because the original compiler is not identified.

USA code-bearing modules (load address, CPU, evidence):

| Module | Load | CPU | Evidence |
| --- | --- | --- | --- |
| KRNL | `0x06006000` | SH-2 | base check passed |
| BOOT | `0x06010000` | SH-2 | |
| IP | `0x06002000` (IP size `0x1000`) | SH-2 | code from `0x06002100` |
| SND | `PROGRAM.BIN[0x44:0x6418]` → sound RAM `0` | 68000 | |
| XBSND | `XBAND.DAT[0x11868:+25,556]` (same bytes as SND) | 68000 | |
| NLSND | `NETLINK/SNDDRV.BIN` | 68000 | |
| XS | `0x00280000` (lead) | SH-2 | first literal `0x00280078` lands in-module |
| FLD | `0x00200000` | SH-2 | base check passed, 0.122 vs 0.0 |
| SAMPLEIP | template | SH-2 | |
| H2H | `0x06002F00` (lead) | SH-2 | leading table of 54 in-module entry pointers |
| XBAND | `0x06006000` | SH-2 | base check passed, 0.197 vs 0.005 |

BOOT `+0x3B4B0` is TRAMP, a 0x8C-byte SH-2 copy routine. Its `mova` targets
`+0x8C`, which is the start of the byte-identical NLSND copy (`+0x3B53C`). The
build now includes that copy from the rebuilt NLSND module.

Japan: KRNL `0x0600A000` (IP first read; 4,835 static entries), IP (`0x1800`
bytes, 15 entries), SND (byte-identical to USA SND).

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
- 14/14 modules byte-identical and disassembled.
- 68000 path: objdump text rewritten for GNU as, then each instruction
  verified by assemble+link+compare, with fallback to raw words.
- New inventories and base checks for IP/SAMPLEIP/XS/FLD/H2H/XBAND/Japan IP.
- TRAMP length resolved.
- USA/Japan module map (`docs/MODULE_MAP.md`, private).
- Public formatter and tests (this PR).

Facts learned about GNU as (they bound the C path):

- It sign-extends negative byte immediates into the 68000 extension word,
  where the original has `00xx`.
- It shortens `(0,An)` to `(An)` unless written `(0:w)`.
- It leaves branches to global symbols as relocations, on both CPUs.

Next frontier:

1. Classify the remaining unclassified bytes (switch tables, unreached code)
   and re-import updated usa-code inventories.
2. Library identification (Sega security/area code in IP; SBL/SGL/GFS/CD).
3. Compiler identification. KRNL has 3,383 `bsr` targets and literal-pool words
   equal to many of them, which is consistent with linker relaxation. Then the
   C path.
4. SBL/SGL/BIOS library signatures.
5. Runtime overlay load map (heavy lock).
6. Recreate the census tool in `tools/saturn_lab` (lost with the 0801Z
   worktree) so the module map's census is reproducible from the public repo.
