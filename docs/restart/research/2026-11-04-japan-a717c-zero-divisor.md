# Japanese kernel A717C zero-shift route

This result executes the original Japan kernel range `[0x060A717C,0x060A727E)`
for the path where a constructed stack argument at entry `SP+4` is 0–3. The
unchanged kernel SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; the
source-range SHA-256 is
`f83724d7adb824d2f15f8d6ef91bb2e2036e06c5286ff3b8aea459b6defffb21`. The
executed bytes were checked against frame-1200 normalized WorkRAM-H; source
residency is not runtime-PC evidence.

## Zero-shift behavior

A717C loads the stack word at `SP+4` into R12 and shifts a copy right by two.
For inputs 0–3 the result is zero, and the original branch skips the unresolved
calls beginning at `0x060A71A6`. The routine stores `R12 & 3` at
`0x060FCD30`, its entry R7 at `0x060FCD34`, and entry R5 at `0x060FCD38`, then
returns `0x5C`. It restores SP, PR, R8–R14 and the non-T SR fields. Each case
executes the same exact 49-PC path in 49 SH-2 steps.

The paired private reports are in `execution-155`, byte-identical at SHA-256
`19d3349f45c110016a4ce4ca38ce670f9702366dc023e22b50ebf79133fcf5fd`. Each
has 2,048 cases spanning four stack-R12 values, two R4 modes, two R5 bases,
two R7 values, two stack-top words, 16 interrupt priorities, and two register
seeds. The result digest is
`9eece26e86183a5179a4b47bf535166175fde08eef7fd5a16000719882f29449`; probe
SHA-256 is
`7b8b2752f415eecf391f9b405a6ae6192be3b92c7f7fb17d04938df4cbba8f0b`.

A separate stack-R12=4 control takes the nonzero path to JSR `0x060A71A6`.
The captured pointer literal at `0x060A7214` contains `0x060A6112`; the
interpreter stops at that unresolved target under the PC fence. No behavior is
claimed for A6112 or for the remaining A717C paths, which call additional
helpers at `0x060A5FC4`, `0x060A600C`, `0x060A6100`, and `0x060A5F98`.

The frame-1200 state hash is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, and
normalized WorkRAM-H hash is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. All
entry values are constructed; this is a bounded branch result, not a full
A717C recovery or natural caller/runtime-PC validation. Other A717C branches,
remaining kernel/module code, and complete asset extraction remain open.
