# Japan A717C → A6112 → A5FC4 original-byte composition

## Executed path

This slice begins at original Japanese kernel entry `0x060A717C` with stack
argument `4`, follows the original call to CHCR helper A6112 at `0x060A6112`,
returns to A717C, follows its call to DMAOR helper A5FC4 at `0x060A5FC4`, and
checks the return to A717C at `0x060A71C0`. The interpreter reports 79 SH-2
instructions for each tested case, including the call and return delay slots.

The paired private reports are under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-177/`.
Each contains 7,776 distinct constructed cases, repeated twice. The reports are
byte-identical with SHA-256
`efa52d1c9920effc8a95df69b09cbfeda937cb2e79054fd7293ada1d9fef051c`; the
ordered result digest is
`48a801bedfced8c272d6c6628d23026d8baa0323303e61bc714ed48b7cef5550`.

The cases cover both CHCR channels, six CHCR values, nine DMAOR values, two
caller base values, two saved-R7 values, three entry stack words, three SR
priority fields, and two register seeds. The executed original caller builds
descriptor words `(0, 1, 15)`. A6112 clears CHCR.DE. A5FC4 applies the
descriptor-controlled DMAOR changes, including the SH7604 write-zero-to-clear
rules for AE/NMIF. Replacing the original A717C `JSR @R2` at `0x060A71A6`
(`0x420B`) with NOP is rejected: the observed path has 70 instructions instead
of the required 79.

The original Japanese kernel identity is SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; the
frame-1200 state is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and its
normalized WorkRAM-H is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
executed source-range hashes are recorded in both machine reports and the
private checkpoint. The probe is
`tools/saturn_lab/probe_japan_a717c_a5fc4_composed.py`.

## Limits and next work

The caller state and CHCR/DMAOR values are constructed. The MMIO fixture models
documented register read/write behavior; it does not run the DMA engine or prove
transfer timing, actual game-time register values, cache-purge effects, natural
caller reachability, or gameplay meaning. Execution stops at A717C's return
from A5FC4, before the subsequent A600C/DRCR/DMAC path, A5F98 purge call, and
outer A717C epilogue. Those call edges need composition and natural runtime
evidence. This does not recover the whole kernel or game.
