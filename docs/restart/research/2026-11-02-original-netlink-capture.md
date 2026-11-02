# Original NetLink command capture and raw forwarding

Issue [#617](https://github.com/elgansayer/Neptune-Bomberman/issues/617), under
#483/#488/#480/#464. Original130E/1326 passes **7,522 constructed cases twice**.
The complete reports are byte-identical, SHA256
`76f1110702835bd30fee234ce039e3362be127eee8fe10253ad70081b0341353`.
There are1,536 complete empty scans,704 complete unready returns and5,282 active
capture prefixes stopping before JSR17F2 at139A. No active command handler is
claimed complete. [Derived evidence](../evidence/2026-11-02-original-netlink-capture.json).

## Original source and recovered contract

USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN`,23,920 bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 mapping0 candidate, NetLink driver lifetime. Whole-source verification
precedes execution. Original positive instruction bytes remain unchanged.
This CPU-only experiment uses the accepted ABI1 Musashi generation from#600.
No SCSP/device address is mapped.

At130E, read4E1. If bit7 is clear, branch directly to1326. If set, read4E0;
return immediately when its bit7 is clear. Otherwise JSR1326, then clear bit7
of4E0 after the helper returns. The nested call really pushes131E and keeps it
separate from the caller sentinel; it is not simulated with a substituted call.

At1326, D0.low16 becomes0700 and A0 takes that word address. The original reads
the first byte of each16-byte slot at0700,0710,...0770. A zero first byte skips
the capture. Empty scans exit after incrementing D0.low8 from70 to80, with
D0.low16=0780, A0=0770, and the tested N/V flag result from that final byte add.
All eight input reads and both return paths are checked.

For the first nonzero slot at address s:

1. Set A0=s+2 and save s to the word at A6+1834. Save D0/A1 with original MOVEM.
2. Read the word at A6+183A and mask it with07F0. Destination is0800+masked,
   a16-byte record selected from128 slots.
3. Copy14 original bytes: the header word at s, then three longwords from s+2,
   s+6 and s+10. Store the word from A6+1838 in destination+14, then clear that
   source timestamp word. The log's last two bytes are the timestamp.
4. Store masked+10hex into both A6+183A and absolute word041A. The value may be
  0800 at the last record; the next capture masks it back to slot0. Word041A
   is sound RAM in this mapping, not an SCSP register.
5. Test bit5 of4E1 via two actual byte doublings. If set, copy **16 original
   bytes from s** to the circular byte buffer A6+1F00, starting at the byte
   cursor A6+1841 and wrapping modulo256. These raw bytes include original
   bytes14/15, **not** the timestamp substituted in the log. Advance cursor16.
6. Restore original D0/A1 and stop at139A, before the unresolved dispatcher call.

All visible D/A registers, PC, SR, stack saves/returns, data addresses/widths/
values/order, executed PCs, output bytes and unaffected canaries are compared
with an independently written Python contract. MOVEM's predecrement transaction
order remains low-word then high-word per saved register. D0's initial high16
bits survive the word operations and save/restore. Forwarding changes D1/A2/A3;
without forwarding those registers retain their initial values. Final prefix CCR
comes from the gate doublings or the cursor byte store; MOVEM does not restore SR.
The all-zero output cursor case at writer240 preserves X from the last ADDQ.

Exactly eight RAM regions are declared: the two handshake bytes,128 source
bytes,8 state/canary bytes,2048 log bytes,041A word, output cursor,256 forwarding
bytes and16 stack/sentinel bytes. Other accesses fail. Complete empty/unready
cases RTS to the explicit sentinel; active cases do not execute139A or a handler.

## Scope and controls

Constructed products include all gate bytes, all command bytes, every one of
eight first-active positions plus empty, every masked log slot, two high/low
noise patterns outside07F0, all forwarding cursor bytes, two handshake bit7
states and two base/SR/timestamp variants. This is a union of bounded products,
not every RAM/register combination. Nonzero active commands stop before dispatch;
later input slots are not processed in those cases. Natural command meaning,
full active scan/ack clearing and downstream handlers remain unresolved.

Observed paths use5..119 instructions and3..67 events, below the explicit128-step
request and accepted ABI1 capacities256/128. The five altered-original controls
are separate byte copies, with their hashes retained:

| Altered instruction | Rejected /32 |
| --- | --- |
| handshake BPL changed to BEQ |8|
| ring mask07F0 changed to03F0 |24|
| ring increment16 changed to8 |24|
| remove timestamp clear |24|
| forward15 instead of16 bytes |12|

The probe runs in guarded jobs with source/original/prepared inputs read-only
and broker authority hidden. Actual shared host limit3 and180-second own leases
are unchanged; leases were released. Per-original-command timeout60seconds,
nice10. No provider call, scheduler, paid fallback, allowance reset or continuity
activation. Other VPS/Gemini owners stay untouched; account/CI spend is unknown.
Seven new owned tests cover fixed examples and failure custody; they are separate
from the real original-code reports.

Original execution head `2b8405d72c4cc3a08f6dafaad7c0092a36c742f4`.
Private reports `/home/dev/neptune-research-private/617/nlsnd-capture-001/`.
Supervisors `/home/dev/neptune-evidence/code617-20261102/`.
Prepared tool `.factory-tools/code600-001/prepared`, binary SHA256
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.
No new native generation or preparation is needed for this CPU-only slice.

## Reproduction and next code

After existing admission and read-only mounting, use fresh report paths:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_capture.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/617/NEW-run1.json
python3 tools/saturn_lab/check.py
```

Continue actual17F2 command classification and its indexed JSR targets, then
the139E slot-clear/rescan path. Selected static code already exposes separate
low/high command classes and table entries with varying instruction widths;
do not assume every four-byte dispatch landing is a valid function. Record
unsupported targets explicitly, including the earlier183E/184A leads. Device
handlers need real side effects, never flat SCSP RAM. Preserve the original
source identity and all natural runtime/timing unknowns. Further kernel/slave/
overlay/common sound/DSP/save/network/Japan code and whole-program denominators
remain open; this bounded result does not complete the programme.
