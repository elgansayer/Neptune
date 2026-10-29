# Gameplay protocol negotiation

Issue #460 implements the network portion of SIM-015/#108. This is a Neptune
compatibility contract; it makes no Saturn/Power fidelity claim.

`shared/network/protocol_negotiation.gd` configures the actual SceneMultiplayer
owned by ClientMain/ServerMain before attaching their transport. Its authentication
phase withholds RPC traffic and `peer_connected` until both ends complete. Account
authentication remains a later, separate operation. The current local backend is
still temporary in-memory authentication, not production identity/security.

Each end sends one reliable, ASCII JSON offer:

```json
{"format":"neptune.protocol/1","versions":[1]}
```

Both ends select the highest intersection of their implemented versions. Product
support is currently **only version 1**, using the pinned Godot 4.5 native wire
protocol and existing RPC signatures. A version may be advertised only when its
actual message semantics are implemented. The tests use extra version numbers to
exercise selection; this does not make those versions supported product codecs.

The bootstrap format has exactly two fields. Offers are at most 1024 received
bytes, with one to eight distinct positive integral version numbers in 1..65535.
Unknown formats, fields, malformed/non-ASCII bytes, booleans, duplicates, fractions
and out-of-range values fail. JSON numbers may arrive as integral floats; they are
checked before conversion. Object decoding stays disabled. No legacy fallback or
protocol translation is implemented.

Pending authentication expires after three seconds. An incompatible/invalid offer
never completes authentication. Its sender stays pending until timeout/disconnect,
allowing already-sent offers to arrive so the other endpoint can report its own
compatibility reason. Immediate disconnect originally raced delivery of the
server offer and hid the reason from ClientMain; the real integration probe caught
this. Repeated packets cannot change a rejected handshake into an accepted one.

The client records `negotiated_protocol` only after mutual completion and emits
`connection_succeeded` afterward. It records `last_connection_error` and the login
screen explains incompatibility, unsupported protocols and timeouts. Connection
attempt/failure/disconnect clears pending map data as well as authentication/version
state. A native regression reproduces stale map data at failure before the fix.
Selection records are removed on peer failure/disconnection. The server disables
client-to-client relay: all game traffic goes through the authority.

The gate depends on SceneMultiplayer's auth API and byte buffers, not ENet-specific
flush calls. Existing native transport remains ENet. WebRTC/browser transport,
signalling/TURN, content/ruleset locks and cross-play are still separate acceptance
work. An application protocol agreement does not certify matching content or
arbitrary Godot engine versions.

## Verification

`tests/test_protocol_negotiation.gd` executes parser/configuration boundary cases
in the pinned native runtime. Required `tools/godot/check_runtime.py --graphical`
also starts the actual ServerMain and default/explicit headless plus graphical
ClientMain processes, requires version selection before ping/pong, checks the
production client's incompatibility message and sends untrusted network offers.
Rejected/silent probes must not produce server `peer_connected`. The supervisor
retains both client and server logs and fails on missing evidence, logged errors,
timeouts and nonzero exits. Existing bind/configuration/startup negatives remain.

This does not close #108: there is no campaign checkpoint implementation to migrate
yet. Save schema compatibility, explicit migrations on copied saves and pack/runtime
lock validation remain part of #35/#43/#53/#54 and #108. Existing map JSON is content,
not a campaign save. Native spawn-reservation snapshots already have their own
`neptune.spawn-reservations/1` format and strict matching-layout checks; protocol
negotiation neither migrates them nor silently upgrades saves.

Primary API semantics: [Godot 4.5 SceneMultiplayer](https://docs.godotengine.org/en/4.5/classes/class_scenemultiplayer.html).
