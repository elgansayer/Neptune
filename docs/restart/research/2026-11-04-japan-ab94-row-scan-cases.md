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

Two independent six-case original-byte reports (execution 304) are identical,
SHA-256 `7c34c7041782f9a8b863e200e1b722ba4e50d30e8230d03392fd469d9fb565d0`,
mode 0600. Probe SHA-256 is
`0be8e9eebbc6819c6ae3c587fa9c3b436387cfc4e446482390cb5b9fa69bd9b2`.
The earlier strict stack-fence failure is preserved in execution 301; the
additional bounded prefix stack window enabled execution 302, which was repeated
as execution 303.

Rows and ready states here are constructed. The results establish selected
original branch behavior and resident continuation bytes, not natural scheduling,
all row/context combinations, device timing, gameplay, or complete code recovery.
The state2 case was continued into A8E8 in a separate CPU using the AB94
register/special-state report and replayed A208/AB94 writes; see the
[A8E8 continuation result](2026-11-04-japan-ab94-a8e8-continuation.md). Broaden
row indices/states and continue remaining functions, modules, and assets.
