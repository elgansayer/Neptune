extends RefCounted

## Presentation-only intake. These bounds describe resources/the existing wire,
## not recovered Saturn timing, reliable delivery or a synchronized client clock.
const Renderer = preload("res://client/ui/explosion_renderer.gd")
const MAX_SEEN_EVENTS := 256
const MAX_PATTERN_TILES := 509 # Center plus four 7-bit directional lengths.
const DIRECTIONS := ["middle", "up", "down", "left", "right", "vertical", "horizontal"]

var last_tick := -1
var server_time_msec := -1.0
var seen := {}
var last_rejection := ""


func reset() -> void:
	last_tick = -1
	server_time_msec = -1.0
	seen.clear()
	last_rejection = ""


func observe_snapshot(tick: Variant, time_msec: Variant, active: Dictionary) -> bool:
	if not tick is int or tick < 0 or not _finite_number(time_msec) or time_msec < 0:
		return _reject("invalid_snapshot_clock")
	if tick <= last_tick or time_msec < server_time_msec:
		return _reject("stale_snapshot")
	last_tick = tick
	server_time_msec = float(time_msec)
	last_rejection = ""
	# An effect may be locally paused or still expanding. Never drop its identity
	# merely because another event batch or a newer snapshot has arrived.
	for id in seen.keys():
		var event: Dictionary = seen[id]
		if not active.has(id) and Renderer.has_finished_age(server_time_msec / 1000.0 - event.start_time, event.max_length):
			seen.erase(id)
	return true


func decode_compact(batch: Variant) -> Array:
	var events: Array = []
	if not batch is Array or batch.size() > MAX_SEEN_EVENTS:
		_reject("invalid_event_batch")
		return events
	for entry in batch:
		if not entry is Array or entry.size() != 5 or not entry[0] is int or not entry[1] is int or not entry[2] is Array or not entry[4] is int or entry[4] < 0:
			_reject("invalid_compact_event")
			continue
		var tiles: Array = []
		var valid: bool = not entry[2].is_empty() and entry[2].size() <= MAX_PATTERN_TILES
		if valid:
			for tile in entry[2]:
				if not tile is Array or tile.size() != 2 or not tile[0] is int or not tile[1] is int or tile[0] < 0 or tile[0] > 0xffff or tile[1] < 0 or tile[1] > 0x6ff:
					valid = false
					break
				var packed_position: int = tile[0]
				var packed_data: int = tile[1]
				tiles.append({"grid_pos": {"x": (packed_position >> 8) & 0xff, "y": packed_position & 0xff},
					"direction": DIRECTIONS[(packed_data >> 8) & 0x07],
					"length": (packed_data >> 1) & 0x7f, "is_end": (packed_data & 1) == 1})
		if not valid:
			_reject("invalid_compact_pattern")
			continue
		events.append({"bomb_id": entry[3], "pattern": tiles, "start_time": float(entry[4]) / 100.0})
	return events


func accept_event(event: Variant, active: Dictionary) -> Dictionary:
	if server_time_msec < 0:
		return _refusal("missing_snapshot_clock")
	if not event is Dictionary or not event.get("bomb_id") is String or event.bomb_id.is_empty() or event.bomb_id.length() > 128:
		return _refusal("invalid_event_identity")
	if not _finite_number(event.get("start_time")) or event.start_time < 0 or event.start_time > server_time_msec / 1000.0:
		return _refusal("invalid_event_time")
	var pattern: Variant = event.get("pattern")
	if not pattern is Array or pattern.is_empty() or pattern.size() > MAX_PATTERN_TILES:
		return _refusal("invalid_event_pattern")
	var positions := {}
	var max_length := 0
	for tile in pattern:
		if not tile is Dictionary or not tile.get("grid_pos") is Dictionary or not tile.grid_pos.get("x") is int or not tile.grid_pos.get("y") is int or not tile.get("length") is int or tile.length < 0 or tile.length > 127 or not tile.get("direction") in DIRECTIONS or not tile.get("is_end") is bool:
			return _refusal("invalid_event_tile")
		var position := Vector2i(tile.grid_pos.x, tile.grid_pos.y)
		if positions.has(position):
			return _refusal("duplicate_event_tile")
		positions[position] = true
		max_length = maxi(max_length, tile.length)
	var id: String = event.bomb_id
	if seen.has(id) or active.has(id):
		return _refusal("duplicate_event" if seen.has(id) and seen[id].start_time == event.start_time else "conflicting_event_identity")
	var age := server_time_msec / 1000.0 - float(event.start_time)
	if Renderer.has_finished_age(age, max_length):
		return _refusal("expired_event")
	if seen.size() >= MAX_SEEN_EVENTS:
		return _refusal("event_budget_exceeded")
	# Record only fully validated accepted events. No partial-pattern tombstones.
	seen[id] = {"start_time": float(event.start_time), "max_length": max_length}
	last_rejection = ""
	return {"accepted": true, "bomb_id": id, "start_time": float(event.start_time),
		"age": age, "pattern": pattern.duplicate(true)}


static func _finite_number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))


func _reject(reason: String) -> bool:
	last_rejection = reason
	return false


func _refusal(reason: String) -> Dictionary:
	_reject(reason)
	return {"accepted": false, "reason": reason}
