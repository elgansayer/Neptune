# Japan A472 TVSTAT timing stores

## Inputs and original-byte execution

This probe executes the Japan `0KRNL.BIN` at WorkRAM-H mapping `0x0600A000`
(786,432 bytes, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`). It
executes original caller entry `0x0600A324–0x0600A32A`, then original helper
range `0x0600A472–0x0600A49E`, stopping at `0x0600A4A0` immediately before the
first BIOS `SYS_SETUINT` service call. Original instructions and
literal words are checked against captured frame-1200 WorkRAM-H; state SHA-256
is `c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f` and
normalized WorkRAM-H SHA-256 is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`.
Interpreter revision is `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`.

Two reports in private evidence directory
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-204/`
are byte-identical. Each covers 16 constructed cases, each executed twice;
cases cross four explicit TVSTAT words (`0x0000`, `0x0001`, `0x020A`, `0x020B`)
with two valid initial SR words and two register seeds. Report SHA-256 is
`51d2f4062837709824b67434a732830faeb36cf55fba92bc39842d3be4480942`; normalized
results SHA-256 is
`4344ff6665d45a2ee7b00ae37783ec19ac5282cdb88cd96e275d04582b86781c`.
The final probe SHA-256 is
`1b7cb385e820e6f7451ac741869c5a845d44d22edc52babc9d3f4016d05fefa2`.

## Recovered prefix behavior

Execution starts at constructed A324 entry with SP `0x06002000` and a sentinel
caller PR. The original prefix pushes that PR, loads SR from R0, and calls A472;
the BSR sets PR to `0x0600A32C`. A472 then saves R14, R13, and PR, reads TVSTAT
as a 16-bit MMIO input, and tests bit 0. The original [Sega VDP2 User's Manual](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/hard/vdp2/hon/p02_50_j.htm)
identifies TVSTAT bit 0 as the PAL/NTSC flag. The independent [Yabause 0.9.15
source](https://sources.debian.org/src/yabause/0.9.15-3/src/yabause.c/) also sets
that bit from `type & 1`; this is a source cross-check, not an executed Yabause
trace.

If PAL bit 0 is clear, the original code selects `0x00DF`; if set, it selects
`0x00FF`. It writes the selected halfword to `0x060BCE88`, adds `0x5000`, and
writes the companion halfword (`0x50DF` or `0x50FF`) to `0x060BCE8A`. The
unmapped TVSTAT address `0x25F80004` is supplied as an explicit MMIO input event,
never backed by ordinary WorkRAM.

`TST #1,R0` also determines SR.T: TVSTAT bit 0 clear leaves T set, while PAL
sets T clear. The later `0xFFFFFF0F` mask and `OR #0xF0` set SR bits 4–7 and
preserve the other supported flags, including this T result. The probe records
four stack saves and the two halfword stores; all other WorkRAM bytes remain
unchanged. It stops before later `SYS_SETUINT`, `SYS_CHGSCUIM`, and A638 calls.

Two mutation controls reject a changed TVSTAT address literal (`0x0600A510`)
and a changed PAL timing literal (`0x0600A4DA`). Initial failures are retained:
`execution-200` exposed the T flag update from `TST`; `execution-201` exposed
the interpreter's valid SR field mask. Both were corrected in the contract.
The intermediate A472-only pair in `execution-202` and the extended A324-start
pair in `execution-203` remain retained; `execution-204` is the final pair.

## Remaining scope

The TVSTAT words are constructed inputs, not status values observed during the
original A472 call. The A472 entry registers are constructed, and the captured
runtime BIOS stubs are not executed in this slice. The paired reports establish
these original instructions and both branch contracts, not natural call
reachability, console video timing, hardware parity, the subsequent service
calls, A638, or whole-kernel behavior. Startup and whole-program recovery remain
active and incomplete.
