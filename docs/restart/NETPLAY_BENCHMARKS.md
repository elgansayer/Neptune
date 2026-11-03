# Competitive netplay: performance and reliability contract

## Standing product requirement

Owner direction, 3 November 2026: network play feels laggy, especially movement.
Neptune must target esports-level competitive play with exceptionally responsive,
smooth, reliable and fair networking. Continuously and aggressively remove all
avoidable input latency, movement jitter, late actions, stalls and disconnects.
This is a core release requirement, applying to every supported native/browser
transport, supported room size and competitive content profile throughout
development.

Optimise the full input-to-display and input-to-authority paths: input polling,
packet scheduling and queues, server tick work, state delivery, prediction,
reconciliation, remote presentation and recovery. Do not alter authoritative game
speed, collision, fuse/damage timing or match outcomes to hide latency. Local
prediction must use validated movement semantics and reconcile to server results.
Discard obsolete replaceable state within bounded queues; preserve acknowledged,
idempotent discrete actions so loss/retry cannot miss or duplicate a bomb command.

Real propagation delay cannot be abolished. Publish the supported RTT/jitter/loss
and load envelope, measured budgets and remaining limits. The competitive goal
does not establish that the current build is ready for esports.

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

Include movement starts/stops, rapid turns, corner sliding, collision, bomb
placement/kicking/throwing, simultaneous actions and deaths. Exercise changing
impairment mid-match, brief missing-update gaps and recovery, with rendered human
clients at 30/60/144 FPS. Keep simulation timing fixed across render cadences.

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
- Snapshot age, input age, send/receive queue depth and oldest queued-state age;
  separate time spent waiting from simulation work and render presentation.
- Movement start/stop/turn response and per-frame visual discontinuities; distinguish
  interpolation delay, extrapolation and authoritative corrections.

Initial correctness gates: zero observed divergent final outcomes or duplicated
accepted actions in the declared suite, and all scripted recoverable reconnects
complete within the stated test deadline. State sample sizes; zero observed errors
is not a guarantee of zero future errors. Establish responsiveness/resource budgets
from the first real baseline and freeze them before comparing implementations.
Only claim an improvement when it exceeds measurement uncertainty and does not
trade away the correctness gates. If reference automation is unavailable, report
Neptune-only results and leave the comparison unverified.

## Release budgets and continuous optimisation

Before a competitive release, #45 must record numeric budgets from real baselines
for each supported transport/profile and declared connection/load envelope. Include
input-to-visible and input-to-authority p95/p99, remote snapshot age, correction
magnitude/frequency, stall duration, tick/frame deadlines, bandwidth/queue bounds,
session success and recovery deadlines. Record hardware, player/concurrent-room
counts, run duration, sample size and measurement uncertainty with those budgets.
Budget selection is an open deliverable; an unset budget cannot pass a competitive
readiness gate.

Every change affecting these paths must run the applicable reproducible benchmark
against its pinned baseline. Correctness gates and frozen budgets must pass;
measured regressions beyond declared uncertainty block the applicable release.
Keep raw slow samples and failures. Investigate each avoidable latency/jitter/stall
source in small measured changes, retaining a continuous regression benchmark and
bounded load/soak runs. Higher send rates or larger buffers alone do not establish
an improvement. Never relax a budget or correctness assertion solely to pass.

The current bounded remote-render correction and its synthetic cadence evidence
are separate from whole-session WAN performance. #112 retains validated local
prediction/reconciliation; #115 retains timestamped remote actors/bombs and
discontinuities; #34 retains cross-play/transport evidence. None is completed by
this contract or a presentation-only regression check.

[3 November remote-motion evidence](evidence/2026-11-03-remote-motion.json) records
the matched synthetic presentation comparison, passing focused tests and native
connection probes, retaining the original full-suite bot timing failures.
[Retry and wait-state evidence](evidence/2026-11-03-netplay-retry.json) records
a reproduced stale-counter defect, its bounded correction and a passing 582-check
native suite with current game code. Published-head/current-base CI remains the
merge gate; these results do not establish competitive release readiness.

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
