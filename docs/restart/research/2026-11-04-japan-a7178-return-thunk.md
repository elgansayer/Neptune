# Japanese kernel A7178 constant-return thunk

The Japanese kernel bytes at `[0x060A7178,0x060A717C)` are `RTS` followed by
the delay-slot instruction `MOV #1,R0`. The unchanged kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; the
four-byte function slice hashes to
`2a24aa75a569310694f29f5b7bce9df48f87cf6bfea96524639fe945839d5a58`. The
source bytes were also checked against the frame-1200 normalized WorkRAM-H
image, which remains private. Static A70B8-area disassembly contains two
branches to this thunk, at `0x060A72AE` and `0x060A72DC`.

## Original-byte execution

The pinned SH-2 interpreter executed the two original instructions for all 16
interrupt-priority values and two register seeds. Each of the 32 cases ran
twice, returned 1, preserved the other GPRs, SP, PR and SR, and performed no
data reads or writes. The only reads were the two instruction fetches. A
separate delay-slot mutation changed `MOV #1,R0` to `MOV #0,R0` and returned 0
in both control runs.

The paired private reports are in `execution-150`; they are byte-identical at
SHA-256 `28c4aa86032e24ae35f9e1b927f39f30a1c6f9efa0ea28a3ddae7ed61fa779c6`.
Their result digest is
`8edd7df25592e71750e99070fbcc731d6cc14c0e12c7547ecae216ba3fe669cc`; the
probe SHA-256 is
`1f385f307744a5e84afdb4d43c1363dcc4e9700b267845538ed378da24526827`.

This establishes only the thunk's bounded constant-return behavior. It does
not establish either branch's natural runtime use, the larger A717C routine,
remaining kernel/module behavior, or complete asset extraction. Continue
through the actual A7178 callers and A717C's call graph.
