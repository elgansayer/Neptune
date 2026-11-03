# Japanese kernel A6150 SCU command writer

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution and MMIO write intents

The original function range `[0x060A6150,0x060A61B0)` reads a 40-byte
descriptor. Descriptor word 9 gates writes of words 0 and 1 to SCU D0R/D0W.
It always writes word 2 to D0C, `word3 | word4` to D0C+4, and a packed value
from words 5 through 8 to D0C+12. The channel number in R5 adds a 32-byte stride
to each register address. The probe uses a rejecting MMIO event sink that records
the original CPU's address and value writes. It does not emulate SCU side effects,
timing, DMA completion, or hardware state.

Thirty-two constructed descriptor-flag/channel/seed cases ran twice. The paired
private reports in `execution-127` are byte-identical at SHA-256
`d74851e1087f1269544fc44245563ec3e2a942882b80a6333d1f370d54649e85`; the
ordered results digest is
`e74e99af5c8d2f5b932e5e6c79d6905174052509f859422020c02d54d7628e0b`. The
function and three source literal hashes are
`3f8d40efd377ff71520926801d1c5835d5a174f93f9f2884d0aac29cf65a90ee` and
`3b7111bf7102ba308a99e407c7eaf1782731c3764e05cf9931e7d64cdc8cdf89`. The
probe hash is
`b39f44e5f1688a9cb3b3d6c066af1802df537a1a0cf9b465e07a717f2ccd2321`.

Changing the D0R literal at `0x060A61EC` to `0x25FE0080` is rejected when its
write intent differs from the expected channel register address.

This recovers the bounded CPU-side descriptor and register-write contract.
Hardware effects, timing, callers, natural descriptors, and A70B8 end-to-end
device behavior remain open.
