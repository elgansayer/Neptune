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
attempt, which lacked a read-only mount for the source checkpoint, is retained
as a preflight failure and was not counted as an emulator execution.

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

Next, add a bounded Japanese-specific observation of the startup path around
`0x0600A312`, after verifying its DVCR, VDP2 and BIOS side effects, then map
further Japan-only ranges and overlays. Keep the Japanese kernel distinct from
USA `0KRNL.BIN`, and keep asset extraction/provenance work separate from
code-byte residency. Only the pinned Beetle/Mednafen lineage is currently
available on this host; no independent emulator cross-check was used.
