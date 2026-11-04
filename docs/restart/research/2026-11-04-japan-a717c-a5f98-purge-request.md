# Japanese A717C A5F98 associative-purge request

This probe begins at `0x060A723C`, immediately after the separately executed
A717C→A600C→A6100 caller-tail result. It runs the original A717C callsite,
including both JSR delay slots, executes original A5F98 through its RTS delay
slot, and stops at `0x060A7244` before the next caller instruction.

For both caller bases (`0x06009000` and `0x06009004`) with R5 size 4, A5F98
masks R4 by `0x1FFFFFFF`, ORs `0x40000000`, rounds the start down to 16 bytes,
and performs one longword zero store at `0x46009000`. Both calls return to
`0x060A7244` with R4 at `0x46009010` and the unrounded end in R5. The probe
records the store as a `CACHE_PURGE_REQUEST` event; it does not map the
associative-purge address as RAM or claim that cache invalidation occurred.

The SH7604 hardware manual maps `0x40000000–0x47FFFFFF` as associative-purge
space. Sega's Saturn technical bulletin describes a specific 16-byte line purge
as a 16-bit zero write. The original helper uses a 32-bit `MOV.L` store, so the
hardware effect of that access width remains unresolved. The pinned SaturnRecomp
runtime logs associative-purge writes and returns without invalidating cache;
that implementation is not hardware-effect evidence. [SH7604 Hardware Manual,
address map](https://antime.kapsi.fi/sega/files/sh7604.pdf#page=135), [Sega Saturn
Technical Bulletin #28, cache purge](https://forum.jo-engine.org/upload/files/SEGA/ST-TECH-1-41.pdf#page=7).

Paired reports `execution-162/report-a.json` and `report-b.json` are byte
identical, each covering two caller inputs twice each, and each has SHA-256
`0fe980144a9c0b41301025c24dab6fa26e0aa9bb0e1ca5e77f5ba0b5fbab24b9`. The
result digest is
`6acc4eabbaac2259dcdcb7362ea35138d101ebf9fe3fe7d7825a9f469c1e5f72`; the
probe SHA-256 is
`baf90e42471fc945af96365cefdf3e68f124dda193c86b20877774844e2eb550`.

Original identities: Japanese kernel SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; A717C
callsite `[0x060A723C,0x060A7244)` SHA-256
`da78ae1234e864976e0aa1586fc536932a0af43bc1fa6a0957f886edc274ba77`; A5F98
code `[0x060A5F98,0x060A5FB4)` SHA-256
`a663c4a5748d6bf15c5603d637f6865fdb49bbc3b1bce92366f3e67ab5151da8`; and
referenced literals `[0x060A5FBC,0x060A5FC4)` SHA-256
`4c1493b4f274c586abb761ae97f6c6554e8e67d9d59e9a991ff6af36d77bd858`. Private
reports are under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/`.

The input context is constructed from the previous A717C/A600C/A6100 caller
result; this is not one continuous execution from A717C entry. No natural call
reachability, active cache-state transition, or timing claim is made. Next
resolve the actual SH7604 longword associative-purge behavior with a suitable
existing emulator or stronger hardware documentation, then continue through
the remaining A717C calls and full game/module inventories. Full code and
asset recovery remains open.
