extends RefCounted

## Public, conservative bomb predictions. A lower fuse bound is never treated
## as an exact sampled fuse. Unknown expiry stays lethal until observed clear.
static func build(game: Node, sampler, now_msec: float, hypothetical: Dictionary = {}) -> Dictionary:
	return build_timeline(game, sampler, now_msec, hypothetical).deadlines

static func build_timeline(game: Node, sampler, now_msec: float, hypothetical: Dictionary = {}) -> Dictionary:
	var result := {"deadlines": {}, "intervals": {}, "uncertain": []}
	if game == null or sampler == null:
		return result
	for key in game.active_explosion_tiles:
		var expiry := float(game.active_explosion_tiles[key])
		if expiry >= now_msec:
			_add(result, key, now_msec, expiry)
	var observations: Array[Dictionary] = []
	for bomb in game.bombs.values():
		if not is_instance_valid(bomb):
			continue
		var observation: Dictionary = bomb.get_forecast_observation()
		observation["already_exploded"] = bomb.has_exploded
		var observed_state := int(observation.get("state", 0))
		if bomb.has_exploded and observed_state not in [ServerBomb.BombState.THROWN, ServerBomb.BombState.CARRIED]:
			# Progressive fire can still reach cells not burning in this frame.
			# The public observation has no private expansion cursor: retain the
			# entire remaining cross conservatively until this actor disappears.
			var growth_step := maxf(ServerBomb.EXPLOSION_GROWTH_INTERVAL, 1.0 / Engine.physics_ticks_per_second)
			var latest: float = now_msec + (GameConfig.EXPLOSION_DURATION + (int(observation.range) + 1) * growth_step + 2.0 / Engine.physics_ticks_per_second) * 1000.0
			for raw_cell in observation.get("blast_cells", []):
				var cell := Vector2i(int(raw_cell[0]), int(raw_cell[1]))
				_add(result, _key(cell), now_msec, latest)
			continue
		observations.append(observation)
	if not hypothetical.is_empty():
		observations.append(hypothetical)
	var deadlines: Array[float] = []
	var latest_times: Array[float] = []
	var blasts: Array = []
	var at_cell := {}
	for index in range(observations.size()):
		var observation: Dictionary = observations[index]
		var cell: Vector2i = observation.cell
		var earliest := now_msec + maxf(float(observation.fuse_lower_bound) - float(observation.elapsed), 0.0) * 1000.0
		earliest = minf(earliest, float(result.deadlines.get(_key(cell), INF)))
		var upper := float(observation.get("fuse_upper_bound", INF))
		if upper < float(observation.fuse_lower_bound):
			upper = INF # Inconsistent/missing public bounds cannot prove expiry.
		var latest := now_msec + maxf(upper - float(observation.elapsed), 0.0) * 1000.0
		var state := int(observation.get("state", ServerBomb.BombState.PLANTED))
		var kind := int(observation.get("bomb_type", 0))
		var receiver_cells: Array[Vector2i] = [cell]
		if kind == ServerBomb.BOMB_TYPE_REMOTE:
			earliest = now_msec # The owner can legally trigger it immediately.
			latest = INF
		var projected: Array[Vector2i] = project(cell, observation.range, sampler)
		if state == ServerBomb.BombState.THROWN:
			var flight: Dictionary = observation.get("flight", {})
			if flight.get("complete", false) and not flight.get("landing_cells", []).is_empty():
				projected = _landing_envelope(flight.landing_cells, observation.range, sampler)
				receiver_cells.clear()
				for raw_cell in flight.get("trajectory_cells", []):
					receiver_cells.append(Vector2i(int(raw_cell[0]), int(raw_cell[1])))
				# The timer is paused in flight and RESTARTS at landing. Reading
				# its pre-pickup elapsed value here would invent an early fuse.
				earliest = now_msec + float(flight.minimum_remaining_msec) + float(observation.fuse_lower_bound) * 1000.0
				latest = now_msec + float(flight.maximum_remaining_msec) + upper * 1000.0
				if bool(observation.get("already_exploded", false)):
					earliest = now_msec
					latest = now_msec + float(flight.maximum_remaining_msec)
			else:
				result.uncertain.append("unresolved_airborne_trajectory")
				earliest = now_msec
				latest = INF
		elif state == ServerBomb.BombState.CARRIED:
			# Future private throw direction is unknown. Include current-drop
			# geometry plus the four public current-origin throw choices. Nearby
			# intentional planting is separately refused by placement_capability.
			projected = _carried_envelope(observation, game, sampler)
			result.uncertain.append("unresolved_carried_choice")
			latest = INF
			if bool(observation.get("already_exploded", false)):
				earliest = now_msec
		elif state == ServerBomb.BombState.KICKED:
			# Kicks can stop at any earlier collision. Cover every possible
			# stopping cross along the observed direction, rather than pretending
			# that the bomb remains at its current tile. A chain can trigger it
			# anywhere along this corridor before its nominal fuse.
			earliest = now_msec
			projected = _kick_envelope(observation, sampler)
			result.uncertain.append("conservative_kick_envelope")
		elif state not in [ServerBomb.BombState.PLANTED, ServerBomb.BombState.LANDED]:
			# Movement/paused timer makes stationary fuse geometry incomplete.
			# Publish the gap instead of silently claiming exact prediction.
			result.uncertain.append("moving_or_carried_bomb")
			latest = INF
		for receiver in receiver_cells:
			earliest = minf(earliest, float(result.deadlines.get(_key(receiver), INF)))
		if kind == ServerBomb.BOMB_TYPE_REMOTE:
			earliest = now_msec
			latest = INF
		deadlines.append(earliest)
		latest_times.append(latest)
		blasts.append(projected)
		for receiver in receiver_cells:
			if not at_cell.has(receiver):
				at_cell[receiver] = []
			at_cell[receiver].append(index)
	# A later bomb's pattern is fixed only when it detonates. Earlier observed
	# bombs may remove its soft blockers first. Alternate conservative geometry
	# expansion and chain settling; neither operation can remove a known hazard.
	for pass_index in range(16):
		_settle_chains(deadlines, blasts, at_cell)
		if not _extend_future_geometry(observations, deadlines, latest_times, blasts, sampler):
			break
		if pass_index == 15:
			# Bound pathological terrain/chain interactions without truncating
			# hazards: use the larger all-soft-blocks-removed envelope.
			var cleared := {}
			var bounds: Vector2i = sampler.get_map_bounds()
			for x in range(bounds.x):
				for y in range(bounds.y):
					cleared[Vector2i(x, y)] = true
			for index in range(observations.size()):
				if int(observations[index].get("state", 0)) in [ServerBomb.BombState.PLANTED, ServerBomb.BombState.LANDED]:
					blasts[index] = project(observations[index].cell, observations[index].range, sampler, cleared)
			result.uncertain.append("conservative_terrain_envelope")
	_settle_chains(deadlines, blasts, at_cell)
	for index in range(observations.size()):
		var deadline: float = deadlines[index]
		var expansion_slack := ((int(observations[index].range) + 1) * maxf(ServerBomb.EXPLOSION_GROWTH_INTERVAL, 1.0 / Engine.physics_ticks_per_second) + 2.0 / Engine.physics_ticks_per_second) * 1000.0
		var expiry: float = latest_times[index] + expansion_slack + GameConfig.EXPLOSION_DURATION * 1000.0
		for cell: Vector2i in blasts[index]:
			_add(result, _key(cell), deadline, expiry)
	for key in result.intervals:
		result.intervals[key] = merge_intervals(result.intervals[key])
	return result

