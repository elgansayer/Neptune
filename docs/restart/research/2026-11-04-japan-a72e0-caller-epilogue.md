# Japan A72E0 caller epilogue

The original A72E0 path calls A717C at `0x060A72FA`; after A717C returns at
`0x060A72FE`, this probe executes the four-instruction epilogue through its RTS
delay slot (`0x060A7304`). It restores PR from the caller frame at `SP+24`,
advances SP by 28 bytes overall, and returns to the staged outer address
`0x060A73B8`, the delay instruction following the dispatcher's indirect JMP at
`0x060A73B6`.

The Japanese kernel and frame-1200 captured WorkRAM-H are identity checked; the
four executing bytes are compared directly to the original. The paired private
reports under `/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-171/`
must be consulted for the report and source hashes. Both runs execute the
original bytes twice and confirm the sole saved-PR read, exact PC/delay-slot
trace, restored PR/SP, and unchanged 1 MiB WorkRAM-H.

The paired report SHA-256 is
`6775c931cf77b410004726d4440aa9373bcd24704a2e6233fb5dc282209b98fd`;
the result digest is
`a95da43e379497a7bc63f112245937db5dae6b1961024dcac2fc17fb66a58b27`,
and the executed source-window digest is
`f03a3f888450176e06f440ac5c3460d1222dc2ff0c66ce81bf8ef71a623b18a3`.

This is a constructed epilogue boundary, not proof of a naturally observed
A72E0 task invocation. Continue with the complete entry/caller path and other
original Japan/USA functions and modules; full code and asset recovery remains
open.
