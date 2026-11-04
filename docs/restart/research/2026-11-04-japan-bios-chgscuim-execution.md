# Japan BIOS SYS_CHGSCUIM bounded execution

Execution 312 compared the 64-byte target at WorkRAM-H `0x060007C0` with the
original Japan BIOS bytes at file offset `0xDC0`, then ran the captured target
through the pinned SH-2 interpreter. The windows match byte-for-byte (SHA-256
`be3dc68978bc39e541d9a2fe7bb556004e282ed26b3e1e1deb96ea24b064c16f`). The
input WorkRAM image is the retained frame-1200 state, SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`.

Four constructed R4/R5 pairs exercise the signed and nonnegative low-word
paths. Each run executes the original instructions from `0x060007C0`, records
its PC trace including the RTS delay slot, and is limited to 32 instructions.
The memory fence allows only the BIOS vector word at `0x06000348` and the three
SCU IMS longwords beginning at `0x25FE00A0`. The bounded results show the
routine writes `(old_vector & R4) | R5` to both the vector word and SCU IMS,
writes the sign-extended low word of `(R4 | R5)` to IMS+4, and writes 1 to
IMS+8 when that low word is nonnegative. The input SR value `0xA1` is restored.

The private successful report is
`execution-312/japan-bios-chgscuim-corrected.json`, SHA-256
`971cdba842963ff9136aa91dd474127ddbce8b4349320ae4abee8f9ed72638f9`. The
first attempt used `0xA5`, whose reserved SR bit is not represented by the
pinned CPU model; its expected writes were already correct, but the readback
assertion failed. It remains private as `execution-312/japan-bios-chgscuim.json`
and is excluded from the successful result. The probe is
[`probe_japan_bios_chgscuim.py`](../../../tools/saturn_lab/probe_japan_bios_chgscuim.py).

These are constructed registers and MMIO backing values, not proof of a natural
caller or hardware timing. Only this captured helper is covered; the full BIOS,
bootstrap caller path, remaining modules and assets remain open. The execution
uses the pinned SH-2 interpreter and has not been cross-checked against another
emulator or hardware.
