# Japan AB94 captured-context continuation

The pinned SH-2 decoder produced a full linear window from the captured resume
target through the return edge. The scheduler body begins at `0x0600AB94`, calls
AB30 at `0x0600ABF0` and `0x0600AC78`, jumps indirectly to A186 at `0x0600ACE4`,
and returns at `0x0600AD5C`. The adjacent `0x0600AD60..0x0600AD78` poll helper is
separate: it checks a VBR-selected ready word and branches to ACE8 when set.
This is a linear disassembly plus observed branch/call evidence; it does not by
itself establish a complete CFG or natural resume path.

The probe starts from captured frame-1200 WorkRAM-H and the saved 48-byte
context at `0x060BDD7C`: R8-R15, PR, MACH and MACL come from that context. R0-R7
and VBR are explicitly constructed because the saved frame does not contain
them. Each run executes original AB94, its original AB30 call, and A186's
restore body. A186 restores the selected live task context at `0x060BCF0C` and
resumes at `0x0600AD38`; the probe checks R8-R15, PR, MACH and MACL against the
selected frame, then stops before the `0x0600AD5C` return instruction. It covers
VBR slots 0 and 1 with two R1-R7 seeds per slot. The full path takes 459
instructions for slot 0 and 428 for slot 1; paired seeds agree on each path
and memory effects. The mutated ABCC comparison is rejected by its different
path/effects.

Private full linear disassembly:
`analysis/japan-ab94-full-linear-disassembly.txt` (SHA-256
`2aa132ac887fbd15f9e0dc7bc1112edb4960f154e28cbfdc312d8f38be9433b2`).
Private original-byte report:
`execution-268/japan-ab94-context-resume.json` (SHA-256
`865280790ebac2258d350510e8b12f9b076ae2862213acf7367c5d290cd8675b`, mode
0600).

Failed strict-harness attempts 261–263 are retained unchanged. They exposed the
AB30 literal at AD7C, its read of BDDAC, and AB94's write to B3D54. Earlier
successful reports 264–267 are also retained. No natural caller, hardware
cache/device behavior, gameplay semantics, or full-game coverage is claimed.
Next, analyze and execute the scheduler's task-row transition from captured
state through A186 with explicit row/context boundaries, then proceed into
further original functions and the remaining game modules/assets. The overall
recovery programme remains ongoing.
