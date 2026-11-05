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

## Status (run 20261105T2122Z)

Private repo commit: `119f126` (this run's commits: `c44d497` to `119f126`).

**442 MATCHING** (145 at the start of the run): the NetLink application layer that BOOT,
XS and XBAND share is now being compiled from C. 97 shared functions are built from one
C source each into all three modules (+291), and 3 XS/XBAND-only loader functions into
both (+6). Among them are the SBL CD block command executor and the transfer service
routine. Every batch was verified by a re-split and `make check` (19/19 identical).
The 418 state was verified as below. The final 442 state was verified by a re-split of
boot/xs/xband and `make check` (19/19) at 22:42Z.
At the end of the run, under the heavy lock:

- a clean `make clean && make split && make check && make audit` passed (19/19 identical,
  audit OK);
- negative control: changing one constant in a shared C source makes `make check` fail in
  BOOT, XS and XBAND, each at that function.

New tooling (private): `tools/toolchain/ctry.py` compiles a candidate C file with a chosen
`cc1`, compares each function with the original bytes in every module holding the same
body (relocated literal words masked), prints a side-by-side diff, and records a match in
per-module lists (`config/usa/<module>.{c_functions,c_globals,status}.txt`) that the
splitter merges into the build. Callee and data addresses per module come from the
original literal words.

**Compiler finding: this layer's compiler left word stores of constants and memory values
to reload.**

- FSF GCC 2.6.3, 2.7.2.3 and the Feb 1996 trunk copy a non-register source into a pseudo
  at expand time when the destination is memory (`prepare_move_operands` in the SH
  backend). Local allocation then gives it `r1`.
- The originals hold such values in the register reload would choose: the first register
  in allocation order (`r1 r2 r3 r7 r6 r5 r4 r0 r8`) that no pseudo uses. Examples: a 0
  stored through `r3` (r1, r2 taken), through `r7` (r1-r3 taken), a -1 through `r5`, and
  one function saves `r8` in its prologue only to store a constant. A cache-purge loop
  re-loads its 0 inside the loop, as a reload does.
- `jan96` plus that two-line change (`nocopy2`: no copy for SImode constant and memory
  sources with a memory destination; `movsi_i` accepts them until reload) reproduces 7
  earlier "register choice" near misses and 50 further functions. It changes no C function
  matched before.
- The prebuilt libraries were not built with it: 14 matched libgcc/newlib units change
  under `nocopy2`. So the application code and the vendor libraries come from different
  compilers.
- **Second finding: branch delay slots as in GCC 2.6.3.** GCC 2.7.x declares annul-true
  slots for SH conditional branches, so `reorg` puts a fall-through insn after a plain
  `bt`/`bf`. The originals instead steal the next test from the branch target into a
  `bt/s` slot, as GCC 2.6.3's definition (no annul-true slot) allows. `nocopy3` (`nocopy2`
  plus the 2.6.3 `define_delay`) matches 5 more functions and keeps all 104 earlier C
  matches. The team's compiler thus mixes Dec 1995/Jan 1996 FSF SH changes with an older
  backend part: a vendor branch rather than an FSF release.
- Next compiler leads in this layer:
  - `clear_by_pieces` (FSF trunk, 24 Dec 1995; small structs are cleared with two word
    stores);
  - `mov #imm8; extu.b` synthesis of constants 128-255;
  - large address displacements whose constant is loaded late (base in `r1`, constant in
    `r2`), the same "left to reload" pattern;
  - the order of callee-saved registers.

