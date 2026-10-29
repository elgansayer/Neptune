# Better netplay: measurement and design contract

Task #45. These are proposed experiments and acceptance targets, not results.
Do not announce that Neptune is faster or more reliable until comparable runs
support that claim. Power Bomberman's transport/internal simulation model is not
established by the public feature announcement.

## Compare the same experience

Pin both builds, hardware, OS, render/capture rate, map geometry, movement/fuse
settings and player count as closely as practical. Document remaining mismatches.
Measure a local baseline for each product, then the added cost under the same
network conditions. Use owned reference servers, never the public community server.

Record input injection, first visible local response, remotely visible action and
authoritative event acknowledgement where instrumentable. For the reference,
record external video measurements and their uncertainty; do not invent internal
timestamps. Keep separate metrics for responsiveness and correctness. A predicted
animation appearing quickly is not proof the server accepted the action.

Same-host monotonic clocks or explicit clock calibration are required for timing
across processes. Frame-rate limits and video detection introduce quantisation.
Retain raw samples, calculation version, sample counts, failures and uncertainty;
report p50/p95/p99 without discarding slow samples as unexplained outliers.

## Initial experiment matrix

| Dimension | Planned cases |
| --- | --- |
| Participants | 2, 4, 8, 12 in extensible mode; reference-specific Saturn limits separately |
| Workload | Human-input clients, bots, mixed; bots do not replace rendered client load |
| Added RTT | 0, 40, 80, 150, 250 ms |
| Jitter | 0, 10, 30 ms with distribution documented |
| Loss | 0%, 0.5%, 2%, 5%; include burst loss as a separate case |
| Connectivity | Direct, forced relay, IPv4/IPv6 where supported, constrained uplink |
| Client | Native, browser/native cross-play, background tab, slow renderer |
| Failure | Reconnect, duplicate/out-of-order input, stale pack, server restart |

Start with a baseline and one stressed case, then expand; a full Cartesian product
is not the first job. Record measured RTT/jitter/loss in addition to configured
network-emulation values. If delay is applied to both directions, account for the
sum instead of accidentally doubling the advertised RTT.

## Metrics and gates

- Input-to-visible p50/p95/p99, remote-action visibility and additional delay over
  each product's local baseline, with measurement uncertainty.
- Correction magnitude/frequency, visible warps, missed/duplicated bomb commands,
  client disagreement, false hit presentation and authoritative match outcomes.
- Connect/join/reconnect success, time to playable state, stalls and disconnects.
- Server tick p95/p99, client frame time, bandwidth, CPU/RAM and relay bandwidth
  at the target participant count and concurrent-room load.
- Bot decision cost and replacement behaviour in the same network scenarios.

Initial correctness gates: zero observed divergent final outcomes or duplicated
accepted actions in the declared suite, and all scripted recoverable reconnects
complete within the stated test deadline. State sample sizes; zero observed errors
is not a guarantee of zero future errors. Establish responsiveness/resource budgets
from the first real baseline and freeze them before comparing implementations.
Only claim an improvement when it exceeds measurement uncertainty and does not
trade away the correctness gates. If reference automation is unavailable, report
Neptune-only results and leave the comparison unverified.

## Architecture decision to measure

Keep authoritative Godot rules. Prototype local input prediction, server
acknowledgement/reconciliation and remote-state interpolation. Separately evaluate
rollback: it needs restorable state, stable ordering, seeded randomness and
reproducible simulation, which arbitrary Godot physics/mod scripts do not establish.
Do not adopt it solely because its name implies better networking.

Transport feasibility belongs to #34: browser/native WebRTC, signalling and TURN
must actually work. The comparative synchronisation experiment follows that
baseline. Keep visual prediction separate from confirmed stats, damage, item
ownership and match results. Record input sequence/tick validation and server
rate limits. Simulate slow/malicious inputs locally without attacking public hosts.

Outcome: a measured architecture decision with raw evidence and budgets, followed
by small implementation issues and a continuous regression benchmark. It is not
a promise of zero latency or a universal improvement on every connection.
