# Japan A680 VDP2 color-RAM clear

## Original-byte execution

This direct-entry probe executes original Japan 0KRNL.BIN at A680 and its
A5B8 halfword-fill helper through both RTS delay slots. It uses the captured
frame-1200 B3D48 destination pointer, 0x25F00800, with two register seeds, each
run twice. Kernel SHA-256 is
23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb; normalized
WorkRAM-H SHA-256 is
3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff. Interpreter:
saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9.

Identical reports are under
/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-224/.
Each report SHA-256 is
9b77b1227ae7820a552ecacedc83ef00adee503d8a002ff9e9335b73f5c0824c; normalized
results SHA-256 is
16cfda6061457bd7602ce361afe1100b1840f5867a01933ba38eb4b57f71e4d3. Probe
SHA-256 is
2f8136cd4de61ffbced9814fed1464106c1c8ef590286ae5fdc70fa65393861d.

## Recovered behavior and address-map cross-check

A680 reads the captured destination pointer 0x25F00800, uses size 0x01FE,
and calls A5B8 to emit 256 zero halfword write intents through 0x25F009FE.
It then updates the B3D48 pointer to the end address, 0x25F00A00. Mutation
controls reject a pointer offset of two bytes and a changed size literal.

The [Sega VDP2 User's Manual address map](https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p01_20.htm)
places Color RAM at relative offset 0x100000 from the VDP2 base at 0x25E00000,
which locates this range in the VDP2 Color RAM address window. The same manual
specifies CPU word and longword access. This is a documentation cross-check;
the probe records writes as intents and does not run an emulator or establish
actual color-RAM effects or display timing.

## Limits and continuation

The A680 entry and return linkage are constructed, though its destination word
comes from the captured frame-1200 state. This does not establish A546 caller
reachability, VDP2 display/color behavior, or natural timing. A546's full
loop, remaining device routines, and original Japan/USA code and assets remain
open.
