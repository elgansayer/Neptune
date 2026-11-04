# Japan F040 loop register snapshots

This follow-up adds selected GPR and special-register snapshots to the bounded
F040 diagnostic. It uses the same frame-1200 capture, direct F040 entry,
constructed registers, source-matching fetch fence, WorkRAM-only data fence,
and 1,024-instruction limit as the [initial result](2026-11-04-japan-f040-entry-diagnostic.md).

Two fresh processes produced byte-identical reports with SHA-256
`49ee070030e41c6ab8d4f8a906aac84993a996a1db1432b2cb423ecc091a2a6f`.
Both runs have identical PC/read traces and write address/width shapes. The
snapshots record four entries to `0x06095C24` at instruction counts 105, 336,
569, and 800. Each call visits `0x06095C60` while R4 decreases from `0x1F` by
two per visit and R5 advances through powers of four. These are original
register values, not a semantic label for the routine.

The fourth helper call returns; the caller resumes at `0x0609DC74` and the
budget stops before executing `0x0609DC7C`. The outer F040/F134 path remains
unfinished. The trace does not establish the helper's purpose, a natural A20E
caller, task ownership, or service/device behavior. The exact probe hash is
`6a1820a74a5637ae53028e914357a1dfaa49f22a0c3321ee7f39d2e46756c57e`.
Private paired reports remain under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-322/`.

Next, trace the original 09DC caller inputs across more of its continuation,
then connect F040 to a caller-derived A20E state if the saved task context
supports it. Other gameplay, module, sound, DSP, and asset recovery remains
open.
