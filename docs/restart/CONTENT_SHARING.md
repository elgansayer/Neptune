# Automatic native room-content sharing

This PACK-005 slice connects the existing exact manifest locks and
[verified cache](PACK_CACHE.md) to the production `ClientMain`/`ServerMain` join
flow. It delivers a clean native-client arena journey. Browser transport, server
discovery and propagation of a player's chosen avatar remain separate work.

## Hosting and joining

Host an existing additive arena selection, for example:

```sh
godot --headless --path . res://main_server.tscn -- \
  --room-pack=res://demo/packs/linked/manifest.json \
  --room-pack=res://demo/packs/wide/manifest.json \
  --room-pack=res://demo/packs/standard/manifest.json \
  --room-arena=example.linked:arena --room-seats=4 --room-fill-to=4
```

The ordinary native client's login flow downloads the selected packs automatically.
It shows download progress and offers cancellation. Verified cached archives are
reused on a later join. A failed/cancelled download offers an explicit retry;
an interrupted archive never becomes ready. Non-pack rooms keep their existing
join flow and default content.

The server packages the complete selected arena manifest set before listening.
Unsupported or invalid payloads refuse startup. It never accepts filesystem paths
or download URLs from joining peers. Current room adapters are arena-only;
the storage format also validates character packs for later avatar integration.

## Admission and transfer

Gameplay protocol **2** adds the reliable `content_message(Dictionary)` RPC.
The bootstrap envelope remains `neptune.protocol/1`; its supported gameplay
version list is `[2]`. Version 1 clients are rejected explicitly before RPC
admission because their method table and readiness contract differ.

After account authentication, a pack-room peer receives an offer with a fresh
session nonce, the exact canonical lock/hash, chosen content ID, and archive
identities, digests and byte sizes in lock order. It has no actor, map, spawn
reservation or gameplay snapshots yet. Pending transfers count against admission
capacity, with at most 12 pending peers. The initial countdown pauses while any
accepted transfer is pending; late transfers never freeze an active match.

The production client revalidates cache hits or pulls sequential 16 KiB chunks
over the existing reliable ENet RPC transport. Limits are 32 packs and 32 MiB
total offered archive bytes per room, with a 30-second transfer deadline on both
sides. Strict message shapes, offsets, sizes and session binding reject stale,
malformed or unexpected traffic. Cancellation, timeout, disconnect or failure
releases the pending hold without admitting a player.

After all archives pass installation, the client loads the chosen arena through
the existing runtime adapter with the expected complete lock. Only then does it
send readiness bound to the offer's session nonce and lock hash. The authority
validates this acknowledgement before normal player admission and countdown.
An initial map is checked against the verified selection, dimensions and terrain
budget before reaching the view. Live terrain remains server-authoritative because
blocks may already have changed when a player joins.

A warm client can acknowledge a verified lock without requesting chunks. This is
a compatibility acknowledgement, not remote proof that a hostile client possesses
files. Ownership/signatures, general capability negotiation, workshop moderation,
browser caching, resumable byte offsets and HTTP/CDN distribution are follow-ups.
Retries restart unfinished archives and preserve independently verified entries.

## Client integration

`ClientMain.content_status_changed(result)` reports downloading/ready/failed state,
received/total bytes, cache hits, pack count and lock hash.
`ClientMain.last_content_result` is detached. `cancel_content_download()` abandons
the transient transfer; another login can retry. Disconnect/reconnect clears the
session selection while preserving immutable cached releases.

`shared/network/content_download.gd` supplies the same coordinator to native
room probes. Its `outbound` signal carries request/ready/cancel messages, while
`begin`, `receive`, `tick` and `cancel` enforce the local state machine. The server
remains responsible for account authentication, bounded pending slots and admission.

## Executable evidence

```sh
python3 tools/godot/check_runtime.py --godot /absolute/path/to/godot --content-only --evidence /tmp/neptune-sharing-evidence
python3 tools/godot/check_runtime.py --godot /absolute/path/to/godot --room-only --evidence /tmp/neptune-room-evidence
python3 tools/godot/run_bot_tests.py --godot /absolute/path/to/godot --run-specific test_content_sharing --timeout 30
```

The required native runtime gate always runs the sharing journeys. Original
fixtures live only in the authority's isolated user directory, with different
client profiles and independently calculated Python manifest/lock/map hashes.
Cases cover a cold join, warm reuse, another server's lock with a shared dependency,
return to the first lock, first-chunk cancellation and clean retry, and wrong-lock
readiness refusal. Each connection uses a fresh production client process, reusing
the same cache profile for cache/switch cases; authorities restart between phases.
This does not exercise a live server-picker UI. Successful clients receive a reliable initial map and active
mixed human/bot snapshots through actual `ClientMain`. Failed clients must receive
neither admission nor gameplay. Focused tests cover malformed messages, corrupted
content, cache boundaries and countdown holds. These are native transport and
creator-system results; no browser or Saturn fidelity result is claimed.
