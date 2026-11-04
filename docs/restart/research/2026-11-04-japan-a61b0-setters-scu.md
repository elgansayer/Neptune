# Japan A61B0 setter calls and SCU request

This experiment continues from original kernel PC `0x060A6236`, immediately
after the captured SYS_GETSINT return. It executes the remaining A61B0 tail
through its original return, with constructed register/frame inputs consistent
with the prior prefix. It covers index categories 0, 1 and 2, selecting service
numbers 75, 74 and 73.

For each category, the original tail stores the captured VBR result at
`0x060FCD20 + 4*index`, sets the byte at `0x060FCD2C + index`, calls the
captured SYS_SETUINT vector and stores the selected table pointer at
`0x06000900 + 4*service`, then calls captured SYS_SETSINT. The latter uses the
original `sega_101.bin` BIOS default at physical `0x600 + 4*service`, read via
the SH-2 cache-through address, and writes it back to the captured VBR slot.
The tail then records the original D0EN store as an MMIO event at
`0x25FE0010 + 32*index`, value `0x0101`, before restoring SR and returning.
The event sink does not emulate SCU device effects or DMA completion.

The paired private reports are in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-190/`.
Each report has twelve distinct category/SR/seed cases, each executed twice;
the reports are byte-identical. reports are byte-identical at SHA-256
`2df355cfc6773872dd8937729e15f024cf9b8bf035023cfd3d311424866ab371`; the ordered results digest is
`7eb77b399c597c98e6b800ec022b0f5656fab0789d30b64b7c82d08f1af2a5ab`. Each path takes 51 original SH-2 instructions. The executed tail range SHA-256 is
`9adc5a627ae241398b408f4acc50f3d5c900b91c04a58356b6e9c6e0be0d88e6`, and the probe SHA-256 is `7230c721d4f0ce35c66d8d82a21703e4ab778c0d6cf48786ec3471d01e10b8af`.

The original Japanese kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; frame-1200
state SHA-256 is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`; normalized
WorkRAM-H SHA-256 is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`; and the
original BIOS SHA-256 is
`dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac`. The
executed tail hash is `9adc5a627ae241398b408f4acc50f3d5c900b91c04a58356b6e9c6e0be0d88e6`;
the probe hash is `7230c721d4f0ce35c66d8d82a21703e4ab778c0d6cf48786ec3471d01e10b8af`.
The captured SYS_SETUINT and SYS_SETSINT runtime stub hashes are recorded in
the reports. A private mutation of the D0EN address literal from `0x25FE0010`
to `0x25FE0090` is rejected by the MMIO event sink.

This is a bounded continuation with a constructed boundary state, not proof of
natural A70B8 reachability. Runtime setter bytes are not established as
byte-for-byte BIOS-ROM copies. The SCU side effect, BIOS device semantics,
natural task/caller path, subsequent frame behavior and remaining Japanese and
other-region code remain open. Additional Saturn emulators may later provide
independent runtime cross-checks; this report uses the already pinned SH-2
interpreter only.
