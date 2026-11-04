# Japan A61B0 through the captured SYS_GETSINT runtime stub

This continuation resumes the original Japanese kernel at `0x060A61B0`,
executes its captured SYS_GETUINT call, preserves the result at `0x060FCD14`,
then executes the captured SYS_GETSINT call and returns at `0x060A6236`. The
captured master-SH2 VBR is `0x06000000`; its service-75 entry at `0x0600012C`
contains `0x0600087C`. The GETSINT vector slot is `0x06000314` and contains
`0x06000774`.

The paired private reports are in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-184/`.
Each has eight SR/seed cases, each executed twice. Reports are byte-identical
at SHA-256
`aa4c41188069773d879c389e5af77eadc4d8a9362be1ec7b05d323fd2452a537`; the
result digest is
`8a69ea48e201b15e82f3696d2447072776d00f21b8d5e4dcd3c33ef98300db1c`. Each
path takes 51 SH-2 instructions, records 12 reads and seven constructed-stack
writes plus the original store of `0x0600083C` at `0x060FCD14`. Captured
WorkRAM-H is unchanged elsewhere. Changing the private GETSINT vector to
`0x06000794` is rejected by the captured-runtime PC fence.

Source identities are Japanese `0KRNL.BIN` SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, frame
1200 state SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and
normalized WorkRAM-H SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
executed A61B0 range hash is
`51c0ab4bfad76ddfb8f759f98fe71fdd6756b63311d54328f1464e22a62c8949`.
The captured runtime range, vector, VBR entry, pinned interpreter revision
and interpreter source hashes are recorded in both machine reports.

The two stubs are identified only as runtime-resident bytes in the frame-1200
capture; this does not establish byte-for-byte BIOS-ROM provenance. Registers
and stack are constructed, so natural A70B8 reachability remains unproven. This
stops before storing the GETSINT result or executing later setters and the SCU
request at `0x25FE0010`. No device side effect is modeled. The next bounded
step is to continue through that store, the actual captured SYS_SETUINT and
SYS_SETSINT vectors, and an explicitly modeled SCU write boundary. Other
Saturn emulators could provide later independent cross-checks; none is claimed
by this execution.
