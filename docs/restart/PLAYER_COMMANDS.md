# Common authority commands

Issue #450 implements the remaining server-side SIM-004/#91 command boundary on
#449's placement guard. These are Neptune rules and APIs, not measured Saturn or
Power fidelity. Godot remains the single gameplay authority.

Human input follows the RPC sender's existing peer mapping into
`GameInstance.handle_player_input(peer_id, packet)`. Native actor helpers delegate
to `GameInstance.submit_player_command(peer_id, command)` after verifying that the
helper object itself matches the roster. Supplying another actor's peer ID on an
unregistered helper cannot control that actor. The command gateway is trusted
server code, not a new RPC or community scripting API.

## Inputs and actions

Packets accept only `input_x`, `input_y`, `place_bomb`, `action_pressed` and
`action_released`. Missing axes default to zero; missing edges default to false.
Axes must be finite int/float values in [-1,1], never booleans, strings or objects.
Flags must be actual booleans. Unknown keys or malformed values reject the
entire packet before movement, ability, bomb or RNG effects. A legitimate
same-tick press/release acts once, then releases; it is not discarded. Godot
[documents rapid same-tick input edges](https://docs.godotengine.org/en/4.5/classes/class_input.html#class-input-method-is-action-just-pressed),
and the runtime regression produces both with the actual Input singleton. Client positions,
speeds, durations, inventory and arbitrary instructions are not accepted fields.
Diagonal intent keeps the existing four-way tie rule and physics speed.

Direct commands use `action` plus the following fields:

| Action | Extra fields | Existing authoritative operation |
| --- | --- | --- |
| `move` | `x`, `y` (default zero) | Validated intent; actual collision remains in physics |
| `place_bomb` | none | Shared [placement guard](BOMB_COMMANDS.md), including line/capacity/fuse rules |
| `pickup_bomb` | string `bomb_id` | Tracked local planted bomb on the actor tile; requires glove |
| `throw_bomb` | none | Actor's actual carried bomb, valid carrier and facing; requires glove |
| `mount_action` | none | Actor's mounted production controller and unchanged 0.5-second cooldown |
| `detonate_remote` | none | Oldest owned planted remote bomb; requires equipped remote type |
| `action_press` | none | Existing mounted/glove/remote context, with explicit outcome |
| `action_release` | none | Clear held action state |

Unknown commands and extra fields fail. Commands require a registered actor from
this authority. Gameplay actions require a living actor and active match. Neutral
movement and release remain available for cleanup after death/end. Actual player
physics also stops normal movement outside the active phase, including old held
intent. Existing speed, four-way movement, collisions, fuse sampling, throw arcs,
mount cooldown and remote ordering are retained.

The Space/placement button supplies glove place/pickup/throw context when unmounted.
Both glove button edges in one frame coalesce to one action. Mounted action and
Space placement remain separate. This fixes the old handler ignoring Space with
a glove despite the client's documented controls. No new inventory is granted.

Kicking is ordinary validated movement into a real bomb with the existing kicker
ability/contact check. There is no privileged kick command that directly moves a
bomb. The native kick task now uses the actual two-argument input API and records
an attempt only when movement is accepted. Native glove and buffered-input tasks
also honour rejection. Pickup/throw boolean helpers preserve compatibility while
`last_command_result` exposes the detailed result.

## Outcomes and atomicity

Results contain `accepted`, `reason`, `action` and `bomb_ids`. Examples of rejection
reasons include `unknown_player`, `foreign_player`, `invalid_movement`,
`unknown_field`, `invalid_action_flag`, `match_inactive`,
`dead_player`, `ability_unavailable`, `unknown_bomb`, `foreign_bomb`, `not_on_bomb`,
`not_carrier`, `invalid_direction` and `cooldown`. Placement reasons retain #449's
contract. No private sampled fuse or opponent input is returned.

Schema rejection applies no packet component. A well-typed frame can contain
independent movement and button actions; it reports `movement` and every `actions`
outcome, including partial success. Its top-level rejection does not hide an
accepted separate action. Per-command rejection leaves gameplay state unchanged;
recording its detached diagnostic result is intentional, not a gameplay effect.

Player queueing validates and copies packets before buffering. The actual native
buffer reader revalidates, so direct buffer injection cannot bypass the boundary.
`buffered` is receipt, not acceptance of a future action. Sequence/replay freshness
and network ACK delivery remain separate protocol work: the current network router
still discards local results. This change does not establish authenticated remote
matches, browser cross-play or complete replay determinism.

## Runtime evidence and remaining work

The new suites use real authority/actors/bombs, native LimboAI tasks, actual physics
contact and the production mount controller with original solid-colour animation
fixtures. They cover malformed packets, membership/impersonation, phase/death,
availability, pickup/throw ownership, real remote expansion, mount cooldown,
buffer alias/injection, physical kick gating and human/native action traces.
Original source yields one valid movement control and seven behavioural failures;
the native kick branch separately logs its genuine argument-count error. The
helper identity regression was also reproduced before its guard.

RNG/refuge/publication fixtures establish an active match before nonneutral intent;
physics remains frozen where the original experiment requires it. Existing hazard,
movement, timing and RNG assertions/tolerances are retained. Kick fixtures clear
the real owner-overlap exception through movement before returning to contact.

The full discovered native suite and real headless/graphical startup checks remain
mandatory, tied to exact head/current base. Accepted results/run IDs belong in
#450 and its PR. Public observations/observer-specific intel (#92/#30), advanced
hazards, room fill/evaluation, portable pack/profile APIs and complete campaigns
remain separate. The shared tile/physics contracts used here have runtime tests;
this does not claim all of SIM-006/#90's future mod query interface is complete.
