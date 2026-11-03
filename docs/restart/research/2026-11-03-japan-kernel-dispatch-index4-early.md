# Japanese kernel A6C94 index-4 early return

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Composed original-byte execution

The dispatcher at `0x060A6C94` reads the index from `context+40` and dispatches
index 4 through the original table word at `0x060B21A8`, which points to
`0x060A72D8`. This path takes A72D8's branch delay assignment `R4=0`, enters
A727E, calls A6142 through the original literal at `0x060A7368`, and reads a
constructed zero word at `0xFFFFFF8C`. A6142 returns zero; A727E returns one
through its RTS delay instruction. Stack writes/reads and the 36 executed
instructions are checked exactly by the probe.

Sixteen constructed R5/context-seed cases ran twice. The paired private reports
in `execution-118` are byte-identical at SHA-256
`a8a731a871349037a27c93a7cf27921c2354e0f917c0900d7ec2226d474cca75`; their
ordered result digest is
`9a97afd0f9f221973e43c2b382793c30ea29fe6907bc3c612e6eb5ee526f164e`. The
composed code and original table hashes are
`08b3b77e4daca6dc95ead087c0645416034171ce61dc6a50fb7b0ba9adbe14a8` and
`b702b1ecab6c76bb6e29d7a294423f5d1ad56cddb40f9818bffbbecdc7354c79`. The
probe hash is `b10b6f503c6e1092393eb2a413da0fc3b9530a631005193aaf1199d796a179d7`.

Changing the index-4 table entry to `0x060A72DC` is rejected at the PC fence;
that alternate A7178 route remains unexecuted.

The zero at `0xFFFFFF8C` is constructed input for A6142, not evidence about a
natural global's value or the caller's eligibility logic. The A7178 branch,
other A727E branch, natural context, device effects, and gameplay remain open.
