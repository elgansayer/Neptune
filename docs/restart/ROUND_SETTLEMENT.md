# Completed-tick round settlement

This is a bounded Neptune last-survivor contract for #105 (SIM-012), implemented
through #556. It is not a measured Saturn/Power rule or complete team, reward,
campaign, replay or durable-statistics system.

## Ordering

Actual deaths through `GameInstance._apply_player_damage()` and actual roster
removals request a survivor check. They do not choose a winner inside a victim,
tile, chain-reaction or hurry-block loop. Invincibility/mount protection that
prevents death does not request settlement. An absent/idempotent leave does not
request settlement either. A single-seat room therefore does not end merely
because it starts with one player.

The authority's existing +100 late physics publisher settles every completed tick
after the -200 clock/status/hurry phase, -150 bombs, -100 bots and 0 player
movement. Settlement runs even when no network packet is due. Independent bombs,
lingering flames, direct and batched hurry damage, and roster removals delivered
before that boundary all contribute to one completed roster.

Timer expiry queues a timeout instead of ending in the early clock phase. The
remaining bomb/actor phases of that final tick still execute. At the late boundary:

- A pending timeout ends the round using that completed roster, with reason
  `timeout`, including when a survivor check is also pending.
- Otherwise a requested survivor check ends only with zero or one living actor,
  with reason `survivors`.
- One living actor is the winner; zero or multiple actors at timeout are a draw.
  These preserve the existing last-survivor winner selection, while removing
  intermediate results that depended on victim iteration order.

`end_match()` remains a trusted immediate explicit stop (e.g. the local console),
with default reason `stopped`. It is not a public client RPC or deferred gameplay
damage path. Pausing or disabling authority physics also stops late settlement;
an isolated test that manually steps the authority must manually run its late
publisher if it wants a complete tick.

## Terminal state

`get_round_result()` returns an empty dictionary while live. At settlement it
returns a detached schema-1 dictionary containing `game_id`, `simulation_tick`,
`server_time_msec`, `reason`, `winner_id` and sorted string peer IDs in `survivors`.
This is local diagnostic state, not an authenticated globally unique result.

The result and `match_active = false` are committed before the existing
`game_ended(winner_id)` signal. Repeated checks/stops, later disconnects and a
reentrant terminal listener cannot emit another result. All four current damage
routes use the same terminal guard: delayed progressive/lingering/hurry damage
cannot kill the committed winner or append further elimination events. Cleanup,
bomb visuals and unrelated world callbacks may still run; this is not a full
world freeze or a guarantee about arbitrary direct calls to `ServerPlayer.die()`.

A trusted false-to-true assignment to `match_active` clears pending/terminal state
for activation and existing isolated native fixtures. It does not reset the map,
players, timer or session elimination history. Public configured rooms still
reject implicit restarts through `start_room_countdown()` after `_room_round_started`.
A future supported next-round/reset/reconnect lifecycle needs its own contract.

The snapshot is additive server-side data. No network message schema, browser
transport, content manifest, pack identity or community code execution changes.
It can support future stats/bot consumers, but has no durable ingestion or rewards
consumer yet. Team outcomes and duplicate reward delivery remain open in #105.

## Verification

`tests/test_round_settlement.gd` uses real GameInstance/ServerPlayer/ServerBomb
code with the permitted original map fixture. It covers simultaneous blast and
lingering victims, independent bombs, both hurry lookup paths, no-send ticks,
timeout ties, disconnect/death combinations, nonterminal deaths, single-seat and
invulnerable compatibility, delayed damage, detached snapshots and reentrant
signals. One test enables the actual SceneTree physics phases and inspects the
roster/elimination count seen by a terminal listener at the timeout boundary.

The unchanged accepted main fails these new behavioral assertions; the retained
baseline logs are not emulator or reference-parity evidence. Focused runs at
30/60/144 render FPS, the existing full native suite and bounded server/client
checks are the applicable verification. CI must run its required gameplay gate
for the exact candidate head and current base; documentation alone is not a pass.
