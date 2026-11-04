# Frame-1200 captured SYS_GETUINT stub

The source for this result is the private Beetle frame-1200 state, SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, core
revision SHA-256
`c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e`. The
normalized captured WorkRAM-H bytes have SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The raw
state and normalized memory image remain private.

## Snapshot-resident byte execution

The frame's system slot at `0x06000304` contains pointer `0x0600077C`; the
captured 8-byte stub at that address loads table base `0x06000900`, shifts R4
left by two, and returns the corresponding table word in the RTS delay slot.
For index 75, the normalized snapshot has word `0x0600083C` at `0x06000A2C`.
The probe executed those eight captured runtime bytes, not the Sega Saturn
Bomberman kernel or BIOS ROM. Sixteen CPU-register seeds were each executed
twice.

The paired private reports in `execution-137` are byte-identical at SHA-256
`52af34b52125da180119a9eb521b710ded41b365512868143c2fc08366eb191a`; the
ordered result digest is
`6af376279be8fe3fe4a2a0c13df0626e7ab2d348d3fa95467a98f73d8d47da20`. The
captured stub code and probe hashes are
`8229fa7de28be087102c8e16e3274878819fba92338a3ac279f97defc801515c` and
`9ebe546b98f70e79c9ed8c483f050220850f8b625af4e5ec85f4f88dcc14b40c`.

Replacing the captured index-75 word with `0x06000840` is rejected when the
stub returns a different value.

This is a static state snapshot and a separate interpreter execution of its
resident bytes. It does not establish that the stub executed at frame 1200,
when or from which BIOS/runtime image it was loaded, or natural A61B0 call
behavior.
