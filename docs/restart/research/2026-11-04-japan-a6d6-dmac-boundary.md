# Japan A6D6 DMAC boundary

The probe executes original Japan `0KRNL.BIN` at `0x0600A6D6` with a constructed
entry and strict SH7604 register handling. It reaches the RTS delay slot after
50 SH-2 steps and 14 reads/writes to listed registers. Two runs with different
seeded registers produce identical instruction and device-register traces.

The manual identifies `0xFFFFFE71/72` as byte-wide DRCR0/DRCR1 and `0xFFFFFFB0`
as the longword DMAOR register. It specifies byte accesses for DRCR and longword
accesses for other DMAC registers. `0xFFFFFFB8` is not listed in the manual's
on-chip register map. The probe stops when the original RTS delay slot attempts
a longword write there; it does not treat that address as RAM or claim a
hardware bus fault. [SH7604 Hardware Manual](https://antime.kapsi.fi/sega/files/sh7604.pdf).

The reproducible paired report is retained privately at
`execution-236/japan-a6d6-run-pair.json` (SHA-256
`398fec803a114b209696a58aeab0f6aa1730b5704b8e78b7c4eff5507a803c67`). The
initial incomplete register model is retained at `execution-234/` and was
superseded after it stopped at the first channel-1 register write. The
independent preliminary pair at `execution-235/` also stopped at the same
address, before the reusable repository probe was added.

This direct entry does not establish a natural A546 caller, DMA engine effects,
video/audio output, timing, or whole-game behavior. The reason for the final
`0xFFFFFFB8` write remains unresolved and needs an original runtime trace or a
Saturn-specific register map before modeling further execution.
