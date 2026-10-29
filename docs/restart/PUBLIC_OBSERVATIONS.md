# Public arena observations

Issue #452 implements schema1 public arena snapshots and integrates them into the
native LimboAI policy. This is an engine interface for the current globally visible
arena. It is not a downloaded-script sandbox, packet protocol or complete mod API.

`GameInstance.get_public_observation(registered_peer_id)` produces a detached,
JSON-compatible dictionary. Human and bot roles share the same visibility; only
`viewer_id` differs. Unknown viewers receive an invalid result without arena data.
Terrain, visible players, exposed pickups, eggs/mounts, active flames and public
bomb state are selected explicitly. Covered pickups, opponent input buffers,
privately sampled fuses, policy/drop RNG state and future hurry paths are omitted.
Public fuse lower bounds and elapsed time remain available without sampling again.

`shared/observations/queries.gd` answers tile occupancy using this data. It keeps
entity presence separate from movement blocking, including actual collision masks,
bomb overlap exceptions, carried/thrown bombs and airborne bomb records. Negative
coordinates use floor division. Out-of-bounds terrain is blocked. This is current
engine occupancy, not continuous swept collision, navigation or a safety proof.

The manager shares one capture source and creates per-participant observation
worlds. Native tree agents are observed actor nodes; public entity records contain
no authority actor references. Existing grid, threat and opponent components read
these views. Exported dictionaries copy nested data. Supported getter and command
methods provide the intended policy interface; trusted GDScript still has engine
reflection and scene-tree access. Never execute arbitrary community GDScript on
this basis. Future portable content engines can use the data/query interface.

Commands bind to the original actor identity, not just a reusable peer ID. They
pass through the same `submit_player_command` validation as human intent. Movement
and throw-facing wait for real player physics; policy tasks do not snap authority
positions or write its facing. Debug paths stay local to the observed agent.

Unknown terrain/bomb identifiers or exhausted observation budgets explicitly mark
bot support false. The manager disables native decisions and submits neutral input.
Known built-in IDs are not certification that every special hazard is predicted
correctly. More mechanics require explicit capability support and runtime cases.

Captures refresh at simulation tick/time changes, child changes, public commands
and explicit perception refreshes. Direct authority edits in fixtures must invalidate
or force refresh. The API does not alter compact network packets or claim equal
human/bot transport latency, browser cross-play or fog-mode visibility. Per-observer
opponent-profile quality, room fill, held-out evaluation and pack registries remain
separate tasks.

Native acceptance and timing evidence will accompany the implementation PR. Frozen
12-actor decision samples are measurements on this host, not room-capacity proof.
