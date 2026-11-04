# Japanese kernel dispatch target busy return

This result uses the original Japanese kernel `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Static dispatch table evidence

At `0x060A6C94`, the kernel scales a context index by 16 and jumps through a
longword at `0x060B2168 + index*16`. The six corresponding first words in the
original file are: index 0 `0x060A8154`, 1 and 2 zero, 3 `0x060A70B8`, 4
`0x060A72D8`, and 5 `0x060A730A`. The full 96-byte table window is retained as
`analysis/japan-a6c94-static-dispatch-table.json` (file SHA-256
`da97c62b05cd70566da137f2831bf181279f6349553e89b58395aa7dfeacd9b7`). This
proves the values in the kernel image; runtime table lifetime and dispatch
reachability remain separate questions.

## Original-byte execution: target 0 busy branch

The target at `0x060A8154` is decoded in
`analysis/japan-a8154-dispatch-target.txt` (SHA-256
`351d7e2f6b9aaa8da7103216be599abfa9f2bb1a52c8a9a15a472109b549834d`). The
bounded busy path executes only `[0x060A8154, 0x060A8178)` and its epilogue
`[0x060A820C, 0x060A8218)`. With a constructed nonzero slot occupancy word,
it returns zero, makes no queue-table writes, saves/restores its stack and
callee-saved registers, and skips the success path. Inverting its condition
at `0x060A8170` is rejected when it attempts to fetch `0x060A8178` outside
the PC fence.

Paired reports in private `execution-107` contain 48 combinations of three
nonzero occupancy values and four R4/R5 values, each executed twice. Both
reports have SHA-256
`a13005b65dc9e55d0e669f2abe1cf5a7f5ed60c2d6125b2c82ef1565f93dd4a4`; the
ordered result digest is
`f85921d221aac7b464d2d9aad7af2168891224624b4c32da4d3225919a21a975`.
The concatenated executed ranges hash to
`d0fa848abc14e20030341b6fbb6135187636749ef9aeb28684a8cbf81692a969`; the
literal hash is
`a704d7fcb6f6183f3b9e54400622e34d690f8d5c72512dbcf693115f3cc5a4b5` and
the probe hash is
`0f7bd77954cc57798b388c03bca10859acb817541e0bd0e4d1408e921f4dc816`.

This is a constructed busy-slot path, not an execution of the A6C94 indirect
dispatch or the target's success path. Its synthetic global/table state does
not prove natural queue occupancy or lifetime. Other dispatch targets,
callbacks, services, device timing and gameplay remain unverified.