| Measure | Value |
| --- | --- |
| Modules in the build | 14 (USA 11, Japan 3) |
| Modules rebuilt byte-identically by `make check` | **14/14** (2,971,194 bytes) |
| Whole code-bearing files rebuilt and verified | **all 14 census code-bearing sources** (USA 11, Japan 3). The 5 containers (USA/Japan system area, USA/Japan PROGRAM.BIN, XBAND.DAT) take their code from the disassembled modules via `.incbin`; their other bytes are data owned by the asset lanes |
| Modules disassembled | **14/14**; 1,988,942 code bytes emitted as instructions, the rest as data |
| Functions MATCHING / NONMATCHING-verified / asm-only | **418** / see usa-code / 18,605 static entries (19,023 known; USA 14,027 incl. the duplicate XBSND; Japan 4,996). 298 are C functions compiled by GCC 2.7.2.3 variants (BOOT 100, XS 99, XBAND 99): the NetLink application layer, built from one source per function into every module that holds it. 120 are library routines compiled from their original free-software sources: GCC's libgcc (BOOT 55, XBAND 22, XS 3, H2H 1) and Cygnus newlib 1.6.1 (BOOT 18, XBAND 17, XS 4). 20 more inventory entries are extra entry points inside those routines and are not counted as functions |
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

### 20261105T0801Z, 0847Z, 0922Z, 1027Z, 1327Z (no result)

- 0801Z built the whole-disc census (`disc_code_census.py` in its worktree;
  2 private census reports kept in evidence).
- 0801Z then hit the account usage limit before committing. The worktree, and
  with it the census tool, was cleaned up.
- 0847Z, 0922Z, 1027Z and 1327Z exited immediately on the same limit.
- The census JSON survives in private evidence and is used by this run's
  module map.

### 20261105T1122Z

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

**MATCHING count at the end of the run: 25.**

- 11 BOOT functions are compiled from `src/usa/boot/*.c` by GCC 2.7.2.3.
- 7 of them are shared library functions that also sit byte-identical in XS
  and XBAND, so the same sources build them there: 7 + 7. Among them:
  - the SBL CD-block command-register write (CR1-CR4);
  - three accessors of a global record.
- A clean `make clean && make split && make check && make audit` under the
  heavy lock passed (19/19, audit OK) at the 16-function state. The last 9
  functions were verified by rebuilding BOOT, XS and XBAND.
- All 8 BOOT fingerprint targets match at `-m2 -O2`, with or without
  `-fomit-frame-pointer` per source file, once the C is phrased like the
  original (statement order and temporaries matter).
- New build features:
  - Globals referenced from C are mapped to their original per-module
    addresses (`c_globals` → linker script).
  - cc1's `.align` is zero-filled, because the original assembler padded
    with `0000` and GNU as 2.44 pads code with `nop`.
- Every addition was verified by a rebuild of the affected modules with
  identical SHA-256.

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

### 20261105T1622Z

Moved: **GCC's runtime library (libgcc) is now compiled from its original
sources inside the byte-identical build: 70 routines MATCHING** (95 MATCHING in
total). Private commit `6a37a0f`.

- Method: compile every libgcc unit for SH (`lib1funcs.asm` members; every
  function of `fp-bit.c`/`dp-bit.c`) for both multilibs (`-m2`, default `sh1`).
  Search each module for the bytes, with the literal-pool words that hold
  external addresses masked. The original words in those slots then give the
  addresses of the callees and data. Identical wrappers (for example
  `___eqsf2`/`___nesf2`/`___ltsf2`) are placed by their references and by object
  order.
- Found:
  - BOOT links the `-m2` libgcc: 6 `lib1funcs.asm` routines and 38 of the 42
    soft-float functions of `fp-bit.c`/`dp-bit.c`.
  - XBAND links the default (`sh1`) multilib (21 units).
  - XS has 3 `lib1funcs.asm` routines and H2H has 1.
- Source revision: the soft-float functions match **GCC 2.7.0's**
  `config/fp-bit.c`, which packs IEEE fields with bitfields; 2.7.1 and later use
  shifts.
  - GCC 2.7.0 is not on the GNU mirrors as a tarball. It was rebuilt from
    `gcc-2.6.3` plus the official `gcc-2.6.3-2.7.0` diff.
  - Check: applying the `2.7.0-2.7.1` diff gives GCC 2.7.2's file.
