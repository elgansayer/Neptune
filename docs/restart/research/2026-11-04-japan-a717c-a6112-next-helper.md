# Japanese kernel A717C → A6112 → A5FC4 boundary

The original Japanese kernel bytes at A717C and A6112 were composed from the
frame-1200 WorkRAM-H snapshot. For constructed A717C stack argument 4, original
A717C calls A6112 for channel 0 or 1. With a modeled SH7604 CHCR contract,
A6112 clears DE and returns; A717C then prepares its helper argument block and
calls A5FC4. Execution stops at the A5FC4 entry before executing that helper.

The probe completed 8,192 constructed input combinations twice each: both
channels; eight CHCR values; two saved R7 values; two incoming stack words; two
R6 values; the A717C base set; all 16 interrupt priorities; and two register
seeds. Each run follows the exact original PC sequence through the A6112 return
and A5FC4 call delay slot. The bytes at `0x060A71BE` are `0x0009` (`nop`), so
the call does not push R3 and SP at the next-helper boundary is `0x06007FA4`.
The earlier failed development runs arose from assuming a push in that slot;
both reports are retained alongside the successful pair.

Reports `execution-158/report-c.json` and `report-d.json` are byte-identical,
each 7,034,303 bytes, SHA-256
`41f2c472afeba30f09eefc64885523244ece91e74d0a338cbc0422a542b53601`. Their
result digest is `751b0e6aafc844cc933276c27ef47dc3b448f7cbb407ca49c3f9c8d9a15f7e8d`;
the probe SHA-256 is
`337bb9114cac3f0b473a0106126e222c303304887322d13f21e0ff0d93117773`. The
private reports are under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/`.

This is original-byte CPU execution over constructed inputs with a CHCR
register fixture. It does not execute A5FC4 or establish DMA timing, natural
CHCR values, or natural reachability of this A717C route. Continue with the
A5FC4 caller chain and other A717C branches; the all-code and asset programme
remains active and incomplete.
