# Japan system-area bootstrap: static triage

Execution 309 privately extracted the 16 index-01 MODE1/2352 sectors of Japan
track 01, validating every raw sector sync/mode header. Concatenated 2048-byte
user payloads reproduce the retained 32,768-byte system-area SHA-256
`7d1041112091b4763cf7a3ccf3a4237323ec698380d4038839ffbfafc15a9875`; the
first 256 bytes also reproduce the IP header hash in the Japan release receipt.
The private source track hash and extraction receipt are held with the output;
raw disc data remains private.

The 6,144-byte IP-size field is recorded in the release summary. The receipt's
`boot_code_sha256` is reproduced by system-area bytes at file offset `0x100`
through the end of the 32-KiB extent. The bytes after that metadata-defined
region have not been assigned code/data meanings. The bootstrap's candidate
instruction view starts at file offset `0x100`; it is formatted at candidate
address `0x06002100` under the conventional Saturn IP mapping. That mapping has
not been established from a Japan runtime trace.

Using the pinned SaturnRecomp SH-2 decoder, a bounded 6,144-byte linear view
produces 3,072 halfwords and begins with `sts.l pr,@-r15`. A bounded static
control-flow walk from direct BSR targets in the initial entry window finds
candidate blocks at `0x06002280`, `0x06002348`, `0x060023E6`, `0x06002404`,
`0x0600245C`, `0x06002486`, `0x06002510`, `0x0600255C`, and `0x06002594`.
Eight candidates reach an RTS along the bounded static paths. The `0x06002594`
walk also encounters an unresolved BSRF target at `0x060026AA`. These are
candidate blocks, not validated functions or a complete CFG.

The entry view has PC-relative references resolved by the decoder to BIOS
locations including `0x06000300` (`SYS_SETUINT`) and `0x06000344`
(`SYS_CHGSCUIM`), plus VDP2 and WorkRAM addresses. This is static evidence from
the original bytes. No bootstrap instruction was executed; no BIOS call, device
write, start address, full code/data boundary, or natural boot role is claimed.

The private extraction and disassembly paths, modes, and hashes are recorded in
the host-private continuation checkpoint and execution receipts.

Next: recover the Japan IPL-to-IP transfer state from a pinned emulator trace or
existing boot capture, then validate the bootstrap entry and its first BIOS
calls against original bytes. Continue static/data classification and follow the
unresolved indirect target while retaining system-area, kernel and loaded-file
identities separately. The kernel routines, remaining modules, assets and
whole-program denominator remain open.
