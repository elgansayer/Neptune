# Initial-round bot filling

Issue #469 implements the first slice of #31. Hosted casual rooms now default
to a total of four reserved participants, capped by the selected map, room and
preset capacity. A single human therefore starts with three `BALANCED` bots in
a four-seat room. The server provisions them at the initial countdown boundary;
no client debug command is needed. A trusted server operator can override the
total reserved-participant target:

```sh
"$GODOT" --headless --path . res://main_server.tscn -- \
  --room-map=res://maps/neptune_twelve.json --room-seats=12 \
  --room-fill-to=12 --room-bot-personality=DEFENSIVE
```

`--room-fill-to=0` disables automatic additions. Other explicit values
must be integers 1..12 within the actual room/map/preset capacity. This is a
minimum initial target, not a limit on human admission or a fixed bot count.
Only the omitted four-participant default is capped to smaller rooms; an explicit
target above capacity is still an error. Omit `--room-bot-personality` to use
`BALANCED`, or select a supported existing personality explicitly.
Existing humans, bots and retained human reservations all count toward it.
Invalid/duplicate/missing options or unsupported personality names fail before
listening. The exact existing BotManager personality names are supported; unknown
names do not silently select BALANCED. Personality is not a new difficulty mode.

The first human starts the existing countdown. Immediately before its initial
activation, the authority revalidates room geometry and provisions only missing
seats through the production bot admission/controller path. Humans joining during
the countdown count before filling; no human is evicted. A retained identity keeps
its seat even when its actor is absent. A controller/provisioning refusal blocks
activation and rolls back the batch's new actors, reservations, controllers,
observation views, RNG streams and ID counter. Old exit callbacks complete before
IDs can be reused by an immediate retry. Existing participants are preserved.

Policy configuration is immutable after admission/countdown. Fill occurs once:
it does not top up a live match after death/disconnect, implicitly restart a
finished round, evict a bot for an arriving human, or take over a disconnected
human. A full room still refuses a new identity. Explicit next-round replacement,
reconnect grace/expiry and takeover remain separate lifecycle work under #31/#100/#128.

Bots retain the accepted public-observation and bound-command interfaces. They
start with the same actual actor inventory and movement stats as humans. The
selected existing personality configures its current reaction/planning/tactics;
this change does not claim tuned difficulty, faithful Saturn CPUs or improved
win/survival rates. No external model call runs in a match tick.

Room metadata adds detached `bot_fill: {target, personality, applied}` and
`participants: {peer_id: {type, personality}}`. IDs remain strings for portable
JSON. Actual participant type is explicit even though movement snapshots remain
compact. The existing bot policy version and match seed remain recorded; private
RNG state and hidden item data are not added. This is public runtime metadata,
not persistent stats, ranked eligibility or a player-facing roster UI.

`tests/test_room_bot_fill.gd` uses actual native actors/controllers and a fixture
that injects one structured provisioning refusal after successful real spawns.
`tools/godot/check_room_capacity.py` retains previous native capacity scenarios
and checks automatic 4/12-seat starts, omitted-target four/two-seat starts,
explicit zero, explicit participant metadata, zero spawn-bot RPCs, extra-human
refusal and invalid startup policy rejection. They do not prove
browser transport, full rounds, held-out quality, latency/load budgets, host UI,
human replacement or persistent ranked history. #31 remains open.

## Client participant display

The in-game HUD consumes the authority's `room.participants` metadata. Bot faces
show a visible `BOT` badge; their tooltip includes the configured personality.
Names and negative peer IDs alone never identify a bot. The roster supports the
protocol maximum of twelve faces in two rows of six, retains scores and removes
faces absent from the next player snapshot. Slot reuse refreshes participant
identity rather than retaining a departed bot's label.

`tests/test_participant_hud.gd` instantiates the actual HUD scene and checks badge
identity, tooltip personality, score refresh, snapshot removal, slot reuse and
layout bounds for twelve participants. These headless checks do not establish
visual polish, browser rendering, difficulty selection or safe human replacement.

## Hosted subsequent rounds and human seats

Hosted casual repeat play now uses a fresh authority per round, as described in
[ROOM_LIFECYCLE.md](ROOM_LIFECYCLE.md). Filling remains initial-only within each
authority. Connected humans and waiting spectators receive next-round seats
before that authority fills missing seats with the existing production bots.
This implements the bounded casual late-join and bot-seat replacement policy;
ranked takeover, reconnect grace and persistent reservations remain separate.
