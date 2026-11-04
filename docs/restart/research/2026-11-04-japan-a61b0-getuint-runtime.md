# Japan A61B0 through the captured SYS_GETUINT runtime stub

This continuation resumes the original Japanese kernel at `0x060A61B0` and
executes through its first `SYS_GETUINT` call and return to `0x060A6224`. The
system vector is read from frame-1200 WorkRAM-H: slot `0x06000304` contains
`0x0600077C`. That captured runtime stub loads the table base at
`0x06000900`, scales service index 75 by four, reads the captured table word at
`0x06000A2C`, and returns `0x0600083C` in R0. R4 is left scaled to 300. Execution
stops before A61B0 stores the result or makes its following SYS_GETSINT call.

The paired private reports are in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-181/`.
Each has eight SR/seed cases, each internally executed twice. The reports are
byte-identical at SHA-256
`ccd772fdb7ee9ac1cecb09cc8d1fdc1da4d49fd33a35937be35db130af826d86`;
the result digest is
`ba9e56d68df7a6aaeba6fbd72ddfae8c1699519b580ef8b4a38836ab140e41b0`.
Every path takes 38 SH-2 instructions, records seven captured-data/literal
reads and seven bounded stack writes, and leaves captured WorkRAM-H unchanged
outside that stack. A private-copy mutation of the runtime vector to
`0x06000774` is rejected by the execution PC fence. The initial failed attempts
remain retained as `a61b0-getuint-runtime-a.json` and `-b.json`; they exposed a
wrong R4 postcondition and an incorrect whole-memory comparison in the new
harness, both corrected before the passing pair.

Source identities are Japanese `0KRNL.BIN` SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, frame
1200 state SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and
normalized WorkRAM-H SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
executed A61B0 source range SHA-256 is
`134ab330930b101c8742ebd5ef4af2b41107a4f2685b603b72591185618060fa`; the
captured stub, its literal, vector and selected table-entry hashes are in each
machine report. Interpreter revision and all three source hashes are recorded
there as well.

The code at `0x0600077C` is identified here only as runtime-resident bytes from
the frame-1200 capture. This execution does not establish that the stub was
copied byte-for-byte from the supplied BIOS ROM. The call uses a constructed
stack/register seed, does not prove natural A70B8 reachability, and does not
execute the returned `0x0600083C` target, the following service calls, or any
SCU/cache effects. Continue from `0x060A6224` with the original result store and
the actual captured SYS_GETSINT vector/table before claiming A61B0 completion.
