# Japan A61B0-installed service callbacks

The original A61B0 family selects one of three callback bodies:
`0x060A62D8` for service 75, `0x060A6348` for service 74 and `0x060A63B8`
for service 73. Each callback clears its category flag, calls captured
SYS_SETUINT and SYS_SETSINT stubs, clears the category flag again, restores the
saved SR priority and returns. The setter calls replace that service's table
and VBR words from the callback's global values. For zero inputs, SYS_SETUINT
uses its captured fallback `0x0600083C`; SYS_SETSINT restores the original
BIOS service default.

The paired private reports are in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-194/`.
Each report contains 72 distinct cases: all three callback/service pairs,
four SR values, two stack seeds, and three separately labeled input sets
(identity-checked frame-1200 globals, constructed zeros and constructed
nonzero values). Each case executes twice. The reports are byte-identical at
SHA-256
`00ecc3cf829011dd950f40977b9f2bf3a159771ea1456a926be9d08b45b4c7a0`; the
ordered results digest is
`71f49114d4e3cff2d5ce812e8e5bd722bc90d3e5bf5863eccb45a4e670061c1c`. Zero
input paths take 60 instructions; nonzero paths take 57. The 24 captured-input
cases use zero values from frame-1200 WorkRAM-H and restore BIOS defaults
`0x0600087C`, `0x06000876` and `0x06000870` for services 75, 74 and 73. A
mutated SYS_SETUINT vector target `0x06000702` is rejected by the execution PC
fence.

Source identities: Japan `0KRNL.BIN`
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, frame-1200
state `c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`,
normalized WorkRAM-H
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`, and
original BIOS `sega_101.bin`
`dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac`. Callback,
setter-stub, probe and interpreter identities are recorded in each report.

Callback registers and stack are constructed. The captured frame has zero
callback globals and does not prove these callbacks have been naturally
installed or entered. The setter bytes are identified only as runtime-resident
captured code, not byte-for-byte BIOS-ROM copies. BIOS table values are read
from the supplied ROM through the pinned interpreter's cache-through mapping;
device timing, natural callers and SCU effects are not modeled. The broader
programme remains active. A previous checkpoint sentence incorrectly
associated frame-1247 task-init evidence with A70B8; the retained A70B8 probe is
constructed and stops at `0x060A7136` before A61B0.
