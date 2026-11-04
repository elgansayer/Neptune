# Japan AB94 row eligibility branches

Starting from caller registers and prefix write events recorded by the A208
probe, replayed into a separate CPU, the original AB94 scan was exercised with
row 0's first longword set to 1 and its +80 byte set to each value 0–3. Captured
rows are also run unchanged. This is a constructed row-state matrix, not a
natural task transition.

Two unchanged-seed baseline runs stop at the 8191-instruction budget at AC46.
The four row-0 cases are:

| Row +80 | Result | A186 restore |
| --- | --- | --- |
| 0 | Budget stop at AC64 | No |
| 1 | Stop before AE76 after 461 instructions | Yes, context BCF0C resumes at AD38 |
| 2 | Stop before A8E8 after 465 instructions | No; PR is A8E8 |
| 3 | Stop before AE76 after 466 instructions | Yes, context BCF0C resumes at AD38 |

Captured WorkRAM-H bytes at A8E8..A946 and AE76..AE96 match the original
kernel exactly (SHA-256 `c44b5ea9ca5584e50d1d6b86ffa9b749233dbd275c53f1e6ee89376e06c32a89`
and `c6fd0a034a029efd0ab271c467538c3ba8e2ecc1062c8f7ab29a3f2897146715`,
respectively). State 2 therefore exposes a resident original-code continuation
at A8E8; this probe stops before fetching its body. The captured-state baseline
reads all 18 task row first words and +80 bytes; none passes the first-word
comparison with 1. Inverting ABCC from `88FF` to `8800` changes the baseline stop
to AC48 and is rejected as a path/effect mutation.

Two independent six-case original-byte reports (execution 303) are identical,
SHA-256 `02527656a15980446517a47b7773783892e0c8ce197fd868c0b8dd2f20ef6beb`,
mode 0600. Probe SHA-256 is
`f00df3b2e41a87b3925c7104d4f1a79e7b2bd28826e34185c7a534f91253449b`.
The earlier strict stack-fence failure is preserved in execution 301; the
additional bounded prefix stack window enabled execution 302, which was repeated
as execution 303.

Rows and ready states here are constructed. The results establish selected
original branch behavior and resident continuation bytes, not natural scheduling,
all row/context combinations, device timing, gameplay, or complete code recovery.
Next execute the A8E8 continuation from its caller-derived state, then broaden
row indices/states and continue the remaining functions, modules, and assets.
