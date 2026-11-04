# Japan AB94 constructed-state path reaches nonresident BCC80 data

This bounded follow-up starts at original `AB94` using frame-1200 WorkRAM-H,
the captured BDD7C context, and constructed R0-R7/VBR. In one SH-2 instance it
executes AB94, AB30, A186, resumes at `AD38`, executes the AD38/ACE8 epilogue,
and stops before fetching `0x060BCC80`. The captured selected-row context's
PR is `0x0600AD38`; the eventual observed target is `0x060BCC80`, which is the
captured task cursor. It is not the previously assumed `AE76` return, so the
probe treats it as a dynamic handoff boundary and does not execute there.

Two independent reports (execution 294) each contain four original-byte runs
(two VBR slots × two register seeds), all reaching the same stop after 461
instructions. Their report SHA-256 is
`40f8ded7eeb6a6cb993d8c100488fcae99d8e3b30d49e245ca48b53778792914`; both
files are mode 0600. Probe SHA-256 is
`0565326fa7ff6bd727a97ca457ee43f959131666198d43d3e7b28e817ffc8d56`.
The earlier failed AE76-boundary attempt is retained privately in execution 293.

This is an AB94-entry continuation, not a single execution composed from A208;
the A208→AB94 prefix remains separate evidence. R0-R7 and VBR are constructed,
and the run does not establish natural dispatch ownership, and the captured memory at BCC80
is not resident original code. Do not execute the kernel-file bytes as a substitute
for captured WorkRAM. Obtain caller-derived R0-R7/VBR by composing from the A208
prefix, rerun the continuation, and only then follow a validated return. Continue
through remaining kernel modules
and asset inventories. Whole-program recovery remains open.
