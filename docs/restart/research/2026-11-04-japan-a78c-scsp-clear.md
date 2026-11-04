# Japan A78C SCSP RAM clear

## Original-byte execution

The probe directly executes original Japan 0KRNL.BIN at A78C, its tail-call
to A58E, and the helper return including the NOP delay slot. Source identity is
SHA-256 23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb;
the starting WorkRAM-H is captured frame 1200, normalized SHA-256
3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff. The
pinned interpreter is saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9.

Two byte-identical reports are in
/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-219/.
Each report SHA-256 is
62d36cced2dd10aec57ac028f4aa0a78db356dbaf2675a61a6592923922501e8; normalized
results SHA-256 is
63e628ca0b34f6a7b40372a96fa5fec14a808f4cf7d4eb999e1644f356779e09. The
probe SHA-256 is
21a8cee48f06589b2ab1749fb5d66fd918a3dd7dbe3b9a0ad06e3f8a8dd2852d.

## Recovered bounded behavior

A78C loads R4=0x25B00800, R5=0, and R6=0x0400, then tail-calls A58E.
The original helper emits 512 sequential zero halfword writes, ending at
0x25B00BFE, and returns through the caller's PR. The destination is SCSP RAM;
the probe records each store as a write intent and does not emulate the SCSP
device. R15 and WorkRAM-H remain unchanged.

Two mutations are rejected: changing the destination to 0x25B00802, or
changing the size literal to 0x03FE, which yields only 511 stores.

## Limits and next range

The A78C entry and registers are constructed. This result does not establish
that A546 reaches A78C, SCSP RAM effects, sound startup timing, or audio output.
The broader A546 sequence and all original Japan/USA code and assets remain
open.
