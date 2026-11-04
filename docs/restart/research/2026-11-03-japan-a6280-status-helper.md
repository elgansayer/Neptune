# Japanese kernel A6280 status-byte helper

This result executes original Japan kernel bytes at `[0x060A6280,0x060A62B4)`.
The kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; the
executed source slice SHA-256 is
`1b9723d06b9aa1ace6301c38922833ddf2617121e10d2aaa5ccd30fc66855d8c`.

## Read and write behavior

The helper takes an output pointer in R4 and index 0–2 in R5, reads the
selected byte from `0x060FCD2C + index`, zero-extends it to a 32-bit word, and
writes that word through R4. It then restores the non-T SR fields, including
the incoming interrupt-priority nibble. The observed return used 26 SH-2
instructions, one selected flag-byte read, two reads of the source SR-mask
literal, one flag-base literal read, and one output write. The frame-1200
snapshot's three selected bytes were all zero.

The paired private reports are in `execution-146`; they are byte-identical at
SHA-256 `f6f5e8c20265adaab95511768e79ebb5639e786477edee63c2c6db0e9f439a74`.
Each report contains 96 baseline cases spanning three
indexes, all 16 interrupt-priority values, and two register seeds, plus 768
constructed flag-byte controls spanning all 256 byte values for each index.
Every case ran twice. The baseline outputs were zero; the constructed controls
returned every value from 0 through 255 at the output pointer.

The ordered result digest is
`f1bc71744200d61b4dafa6ee4ea7314cbc61ca782d4dcf50826334a8202899eb`; probe
SHA-256 is
`e408f5035349c938aaa4cf9c2d8a155dfb9737ffe6c96f37f27e3546c9868b42`.
The frame-1200 save state hash is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and
normalized WorkRAM-H hash is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`.

This is a bounded interpreter execution with the original routine resident in
captured WorkRAM-H and a constructed output pointer. The exhaustive flag matrix
is constructed input, not a claim about natural game states. No natural caller,
runtime-PC timing, BIOS behavior, device effects, full kernel recovery, or full
asset extraction follows from this helper result.
