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
A corrected bounded control-flow walk from the entry and these candidates reaches
an RTS on each reported path. The entry path contains nine unresolved indirect
JSR calls through R2/R3; the BIOS vector values and runtime destinations are not
resolved by this walk.

The preliminary linear scan also showed a BSRF at `0x060026AA` in the bytes
after `0x060026A6`. A control-flow audit found that this BSRF was an unreachable
linear fall-through: the unconditional BRA at `0x060026A6` takes the path to
`0x060026C4` after its NOP delay slot. The earlier note incorrectly counted it
as reachable from `0x06002594`. The corrected analysis is retained separately;
this correction does not establish a complete CFG or function boundaries.

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


## Static CFG correction (execution 309 follow-up)

The first bounded control-flow summary misclassified a sequential word after an
unconditional delayed BRA as reachable. A second pass with corrected SH-2 branch
and delay-slot handling retains the preliminary listing, but removes the false
`0x060026AA` BSRF edge from the `0x06002594` candidate. Its private report is
`japan-ip-static-cfg-v2.json`, SHA-256
`c293f79f4e3f6d8f68193820ad577a73ce76134b939419e5f98fb3eb8ce46d97`; the
reproducible analyzer is `analyze_ip_cfg.py`. The corrected walk has 9
unresolved indirect JSR sites from the candidate entry through R2/R3. Direct
candidate blocks reach RTS along the walked paths, but unknown BIOS call targets,
other indirect edges and full executable/data coverage remain unresolved.

## Frame-1200 resident-byte comparison (execution 310)

A read-only comparison against the existing natural frame-1200 Japan emulator
checkpoint supports the candidate load base. At guest `0x06002000`, 32,755 of
the 32,768 system-area bytes match the privately extracted original. The first
256 program bytes at guest `0x06002100` match source file offsets `0x100–0x1FF`
exactly, including first halfword `0x4F22`. The 13 differing bytes are at file
offsets `0xD7C–0xD86` and `0xE9A–0xE9B`; they are retained as observed changes,
not assigned to a patch or runtime writer. This is natural memory-residency
evidence from the saved state, not a trace proving which bootstrap instructions
executed.

In the same captured WorkRAM-H image, vector slots `0x06000300` and
`0x06000344` contain `0x06000794` and `0x060007C0`. The static decoder labels
the slots `SYS_SETUINT` and `SYS_CHGSCUIM`; the function targets, ABI and
behavior remain unvalidated. A static decode of 48 halfwords at each captured
target is retained privately. The full checkpoint and normalized WorkRAM hashes
are the same as the scheduler evidence already cited; the first frame-1200 read
attempt used absolute guest addresses as buffer offsets and is retained but
excluded.

This narrows the bootstrap mapping hypothesis and provides concrete runtime
resident targets to follow. Next validate the IP-to-first-read transfer and
capture these early call targets in a boot-time trace; continue code/data and
indirect-target recovery across the bootstrap and loaded modules.
