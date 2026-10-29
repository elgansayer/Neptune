# Authoritative bomb placement

Issue [#448](https://github.com/elgansayer/Neptune-Bomberman/issues/448) is a bounded
part of #91 (SIM-004) and #30 before fair bot rooms. These are Neptune authority
contracts, not measured Saturn/Power rules or complete input validation.

## One placement boundary

`GameInstance.place_bomb(ServerPlayer)` validates the registered actor and world
before allocating an ID, sampling a fuse or changing capacity. Human packet dispatch
and native planting/glove/throw callers converge here. Policy checks such as
`can_place_bomb`, `check_capacity` and `check_existing` remain planning conveniences;
disabling them never disables the authority guard.

The guard rejects, in order:

| Reason | Condition |
| --- | --- |
| `unknown_player` | Null/invalid actor or roster entry does not reference this actor |
| `foreign_player` | Actor belongs to another authority |
| `match_inactive` | Countdown, ended or otherwise inactive match |
| `dead_player` | Actor is dead |
| `placement_disabled` | Existing constipation status prevents placement |
| `capacity` | Actor already holds its maximum number of placed bombs |
| `invalid_position` | Actor position contains NaN or infinity |
| `outside_map` | Tile is outside its actual row/map bounds |
| `blocked_tile` | Live terrain is not empty |
| `occupied_tile` | A tracked live bomb node already occupies the tile |

Live terrain values are 0 empty, 1 hard wall, 2 soft wall and 3 hurry wall.
Powerups are separate nodes; a value greater than 2 is not permission to plant.
This also fixes line placement crossing hurry walls. No new fuse/cooldown/speed
rule or personality stat boost is introduced.

Every result is a dictionary:

```json
{"accepted": true, "reason": "placed", "bomb_ids": ["12", "13"]}
```

Rejections set `accepted: false`, return a reason and empty `bomb_ids`, and leave
bomb IDs, roster capacity, world, gameplay RNG and hazard caches unchanged.
Successful single placement retains real ownership, centering, overlap collision
exceptions, fuse/range/type selection and production explosion/cleanup callbacks.

A line reports only the actual created IDs in placement order. It stops at the
existing capacity, terrain boundary or bomb; a nonempty partial line succeeds.
The complete accepted line refreshes AIManager and HazardPredictor immediately,
as single placement does. Private construction helpers are trusted engine
internals below this boundary, not network or community content APIs.

Native BTPlaceBomb returns FAILURE on authority rejection and records its reason
without fabricating a plant timestamp or escape state. Only acceptance updates
plant time and immediate escape bookkeeping. Native glove/throw placement also
requires acceptance before reporting a placement or entering pickup.

`handle_player_input` returns the placement result for its standard/remote and
power-glove fallback placement branches. Packets without a placement return
`input_applied`; that does not certify other ability outcomes. The current network
router discards this local return value: client acknowledgements/rejection events
remain future command protocol work. Input parsing/movement, kick, pickup, throw,
mount and remote detonation validation are not completed by this change. Neither
is the public bot observation boundary (#92), browser play or replay determinism.

## Runtime evidence

`tests/test_bomb_commands.gd` runs real authority, ServerPlayer, ServerBomb and
LimboAI tasks. The original fourteen-case fixture produces one valid-placement
control pass and thirteen assertion failures without engine/script errors. The
expanded twenty-six cases include valid real collision hooks, native acceptance
and rejection, ID results, human/bot trace equality, capacity/line bounds, hurry
and bomb blockers, complete line hazard publication, nonfinite positions and
rejected long-fuse RNG preservation. Original and permitted code fixtures are used;
no reference media or redistributed extracted art is claimed by these tests.

Human/bot equivalence uses a human-marked ServerPlayer through actual authority
packet dispatch and a bot-marked actor through direct authority calls. Negative
fixture peer IDs avoid sending RPCs to nonexistent peers. This proves dispatch
semantics, not an authenticated remote match or browser transport.

The required merge gate runs the complete discovered native suite. The Godot
workflow additionally runs the focused suite at FPS caps 30/60/144. Accepted
head/base/run IDs and final results belong in #448 and its PR; diagnostic fixtures
and old-source failures remain distinct from passing candidate validation.
