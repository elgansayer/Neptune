# Japanese A717C caller tail through A600C and A6100

This probe begins at `0x060A71C0`, immediately after the separately executed
A717C→A6112→A5FC4 boundary and a separately bounded A5FC4 execution. It runs
the original A717C descriptor-building tail, calls original A600C at
`0x060A7232`, executes the A595B6 leaf when selected, then calls A6100 and
stops at `0x060A723C`, the following A5F98 call boundary.

Across 216 input combinations, each run covered the original SH-2 path twice:
three signed R8 values, three caller stack-top values, two saved R7 values, both
channels, two R10 bases, and three initial CHCR values. The A717C tail derives
descriptor flags `0x2FF`, SAR from saved R7, DAR from R10, TCR from R13, and
CHCR fields from the signed R8/stack-top branches. A600C writes the selected
SAR/DAR/TCR/CHCR registers. The original A6100 helper then reads the selected
CHCR, sets DE, writes it back in its RTS delay slot, and returns to the exact
A5F98 call boundary.

The caller leaves its descriptor word `+32` untouched. In the captured frame
the inherited word at `0x06007FCC` is zero. Since `0x2FF` does not set flag
`0x100`, A600C does not read that word or write DRCR on this route. A semantic
control mutates the word to `0x123456AB`; the A600C write trace and final CHCR
remain unchanged, and no DRCR write occurs. This says nothing about other
callers that may set flag `0x100`.

Paired reports `execution-161/report-l.json` and `report-m.json` are byte
identical, each 216 cases with two executions per case, and each has SHA-256
`a0f344e60d60a1983191120f5818d5f08c72b69c9a2f0cd2c60456f9b6667833`. The result
digest is `5d6842291660bd6d51bad5d52348b2c5bc7dcb33df7248cac2eb4da160b7e9f3`;
the semantic-control result digest is
`d1d40324ec4b5f2db302fca4c4632a419eb1b6b3bd25e623d64080bb2003f632`. The probe
SHA-256 is
`4c70246e1f07148abef8125ace827c626da9e8cbbd82e1ab4c234de52fa89265`.

Original source identities: Japanese kernel SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`;
A717C tail `[0x060A71C0,0x060A723C)` hash
`4434ca0a12db6eab2b242256c65518447a45cee424cd7f48c9aef5fb105a3f54`;
A600C `[0x060A600C,0x060A60EA)` hash
`69598226840204f2e19d76d91667fc0da15c3c7ca86a7358b8517db45db58407`;
A6100 `[0x060A6100,0x060A6112)` hash
`96dc1b3ef1c27a5d07701f53484bdce4dac42fd1f45995495333ef5b42de1807`; and
A595B6 `[0x060959B6,0x060959C0)` hash
`a608042d89a94b2cf713cfac2d55bb0309a6b12365134738aeb1fd3b70f5e2a6`. The
frame-1200 state and normalized WorkRAM-H hashes match the existing private
checkpoint. Reports remain under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/`.

The adjacent A5F98 helper is statically decoded at
`[0x060A5F98,0x060A5FB4)`. It transforms R4 into the SH-2 associative purge
space, rounds the start down to a 16-byte boundary, then issues a longword
zero store every 16 bytes until the end bound. The SH7604 manual identifies
`0x40000000–0x47FFFFFF` as associative purge space, and Sega's Saturn dual-CPU
bulletin describes purging the 16-byte line by a 16-bit zero write. A5F98 uses
`MOV.L`, so its access-width behavior needs emulator or hardware evidence before
we model the side effect or continue the caller through this target. [SH7604
Hardware Manual, address map](https://antime.kapsi.fi/sega/files/sh7604.pdf#page=135),
[Sega Saturn Technical Bulletin #28, cache purge](https://forum.jo-engine.org/upload/files/SEGA/ST-TECH-1-41.pdf#page=7).

The input at `0x060A71C0` is constructed from the previously tested A717C
boundary contract. This is not one continuous execution from the A717C entry;
it does not prove natural gameplay reachability, active DMA behavior, or hardware
timing. A5F98 is the next unresolved call. Its static Japan decode suggests a
zero-fill loop over an address transformed with `0x1FFFFFFF` and `0x40000000`;
classify that target mapping before modeling writable memory or executing it.
Continue through A5F98 and the wider Japan/USA module inventories. Full original
code and asset recovery remains open.
