# Japan AE98 VBR-selected record store

The Japan T-14302G V1.000 KRNL bytes at `0x0600AE98..0x0600AEAE` select a
record pointer from cache-through words `0x2600A020` and `0x2600A024` using VBR
bit 10. They store input R4 at record offset `+12`, then store input R5 at
`+16` in the RTS delay slot. The observed clobbers are R0 and R6; the probe
checks the other GPRs, PR, MACH, MACL, and SP remain unchanged.

Four original-byte runs cover both VBR values and two distinct R4/R5 seeds.
They use captured frame-1200 WorkRAM-H as the base, while explicitly
constructing the two VBR-selected pointers and destination words. Slot 0 points
to row 3 and slot 1 to row 12, matching the existing scheduler probe's selected
rows. Each run executes 11 instructions and permits exactly one literal read,
one selected cache-through pointer read, and the two ordered record stores. An
AEAC mutation changes the delay-slot source from R5 to R4 and is detected.

Two independent reports, executions 282 and 283, are byte-identical. Each is
mode 0600 and has SHA-256
`13780b2d90431ea4a5da37c116ea91c9a45e17952494749fded702b5d978b80b`. The probe
source SHA-256 is recorded in each private report. Failed harness reports 276,
277, and 279 remain preserved; they record the initial memory-view and VBR-row
corpus mistakes.

The source kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; its Japan
mapping is `0x0600A000`. The callsite and natural lifetime of AE98 remain
unresolved. This contract does not establish natural scheduler behavior,
device effects, timing, gameplay, or full-game equivalence. Continue with the
AE3A loop and its A208 indirect caller, then further original modules. Full
code and asset recovery remains active and incomplete.
