# Japanese kernel A5FC4 DMA operation register helper

The original Japanese kernel helper at `0x060A5FC4` was executed through its
`RTS` delay slot at `0x060A600A`. The original bytes in
`[0x060A5FC4,0x060A600C)` hash to
`be24080b1b044185a14caedc18fd85ef9c21b6b04d0bdbc43e59bc6978e2d2df`.
Frame-1200 WorkRAM-H contains the same bytes. Execution used the pinned SH-2
interpreter and an explicit fixture for SH7604 DMAOR at `0xFFFFFFB0`.

The decoded helper tests descriptor mask bits 0, 3, 1 and 2. It conditionally
clears DMAOR.PR and updates DME from descriptor words 0 and 4; the bits 2 and 1
conditions clear AE and NMIF. It always reads DMAOR in the first branch's delay
slot and writes the result in the `RTS` delay slot. The [SH7604 Hardware Manual,
§9.2.7](https://antime.kapsi.fi/sega/files/sh7604.pdf#page=258) identifies DMAOR
as a 32-bit register at `0xFFFFFFB0`, with PR/DME controls and AE/NMIF flags that
are cleared by writing zero. The fixture implements these access semantics; it
does not run the DMA engine.

The probe ran 16,384 input combinations twice each, covering all 16 descriptor
flag values, DMAOR low-nibble values 0–15, and descriptor values 0, 1, 2, 4, 8,
3, 12 and 15 for each value word. Every run checks the exact PC path, all data
accesses, one DMAOR write, preservation of unrelated registers and the
write-zero-to-clear result. Reports `execution-159/report-b.json` and
`report-c.json` are byte-identical at 11,215,541 bytes and SHA-256
`631c0ae9566ccd84a4dd8dae7758a6ebfcfff5e98616658314212cf7224dc33a`. Their
result digest is `0a56db64167e8c28c44f34fd3b565e02993b03a41041a9f620cf6d69829f2ea2`;
the probe digest is
`0d37cbe63933b9262d6975e5623a4caddeb827e4b23b705b4ca64ad6cba95849`. Private
reports are retained under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/`.

This executes original CPU bytes against constructed descriptors and DMAOR
values. It does not establish natural register values, transfer timing or
natural A5FC4 reachability. The oversized interrupted first attempt is retained
as an empty non-result (`execution-159/report-a.json`); it is not counted as
execution evidence. Next, compose A717C through both A6112 and A5FC4, then
continue its alternate branches and other kernel helpers. Full code and asset
recovery remains open.
