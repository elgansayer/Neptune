# Japan kernel residency during original boot

This bounded original execution advances the module census for Japan
T-14302G V1.000. It proves byte residency at a candidate mapping in two captured
states; it does not recover every function, prove all matching instructions
executed, or complete the all-code/all-assets programme.

## Source identity and extraction

The original Japanese `0KRNL.BIN` is the lowest-LBA ISO file at Track 01 LBA
21, 786,432 bytes, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`. It was
read from all 384 Mode 1 sectors with EDC verification and matched the committed
Japan disc inventory. Its boot mapping candidate is `0x0600A000`; USA's
`0x0600A0EC` observer address is not portable to this region. In Japan's image,
that mapped file offset (`0xEC`) is zero padding.

The selected Japanese media lock file SHA-256 is
`8a081f263480088d511fe5f48413ba8ee83bbf5d870324d01930f989a42aa899`; the
settings file SHA-256 is
`0c84d9f6074ee78daa57ff048774c5a85b3383f9e9becc01864cf654fafa2297`. The
reference core is the pinned Beetle/Mednafen generation with SHA-256
`c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e`.

## Actual original execution and state comparison

Two consecutive, fresh-process windows each advanced 600 frames with no input.
The first captured frame 600 on the Sega startup screen; the second resumed that
state and captured frame 1200 at the Japanese backup-memory choice screen. The
original media and core were mounted read-only inside the offline worker, under
the shared host gate (limit 3, 180-second lease). The private run receipts and
states remain under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/`.

Two more 600-frame windows continued from the frame-1200 checkpoint. A one-frame
confirm was delivered in the first, and a short horizontal selection followed
by confirm in the second. The screens remained at the backup-memory choice at
frames 1800 and 2400. These runs prove continued original execution and preserve
the input/output states; they do not establish a successful menu transition or
gameplay. The frame-1800 state SHA-256 is
`da61fd983f32c79ec6ffd145a169e63484fe621ed2662a827ef38fedd994270c`; frame 2400
is `8749b0430e45ec67726c9b9b3fb39d2b706acd3b179e41cc4e0219fb9c19bd6d`. The
second run delivered masks `[0,64,256]` to the first port. Its first setup
attempt could not access the source checkpoint because its directory was not
mounted into the worker. That failed worker receipt is retained at
`continuation-004/supervisor.json`; the run stopped before emulation and is not
counted as an original execution.

The same residency comparer found 729,974 exact source bytes in three ranges at
both frame 1800 and frame 2400. This confirms the previously observed partial
mapping persisted through these windows; it still does not show which resident
instructions ran. Reports are retained as `analysis/frame1800-residency.json`
and `analysis/frame2400-residency.json` beside the earlier comparisons.

At mapping `0x0600A000`, the frame-600 WorkRAM-H state matched 573,440 source
bytes in two exact ranges of at least 4 KiB:

- file `0x00000..0x88000` → mapped `0x0600A000..0x06092000` (557,056 bytes)
- file `0xBC000..0xC0000` → mapped `0x060C6000..0x060CA000` (16,384 bytes)

At frame 1200, three exact ranges matched 729,974 bytes:

- file `0x00114..0xA9D41` → mapped `0x0600A114..0x060B3D41` (695,341 bytes)
- file `0xA9F48..0xAE8FD` → mapped `0x060B3F48..0x060B88FD` (18,869 bytes)
- file `0xAE903..0xB2697` → mapped `0x060B8903..0x060BC697` (15,764 bytes)

Checkpoint state SHA-256 values are `51b76bdf27a1414af49dda1f5e7261645e134f697579f3cdd32e6f716b6c1441`
at frame 600 and `c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`
at frame 1200. The later image has more large exact ranges, while neither state
supports claiming the full 786,432-byte file is resident or unchanged.

The new [resident-module comparison tool](../../../tools/saturn_lab/compare_resident_module.py)
validates source and checkpoint hashes before comparing bytes. It reports only
source-relative ranges and hashes, not original bytes. Its two owned synthetic
tests pass; the two private original runs independently produced the ranges
above. Re-run against the existing private extraction and checkpoints with fresh
report paths:

```sh
python3 tools/saturn_lab/compare_resident_module.py \
  --source /home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/private-original/0KRNL.BIN \
  --expected-source-sha256 23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb \
  --checkpoint /home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/continuation-002/boot-002-next-600frames/checkpoint.json \
  --mapping 0x0600A000 --minimum-range 4096 \
  --report /home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/analysis/new-report.json
```

## First Japanese kernel stub and limits

Pinned SH-2 disassembly of the original file at the candidate mapping shows the
first stub at `0x0600A000`: it loads a literal target `0x0600A114`, jumps through
`r3`, and executes a NOP delay slot. The second stub targets `0x0600A79C`, whose
first instruction is a self-branch. At `0x0600A114`, the decoded prefix sets SP
to `0x060BD91C`, clears the byte range beginning at `0x060B2404` up to the word
at `0x060B2408`, writes `1` to `0xFFFFFF08` (SH-2 DVCR), calls `0x0600A312`, and
then loops at `0x0600A13A`.