- Compiler: a GCC 2.7.0 `cc1` was rebuilt the same way (bison 3 needed two
  grammar fixes). Its soft-float output matches nothing, while 2.7.1 and
  2.7.2.3 both give the 38 matches. So the original `cc1` is 2.7.1-like.
- The 4 BOOT misses (`_pack_d`/float, `___fixsfsi`, `__fpmul_parts`/double,
  `___fixdfsi`) differ in how `constant - register` is compiled:
  - the original emits `neg` + `add #imm`;
  - FSF 2.7.x's `subsi3` has no constant-operand expansion.

  This points to a later (Cygnus-era) SH backend: the next compiler lead.
- Build: new `[[module.lib_function]]` entries, plus `tools/split/libfunc.py`
  (compile one library source, extract one unit, make its labels unique, resolve
  its references per module).
  - `make check` stays 19/19 identical.
  - Negative control: mutating one statement of `fp-bit.c` breaks `usa/boot`
    and `usa/xband`.
- Counting rule: 20 inventory entries are extra entry points inside one
  `lib1funcs.asm` routine (`___ashiftrt_r4_N`). They are recorded as `covered`
  and no longer counted as functions, so the MATCHING count is not inflated.

Later in the run (private `5a1180f`, `8f1b0de`, `978a858`): **136 MATCHING**.

- `libgcc2.c` of GCC 2.7.0 adds BOOT's `___divdi3`/`___moddi3`/`___udivdi3`/
  `___umoddi3` and XBAND's `___lshrdi3`.
- **Compiler variant found.** The 4 soft-float misses need Jim Wilson's FSF
  trunk SH change of **9 Dec 1995** (`subsi3` expander, `ADDRESS_COST`; GCC
  2.8.0 ChangeLog.10).
  - GCC 2.7.2.3 with only that change (`cc1 = "dec95"`) matches all four, plus
    BOOT's `___lshrdi3`, and keeps every other BOOT/XS/H2H unit and C function
    identical.
  - XBAND's libgcc does not have the change, so XBAND was built with a
    different toolchain.
  - BOOT's toolchain therefore had a 1996 backend with mid-1995 library
    sources: a Cygnus-style release branch.
- **C library identified: Cygnus newlib.** newlib 1.6.1's sources compile to
  BOOT's string functions and `mktime` (16), XBAND's string and stdio pieces
  (14) and XS's (3). BOOT's `vfprintf` tables are the BSD 4.4 ones that newlib
  carries.
- Matching discipline:
  - A one-call wrapper under 64 bytes counts only if one of its references
    points at another accepted unit. This rejected look-alike
    `___builtin_vec_new`/`___builtin_vec_delete` hits.
  - Data tables are not units.
  - The matcher reads the original files, never build outputs.
- Public: `tools/saturn_lab/lib_unit.py` (this PR) is the generic,
  content-free core, with synthetic tests.
- Two older GCCs were rebuilt for the comparison:
  - FSF 2.7.0 from gcc-2.6.3 plus the official diff; its parser was
    regenerated with Debian bison 3.8.2 after two grammar fixes;
  - 2.7.1 from 2.7.0 plus the 2.7.0-2.7.1 diff.

Final part of the run (private `fe239a6`-`3ab68a3`): **138 MATCHING**.

- A second backend change is confirmed: Jim Wilson's **2 Jan 1996**
  `gen_shifty_op` change (a `nop` for a shift by 0).
  - Added to the Dec-1995 cc1, it gives `jan96`. That matches BOOT's
    double-precision `__fpmul_parts` (876 bytes) and loses nothing.
  - BOOT's compiler therefore has the FSF trunk SH work through at least
    2 Jan 1996.
- `___udivmoddi4` matched once `longlong.h` was vendored; the matcher had been
  skipping it as a compile failure. BOOT's whole libgcc is now compiled from
  source.
- Shared lead: XBAND's unmatched soft-float core and BOOT's corrected near miss
  `0606F4E4` differ from our output **only in register choice**.
  - `REG_ALLOC_ORDER` is the same, and FSF 2.7.0/2.7.1 do not help.
  - Suspect a generic register-allocation change from late 1995 or 1996.

