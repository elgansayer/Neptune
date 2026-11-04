# Japan A717C full helper return path

The prior paired boundary execution resumes here from an exact serialized
return state at `PC=PR=0x060A71C0`. The first stage covers 23,328 constructed
caller/CHCR/DMAOR/R6 cases twice and records all R0–R15, SR, and stack writes.
The paired boundary report SHA-256 is
`6168725611c858f09c082c8ac47f788d08e21f64cf2702b4c602bc2c0073929b`.

This continuation restores that register and stack state over captured Japanese
frame-1200 WorkRAM-H and executes the original A717C tail through A600C,
A595B6, A6100, A5F98 and the outer A717C epilogue/RTS delay slot. It ends at
the pinned interpreter return sentinel. The restored continuation is a
serialized CPU boundary, rather than a single uninterrupted interpreter
process.

The paired private reports are in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-180/`.
Each report has 1,728 cases, with each case internally repeated twice. The
reports are byte-identical at SHA-256
`e4ddfad265ac6f4d07f476825698575b9adaf591e00d98d65323238187aadc78`; the
result digest is
`cc2e4bd612bd65cdb217fc275dc09a8c42a0948891827c2ac5937432432cc003`.
Paths take 200–206 SH-2 instructions depending on the tested R8 and stack-word
branches. Replacing the original A600C call at `0x060A7232` (`0x430B`) with NOP
is rejected by the path check (91 instead of 202 instructions in the control
case).

For every selected case, A717C builds flags `0x2FF` and the expected A600C
descriptor. The original calls yield three DMAC writes and two CHCR writes
(A600C then A6100). A5F98 receives the original R10 base and size 4 and emits
one aligned zero longword request at `0x46009000`; the harness records the CPU
request without modeling cache invalidation. The outer epilogue returns R0 as
`0x5C` and publishes the three expected words at `0x060FCD30..0x060FCD3B`.

Source identities remain Japanese `0KRNL.BIN` SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, frame
1200 state SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and
normalized WorkRAM-H SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
probe is `tools/saturn_lab/probe_japan_a717c_tail_from_boundary.py`; its hash
and each source-range hash are in the machine report and private checkpoint.

## Limits and next work

Caller registers and CHCR/DMAOR values are constructed; the register fixture
uses documented SH7604 access rules. The result does not establish natural
caller reachability, active DMA or timing, cache invalidation, hardware parity,
or gameplay meaning. Continue from the original natural callers, resolve the
associative-purge longword effect with stronger evidence, and expand to other
Japanese/USA modules. Full code and asset recovery remains open.