static func placement_capability(game: Node, sampler, cell: Vector2i) -> Dictionary:
	if game == null or sampler == null:
		return {"supported": false, "reason": "missing_projectile_observation"}
	for bomb in game.bombs.values():
		if not is_instance_valid(bomb):
			continue
		var observation: Dictionary = bomb.get_forecast_observation()
		var state := int(observation.get("state", 0))
		var unresolved: bool = state == ServerBomb.BombState.CARRIED or state == ServerBomb.BombState.THROWN and not observation.get("flight", {}).get("complete", false)
		var origin: Vector2i = observation.cell
		var radius := mini(8, maxi(4, int(observation.range) + ServerBomb.THROW_RANGE + 2))
		if unresolved and absi(origin.x - cell.x) + absi(origin.y - cell.y) <= radius:
			return {"supported": false, "reason": "unresolved_nearby_projectile_choice"}
	return {"supported": true, "reason": "observed_projectile_model"}

static func _landing_envelope(raw_cells: Array, radius: int, sampler) -> Array[Vector2i]:
	var found := {}
	for raw in raw_cells:
		var origin := Vector2i(int(raw[0]), int(raw[1]))
		if sampler.is_in_bounds(origin):
			found[origin] = true
		for direction: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			for distance in range(1, radius + 1):
				var cell := origin + direction * distance
				if not sampler.is_in_bounds(cell):
					break
				found[cell] = true
	var cells: Array[Vector2i] = []
	for cell in found:
		cells.append(cell)
	return cells

static func _carried_envelope(observation: Dictionary, game: Node, sampler) -> Array[Vector2i]:
	var origin: Vector2i = observation.cell
	var raw_cells: Array = [[origin.x, origin.y]]
	var bounds: Vector2i = sampler.get_map_bounds()
	for direction: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for distance in range(ServerBomb.THROW_RANGE, ServerBomb.THROW_RANGE + 20):
			var probe := origin + direction * distance
			var cell := Vector2i(posmod(probe.x, bounds.x), posmod(probe.y, bounds.y))
			var occupied: bool = sampler.get_tile_type(cell) != 0
			for player in game.players.values():
				if is_instance_valid(player) and not player.is_dead and player.get_tile_position() == cell:
					occupied = true
			for other in game.bombs.values():
				if is_instance_valid(other) and not other.has_exploded and other.get_tile_position() == cell:
					occupied = true
			if not occupied or distance == ServerBomb.THROW_RANGE + 19:
				raw_cells.append([cell.x, cell.y])
				break
	return _landing_envelope(raw_cells, observation.range, sampler)

