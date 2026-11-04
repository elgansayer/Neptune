# Japanese kernel scaled-difference leaf

This result uses the unchanged Japanese kernel `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution

The five-instruction leaf at `0x060A750A` has executable range
`[0x060A750A, 0x060A7518)`, including the subtraction in the RTS delay slot.
It reads longwords at record offsets `+44`, `+4`, and `+8`, computes the low
32 bits of `field(+4) * field(+44)`, subtracts `field(+8)` modulo 2^32, and
returns the result in R0. It leaves the input record unchanged. Replacing the
RTS-delay subtraction at `0x060A7516` with `nop` is rejected by the result
control.

The private paired reports in `execution-099` each contain 512 Cartesian
combinations of eight unsigned boundary values, each combination executed
twice. Both reports have SHA-256
`124d4b01ab5813d0412768d3f05cc92b6fabde20d3bc181d99af5834c38d5d81`; the
ordered result digest is
`7b5e6865d8e7be6f02d5a88efd7646068faef48aee3cf609aa43ec09ceceface`.
Executed range SHA-256 is
`ace7df5a9571abb1bcd54f3bac081a763ca30c4fd6dab60b2504e5670372889e` and
probe SHA-256 is
`5db45584f9d5fb94e16ab7ba86848a8c07d4c6af23952833b5157c6aa798f545`.

This is a constructed CPU-only arithmetic test. It makes no claim about
call-site input units, service behavior, hardware timing, gameplay, or an
independent emulator.

## Request-state-zero caller path

Static decode of `0x060A6FFA` is saved privately as
`analysis/japan-a6ffa-request-state-zero.txt`, SHA-256
`329151e853d910e2049725eab54e3cda5485c6724d28d863d6003819aa959504`. It
calls `0x060A750A` and `0x060A753C`, and may call the original `0x06095C8C`
and `0x060A6C94` dependencies. Those caller operations and their natural
request inputs remain to be executed and validated.
