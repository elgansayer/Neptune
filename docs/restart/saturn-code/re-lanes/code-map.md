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

Private repo commit: `ee907bd`. Earlier commits from this run:

| Commit | Content |
| --- | --- |
| `e719fdc` | SHC division helper names |
| `b4a1b04` | census JSON in the repo |
| `2e2abd3` | `check.py` first-difference report |
| `9631d2b` | runtime CPU roles |
| `a5d583a` | SINIT/MINIT leads |
| `81b6e5a` | cross-module function matching |
| `c440853` | classification frontier |
| `182954f` | workflow docs for other lanes |
| `2e11d23` | Cinepak work-area correction |
| `6d76714` | non-zero-only residency |
| `6c190e9` | whole container files |
| `6a4a418` | toolchain and runtime screen |
| `f8b7c10` | library anchors |
| `3bc8b5a` | all modules disassembled |
| `7765c40` | verified 68000 path |
| `8827e3b` | Japan, docs, progress |
| `211da81` | splitter |

PR #867 published the SH-2 formatter. The follow-up PR publishes the generic
splitter (`saturn_split.py`) and the 68000 emitter (`m68k_gas.py`).

| Measure | Value |
| --- | --- |
| Modules in the build | 14 (USA 11, Japan 3) |
| Modules rebuilt byte-identically by `make check` | **14/14** (2,971,194 bytes) |
| Whole code-bearing files rebuilt and verified | **all 14 census code-bearing sources** (USA 11, Japan 3). The 5 containers (USA/Japan system area, USA/Japan PROGRAM.BIN, XBAND.DAT) take their code from the disassembled modules via `.incbin`; their other bytes are data owned by the asset lanes |
| Modules disassembled | **14/14**; 1,988,942 code bytes emitted as instructions, the rest as data |
| Functions MATCHING / NONMATCHING-verified / asm-only | **3** / 0 / 19,019 static entries (USA 14,026 incl. the duplicate XBSND; Japan 4,996). The 3 MATCHING are BOOT functions compiled from C by GCC 2.7.2.3 inside the build |
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

Runtime residency comes from captured Beetle states on sound-68k's cold-boot
route. It counts matched non-zero bytes at the load address (runs of at least
16 bytes).

| Module | f900 | f1200 | f1800 | f7200 (stage 1-1) |
| --- | ---: | ---: | ---: | ---: |
| BOOT | 399,184/399,184 | 0 | 0 | 0 |
| KRNL | 0 | 580,550 (loading) | 688,475/693,936 | 688,483 |
| **H2H `0x06002F00`** | 0 | 7,240/7,334 | 7,239 | 7,239 |
| **XS `0x00280000`** | 0 | 34,409/34,409 | 0 | 0 |
| **FLD `0x00200000`** | 0 | 4,378/4,378 | 0 | 0 |
| XBAND | 0 | 0 | 0 | 0 |

So XS, FLD and H2H run on the normal USA path, and H2H stays resident in game.

Uncovered WorkRAM bytes were screened for SH-2 code and chunk-matched
against every disc file and the BIOS images. No unknown disc-derived code
overlay was found in these frames.

The one code region that is not from a disc file is WorkRAM-L
`0x002F0000`-`0x002F33FF`:

- **What the address is.** KRNL `0x0600B494` builds an SBL Cinepak (CPK)
  player parameter block:
  - work area `0x002F0000`, size `0x3190`;
  - ring buffer `0x060C341C`, size `0x2D000`;
  - PCM buffer in sound RAM `0x25A20000`, size `0x10000`;
  - decoding goes to VDP1 VRAM `0x25C08000`.

  So the region is the player's work area. KRNL also passes `0x002F31A0` as a
  code or callback address (`0x0600B730`).
- **Its SH-2 code has an open origin.** It is not raw on the disc or in the
  BIOS. BIOS images match it 10x more often than they match game code, so it
  may be Sega library code that is unpacked or generated at runtime.
- **Rejected: "BIOS backup-RAM library".** KRNL's `BUP_Init` call installs BUP
  in WorkRAM-H at `0x060EC8B0` or `0x060770A4`.

The other code-signal regions were raw PROGRAM.BIN banks staged in WorkRAM-L
(data), and BOOT/XS bytes in transit.

Toolchain (static idiom evidence; no matching build yet):

- **KRNL (USA and Japan) is Hitachi SHC output**:
  - no GCC libgcc helpers and no frame pointer;
  - SHC-style register-preserving division helpers (dividend r1, divisor r0,
    r2-r4 saved);
  - 3,519 direct `bsr` near calls.
- **BOOT/XBAND/XS/H2H are GNU GCC (SH) output**:
  - libgcc `___sdivsi3`/`___udivsi3`/`___movstrSI`;
  - frame-pointer prologues and epilogues.

Cross-module function matching (`tools/split/function_match.py`, private):
functions of at least 12 instructions are hashed with PC-relative
displacements masked and literal pools ignored.

