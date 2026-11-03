# Japanese kernel dispatch target null return

This result uses the original Japanese kernel `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution: target index 3

The static A6C94 table assigns index 3 to `0x060A70B8`. The target's
`R4==0` branch executes only `[0x060A70B8, 0x060A70C6)` and its epilogue
`[0x060A7144, 0x060A714E)`. It preserves incoming R0, restores R13/R14/PR and
SP, performs only the expected stack transactions, and leaves SR.T set by the
original `tst`. Inverting the branch at `0x060A70C4` is rejected when it tries
to fetch `0x060A70C6` beyond the path fence.

Paired private reports in `execution-108` each contain 16 combinations of
eight R0 boundary values and two stack seeds, each executed twice. Both
reports have SHA-256
`099f2f6d17df4f7185e38beb606cd4d3058ef4cfe22f93f7723373a1d8ebee27`; the
ordered result digest is
`56b39de5d45a68b1483e9310a8948b7ddd8da7e0292fb606ebd0768c47157ec1`. The
executed ranges hash to
`23fdf213f389400e6a852240e6a87678e505c123b1e6f630dbf890f256d9e041` and the
probe hash is
`d60a43d5b24a13eaa88e5899be394b263571992b8ceb4320beb7dec09f318485`.

This directly executes the null-input target branch; it does not execute the
A6C94 indirect dispatcher, the non-null target path, callbacks, or SCSP/SCU
device behavior. The original table bytes are resident at the candidate
mapping in the saved frame-1200 byte-matching range, but that does not prove
runtime dispatch or table lifetime.