Rejected at the end of the run: a cc1 built from the FSF trunk of 14 Feb 1996
(GCC git mirror, overlaid on 2.7.2.3; two build fixes).
- It gives fewer BOOT matches than `jan96` (libgcc 41 vs 55, newlib 14 vs 16)
  and leaves the near misses unchanged.
- So BOOT's compiler is a 2.7.2 branch with selected SH backports, not the
  trunk.
- The GCC git mirror does serve 1996 commits (`gh api
  repos/gcc-mirror/gcc/commits?path=...`), so single commits can be tested on
  top of `jan96`.

Last change of the run (private `d7c5b11`, public `lib_unit.py` in this PR):
**145 MATCHING**.

- The resolver resolves larger units first and allows one name per address.
  - It rejected a `_localeconv` look-alike whose callee address belongs to
    XBAND's `_rand_r`.
  - It added BOOT's `index`/`bcmp`, which wrap the placed `strchr`/`memcmp`.
- XBAND/XS library units match best with `-O2 -fno-force-mem` (+5, one unit
  keeps plain `-O2`), a proxy for their compiler variant.

Next frontier (from this run):

1. Register allocation: find the generic 1995-96 change behind the
   register-choice differences:
   - XBAND's `sh1` soft-float core;
   - BOOT's near misses;
   - probably many more GCC-module functions.
2. XBAND's toolchain:
   - `-O2 -fno-schedule-insns2` also matches its `___negdf2`;
   - most of its newlib (`_malloc_r`, `__swbuf`, `fflush`, `vfprintf`) does not
     match yet.
3. BOOT's remaining C library (`vfprintf`, `sprintf`, `strtol`, ...). These now
   compile but do not match.
4. Decompile BOOT/XBAND/XS/H2H game and NetLink code with
   `[[module.c_function]]`. BOOT should use the `jan96` cc1.
5. Still open from the previous run: the CPK work-area writer, classification
   of unclassified bytes, SBL symbol names, census verification. Owner decision:
   Hitachi SHC for KRNL.

### 20261105T1852Z (no result)

Exited at once on the account usage limit.

### 20261105T2122Z (this run)

Moved: **442 MATCHING** (from 145). See the status section for the two compiler findings.

- Target: the code BOOT, XS and XBAND share (function-match report: about 210 bodies), the
  NetLink application layer above the libraries. One C source per function goes into all
  three modules, so each function adds three MATCHING.
- Batches of 3-14 functions; each batch was rebuilt (re-split of boot/xs/xband, then
  `make check` 19/19 identical) and committed.
- Rules that turned near misses into matches (recorded in the private progress file):
  - callee return types decide the call register (`r0` for value-returning callees);
  - struct member access instead of `char *` arithmetic;
  - `return f(x)` per switch case keeps the original's separate calls;
  - branch order of `if (...) return A(); return B();`.
- An `r1`/`r2` register swap in many functions was traced to the compiler, not the source
  (status section). Two experimental `cc1` builds (constants only; constants and memory
  sources) took about 3 s each, because only `sh.o` is rebuilt.
- About 25 near misses remain, listed in the private `docs/TOOLCHAIN.md` with their cause
  where known.
- Rejected experiment: leaving every large `add` constant to reload (`nocopy4`) improves
  some near misses and breaks others, so it was not adopted.

Next frontier:

1. Continue the shared layer (about 120 larger bodies left), then BOOT-only and
   XBAND-only code of the same layer.
2. Build the next compiler variants one change at a time (`clear_by_pieces`, constant
   synthesis, delay slots, callee-saved order) and keep only changes that lose nothing.
3. Still open from earlier runs: XBAND's soft-float core and newlib, BOOT's remaining C
   library, the CPK work-area code origin, unclassified bytes, SBL symbol names.
   Owner decision: a licensed Hitachi SHC for KRNL.
