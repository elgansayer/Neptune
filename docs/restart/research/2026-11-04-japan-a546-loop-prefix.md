# Japan A4C4/A638/A546 loop prefix

## Paired original-byte execution

The probe begins at original Japan `0KRNL.BIN` address A4C4 with constructed
registers and captured frame-1200 WorkRAM-H. It executes original A638 setup,
then all four A546 loop iterations, including A610, A680, A66C, A694, the
counter update, and A714. It stops at A6D6 before the SH-2 on-chip-register
path. Kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; normalized
WorkRAM-H SHA-256 is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`.
Interpreter: `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`.

Two seeds were each run twice. The two private reports under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-233/`
are byte-identical, SHA-256
`345864a802bf747b0b820e1c50da7921019825c9f29345f7228edfaf86ddd835`; normalized
result SHA-256 is
`94346bca7a30711fcd59fbc2c9c70db61c67f6bdc68d14ff9da36ec255bb8cdd`. Probe
SHA-256 is
`a202622cce943e66f188f19e189e20a4abff3970e3cab3e9f8bcd00a6504d351`.

## Observed bounded behavior

Each execution takes 664,714 SH-2 instructions and reaches A6D6 with B3D42=4.
Static PC counts show four visits to each loop call site A52C/A534/A53A and
original A694 branch-path counts for modes 0, 1, 2, and 3.

- A638 initializes the 96-byte descriptor and emits 48 sequential VDP1
  halfword write intents.
- A610 consumes twelve explicit external samples: for each iteration an
  initial value, an unchanged poll, and a changed value. The first is captured
  B3D40=5; later values are constructed test inputs, not a natural producer
  trace.
- A66C emits 131,072 zero longword write intents (512 KiB) from 25E80000
  through 25EFFFFC; B3D44 advances to 25F00000.
- A680 emits 1,024 zero halfword write intents; B3D48 advances to 25F01000.
- A694 follows all four counter-selected modes: SMPC commands 7 and 6 plus
  259 SCSP write intents for mode 1.
- A714 emits 769 SCU write intents: one PPAF clear, 256 PPD writes, and 256
  paired writes to PDD-4 and PDD.

Every device-facing store is intercepted as a strict intent; no hardware
effect, protocol completion, display behavior, sound output, or timing is
claimed. Starting at A4C4 does not establish the preceding A472 call or natural
A546 reachability. A6D6, A78C, the BIOS epilogue, and the rest of the kernel
remain open.

## Retained modeling failures

Reports execution-227 through execution-231 retain corrections for the A638
sign-extended `0xFFFF8000` register value, two omitted counter-address literals,
and SCSP/DSP sink range and event-count boundaries. Execution-232 is retained
as a successful CPU run whose top-level prose incorrectly said 513 SCU intents
while its measured sequence contained 769; it is superseded by execution-233,
whose contract and counts agree. These failures are not counted as additional
successful executions.
