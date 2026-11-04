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
