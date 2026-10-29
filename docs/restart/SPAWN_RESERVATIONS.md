# Authoritative spawn reservations

Issue #458 supplies the engine-admission part of #100, needed by room capacity
#121 and bot filling #31. It is not the complete room, reconnect or protocol work.

GameInstance.add_player returns a structured admission/refusal and creates an
actor only after reserving a declared centered spawn. ServerBotManager uses the
same path and creates its real native controller/RNG stream only after admission.
ServerMain records game membership only after acceptance. add_child completes the
actor's current synchronous _ready; admission no longer leaves a coroutine waiting
one process frame just to print its success message.

Slots must be declared in the map, distinct, within bounds, on empty terrain and
have an empty cardinal neighbor. This means an actor can leave its starting cell;
it does not require all opponents to share an initially empty connected component,
since destructible walls can intentionally separate Bomberman starts. Capacity
preflight reports insufficient geometrically supported starts; live admission also
checks the current exit is clear of blocking bombs/fire. Current player/bomb hitboxes and
active flames exclude occupied starts, including fractional overlap across tile
edges. This is start geometry/current occupancy, not a future-hazard or safe
mid-round-join guarantee. Round-boundary admission still belongs to #31.

A participant key owns its reservation. Duplicate peer/key admission fails before
roster mutation. An explicit position must match a supported declared slot; there
is no modulo wrap or fallback position. Normal removal releases the key; trusted
remove_player(peer, true) retains it for a later peer rebind. Explicit unbound-key
release and empty-roster reset support future coordinator policies. Retained keys
have no automatic network/grace policy here and are not enabled by disconnect RPCs.
Never interpret this native API as completed authenticated reconnect behaviour.

spawn_seed and a stable SHA-256 ordering choose among available starts without
using gameplay/policy RNG. Equal layout, seed and ordered admissions reproduce the
allocation; changing arrival order can legitimately change remaining availability.
Clients consume authoritative positions rather than competing local randomness.
Default identity is connection-local peer:<id>; a trusted caller can supply an
opaque stable participant ID. Current quick-start uses its authenticated username
identity; durable accounts and identity migration remain separate work.

get_spawn_reservation_state exports detached JSON data tagged
neptune.spawn-reservations/1, with string seed, layout digest and key-to-cell arrays.
Trusted restoration requires an empty roster, matching version/seed/layout and
valid distinct supported cells. Integral JSON numbers are accepted explicitly;
fractional, nonfinite, overflowing or incompatible values fail atomically. This
is reservation state only, not a full save, migration or negotiated wire protocol.
#108 owns those compatibility gates. No arbitrary downloaded code is involved.

The legacy get_next_spawn_point helper is a non-mutating debug preview returning
null when no supported slot exists. Debug spawn callers check refusal; respawn/reset
use each player's own reservation. Battle admission still uses the structured API.
Original runtime fixtures now declare their supported starts and admit bots at the
requested location. Intentional player overlap is produced through ordinary
movement, not duplicate spawn admission. Default four-spawn content is not silently
expanded to twelve; an original fixture may explicitly declare twelve valid starts.

Reference preset limits, twelve-seat room settings, authoritative round transitions,
client-visible admission UI, reconnect expiry/reservation ownership, protocol
negotiation and full native/browser sessions remain #121/#31/#108 and related work.
This interface neither closes those issues nor establishes Saturn/Power fidelity.
