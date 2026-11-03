# Japanese kernel A6C94 index-5 dispatch

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Composed original-byte execution

The dispatcher at `0x060A6C94` reads a context index from `context+40`,
multiplies it by 16, and loads the target pointer from the static table at
`0x060B2168`. For index 5, the original table word at `0x060B21B8` is
`0x060A730A`. The probe composes the dispatcher range
`[0x060A6C94, 0x060A6CB2)` with the two-instruction target
`[0x060A730A, 0x060A730E)`. It records the original indirect target, executes
the `jmp` delay slot that restores R14, and executes the target's RTS delay
instruction. The result is R0=1 and R4=context+12.

Sixteen constructed R5/context-seed cases were each executed twice. The
paired private reports in `execution-111` are byte-identical at SHA-256
`541a94a3b8a240a0096dae0cf036c91b75fb9dcb4d356eccc3ab86272873664d`; the
ordered result digest is
`f159409a1963855fde494828459dd6c5eb8d2b32a7a2d7cacd4297c523621b6f`. The
composed code, original 96-byte table and table-pointer literal hashes are
`5d1972fda1ae931fb095f422fd4a65597130a8108e5360bb6a22d35e78e0698f`,
`b702b1ecab6c76bb6e29d7a294423f5d1ad56cddb40f9818bffbbecdc7354c79`, and
`1f2447a932e23b693cf88a56c0238741a3cb0707055d1ff561b73e8556a995d1`. The
probe hash is
`d548a03e822e9b8e2e31fb6e90292a4e11c93f9b54574588c8ce49cdf74fbdcd`.

Changing the table target to `0x060A730C` is rejected when execution falls
through the handler's delay instruction and tries to fetch `0x060A730E`
outside the composition fence.

This proves the original CPU path for a constructed index-5 context and the
static image table bytes. The mapped table's byte residency in saved frame
1200 is separately recorded; natural caller inputs, table lifetime, indexes
0, 3 and 4, callback side effects and gameplay remain unverified.
