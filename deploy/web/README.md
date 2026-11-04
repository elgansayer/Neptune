# Continuously playable development demo

The public demo uses the real Godot Web client, the authoritative dedicated
Godot server, the existing Nginx `/ws` proxy, Arcane Compose and Cloudflare Tunnel
at `https://bomberman.elgansayer.com`. It is a casual development configuration;
its timings and bot profile are not claims of Saturn fidelity.

Normal settings are 180 simulation seconds of battle, a three-second countdown,
a five-second results period, and four total participants with `BALANCED`
authoritative bots, capped by the selected map/preset. Explicit
`--room-fill-to=0` still means human-only. Remove any old Compose override using
that flag when running the demo. Trusted server options
`--room-duration`, `--room-countdown` and `--room-intermission` accept validated
positive integer seconds. Browser clocks never settle the battle.

The first human starts the countdown. Connected humans continue through results
into fresh arenas; late arrivals spectate until the next countdown, replacing bot
seats when capacity permits. Empty rooms stop scheduling battles. See
[the round lifecycle contract](../../docs/restart/ROUND_SETTLEMENT.md) and
[room bot filling](../../docs/restart/ROOM_BOT_FILL.md).

## Source identity and cache freshness

`export.py` requires committed source, stamps both exported packs with the same
full commit and restores the development placeholder locally afterward. The HUD
shows a compact client revision. Protocol negotiation carries each full revision;
a stale or incompatible pair offers a clear reload path. Source-tree fixtures
identify themselves as `development` and cannot serve as release identity proof.

Exported JavaScript, WASM, PCK and extension assets use `game-<full commit>`
filenames. Root HTML and `/release.json` are served with `Cache-Control: no-store`
and retain cross-origin isolation and explicit WASM/PCK MIME types. A loaded old
page cannot silently fetch a new pack under the old URL. Public browser evidence
checks the actual negotiated client/server pair; a `no-cache` request alone is
insufficient proof. No additional simulation or hosting stack is introduced.

## Required execution and publication

`.github/workflows/web-gameplay.yml` is a read-only reusable gate invoked by both
`Neptune required tests` and `Web release`. The literal required
`Neptune merge gate` now waits for the native checks **and** actual exported
browser/server execution. The native gate still verifies the exact PR head and
current base. `Pinned Godot and Saturn installation` remains independently
required. Browser execution covers every PR, including gameplay and bot paths;
there is no deployment-only path filter that can omit it.

The gate installs the compatible hash-pinned Godot editor and matching templates,
exports the actual client and Linux server, builds the two existing Docker
images, and uses Chromium against Nginx and the real authority. CI uses explicit
60/3/1-second battle/countdown/results durations while retaining four real seats
and the production bot controller. No global time scaling or injected successful
actions is used.

`node deploy/web/smoke_evidence.test.mjs` runs five named evidence-rejection cases.
`smoke.mjs` then requires actual keyboard movement, a human bomb and explosion,
bot movement and bombs, decreasing server timing and terminal outcomes, two
complete rounds on one page/authenticated connection, a fresh map, a second
independent client, active-round spectating and next-round admission, empty-room
recovery and a warm-cache reconnect. Native tests cover timeout/simultaneous
settlement and empty-room ownership. Missing/stalled execution or engine/script
errors fail. Bounded screenshots, console/server logs and JSON state/round/action
receipts are uploaded on success and failure. `report.json` explicitly records
`mode=full`; optional `SMOKE_MODE=release` only proves authenticated build identity
and must never be described as full gameplay acceptance.

Main builds publish the **tested image bytes**, without rebuilding after the gate:

- `ghcr.io/elgansayer/neptune-bomberman-web:sha-<full commit>`
- `ghcr.io/elgansayer/neptune-bomberman-server:sha-<full commit>`

Both images carry the same OCI source revision. Immutable tags are published
before advancing `latest`; a paired-release artifact retains both new digests,
the previous manifests/digests and previous public release metadata. The initial
transition, before `/release.json` existed, falls back to the accepted
`e6bc43980e197e1b14db6be3ff12b29c1b9a4438` pair in `initial-rollback.json`, with
publication-run provenance; both immutable digests must resolve before tags move.
Roll back **both** images to a recorded matching pair of digests or
`sha-<full commit>` tags, then redeploy through the existing Arcane project. Do
not pair one new image with one old image. Current workflow/action versions and
upstream checks are recorded in `dependency-releases.json`.

## Rollout verification and access boundary

Main publication, the existing Arcane webhook and public verification run in one
serialized `web-release-production` concurrency group. Current main is rechecked
before publication/tag advancement and immediately before the trigger, so an old
queued CI run cannot deploy after a newer accepted source. The repository secret
`DEPLOY_WEBHOOK_URL` and `DEPLOY_RESOLVE` remain the configured deployment path.
No credentials are stored in this repository or retained in rollout evidence.

HTTP 202 means only asynchronous acceptance. The deployment job now waits for
`/release.json` to serve the intended SHA, then runs the full public browser
journey with normal **180/3/5** timing and a bounded fifteen-minute browser budget.
Its success proves the public client and authoritative server negotiated the
intended release and completed the measured journey. The full workflow retains
public JSON, logs and screenshots; a publication or webhook-only run cannot pass
that verification.

Arcane's actual deployment state/Event Log and running-container digests still
require authorized host/Arcane access. The repository currently exposes a webhook
trigger, not a documented read-only Arcane state API. Check that existing project's
Event Log and image pair through authorized deployment access; do not invent an
API, infer a host rollout from HTTP 202, or call public observation a host digest
inspection. If those credentials are unavailable, report that exact operational
limitation alongside the public evidence and the paired image receipt. The CI
serialization prevents overlapping CI requests through public verification;
external/manual Arcane jobs also require host-side ordering/state inspection.
