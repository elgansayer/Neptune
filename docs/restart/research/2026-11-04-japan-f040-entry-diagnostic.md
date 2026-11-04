# Japan KRNL F040 bounded entry diagnostic

This diagnostic begins directly at original `KRNL` address `0x0600F040`, using
the frame-1200 captured Japan WorkRAM-H image. The original `0KRNL.BIN` identity,
captured state, normalized WorkRAM-H, and pinned SH-2 interpreter are checked
before execution. Every fetched instruction must match the original kernel at
its mapped address. Reads and writes are confined to the captured WorkRAM image;
the probe does not invent BIOS, device, or other memory mappings.

Two constructed GPR seeds execute 1,024 instructions each. Both follow the
same PC and read traces and the same write address/width sequence. They record
250 reads and 72 writes per run; stack write values vary with the seed. Both
stop at the declared instruction bound at `0x0609DC7C` in a repeated path through
`0x06095C24`–`0x06095C8A` and `0x0609DC2E`–`0x0609DC7A`. The captured reports
are byte-identical with SHA-256
`003ca1928f6fc8ff33f2b590b138ab0f7279b9f435e680705f940a2434202686`.

This is a bounded direct-entry diagnostic, not a natural return from the
`0x0600A20E` caller. It does not complete F040, F134, or A946, and does not
establish the repeated loop's service contract or task ownership. The resident
context and initial task-cursor word are captured; other initial registers,
stack, and VBR are constructed. No independent Saturn emulator or hardware
trace was available for this Japan address. The USA-only matched-core calltrace
allowlist and configured owners/limits remain unchanged.

The reproducible probe is
[`probe_japan_f040_entry.py`](../../../tools/saturn_lab/probe_japan_f040_entry.py).
Two private execution receipts remain on the VPS under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-320/`.
The probe SHA-256 is
`b96536ef39b4461dbde32e230f6e7c36e3ead21c6b04ffd5290fdd31361d8da6`.
The earlier prepared USA kernel probe also ran again on 4 November: all 256
cases and both mutation controls passed, producing the already accepted report
digest `12e4e02aa382172f5aa77c56534cd339ae8eb486a464f9eac082c9f98250fa6a`.
That repeat confirms reproducibility; it is not a new semantic or gameplay
claim.

Full original code and asset recovery remains open. Next work is to inspect the
F040 diagnostic's repeated branch path and obtain a caller-derived continuation
from A20E or another existing approved capability, then continue through other
kernel, gameplay, sound, DSP, and asset code.
