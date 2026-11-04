# Japanese kernel request initializer

This result uses the unchanged Japanese `0KRNL.BIN` (SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`) at
mapping `0x0600A000`.

## Composed original-byte execution

The probe composes the initializer at `0x060A6D04`, its setter at
`0x060A6D46` including the `0x060A6D48` RTS delay instruction, and the reset
helper at `0x060A6D3A`. The mapped executable range is
`[0x060A6D04, 0x060A6D4A)`. Across 32 constructed records, each executed twice,
the original code initializes offsets `0..32`, writes `1` at `+20` and `+44`,
clears `+52`, stores incoming state `3` at `+56`, clears `+36` and `+40`, and
returns the request pointer. The prior value at `+56` is read, but the caller
returns its pointer rather than that prior value. Exact stack transactions,
remaining record bytes, registers, PR, SR and stack pointer are checked.

Changing instruction `0x060A6D3C` to store at `+52` is rejected by the request
image and exact-write control. The probe and executed-code SHA-256 values are
`34cd779f25c22ce4f467ce22822e8bde50fd5879e71da452eff4ff99968d9f3a`
and `88cf38b3230bf90329949ae4a309421c049f7220637d834d664e0b466452dfd3`.
The ordered results digest is
`16c3e0b2f52ead63f9159b8b88e14f066e0f3465b2f3df6e2a83b3738f0ab558`.
Paired reports in private `execution-096` are byte-identical at SHA-256
`306bcec284c292a551ae08b8e691e27deba4fb17aadb2a87abcac625b6a0b131`.

This is a constructed CPU-only caller composition. It does not prove where
natural requests originate, what the state machine's downstream services do,
or any BIOS, device, timing, gameplay or independent-emulator behavior.

## Next request-service dependency

Static decode of original bytes at `0x060A6F20` is saved privately as
`analysis/japan-a6f20-request-service-helper.txt`, SHA-256
`b9f5caa0022b95e77751b0634eefb1c2649f9b02a1c8795a7c9040a6a1eb19b7`. It
dispatches request states `0..5` to `0x060A6FFA`, `0x060A7076`,
`0x060A736C`, `0x060A73BE` and `0x060A7480`; the final stage also calls
`0x060A6CCE` and `0x060A7564`. These branches and dependencies still need
bounded original-byte execution and service-level evidence. The broader
request loop at `0x060A6DA6` and additional game modules/assets also remain.
