# Restart backlog

Tracker: [#23](https://github.com/elgansayer/Neptune-Bomberman/issues/23).

Priorities order eligible work, not permission to skip dependencies. The operator
can prepare the host while the game baseline and bot audit proceed. Read each
issue's acceptance checks before claiming. Broad tasks should be split further
when they exceed one reviewable implementation change.

| Issue | Task | Dependencies |
| --- | --- | --- |
| [#24](https://github.com/elgansayer/Neptune-Bomberman/issues/24) | [P0] Reproduce Godot build and reconcile test-runner PRs #18/#20 | Foundation PR |
| [#25](https://github.com/elgansayer/Neptune-Bomberman/issues/25) | [P0] Provision isolated research host and operator prerequisites | Foundation PR |
| [#26](https://github.com/elgansayer/Neptune-Bomberman/issues/26) | [P0] Fingerprint real Saturn inputs and catalogue existing assets | #25 |
| [#27](https://github.com/elgansayer/Neptune-Bomberman/issues/27) | [P0] Build noninteractive Saturn emulator control and repeatability harness | #26 |
| [#28](https://github.com/elgansayer/Neptune-Bomberman/issues/28) | [P0] Extract real sprite and background data with provenance | #27 |
| [#29](https://github.com/elgansayer/Neptune-Bomberman/issues/29) | [P0] Reproduce one campaign room and battle arena against original traces | #24, #28 |
| [#30](https://github.com/elgansayer/Neptune-Bomberman/issues/30) | [P0] Audit bot decisions and fix hazard/oscillation regressions | #24 |
| [#31](https://github.com/elgansayer/Neptune-Bomberman/issues/31) | [P1] Add fair online bot room filling and human seat replacement | #30 |
| [#32](https://github.com/elgansayer/Neptune-Bomberman/issues/32) | [P1] Build reproducible bot tournaments and policy promotion checks | #30 |
| [#33](https://github.com/elgansayer/Neptune-Bomberman/issues/33) | [P0] Prove one durable OpenHands issue-to-PR job with independent gates | #25 |
| [#34](https://github.com/elgansayer/Neptune-Bomberman/issues/34) | [P1] Prove browser/native cross-play with authoritative bots | #24, #31 |
| [#35](https://github.com/elgansayer/Neptune-Bomberman/issues/35) | [P1] Define portable pack format and enforce online compatibility | #24 |
| [#36](https://github.com/elgansayer/Neptune-Bomberman/issues/36) | [P1] Add shared player identity and trusted event-based match statistics | #31 |
| [#37](https://github.com/elgansayer/Neptune-Bomberman/issues/37) | [P2] Build community workshop upload-to-cross-play experience | #35, #34, #36 |
| [#38](https://github.com/elgansayer/Neptune-Bomberman/issues/38) | [P1] Expand verified campaign, bosses, battle modes and Saturn CPU coverage | #29 |

## First eligible server work

1. #24: reproduce the actual Godot build and reconcile existing test PRs.
2. #25: inspect/provision the supplied host and credential boundaries.
3. After #24, #30: reproduce the concrete bot hazards/decision failures.
4. After #25, #26 and #33: pin real reference inputs and prove one bounded factory job.

The foundation input tool is available before these tasks but does not close #26:
that issue requires actual supplied media, a full asset audit and evidence.

## Server execution follow-ups

- [#40](https://github.com/elgansayer/Neptune-Bomberman/issues/40): reviewable
  runner reconciliation/failure-boundary portion of #24. Passing these checks
  establishes test infrastructure, not the full game baseline.
- [#47](https://github.com/elgansayer/Neptune-Bomberman/issues/47): reproduced
  duplicate server startup and headless client role failures, also under #24.
- [#48](https://github.com/elgansayer/Neptune-Bomberman/issues/48): operator
  dependency for real media/release, explicit spending policy and backup target.
- [Actual host/runtime evidence](evidence/2026-10-29-server-baseline.md).
