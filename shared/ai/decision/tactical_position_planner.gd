extends RefCounted

## Bounded public-state attack positioning. Targets are provisional: movement
## revalidates its route and BTPlaceBomb still performs the final escape check.
## This is a reachable firing-position search, not an opponent-action simulator.

const BlastForecast = preload("res://shared/ai/perception/bomb_threat_forecast.gd")
const MovementTiming = preload("res://shared/ai/movement_timing.gd")
const DIRECTIONS: Array[Vector2i] = [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]

static func choose(player, opponent_tile: Vector2i, sampler, manager, checker,
		now_msec: float, max_steps: int = 24, max_expansions: int = 512,
		max_safety_checks: int = 8) -> Dictionary:
	var result := {"found": false, "tile": Vector2i(-1, -1), "reason": "unavailable",
		"expanded": 0, "candidates": 0, "safety_checks": 0, "budget_exhausted": false}
	if player == null or sampler == null or manager == null or checker == null:
		return result
	if max_steps < 0 or max_expansions < 1 or max_safety_checks < 1 or not is_finite(now_msec):
		return result
	var start: Vector2i = player.get_tile_position()
	if not sampler.is_in_bounds(start) or not sampler.is_in_bounds(opponent_tile):
		return result
	var speed: float = MovementTiming.tiles_per_second(player)
	if not is_finite(speed) or speed <= 0.0:
		return result
	var threats: Dictionary = manager.get_current_threat_matrix()
	if threats.has(_key(start)):
		result.reason = "current_danger"
		return result
	var radius: int = player.get_effective_bomb_range()
	var candidates: Array[Dictionary] = []
	var queue: Array[Vector2i] = [start]
	var depths := {start: 0}
	var head := 0
	while head < queue.size() and head < max_expansions:
		var cell: Vector2i = queue[head]
		head += 1
		var depth: int = depths[cell]
		# Only cross cells without a public hazard. The temporal movement layer
		# can support tighter escape timing; attack positioning stays conservative.
		if sampler.is_tile_safe_for_target(cell) and not sampler.is_tile_occupied(cell, player):
			var distance := absi(cell.x - opponent_tile.x) + absi(cell.y - opponent_tile.y)
			if distance > 0 and distance <= radius and (cell.x == opponent_tile.x or cell.y == opponent_tile.y):
				var blast: Array[Vector2i] = BlastForecast.project(cell, radius, sampler)
				if blast.has(opponent_tile):
					var exits := _safe_exits(cell, sampler, player, threats)
					if exits >= 2:
						var covered_exits := 0
						for direction: Vector2i in DIRECTIONS:
							var escape := opponent_tile + direction
							if sampler.is_tile_walkable(escape) and blast.has(escape):
								covered_exits += 1
						candidates.append({"tile": cell, "steps": depth, "exits": exits,
							"score": 4 * covered_exits + exits - 3 * depth})
		if depth >= max_steps:
			continue
		for direction: Vector2i in DIRECTIONS:
			var next := cell + direction
			if depths.has(next) or not sampler.is_tile_safe_for_target(next) or sampler.is_tile_occupied(next, player) or threats.has(_key(next)):
				continue
			depths[next] = depth + 1
			queue.append(next)
	result.expanded = head
	result.candidates = candidates.size()
	result.budget_exhausted = head < queue.size()
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a.score != b.score: return a.score > b.score
		if a.steps != b.steps: return a.steps < b.steps
		if a.tile.y != b.tile.y: return a.tile.y < b.tile.y
		return a.tile.x < b.tile.x)
	for candidate: Dictionary in candidates:
		if result.safety_checks >= max_safety_checks:
			result.budget_exhausted = true
			break
		result.safety_checks += 1
		# Use the actual actor speed and public lower-bound fuse. This evaluates
		# a placement in the observed state; it does not pre-authorize a future
		# plant after approaching a moving opponent or a changing bomb field.
		if checker.can_safely_plant_bomb(candidate.tile, candidate.tile, radius,
				speed, now_msec, player.get_bomb_fuse_lower_bound(), player):
			result.found = true
			result.tile = candidate.tile
			result.reason = "reachable_firing_position"
			result["steps"] = candidate.steps
			result["covered_exits_score"] = candidate.score
			return result
	result.reason = "no_safe_firing_position" if not candidates.is_empty() else "no_reachable_firing_position"
	return result

static func _safe_exits(cell: Vector2i, sampler, player, threats: Dictionary) -> int:
	var count := 0
	for direction: Vector2i in DIRECTIONS:
		var next := cell + direction
		if sampler.is_tile_safe_for_target(next) and not sampler.is_tile_occupied(next, player) and not threats.has(_key(next)):
			count += 1
	return count

static func _key(cell: Vector2i) -> String:
	return "%d,%d" % [cell.x, cell.y]
