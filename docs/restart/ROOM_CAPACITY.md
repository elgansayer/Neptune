# Room capacity and startup

ROOM-001/#121 separates three limits: application protocol supports twelve match
seats; the native server admits up to sixteen connected transport peers, including
people outside the room; a trusted preset/room may choose a smaller limit. Sixteen
connections is an initial bound, not a concurrent-hosting performance guarantee.
No particular Saturn/Power preset limit is inferred from this Neptune requirement.

Launch the original twelve-start geometry with the pinned native Godot binary:

```sh
"$GODOT" --headless --path . res://main_server.tscn -- \
  --room-map=res://maps/neptune_twelve.json \
  --room-seats=12 --room-preset-limit=12
```

`--room-seats` and `--room-preset-limit` accept integers 1..12. If seats are omitted,
the server explicitly chooses the minimum of supported starts, preset limit and
protocol limit. An explicit seat request is never reduced silently. Duplicate or
invalid options fail with exit 2. The optional map selection is an installed local
`res://maps/*.json` resource; it is not a public upload/pack loader. An explicit
missing/invalid map never falls back to a different arena. Existing JSON terrain
numbers are validated and normalised to integer codes, matching spawn geometry.
Legacy code-bearing PCK loading remains outside the future portable pack interface.

ServerMain prepares the shared room after autoload initialization and validates
its requested map/seat combination before listening. Invalid combinations exit 2
without starting a countdown. Its first admitted human starts the one-second
countdown. Repeated joins do not reset it, and final geometry is rechecked before
activation. A finished round cannot implicitly restart; next-round lifecycle and
safe human/bot replacement remain #31. The separate
[initial-round bot-fill policy](ROOM_BOT_FILL.md) now provisions missing seats at
this first activation boundary when the trusted operator explicitly enables it.

`GameInstance.configure_room_capacity(seats, preset_limit)` validates integral
inputs, protocol/preset limits and actual supported map starts. Active/counting-down
rooms, actors or retained reservations prevent reconfiguration. Admission counts
humans, bots and retained identities against the same capacity. Full rooms refuse
before creating an actor/controller or consuming a bot identity/RNG stream. A
reserved identity can rebind to its own seat; a new participant cannot steal it.
Snapshot restoration also rejects reservations exceeding the configured limit.
This uses the native reservation API; authenticated network grace/expiry remains
#100 and is not implemented by this capacity check.

Authentication responses report success only after authoritative admission.
Room-full responses use `success:false,error:room_full`; refused peers receive no
map/state and acquire no game/lobby membership. Authentication storage remains the
temporary in-memory backend, separate from production identity work.

Initial map and regular snapshots include detached `room` metadata: protocol and
transport limits, seats, preset limit, configured status, occupied/reserved counts,
human/bot counts, bot policy version and match policy seed. Seeds are strings to
preserve integer identity. These are optional additions to the existing v1 state
dictionary; RPC signatures and the pre-connection negotiation contract are unchanged.
They do not provide persistent participant history or trusted stats yet.

`maps/neptune_twelve.json` is original Apache-2.0 geometry, with twelve declared
starts and no extracted artwork/audio. It is a capacity fixture and usable local
arena, not a claim of reference fidelity or final competitive balance.

## Runtime evidence

`tests/test_room_capacity.gd` exercises real actors/controllers, bounds, smaller
presets, retained identities, atomic restore, map refusal and countdown behavior.
Required `tools/godot/check_runtime.py --graphical` retains prior connection/protocol
checks and adds actual ServerMain room tests through
`tools/godot/check_room_capacity.py`:

- Twelve independently authenticated native network clients plus a refused thirteenth.
- Six authenticated human clients plus six server bots and a refused extra human.
- Four clients in a four-seat preset, with protocol maximum still twelve, plus refusal.
- Actual initial maps, full rosters, metadata and round activation for every admitted
  human; source policy version/seed retained in receipts.
- A four-start map requested for twelve fails before listening; invalid/duplicate
  capacities fail nonzero.

Each multi-client probe uses independent SceneMultiplayer/ENet peers in one bounded
native process and the shared RPC interface. ServerMain performs actual auth,
admission, physics, bot creation and publication. This does not represent twelve
rendered game clients or a complete round, browser cross-play, held-out bot quality,
multiple-room load, host UI, matchmaking, ranking or workshop
acceptance. Those requirements remain in their respective issues.