The disassembled `0x0600A312` entry saves `r9..r14` and PR, masks/writes SR,
calls the BIOS `SYS_CHGSCUIM` and `SYS_SETUINT` vectors, writes cache-through
address `0x2600A038`, and polls it before proceeding. Its nested `0x0600A472`
routine reads VDP2 `TVSTAT`, writes its value-derived words to WorkRAM-H, then
calls BIOS interrupt services and another helper. These references need real
device and BIOS side-effect semantics before direct replay. Disassembled
Japanese `0x0600A4B0` is an immediate inside `A472`, not the USA `A4B0` helper;
absolute addresses cannot be transferred between regional kernels without
matching source evidence.

This is static instruction evidence; a save-state byte match does not supply a
PC trace through that path or a device-side-effect model. Full private decode
output is retained at
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/analysis/next-kernel-functions.txt`
(SHA-256 `15b8f624d261a31e6ea5600ebfd442d02d6c1a39b3963be29ada660df3c035d2`).

## Isolated Japanese startup buffer helpers

Continuing the original-byte disassembly found two bounded helper entries in
the `0x0600A638` startup area: `0x0600A58E` is called and stores a word value to
a destination buffer; `0x0600A5A2` is reached by a tail branch and copies words
from a source buffer to a destination.
`tools/saturn_lab/probe_japan_startup_helpers.py` executes the original Japan
kernel bytes under the pinned SH-2 interpreter. It maps only the exact original
code range plus explicit source/destination WorkRAM buffers; reads outside code
and the copy source, writes outside the destination, or instruction fetches
outside the two helper ranges fail.

For signed lengths `R6` in `{-2,-1,0,1,2,3,4,5,6,7,8,15,16,17,30,31,32,63,64,65,126,127,128,129}`,
both helpers were executed twice per length. Nonpositive lengths perform no
buffer transfer. Positive lengths transfer `ceil(R6/2)` 16-bit words, so odd
byte lengths round up by one word. The fill helper writes the low 16 bits of
`R5`; the copy helper reads through `R5`, writes through `R4`, and advances both
pointers by two bytes per word. The probe checks the full destination buffer,
source preservation, pointer changes, untouched GPRs, SR T result, SP/PR,
instruction-PC fences, and exact write addresses and widths. Two wrong-opcode
controls (word fill changed to long fill; word load changed to byte load) are
rejected. The report retains 48 repeated case pairs and both control results.
The successful private report is
`execution-005/japan-startup-helpers.json` (SHA-256
`d430f7e3e3e81b88bfae23d376b48eb94cb14d9768a72ef0911bc6a90cf99838`); it binds
the probe source hash, original range hash, and pinned interpreter source hashes.
The focused 20-test suite passes, including three tests for this probe tool.

This is isolated original-CPU execution, not a natural caller or a complete
`A638` execution. In particular, `A638` also accesses VDP1, SMPC, SCSP, SCU and
SH-2 DMA registers; those hardware effects are not mapped or simulated here.
The complete report and failed earlier bounded attempts remain private under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-*/`.

Further disassembly of the adjacent initialization path at `0x0600A6D6` reads
SH-2 on-chip `0xFFFFFE73`/`0xFFFFFE71` registers and accesses SCU PPAF/PPD at
`0x25FE0080`, `0x25FE0084` and `0x25FE008C`. It is therefore outside the
bounded WorkRAM-only helper replay. Original decode files are retained privately
as `analysis/japan-a6d6-disassembly.txt` (SHA-256
`57af4bbf7af088fd8131b7677c7acd167c45e49bf2e709727814a99e291443ed`) and
`analysis/japan-a714-disassembly.txt` (SHA-256
`054458fe84d8c22cb96bf1aec51ba0180aa504723f0c218f1f09435cdc29aa8e`).

Next, add a bounded Japanese-specific observation of the startup path around
`0x0600A312`, after verifying its DVCR, VDP2 and BIOS side effects, then map
further Japan-only ranges and overlays. Keep the Japanese kernel distinct from
USA `0KRNL.BIN`, and keep asset extraction/provenance work separate from
code-byte residency.

The user's suggestion to use another Saturn emulator is useful here. Yabause is
an independent candidate to the current Beetle/Mednafen lineage. Its upstream
debugger-interpreter documentation describes SH-2 register/disassembly views,
code and memory breakpoints, and per-instruction trace logging ([project](https://github.com/Yabause/yabause),
[debugger guide](https://wiki.yabause.org/index.php5?title=Readme_QT#Debug_Windows)).
It is not installed or validated on this host yet. Prepare a pinned build
through the existing provisioning boundary, keep its inputs read-only, and use
it for independent startup observations; do not treat its save states as
interchangeable with Beetle/Mednafen states.
