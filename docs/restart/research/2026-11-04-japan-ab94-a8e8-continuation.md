# Japan AB94 row state 2 through original A8E8

The constructed AB94 row0/+80=2 case reaches PC A8E8 with captured caller
registers, PR, MACH, MACL, SR and VBR. Its separate continuation replays the
bounded A208 prefix write list and AB94 write list into a new CPU/memory
instance, then executes the resident original A8E8 caller and its original A80E
callee. The entry state is not a same-instance handoff; R6/R7 remain seeded.

The run executes 221 instructions, calls A80E once, does not enter AACC,
decrements the captured global count from 5 to 4, restores SP and PR, and stops
before ACE8. The task table changes from SHA-256
`b15d67dc19884ffcf23b9147fc3c2c15f93cfe1c19bd821a958174631978a369` to
`53c58f6350b0bcaf4c43e60c9c13936d2ba4b4b2de82ccd108f091aeff754c66`. Two
independent reports (execution 306) are byte-identical, SHA-256
`0c94a935f193e72ce9cd3da2a50c624e8633eac673e7b0620dc978514d6f84a8`, mode
0600. Probe SHA-256 is
`5a226bde08f853d34f2a3b61bab5a6895c33f798c7b57fa37bf8c3473ebd97b0`.
The initial 64-byte stack fence failure is retained in execution 305; execution
306 uses the declared 256-byte prefix stack window.

This demonstrates the selected original A8E8/A80E path under replayed,
constructed row state. ACE8's scheduler body, natural row selection, same-instance
continuity, hardware effects/timing, gameplay, remaining modules and assets stay
open. Next continue from ACE8 using validated caller state, then proceed across
further functions and modules.

## Follow-up execution 307: special-register boundary receipt

A follow-up pair reran the same bounded A8E8 continuation with MACH, MACL and
SR added to the exit receipt. Both private reports are byte-identical at
SHA-256 `0f249715d694ac5fdb34873439a81f7b72eb0beb449e3a8b53f70d597de01bc6`.
The updated probe SHA-256 is
`03a157dbb0ef657b227e0c765aa3dccc7c0c4326e68cf94f72daddd5c17f5ecf`.
At ACE8 the saved exit state is MACH `0x10203040`, MACL `0`, SR `0xF0`,
PR `0x0600A8E8`; the previous instruction, call-count, table and SP/PR results
remain the same. This receipt improves the reproducibility of a later separate
ACE8 continuation; it does not turn the replayed entry into a same-instance
handoff.

## Follow-up execution 308: ACE8 task-save and restore edge

The existing ACE8 task-save probe was run against the original Japan kernel
and verified frame-1200 state checkpoint. It performs 12 original-byte
executions in each report: four ACE8/A164 task-save prefixes, four A186 restore
handoffs, and four composed AD60→ACE8→A164→A186 handoffs across both VBR slots
and two seeds. The first group stops at A186; composed cases restore the
captured frame and stop at PR `0x0600AB94`, before executing AB94. The paired
private reports are byte-identical, SHA-256
`e56b691ced85e77c8128c220e3f87a22a57ae3024959b68cf0de7c19b9380d1b`; probe
SHA-256 `254423d67be359452b1efe62c893682f5846390b04585673d091c7989b3ad181`.
The original kernel, emulator checkpoint and normalized WorkRAM hashes are
recorded in the report. Mutation controls reject altered A164 and A186
instructions. These are constructed ready words, rows, VBR-selected pointers
and registers; natural ready-word provenance and scheduling are not established.

The initial invocation used the broad research index in place of the
frame-1200 emulator checkpoint and correctly rejected the identity. That
failure is retained as execution-308's first report. The corrected invocation
used `continuation-002/boot-002-next-600frames/checkpoint.json`; no checkpoint
identity check was weakened. ACE8's caller-state integration, same-instance
continuity from AB94, and remaining kernel/module code stay open.
