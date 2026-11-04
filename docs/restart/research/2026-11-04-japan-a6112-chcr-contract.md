# Japanese kernel A6112 and SH7604 CHCR access contract

The original Japanese kernel bytes at `0x060A6112` were executed through the
complete nine-instruction return, including the `RTS` delay slot. The source
range `[0x060A6112,0x060A6124)` hashes to
`1086b67d2921b8e6ec2155461022e9fff11c46c6de5a922ead60fd11e48cff79`; the
private original kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`.
Frame-1200 WorkRAM-H contains the same bytes at that address.

## Register contract and observed function

The pinned SH-2 decode shows A6112 calculating `R4 * 16 - 116`, reading a
longword, clearing bit 0, then writing the value back in the `RTS` delay slot.
The [Hitachi SH7604 Hardware Manual, Table 9.2 and §9.2.4](https://antime.kapsi.fi/sega/files/sh7604.pdf#page=250)
identifies the selected addresses as CHCR0 (`0xFFFFFF8C`) for R4=0 and CHCR1
(`0xFFFFFF9C`) for R4=1. These are 32-bit registers. CHCR bit 0 is DMA enable
(DE); bit 1 is transfer-end status (TE), which is cleared by writing zero.

The original function was executed for 544 constructed register states, each
twice: all 256 low-byte patterns for both channels, plus high-byte one-hot
patterns with DE both clear and set. Each trace has exactly one CHCR read and
one CHCR write and takes nine original SH-2 steps. A6112 returns the register
value with DE cleared in R4, preserves R0, and leaves TE unchanged under the
documented write-zero-to-clear contract. A mutated `MOV #-1,R3` control fails
the DE-clearing assertion for each channel.

Paired private reports are `execution-157/report-a.json` and `report-b.json`,
byte-identical at SHA-256
`3776dbccaf1c67ab1eba0e5a22b59a3e65ddb4e91ab60f383ab471edb82b8fd5`. Their
result digest is
`c0d4200187871565941a64a1b65eb4c033b90ec9a9c29b064a1c73e9887329e5`; the
probe digest is
`0f171ad0e6e3cbf419f702fd73285d9918058a68c31e77aa9008b91b20886f2d`.
The pinned interpreter revision is `f20de940e8013fc84103a5b39c4069ed8071b1f9`.

The register fixture models only CHCR value access and the documented TE
write-zero-to-clear rule. It does not run the DMA engine, emulate transfer
timing, capture natural game-time CHCR values, or establish whether A6112 was
reached naturally. A717C's subsequent A5FC4/A600C/A6100/A5F98 calls and its
nonzero-shift outcomes remain open; the whole original-code and asset-recovery
programme remains active and incomplete.
