# Japanese kernel A714E status dispatch through A6280

This result composes two original Japan kernel ranges: A714E
`[0x060A714E,0x060A7178)` and its captured function-pointer target A6280
`[0x060A6280,0x060A62B4)`. The frame-1200 pointer at `0x060A7210` contains
`0x060A6280`. Both executed ranges were byte-compared with the unchanged Japan
kernel, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`.

## Composed status path

A714E saves PR, reserves an output word, calls A6280 through the captured
function pointer with R5 set to zero, and compares the returned status byte
with exactly 1. For status 1 it returns 1 and leaves `0x060FB588` unchanged.
For statuses 0, 2, and 255 it clears `0x060FB588` and returns 0. The output
word is written by A6280; the report fences the call path, status slot, saved
PR, and optional global clear.

The paired private reports are in `execution-149` and have identical SHA-256
`23967fe9843af9a4a97be13d4f3d5b5e59a886b8261642159c977fbe58592fb2`. Each
contains 128 cases: four status values, all 16 interrupt-priority values, and
two register seeds. Every case ran twice. Step counts were 39 for the status-1
return and 43 for the clear-and-return path. The ordered result digest is
`3ac1fe715f0ac9d72515d5ec867b7b8f000a9959b99b36c970c5f6b5a1b6fcf8`.
The A714E and A6280 source hashes are
`6dc5672993669a8494ba95b53b3497c6260a15f96e7bc2a6d1c3ec7d38e7a9f0` and
`1b9723d06b9aa1ace6301c38922833ddf2617121e10d2aaa5ccd30fc66855d8c`; probe
hash is `d5fc15f26e3d32a8b245f1d4cfa728a9af4621e805b9ff8248de13d4f0fabf77`.

The private frame-1200 state hash is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`; its
normalized WorkRAM-H hash is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
four tested status values are constructed inputs. This proves bounded
interpreter behavior for the two original routines and captured pointer table;
it does not prove a natural caller or runtime-PC occurrence, full BIOS/device
semantics, all original code, or complete asset extraction.
