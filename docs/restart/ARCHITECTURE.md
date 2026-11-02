# Factory and community architecture

## Durable factory

Read [FACTORY_PLAYBOOK.md](FACTORY_PLAYBOOK.md) for queue ownership, evidence
contracts and restart tests. Saturn and Power Bomberman research feed independent
specifications into the same game repository; they are separate reference baselines.

GitHub issues are the visible work queue. A durable coordinator tracks issue ID,
dependency state, input/base/head hashes, worker lease/heartbeat, attempt history,
spend and evidence references. Define explicit states such as ready, claimed,
implementing, verifying, mergeable, merged and blocked. Claims must be
idempotent and recover after process/host restarts.

Begin with one live worker to prove intake, provider authentication, evidence,
restart recovery and costs. Increase to two implementation workers once measured.
AI review is optional. Keep interface-changing work serial where necessary.

Reuse the deployed Elgl Repo Factory and supported shared provider broker as
specified in [FACTORY_PLAYBOOK.md](FACTORY_PLAYBOOK.md); do not create a competing
scheduler or assume OpenHands is required. Dispatch version-pinned supported
workers in isolated workspaces. GitHub Actions executes deterministic checks.
Provider adapters use documented authentication,
bounded retries/backoff and explicit paid-fallback policy. A provider failure must
not mark a task complete or produce an infinite retry loop.

Follow [MERGE_POLICY.md](MERGE_POLICY.md): no mandatory human/AI approval wait.
Re-check applicable CI, branch base and dependencies after any push/rebase before a
serial merge. Keep merge credentials out of workers. Do not weaken fixtures/tests
or silently alter the coordinator's policy to obtain a passing result.
Separate policy deployment from ordinary gameplay changes.

Failure handling should create a focused diagnosis or split task, release stale
claims and continue other eligible work. Deployment uses immutable build identities,
smoke tests, a recorded previous version and tested rollback. Health reports must
distinguish a paused/budget-exhausted worker from a functioning continuous factory.

## Game and browser

Keep one Godot authoritative simulation and shared rules. Browser and desktop
clients share game/content semantics. Prototype WebRTC data channels to native
Godot servers, including native plugin support, signalling and TURN; ENet alone
cannot serve browser clients. Transport adapters must validate messages and keep
network IDs separate from persistent user IDs. Start with explicit tick/seed
management and authoritative replay snapshots; do not promise cross-platform
deterministic Godot physics without proving it.

Version ruleset profiles: faithful Saturn and extensible Neptune. Profiles define
timebase, mechanics, mode lifecycle, objectives, capabilities and participant
limits. Design extensible rooms for twelve seats while retaining original limits
where fidelity requires them. Snapshot profile/settings/pack hashes into replays
and stats. Power-inspired changes must not silently mutate Saturn defaults.

Use [NETPLAY_BENCHMARKS.md](NETPLAY_BENCHMARKS.md) to select prediction/reconciliation
or rollback from measurements. Browser transport support alone proves neither
responsive gameplay nor synchronisation correctness.

Audit LimboAI, SQLite and other native addons for web exports; exclude server-only
dependencies from clients. Test Compatibility renderer exports, input/audio startup,
background tabs, reconnects, pack cache eviction, HTTPS/headers and memory limits.

## Portable packs and workshop

The product contract in [COMMUNITY_CONTENT.md](COMMUNITY_CONTENT.md) extends packs
to declarative power-ups and complete solo/co-op campaigns. It defines effect
ordering/budgets, campaign saves, explicit co-op support, bot roles and creator
acceptance. Implement these through the shared simulation and public interfaces.

Define a versioned, namespaced data-only format for maps, characters, animations,
cosmetics, sound and supported rules. Include author, licence/provenance,
dependencies, API compatibility and content hashes. Reject traversal, archive
bombs, excessive resources, unsupported file types and executable scenes/scripts.
Do not treat a signature as a sandbox.

Bundled content must use the same interface. Each match pins exact pack versions
and ruleset hashes; clients download/validate before joining. Registry versions are
immutable; publisher updates do not change active matches or old replays. Advanced
scripting is a later restricted-runtime decision. Ranked servers use approved packs.

Allow any installed compatible character without compulsory unlocks. Cosmetic art
does not change hitboxes or abilities; ability packs declare gameplay capabilities.
Creators need template, validator, preview and bot test tools. Keep APIs compatible
with later self-hosted registries and separate code/content release provenance.

Workshop flow: draft upload -> validation -> previews/test match -> publish ->
share/play/subscribe. Include map/character editors, templates, creator pages,
version history, reports, reversible moderation, access controls and rate limits.

## Accounts, stats and community

One player identity across native game, browser game and website. Nakama supplies
accounts/social primitives/matchmaking; Godot retains gameplay authority. Community
services use supported APIs and their own store as needed rather than modifying
Nakama's internal database schema. Store pack binaries and large replays in object
storage. Use short-lived launch tickets instead of exposing long-lived credentials
in URLs, mods or static assets.

Trusted servers emit versioned events with match ID, event ID, tick, player ID,
map/version, ruleset hash and relevant causes. Durable ingestion and idempotent
aggregation prevent lost or duplicate statistics. Partition ranked/custom/bot
matches. Only trusted servers contribute to official rankings. Rebuild aggregates
from retained event history; document metric definitions and inference limitations.

Website: accessible TypeScript application for profiles, histories, heatmaps,
leaderboards, achievements, workshop, friends/parties, clubs, notifications and
events. Account privacy/deletion, moderation and operational restoration need
end-to-end tests. Untrusted user text is not a factory instruction.

## Integrated platform gates

A player signs into the website, uploads a custom map, invites a friend via a link,
plays a browser/desktop match using the exact same pack version, and sees correct
server-confirmed results on both profiles.

That first map-only gate can proceed using original/permitted content without
waiting for full reference extraction. #57 expands it to a custom power-up,
two-level solo/co-op story, companion bots and checkpoint recovery. Reference
fidelity and network-superiority claims retain their separate evidence gates.
