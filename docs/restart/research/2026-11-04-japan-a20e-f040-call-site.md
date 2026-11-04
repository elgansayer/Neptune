# Japan KRNL F040 caller decode note (A20E call site)

This note records the static decode of the original Japan kernel `KRNL` around
the `0x0600A20E`/`0x0600A210` pair that reaches `0x0600F040`. It is a
documentation-only record. No tool, test, or probe is changed here, and no
new original bytes were extracted for it: the decode was produced and
cross-checked in #779, and this file carries that result into the research
record.

## Static decode facts

The items in this section are decode facts about original bytes. They are not
execution results.

The source is Japan T-14302G V1.000 `KRNL`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped at
`0x0600A000`. It was decoded with the pinned SaturnRecomp
`f20de940e8013fc84103a5b39c4069ed8071b1f9` `Image.disasm`, 32 instructions from
`0x0600A1F0`. The listing SHA-256 is
`083d388e5c5ef70477b68cb36892bfb4f26e27fa04ae28ac523a9cf5c2acf659`, and two
independent derivations are byte-identical (#779).

The decoded listing shows:

- `0x0600A204` `jsr @r3` → `0x0600ADE6`; its delay slot `0x0600A206` is
  `mov.l @r11,r4`, with r11 = `0x060BCC80` (loaded at `0x0600A1F4`).
- `0x0600A20A` `jsr @r2` → `0x0600AE3A` (r2 loaded at `0x0600A208`); its
  delay slot `0x0600A20C` is `mov.l @r11,r4`.
- `0x0600A20E` `mov.l 0x0600A2D0,r3` loads `0x0600F040`.
- `0x0600A210` `jsr @r3` → `0x0600F040`; its delay slot `0x0600A212` is `nop`.
- `0x0600A214` `bra 0x0600A24A`.
- No R4–R7 write occurs between AE3A's return and the F040 call.

## Hypotheses

The items in this section are inferences from the decode facts above. They are
not established results.

F040 receives R4–R7 as left by AE3A (caller-scratch under the Hitachi SH ABI), so a natural F040 entry state should come from the AE3A return state in the same instance.

This is a static decode, not an execution trace. It does not name the purpose
of F040 or AE3A, and it does not establish gameplay behaviour.

## Relation to the existing F040 results

The [bounded entry diagnostic](2026-11-04-japan-f040-entry-diagnostic.md)
begins directly at `0x0600F040` with constructed registers and already records
that it is not a natural return from the `0x0600A20E` caller. The
[8,192-instruction continuation](2026-11-04-japan-f040-8192-continuation.md)
extends that same direct entry and stops during the 36th helper call. The
decode facts above locate the caller-side instructions that a natural
continuation would have to pass through, and they show why a direct entry
cannot supply the caller-derived register state.

## Next steps

Continue the original code-first programme: obtain an AE3A return state in one
CPU and memory instance and enter `0x0600F040` from that state, then compare
the resulting register and trace shapes against the direct-entry results. The
purpose of `0x0600F040` and `0x0600AE3A`, the remaining kernel and game module
code, gameplay, sound/DSP code, and all assets remain open.
