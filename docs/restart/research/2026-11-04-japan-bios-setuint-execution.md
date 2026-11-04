# Japan BIOS SYS_SETUINT bounded execution

Execution 311 compared the 64-byte target at WorkRAM-H `0x06000794` with the
original Japan BIOS bytes at file offset `0xD94`, then ran the captured target
through the pinned SH-2 interpreter. The two windows match byte-for-byte
(SHA-256 `91e3dbb549b21545f422ac687f7164edf3aa7413a0f4cb5a63cf455f507616f4`).
The input WorkRAM image is the retained frame-1200 state, SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`.

Four executions use constructed R4 indices 3 and 12 and R5 values 0 and 1.
Each begins at the captured original target, records the executed PC sequence,
and includes the RTS delay slot. With R5 zero, the routine stores its embedded
default value `0x0600083C` in the selected vector slot. With R5 nonzero, it
stores R5 directly. Each run is limited to 16 instructions and one exact
longword write at `0x0600090C` or `0x06000930`; the observed runs take six or
seven instructions including the delay slot.

The private report is
`execution-311/japan-bios-setuint-corrected.json`, SHA-256
`62d3182c9886b8825586f5a98b3f330f9dc735cad4b345703374a29ae884d3dd`.
The first assertion attempt reversed the zero/nonzero cases and is preserved
privately as `execution-311/japan-bios-setuint.json`; it is excluded from the
successful result. The probe is
[`probe_japan_bios_setuint.py`](../../../tools/saturn_lab/probe_japan_bios_setuint.py).

This establishes a bounded behavior for the captured Japan BIOS target under
constructed inputs. It does not prove a natural startup call, identify the
routine's full caller ABI, cover other vector slots, or establish BIOS-wide or
gameplay behavior. It uses the pinned SH-2 interpreter and has not been
cross-checked against another emulator or hardware. The original Japan IP's
startup execution trace, unresolved indirect calls, other kernel routines,
modules and assets remain open.
