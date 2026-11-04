# Japan ACE8 task save prefix

The original Japan ACE8 scheduler entry was executed from its entry through
its A164 context-save call. The probe stops at the A186 restore entry before
executing that restore routine. It tested both VBR-selected task pointers
(records 3 and 12), twice each, for four original-byte runs. ACE8 writes the
selected task marker and global field, and A164 stores the caller's register,
PR, MACH and MACL values into the record's 48-byte context at row offset 32.
The A164 R8 value appears at both context offsets 0 and 4. At the stop boundary
R0 is zero from A164's RTS delay slot and the ready words remain unchanged;
ACE8 has not yet returned from A186 or executed its later ready-word clear.

The private execution report is
`execution-252/japan-ace8-task-save.json` (SHA-256
`6fe819d192e741cb515c6721f44a7384eb540e7e0d3cf70d1d2b9347cb6458b0`). All
four runs stop after 64 original instructions at `0x0600A186`; each A164 frame
matches an independent snapshot of its pre-call registers. An altered first
A164 store (`0x1480` to `0x1490`) is rejected.

This is constructed scheduler state and does not prove a natural task switch.
The A186 restore body, post-restore ready clear, task lifetime, timing,
gameplay, and other modules remain open.