static func _settle_chains(deadlines: Array[float], blasts: Array, at_cell: Dictionary) -> void:
	var queue: Array = range(deadlines.size())
	var settled := {}
	while not queue.is_empty():
		queue.sort_custom(func(a, b): return deadlines[a] < deadlines[b] or deadlines[a] == deadlines[b] and a < b)
		var index: int = queue.pop_front()
		settled[index] = true
		for cell: Vector2i in blasts[index]:
			for other in at_cell.get(cell, []):
				if not settled.has(other):
					deadlines[other] = minf(deadlines[other], deadlines[index])

static func _extend_future_geometry(observations: Array[Dictionary], deadlines: Array[float], latest_times: Array[float], blasts: Array, sampler) -> bool:
	var removal_sources := {}
	for index in range(blasts.size()):
		for cell: Vector2i in blasts[index]:
			if sampler.get_tile_type(cell) == 2:
				if not removal_sources.has(cell):
					removal_sources[cell] = {}
				removal_sources[cell][index] = deadlines[index]
	var changed := false
	for index in range(observations.size()):
		if int(observations[index].get("state", 0)) not in [ServerBomb.BombState.PLANTED, ServerBomb.BombState.LANDED]:
			continue
		var cleared := {}
		for cell in removal_sources:
			for source_index in removal_sources[cell]:
				# A bomb cannot clear its own blocker before calculating its
				# pattern, even when its sampled detonation time is uncertain.
				if source_index != index and float(removal_sources[cell][source_index]) < latest_times[index]:
					cleared[cell] = true
					break
		var projected := project(observations[index].cell, observations[index].range, sampler, cleared)
		if projected.size() > blasts[index].size():
			blasts[index] = projected
			changed = true
	return changed

static func _key(cell: Vector2i) -> String:
	return "%d,%d" % [cell.x, cell.y]

static func _kick_envelope(observation: Dictionary, sampler) -> Array[Vector2i]:
	var direction: Vector2 = observation.get("kick_direction", Vector2.ZERO)
	var step := Vector2i(signi(int(direction.x * 1000.0)), signi(int(direction.y * 1000.0)))
	var origin: Vector2i = observation.cell
	var found := {}
	var cleared := {}
	var bounds: Vector2i = sampler.get_map_bounds()
	for x in range(bounds.x):
		for y in range(bounds.y):
			var cell := Vector2i(x, y)
			if sampler.get_tile_type(cell) == 2:
				cleared[cell] = true
	for cell in project(origin, observation.range, sampler, cleared):
		found[cell] = true
	if step != Vector2i.ZERO:
		var next := origin + step
		while sampler.is_in_bounds(next) and sampler.get_tile_type(next) in [0, 2]:
			# A different observed blast can remove a soft blocker while the
			# kick is in flight. Its possible disappearance cannot truncate an
			# otherwise conservative trajectory envelope.
			for cell in project(next, observation.range, sampler, cleared):
				found[cell] = true
			next += step
	var cells: Array[Vector2i] = []
	for cell in found:
		cells.append(cell)
	return cells

static func _add(result: Dictionary, key: String, start: float, end: float) -> void:
	result.deadlines[key] = minf(float(result.deadlines.get(key, INF)), start)
	if not result.intervals.has(key):
		result.intervals[key] = []
	# Godot Vector2 uses engine real precision. Outward millisecond rounding
	# keeps a float representation from clearing an inclusive boundary early.
	result.intervals[key].append(Vector2(floorf(start), ceilf(end)))

static func merge_intervals(windows: Array) -> Array[Vector2]:
	var ordered: Array[Vector2] = []
	ordered.assign(windows)
	ordered.sort_custom(func(a, b): return a.x < b.x or a.x == b.x and a.y < b.y)
	var merged: Array[Vector2] = []
	for window in ordered:
		if merged.is_empty() or merged.back().y < window.x:
			merged.append(window)
		else:
			merged[-1].y = maxf(merged[-1].y, window.y)
	return merged

static func is_window_safe(intervals: Dictionary, cell: Vector2i, start: float, end: float, buffer_msec: float = 100.0) -> bool:
	for window: Vector2 in intervals.get(_key(cell), []):
		if start - buffer_msec <= window.y and end + buffer_msec >= window.x:
			return false
	return true

static func project(origin: Vector2i, radius: int, sampler, cleared_soft_blocks: Dictionary = {}) -> Array[Vector2i]:
	var cells: Array[Vector2i] = []
	if not sampler.is_in_bounds(origin):
		return cells
	cells.append(origin)
	for direction: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for distance in range(1, radius + 1):
			var cell: Vector2i = origin + direction * distance
			if not sampler.is_in_bounds(cell):
				break
			var tile_type: int = sampler.get_tile_type(cell)
			if tile_type == 1 or tile_type == 3:
				break
			cells.append(cell)
			if tile_type == 2 and not cleared_soft_blocks.has(cell):
				break
	return cells
