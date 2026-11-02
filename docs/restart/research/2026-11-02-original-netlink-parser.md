# Original NetLink queue parsing, dispatch and flag returns

Issue [#609](https://github.com/elgansayer/Neptune-Bomberman/issues/609), under
#483/#488/#480/#464. Two original runs pass13,690 constructed cases:9,979 transfers
through the original eight-entry table, plus3,711 complete paths returning through
the three flag handlers. Complete reports match, SHA256
`2a635184870c677e6a1dd5803ecbfc2d5b34edd03c8cc683f9cfde7d8bba7dc2`.
[Derived receipt](../evidence/2026-11-02-original-netlink-parser.json).
This is isolated CPU evidence; the other five target handlers are explicitly
unexecuted beyond the transfer. Natural sound/protocol/device/timing remains open.

## Original identity and exact queue behavior

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`,23,920bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, separate NetLink driver lifetime. Full source hash/
length is checked before execution. Executed queue/table range `[241A,24D2)` and
flag-return extensions through24EA remain original and are hashed in the receipt.
Other drivers/regions and naturally loaded state remain separate/unvalidated.

Given base A6, the routine reads the byte index at base+1842, increments it modulo
256, and selects the four-byte input at base+1A00+4*old_index. It reads another
byte cursor at base+1841. These differ from the recovered writer's1840 index.
There is no empty-queue guard in this entry itself; caller readiness is separate.

When bit6 of byte4E1 is set, it formats output in the256-byte base+1F00 area:

```text
status = 0x80 | ((input[0] << 4) & 255) | (input[1] & 15)
output: status, input[2], and input[3] unless 0xC0 <= status < 0xE0
```

Each output byte uses the current cursor and byte-wrap increment; the updated
cursor is stored at base+1841. Bit7 alone does not enable formatting. The2-byte
classes and3-byte classes, including wrap from255 to0, are tested. When bit6 is
clear no output byte or output cursor changes. Input consumption still occurs.
No natural protocol identity, external transmission or sound is asserted here.

The original then decodes fields and writes three big-endian halfwords:

| RAM location | Written value |
| --- | --- |
| base+1800 | `(input[1] & 0xE0) << 4` |
| base+180A | `input[1] << 4` |
| base+1802 | `input[1] & 31` |

The1800 halfword is read back during the180A addition. A1 points at input+3
(the fourth read does not postincrement); A2 is the output-area base. D0 becomes
`4*(input[0]&7)`. D1.low16 is input[1]&31, preserving its initial upper16 bits.
D2.low16 is `((input[1]<<4)&0xFF00) | input[2]`; its initial upper16 bits remain.
The third-byte move does **not** clear that intermediate high byte. D3.low8 is
input[3], preserving its other bits; D4 is the final byte cursor. Other initialized
registers stay unchanged in this prefix. Final prefix CCR is Z for selector0,
otherwise zero; the last word shift clears X/C for this0..7 selector range.

All input/index/cursor/flag/field/output transactions, execution PCs and visible
registers are compared with an independent scalar/byte contract. Six explicit
data regions contain the scratch/index bytes, selected4-byte input, gate byte,
256-byte output, flag417 and outer return slot. Every unaffected byte and the
entire original code buffer are compared unchanged. No device memory exists.

## Original target table and completed branches

The JMP at24AE selects the four-byte table entry24B2+4*selector; that original
entry JMPs to these actual observed destinations:

| Selector | Target | This slice's validation boundary |
| --- | --- | --- |
|0|3248|stop before handler|
|1|2BFC|stop before handler|
|2|24D2|BSET bit2 at417; RTS fully executed|
|3|24EA|stop before nested dispatcher|
|4|1762|stop before handler|
|5|24DA|BSET bit3 at417; RTS fully executed|
|6|2B08|stop before handler|
|7|24E2|BSET bit4 at417; RTS fully executed|

Every target is exercised as a transfer; the three complete returning paths are
additional cases. Their read/modify/write of byte417, old-bit-dependent Z, outer
return-slot read, SP+=4 and final sentinel are checked. Setting an already-set bit
remains distinct from setting a clear bit in the CCR comparison. Prefix-only rows
explicitly state that an unmodeled handler was not executed. No full parser or
whole-driver completion is inferred from those stops.

## Actual cases, controls and limits

The declared products cover every raw first byte0..255, every second byte for
each selector/gate class, every input/output index through declared permutations,
every gate byte for selected groups, and four payload/SR/base/flag variants.
The suite contains9,979 unique prefix cases plus3,711 returning-path cases; it is
not the Cartesian space of every byte, RAM, register or runtime state. All cases
use fresh reset/initialized CPU state and controlled data, not captured gameplay.

| Altered original instruction | Rejected /64 cases |
| --- | --- |
| remove input-index increment |64|
| use bit7 instead of bit6 gating |32|
| change2-byte threshold C0 to B0 |4|
| narrow selector mask7 to3 |32|
| change flag-handler bit2 to1 |4|

Changes fail actual registers, bytes or target/PC guards. Unchanged-result cases
are retained. Mutations alter private copies, never accepted original sources.
All five controls reject meaningfully wrong behavior; no independent CPU/hardware
oracle is claimed.

Source execution head a00eb485b5e9531c97156684a1e575a4a5e0ef94, intake base
64a7429a47f9e40e236789fb5047a5b0a080e9ec. Full reports are private at
`/home/dev/neptune-research-private/609/nlsnd-parser-001/`; scripts/supervision/logs
at `/home/dev/neptune-evidence/code609-20261102/`. They reuse unchanged accepted
ABI1 binary cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c,
with96 instructions/call and existing256/128 layout limits. Both reports completed
within60-second command bounds, about11seconds total, under existing shared
host admission at observed limit3 unchanged. Own leases released; originals and
prepared artifacts read-only, broker hidden. No new provider job, compiler/core,
scheduler, allowance or paid fallback. Preserve coordinator#597/#608 and Gemini
#487; account/CI spend unknown. Six new synthetic tests and all203 input tests
pass. Original execution and current-base exact-head CI remain separate evidence.

After existing admission, repeat with two fresh reports and compare them:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_parser.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/609/NEW-parser-run1.json
python3 tools/saturn_lab/check.py
```

## Remaining original parser/device scope

Targets3248/2BFC/24EA/1762/2B08 and their full state/device behavior remain open.
Selected source also identifies the caller's queue guard and a later output
boundary: main-loop10B2 tests gate60, pending cursors1843/1841, then bit4 at
A5+404 before writing a queued byte to A5+407 and advancing1843. Reset sets
A5=100000. The pinned Beetle SCSP code provides real FIFO/status/interrupt effects
for those addresses, whereas the installed saturn-recomp SCSP implementation
explicitly lacks MIDI. A subsequent experiment must use an actual bounded FIFO
component/model and preserve IRQ effects rather than map those registers as RAM.
This is a source lead only, not an executed device result. Natural timing/audio,
all other modules/regions, and whole-program/function/dynamic-target denominators
remain open. Continue the full programme after this slice.
