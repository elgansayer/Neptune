# Delivered explosion presentation

[#560](https://github.com/elgansayer/Neptune-Bomberman/issues/560), a bounded
[#284](https://github.com/elgansayer/Neptune-Bomberman/issues/284) slice, fixes the
client's treatment of delivered explosion events. The server sends one new
explosion in a state packet, not the complete set of active visuals. Consecutive
batches now coexist, and an empty/absent batch cannot delete another effect.
Server damage, gameplay timers and source constants are unchanged.

## Timing and lifetime

The first rendered sample uses the publishing snapshot's room simulation time:

`initial_age_seconds = server_time_msec / 1000 - event.start_time_seconds`

Missing, nonfinite, negative, boolean or future timing is refused before creating
the event. Valid delivered events start at their existing expansion/size phase,
including late observations after the final size phase begins. Subsequent local
presentation advances through physics `delta`, so local pause/time scaling no
longer depends on process uptime. This continuation remains an approximation
between authoritative snapshots. The client does not estimate transport delay,
measure a server/client clock offset or infer remote pause/rate changes.

Existing Neptune visual values remain `0.02` seconds per expansion length,
`0.15` per size phase and a strict minimum age greater than `0.8` before cleanup.
An effect also has to finish expanding. Thus a length-127 pattern remains eligible
until its growth boundary near `2.54` seconds; it must not be pruned as a short
effect. These values are not newly measured Saturn timings. Rendering samples
clamp to the useful phase/length before integer conversion, including very large
finite timestamps or deltas.

## Delivery identity and lifecycle

`client/explosion_event_timeline.gd` observes valid snapshot headers even when no
events are included. A non-increasing `simulation_tick` or decreasing
`server_time` cannot introduce effects. This guard applies only to effect intake;
the existing actor and map-delta processing still runs. It does not repair the
transport's overall snapshot consistency.

Within the current timeline, an accepted bomb ID is remembered after its renderer
self-expires. Repeated events do not reset phase, recreate visuals or redispatch
the linked bomb's sound. A changed start time for an ID still remembered or active
is refused as a conflicting event. Identities are pruned only after a newer
accepted snapshot proves the original event has finished under the existing
growth/lifetime rule and its renderer is no longer active. Already-expired events
are refused even after their tombstone has been pruned.

The retained identity budget is 256. New events are refused at the limit rather
than evicting a replayable identity. A newer snapshot can release expired entries.
Event batches are bounded to 256 entries and each fully validated pattern to 509
tiles, matching center plus four 7-bit directional lengths in the existing compact
format. Packed coordinate/data ranges, shape, directions, flags and duplicate
positions are checked. Legacy events preserve integer coordinates and the same
seven direction names. Malformed individual events have no renderer, audio or
tombstone side effects; valid siblings can still be accepted. This intake is not
a new public content API.

Renderers remove their own dictionary entry on tree exit. Cleanup checks instance
identity, so an old node cannot delete a newer same-ID node. A new GameView starts
a fresh timeline. A lifecycle owner deliberately reusing a view must call
`reset_explosion_timeline()` as part of its explicit room/replay reset; the method
removes existing effect nodes and clears event/clock history. A decreasing network
clock never guesses that a new room began. No wire epoch or automatic room-switch
mechanism is introduced here.

## Evidence and remaining work

The focused native suite instantiates the production GameView scene using the
existing `arena_view_fixture` to omit network/debug setup. It exercises actual
renderer/segment nodes, late phase selection, wall-pacing independence, additive
compact/legacy batches, stale headers, self-expiry, long patterns, replay
tombstones, explicit reset, malformed inputs and resource bounds. Sound assertions
count the existing linked-bomb dispatch through a test receiver; they do not
measure playback samples or audio hardware.

```sh
python3 tools/godot/run_bot_tests.py --godot /path/to/pinned/godot \
  --run-specific=test_explosion_timeline --timeout 120 \
  --log work/explosion-timeline-native.log
```

The server still sends a one-shot event over unreliable state transport. Lost
events remain possible; no acknowledgement/retransmission service is added.
Compact start times still have centisecond quantization. The existing linked-bomb
audio path can still be absent if its bomb node is unavailable, and delivered
sounds are not sample-scheduled. Actual Saturn clock recovery, exact visual/PCM
comparisons, reliable event delivery and full room/replay epoch negotiation remain
separate work under the [fidelity contract](SATURN_FIDELITY.md).
