# Japanese kernel A72B0 → A717C caller path

This result executes the original Japanese kernel at `0x060A72B0`, through its
real `BSR` at `0x060A72CC`, into the A717C zero-shift branch, and back through
the A72B0 epilogue. The private original kernel has SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`. The
executed source range `[0x060A72B0,0x060A72D8)` hashes to
`a637961468ed48e8f5fb90ed65709bdd162dec7e8d5e8398e3b24ebaa74361a0`; A717C
source bytes and the frame-1200 WorkRAM-H mapping were also checked against
that original and captured state.

## Caller contract observed

A72B0 sets R4 to zero before saving its local argument frame. It forwards the
fifth stack argument from its entry frame to A717C, along with the saved caller
register arguments. For stack values 0–3, A717C shifts the value right by two,
skips the unresolved A6112 call, writes `argument & 3`, A72B0's incoming R6,
and zero to `0x060FCD30`, `+4`, and `+8`, then returns `0x5C`. The composed
path executes 69 original SH-2 instructions with 18 observed data reads and 20
observed writes per case. PC fetches are fenced to the exact caller, callee,
and return-delay-slot path. A6112 and the remaining A717C helper calls remain
unexecuted and unresolved.

Two independent runs each executed 4,096 cases twice. The corpus spans all four
stack argument values, two initial R4 values, two values each for incoming R5,
R6, R7, and the sixth stack word, all 16 interrupt priorities, and two register
seeds. The paired private reports in `execution-156/report-m.json` and
`report-m2.json` are byte-identical with SHA-256
`6c4f4bf1d44b382a6ad4d6a2606f0274b85ff61b267cce020db06bcc24ee5575`. Their
result digest is
`1846ff4d3b9925c04ec345948dcc44bc07d152fae09d99f47a305eb8d8983b4c`, the
probe digest is
`614ebf0442bfbd025718165cd4e6f06dd59694254b1f81c598439c4cd67a1681`, and
the pinned interpreter revision is `f20de940e8013fc84103a5b39c4069ed8071b1f9`.

Development attempts `report-a` through `report-l` are retained beside the
successful reports; they exposed harness errors and stricter-than-needed PC,
stack, or event-count assumptions and are not counted as original execution
evidence. The final pair completed with the stated guards and exact path.

This is constructed-input caller evidence from a captured state, not proof that
A72B0 was reached by natural gameplay. A717C's nonzero-shift route, BIOS and
on-chip register behavior, other kernel/module code, and full asset extraction
remain open. The all-original-code programme remains active and incomplete.
