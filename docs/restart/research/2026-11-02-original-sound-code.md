# Original USA sound CPU code: three static module identities

Issue [#596](https://github.com/elgansayer/Neptune-Bomberman/issues/596) continues
#480/#481/#488/#515/#464 after four kernel entries were original-byte tested in
PRs #593/#595. This slice reads the actual supplied disc, verifies the three
source identities and descends through original 68000 code with the installed
pinned decoder. **No original sound CPU instruction was executed.** Static
instruction counts below are leads, not semantically recovered function counts.

## Actual source and tool evidence

The [derived receipt](../evidence/2026-11-02-original-sound-code.json) retains
container extents/hashes, source-sector EDC, exact driver slice hashes, vectors,
static maps, unresolved/bad paths, repeated report hashes and native decoder
source/compiler/artifact identities. Original sources and complete reports remain
private at `/home/dev/neptune-research-private/596/sound-001/`. The extraction
and guarded runner recipes are in `/home/dev/neptune-evidence/code596-20261102/`.
Both original files and accepted decoder checkout were mounted read-only; extracted
containers are private analysis copies, verified before each analysis. No sound
samples, songs or videos were extracted as a substitute for code recovery.

| Lifetime / source | Source slice, exclusive end | Driver bytes | Driver SHA-256 |
| --- | --- | --- | --- |
| SND / `BOMSS/PROGRAM.BIN` | `[0x44,0x6418)` | 25,556 | `c8842cc957bf82693ddd72d996353c9cb92feb34fe5f2834c0651aebacb4bd04` |
| XBSND / `XBAND/XBAND.DAT` | `[0x11868,0x17C3C)` | 25,556 | `c8842cc957bf82693ddd72d996353c9cb92feb34fe5f2834c0651aebacb4bd04` |
| NLSND / `NETLINK/SNDDRV.BIN` | `[0,0x5D70)` | 23,920 | `f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296` |

The first two complete driver slices compare byte-for-byte equal, not merely by
hash or decoder count. They still retain distinct container provenance and load
lifetimes at sound CPU address zero. NetLink is a different source. No USA mapping
is assigned to Japan. The original source-track SHA-256 matched the accepted
inventory, and extraction used EDC verification for all sectors read for these
files, with zero EDC mismatches. Full source container SHA-256/length checks precede
slicing; the 15-candidate census's previously unknown slice hashes are now measured
in this receipt, without changing its strict historical metadata join.

The decoder is existing `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`
`m68k.py` plus its bundled Musashi disassembler. Four exact source files are
hash-checked before import/build. The pinned adapter forces 68000 brief indexed
extension format as documented upstream; it is not a 68020 decoder or emulator.
The native library was compiled privately with the existing free compiler and
validated on owned NOP/RTS/BRA bytes before each original analysis. It runs no
original CPU or SCSP model. Original driver analysis was repeated twice per
module; complete reports compare equal. Their hashes are in the receipt.

## Static observations and retained gaps

All three source vector tables declare initial SP `0xA000` and reset PC `0x1000`.
The first 1,024 bytes are treated as vector data. Descending from every even
in-image vector target yields these **candidate** partitions:

| Driver lifetime | Vector target seeds | Candidate instructions / bytes | Candidate data bytes | Unclassified bytes |
| --- | --- | --- | --- | --- |
| SND | 7 | 4,051 / 13,428 | 1,632 | 10,496 |
| XBSND | 7 | 4,051 / 13,428 | 1,632 | 10,496 |
| NLSND | 7 | 3,747 / 12,442 | 1,288 | 10,190 |

Each partition accounts for its file slice, without overlapping code/data byte
sets. This checks the static algorithm's bookkeeping, not actual execution or
correctness of every inferred boundary. Multiple entries can belong to one
routine, and an apparent instruction can instead be data or patched code.
Whole-program and recovered sound-function denominators remain unknown.

Two shared-driver paths are retained as decoder conflicts: `0x1B0A` overlapping
`0x1B0E` and `0x1B12` overlapping `0x1B16`. These may expose a table-boundary or
other static-analysis error; no overlapping instruction stream or self-modification
is declared proven. NetLink retains undecodable paths at `0x183E`/`0x184A` and
an unresolved indirect jump at `0x4122`. An empty unresolved set for the other
driver does not establish complete dynamic-target discovery.

Selected original reset disassembly gives concrete next behavior hypotheses:

- Shared driver reset at `0x1000` sets SR to `0x2700`, clears D0–D7 and A0–A4,
  then branches from `0x101E` to `0x108A`. Bytes at `0x1020` are skipped on this
  path; linear decoding across them would not prove they execute.
- NetLink reset at `0x1000` sets SR to `0x2700`, compares the longword at `0x5D6C`
  with `0x53454741`, and branches back to `0x1000` on inequality. A match reaches
  register initialization and the branch to `0x1060`. This is a static signature
  wait hypothesis, not a naturally observed handshake or trigger protocol.
- NetLink clears D7 at `0x4114`, reads a byte from A6+2, masks it to 0..7, shifts
  it left two and adds it to A2 before `JMP (A2)` at `0x4122`. This constrains the
  added displacement to {0,4,8,12,16,20,24,28}. The incoming A2 base is unresolved;
  the adjacent eight branch entries at `0x4124..0x4144` are a lead, not a proven
  dispatch table. Do not force that base into the decoder to manufacture closure.

Selected text/length observations, without original opcode bytes, are retained in
private `selected-paths.json`. No runtime counter, original instruction timing,
self-modification, sample sequencer, SCSP DSP program or natural sound event has
been validated by this slice.

## Bounds, controls and continuation

`analyze_sound_driver.py` rejects changed/truncated source containers, changed
native decoder sources, an invalid reset target and inconsistent/overlapping
static partitions. It records an exclusive-create mode-0600 report, including
failure phase. An in-memory original reset vector altered to an odd address is
rejected for each driver; this is a structural control, **not an executed semantic
mutation**. Six synthetic wrapper tests passed; the full 166-test input-tooling
suite passed. Native decoder identity and smoke are real host-tool evidence.

Actual source head `bbd57b5e00bbf668b5c06cdd6cb4d7e5cde7a6a9`, base accepted
`a8cbc796cdef88959eba056977fde8ff125416d2`. The existing host gate admitted one
bounded job at unchanged configured shared limit 3 and lease 180 seconds.
Extraction and each analysis used timeout 60 seconds; all commands, including
isolated mount assertions and initial native build, finished in about 15 seconds
total. The supervisor released only its own lease. No new model session, paid
fallback, scheduler, allowance or other owner's work changed; account/CI spend
remains unknown. Exact-head/current-base publication tests remain mandatory.

With existing admission, repeat one module using fresh report names:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/analyze_sound_driver.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --module NLSND --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --cache /home/dev/neptune-research-private/596/sound-001/decoder-cache \
  --report /home/dev/neptune-research-private/596/NEW-NLSND-run1.json
python3 -m unittest discover -s tools/saturn_lab/tests -p test_analyze_sound_driver.py -v
```

Next sound slice: establish the incoming A2 at NetLink `0x4122` from original
callers or bounded original-emulator register traces, reconcile shared-driver
conflicts and derive one driver routine's actual memory/device contract before
68000 execution. Reuse existing Mednafen/Musashi sources; the present adapter is
a disassembler, not an execution harness. Device accesses need a real side-effect
model. SH-2 task/entry helpers `0x06006B38`/`0x0600940A`/`0x0600942E` remain
independently eligible; actual scheduler meaning and RNG taps are not inferred
from symbols. Keep the complete code programme active.

A further selected static inspection found five A2-setting wrappers at `0x40C8`, `0x40D2`, `0x40DC`, `0x40E6` and `0x40F0`, choosing bases `0x4124`, `0x414C`, `0x4138`, `0x4160` and `0x4174`, respectively. Each branches to `0x4104`, which first calls `0x4B00`. A2 preservation across that subroutine is unvalidated; these base-setting leads therefore do not close the indirect jump. The next concrete source question is the `0x4B00` call/return and register contract. Selected observations and their digest are retained, with no original CPU execution.