| Module pair | Shared bodies | Reading |
| --- | ---: | --- |
| USA KRNL + Japan KRNL | **3,844** of about 4,200 | one C source per function can serve both releases |
| XBAND + XS | 229 | GCC-built NetLink/XBAND modules share a library layer |
| BOOT + XBAND | 216 | same |
| BOOT + XS | 210 | same |
| KRNL + BOOT | 3 | SBL was shipped as source, so each studio compiled it with its own compiler |
| FLD + KRNL | 29 | FLD_KNL.BIN came from the KRNL team and toolchain |
| USA IP + Japan IP + SAMPLEIP | 14 (all) | Sega's security/area code |

CPU roles:

- KRNL kicks the slave SH-2 via SINIT from `06067608`, and 8+ functions signal
  the master via MINIT. Japan KRNL is the same.
- In all 12 captured states (f900-f7200 and the f10800 menu), **the slave
  SH-2's PC is 0**: it is not running on this route.
- The master executes:
  - BOOT at f900;
  - **FLD in WorkRAM-L at f1200** (`0x002007C6`), so the field loader runs;
  - the Cinepak player path at f2400-f3600;
  - KRNL's main loop in game.

Libraries (version strings):

- SBL `GFS 2.10` (1996-02-01) in both KRNLs, BOOT, XS and XBAND.
- SBL `STM 2.10` and `PCM 1.15`, plus a Cinepak player, in both KRNLs.
- `SYS 2.21` (1996-10-01) in USA KRNL only.
- `FLD 1.21` in FLD/XS/XBAND.
- The PlanetWeb browser in BOOT.
- Sega's 1994 security code in the IPs.
- No SGL.
- USA KRNL's CD-block code clusters in `060958EA`-`06095ACE`.

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

**First MATCHING functions (end of run 20261105T1122Z):**

- GCC 2.7.2.3 for SH was built here without root:
  - 32-bit i386 host from Debian multilib debs;
  - `--host=i386-linux --target=sh-hms`;
  - an `obstack.h` cast-lvalue patch for modern host compilers;
  - `cc1` SHA-256 `63fb80a61c9517e23bcbe833c08fd307db4bf591baab084261a5a5ccb8264bd4`.
- It reproduces three small BOOT functions byte for byte:
  - `06041DAC` with `-m2 -O2 -fomit-frame-pointer`;
  - `0606E2C8` and `0606E2E0` with `-m2 -O2`, frame pointer kept.
- They are now compiled from C into the build (`[[module.c_function]]`:
  `.include` of the cc1 output), and `make check` stays 19/19 identical.
- Negative control: changing one constant in a C source makes `make check`
  fail at `0x0606E2ED`.
- So NetLink's BOOT is GCC 2.7-era code with per-file flags. KRNL (Hitachi SHC)
  remains blocked on a licensed compiler.
- The whole-disc census tool is restored (this PR). Regenerating the census
  reproduces the 0801Z census byte for byte (SHA-256 `65d9aba7…d5e2`).

Later in the run:

- `tools/check.py` now locates the first differing byte. Negative control: a
  flipped FLD byte is reported at `0x00200064`.
- Toolchain preparation for the GCC-built modules:
  - Debian i386 multilib debs unpacked without root (`$RE_TOOLS_DIR/i386-multilib`,
    with a `cc32` wrapper; a 32-bit test program links and runs).
  - GCC 2.7.2.3 source downloaded (SHA-256
    `16166e0f0f2064bb3114716650569065ef3855ae2331d7a29b85d4b9aa73773c`).
  - A bounded `cc1` build for `sh-hms`
    (`$RE_TOOLS_DIR/build-gcc-2.7.2.3-sh/build.sh`) succeeded on the third
    attempt. The first failed on `obstack.h`; the second on read-only tarball
    files.
  - Hitachi SHC for KRNL is proprietary and was not fetched. The owner needs
    to supply a licensed copy.
- Incident: replaying the 0801Z run's edit commands to recover the census tool
  also ran one recorded cleanup command. That command deleted the superseded
  private `census-run1.json` from this lane's evidence directory.
  `census-run2.json`, the one in use, is intact. The reconstructed tool is
  validated: regenerating the census gives byte-identical output.

Also moved later in the run:

- Container files are in the build.
- Library and toolchain identification.
- Runtime residency and overlay screen from captured states.

Next frontier:

1. Compilers:
   - GCC 2.7.2.3 is live for the GCC-built modules (BOOT, XBAND, XS, H2H).
     Decompile them function by function; BOOT semantics belong to usa-code.
   - **Blocked on the owner:** a licensed period Hitachi SHC (and its
     optimizing linker) for KRNL.
2. Trace the writer of the SH-2 code in the CPK work area
   (`0x002F0000`-`0x002F33FF`) with a write-watch (heavy). Extend the
   residency screen to battle mode, stage changes and the NetLink/XBAND paths.
3. Classify the remaining unclassified bytes (switch tables, unreached code)
   and re-import updated usa-code inventories.
4. Separate SBL library functions from game code (anchors above) in the
   symbol files.
5. The census tool is restored (`tools/saturn_lab/disc_code_census.py`). Use
   its `verify` on future census updates.
