# Japan A472 service-call continuation

## Original bytes and execution evidence

This continuation starts at the same constructed A324 boundary as the [A472
TVSTAT probe](2026-11-04-japan-a472-tvstat-timing.md). It executes original
Japan `0KRNL.BIN` at WorkRAM-H `0x0600A000` (786,432 bytes; SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`) from
`0x0600A324` through the complete A472 prefix and stops at `0x0600A4C4`, before
the `BSR 0x0600A638`. It also executes the captured frame-1200 WorkRAM-H service
bytes at `0x06000794–0x060007A0` (`SYS_SETUINT`) and
`0x060007C0–0x060007E4` (`SYS_CHGSCUIM`). These runtime bytes are not proven to
be BIOS-ROM copies or to have been live at the original A472 call.

The state is frame 1200, SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`; normalized
WorkRAM-H SHA-256 is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
pinned interpreter is `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`.
Two byte-identical reports in private evidence directory
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-211/`
cover 16 constructed cases, each executed twice. The cases cross four explicit
16-bit TVSTAT inputs (`0000`, `0001`, `020A`, `020B`), two initial SR inputs,
and two register seeds. Each report SHA-256 is
`d49d149a28888162a2d5b39451452e9274fa28167388279b3040d1e55d70b952`; normalized
results SHA-256 is
`df8b194df1d69e832beb4851c35329d8c3e253d54f40047e024c2106523625c4`.
The probe SHA-256 is
`7b8c9ad0cf7420d1a22dcc09291b0b3ff4792ca98eb615d63fd20f1ff3ca61f7`.

## Recovered call behavior

After the TVSTAT-dependent timing stores, A472 calls the captured
`SYS_SETUINT` vector twice. Its original runtime stub scales R4 by four and
writes the R5 pointers `0x0600A5E4` and `0x0600A5EE` to service table entries 64
and 65 at `0x06000A00` and `0x06000A04`. It then calls captured
`SYS_CHGSCUIM(-4)`. With the frame-1200 mask word `0xFFFFD77C`, that routine
preserves the word, emits write intents `0xFFFFD77C` to SCU IMS at `0x25FE00A0`
and `0xFFFFFFFC` to `0x25FE00A4`, and takes the negative branch that skips
`0x25FE00A8`.

The `SYS_SETUINT` stub tests its nonzero R5 pointer; that final TST clears SR.T.
`SYS_CHGSCUIM` saves and restores the SR around its mask update. The original
A472 tail then applies `0xFFFFFF0F` to SR, clearing the temporary interrupt mask
set earlier. A mutation of the captured setter vector is rejected by the strict
PC fence; mutation of the SCU IMS address is rejected by the MMIO allowlist.

## Limits and next range

TVSTAT and entry registers are constructed, the captured service bytes and
frame-1200 table/mask are inputs, and SCU writes are recorded intents rather
than hardware effects. No natural A324 caller, runtime service provenance,
device timing, or A638 dependency is established. Earlier incorrect attempts
remain in `execution-205` through `execution-210`: they exposed the A472 timing
read, the caller-specific `0xFFFFFFFC` SCU write, a too-small instruction
budget, the post-service SR result, and an incorrect interpreter path. The
corrected paired result is `execution-211`.

The next original range is the A638 call and its device dependencies. The
all-code and full-assets programme remains active and incomplete.
