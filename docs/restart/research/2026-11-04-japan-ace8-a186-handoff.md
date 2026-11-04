# Japan ACE8 to A186 captured-context handoff

This follow-up extends the ACE8 prefix through the original A186 restore body.
Four runs execute the 64-instruction ACE8/A164 prefix and stop at A186; four
more execute the same prefix plus A186's 18 instructions. Each run uses a
constructed VBR-selected task row (3 or 12) and register seed. A164 saves the
pre-call register frame into that row. A186 then reads the 48-byte context at
`060BDD7C` from the captured frame-1200 WorkRAM-H state and transfers to the
context PR `0600AB94`.

At the boundary, R8-R15, PR, MACH and MACL match the captured context; the RTS
delay slot places incoming R5 (one) into R0. The restored R15 is `060BD8F4`.
The resume PC is checked against the original kernel bytes, but `0600AB94` is
not executed. The VBR-selected ready words remain unchanged because A186
transfers away from ACE8 before its post-restore ready-word clear. This
concretely narrows the earlier static return-through-epilogue interpretation
for this captured context.

The private paired report is
`execution-256/japan-ace8-a186-handoff.json` (SHA-256
`2ec4a5c806fc9bba88b0c34cc45835d252797d8f18cd891809709338ad9435ef`). It
records eight original-byte runs and two instruction
mutation controls: the A164 first-store change and an A186 PR-load change.
Earlier failed attempts remain private in execution-253 through execution-254;
execution-255 is the successful report before explicit run-count fields were
added.

The caller's task row/VBR/register inputs are constructed. The restore payload
comes from a captured original emulator state, but this does not prove that
the full chain naturally reached ACE8 or that AB94 is a natural runtime resume.
No hardware cache effects, scheduler timing, gameplay, or whole-game recovery is
claimed.
