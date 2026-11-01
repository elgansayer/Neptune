# Authoritative local elimination evidence

This is the first bounded SIM-009 slice, tracked in #551 under #102, for bot
evaluation #32 and future statistics #36. It adds server-local events to the
existing direct blast, lingering flame and hurry-block damage paths. It does not
change damage/protection, chain timing or round settlement rules.

## Interface and identity

`GameInstance.elimination_recorded(event)` fires once for an actual living-to-dead
transition. Invincibility and a mount absorbing a hit emit no elimination. Repeated
hits against a dead player do not emit again. The signal has no RPC annotation and
is not added to client snapshots or bot observations.

`get_elimination_event_state()` returns a detached dictionary:

```text
schema: 1
game_id: existing GameInstance identifier
last_sequence: monotonic counter for this GameInstance lifetime
discarded: number removed from the diagnostic buffer
events: last 256 eliminations
```

Each event contains `schema`, `sequence`, `game_id`, `simulation_tick`,
`server_time_msec`, `[x, y]` tile, `victim`, `source` and nullable `self_ko`.
An actor snapshot contains `peer_id`, existing `player_id`, spawn-reservation
`participant_id`, admission `incarnation`, and explicit `human`/`bot` type.
Incarnations are monotonic within the GameInstance, consume no gameplay RNG and
are never reused after a departure or rolled-back admission.

These are room-local identities, not authenticated website accounts. Counters
are not globally unique event IDs, and the bounded history is not durable replay
or idempotent statistics ingestion. Consumers must detect discarded sequences.
The retained history is isolated from signal/getter consumers' mutations.

## Damage provenance

Both production placement paths snapshot the bomb's ID and original owner's
actor/participant metadata. Kicking, carrying and throwing keep the existing
ownership rule. Source snapshots contain no node references and survive owner
departure and bomb deletion. A replacement in the same peer slot cannot inherit
the old actor's ownership.

Immediate hits use the actual bomb's progressive expansion callback. Each active
flame retains its own source and inclusive expiry, alongside the unchanged public
`active_explosion_tiles` expiry-only interface. Sources expire independently in
overlapping flames. For later contact, the earliest observed source still burning
is selected. This is an explicit diagnostic convention, not a measured Saturn
scoring/assist rule. The existing inclusive flame expiry boundary is preserved.

`self_ko` is true/false only for known admitted bomb-owner and victim incarnations:
true means that exact actor was killed by its own bomb. It is null for unknown
ownership and environmental causes. It does not classify avoidability, account
identity across reconnection, chain initiators, assists or last-kicker credit.
Hurry damage has `kind: hurry_block`; a flame inserted without provenance has
`kind: unknown_flame`. Neither invents opponent credit from nearby players.

## Validation and remaining work

`tests/test_elimination_events.gd` uses actual native ServerPlayer/ServerBomb
instances and production placement/progressive expansion. It covers direct and
lingering hits, departure/reused peer slots, overlap expiry, duplicate callbacks,
invincibility, the real mount-protection branch with a visual-free mount fixture,
environment/unknown causes, simultaneous victims, detached output and bounded
retention. The test fixture explicitly controls physics and the simulation clock;
it is not a bot-quality, network-latency or reference-parity measurement.

#102 remains open for chain origin/assists and result consumption. Simultaneous
death records do not fix the existing per-player early round-settlement behaviour
under #105. #32 still needs a repeatable tournament consumer and held-out quality
metrics. The old proximity-based battle diagnostic is not an authoritative
self-KO classifier or a replacement for these events. #36 retains authenticated
identities, durable match metadata, trusted ingestion and persistent aggregates.
No persistent rankings, network event API or complete replay format is added.
