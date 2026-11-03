@tool
extends BTCondition
class_name BTCanSafelyPlant

const SimulationTime = preload("res://shared/ai/simulation_time.gd")
const MovementTiming = preload("res://shared/ai/movement_timing.gd")

## Validates that the selected farming tile can be bombed safely and caches an escape cell

@export var target_cell_var: StringName = &"target_cell"
@export var escape_target_var: StringName = &"target_escape_cell"
@export var min_safety_margin_ms: float = 500.0
@export var debug_logging: bool = false

const INVALID_TILE := Vector2i(-1, -1)

func _generate_name() -> String:
	return "CanSafelyPlant(%s)" % target_cell_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var ai_manager = blackboard.get_var("ai_manager")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	var target_tile = _coerce_to_tile(blackboard.get_var(target_cell_var))
	
	if not player or not bomb_safety_checker or not ai_manager or not grid_sampler:
		_debug("Missing dependency (player=%s, safety=%s, ai=%s, grid=%s)" % [bool(player), bool(bomb_safety_checker), bool(ai_manager), bool(grid_sampler)])
		return FAILURE
	if target_tile == INVALID_TILE:
		_debug("No target tile set on %s" % target_cell_var)
		return FAILURE
	
	var bomb_range = player.get_effective_bomb_range()
	var current_time_msec = SimulationTime.milliseconds(blackboard)
	var bot_speed := MovementTiming.tiles_per_second(player)
	if bot_speed <= 0.0: return FAILURE
	
	var safety = bomb_safety_checker.check_plant_safety_detailed(
		target_tile,
		target_tile,
		bomb_range,
		bot_speed,
		current_time_msec,
		false, player.get_bomb_fuse_lower_bound(), player)
	if not safety.get("safe", false) or float(safety.get("margin_ms", 0.0)) < min_safety_margin_ms:
		blackboard.set_var(escape_target_var, null)
		_debug("Safety checker rejected tile %s (range=%d)" % [target_tile, bomb_range])
		return FAILURE
	var escape_tile := _coerce_to_tile(safety.get("escape_tile", INVALID_TILE))
	
	if escape_tile == INVALID_TILE:
		blackboard.set_var(escape_target_var, null)
		_debug("No escape tile found for %s" % target_tile)
		return FAILURE
	
	blackboard.set_var(escape_target_var, escape_tile)
	_debug("Approved plant at %s with escape %s" % [target_tile, escape_tile])
	return SUCCESS

func _find_escape_tile(
	start_tile: Vector2i,
	bomb_range: int,
	ai_manager,
	grid_sampler,
	bot_speed: float,
	current_time_msec: float,
	fuse_lower_bound: float
) -> Vector2i:
	var simulated_matrix = ai_manager.simulate_threat_matrix(start_tile, bomb_range, current_time_msec, fuse_lower_bound)
	var msec_per_tile = (1.0 / bot_speed) * 1000.0
	var queue: Array[Vector2i] = [start_tile]
	var visited: Dictionary = {_tile_key(start_tile): current_time_msec}
	var head := 0
	var best_tile := INVALID_TILE
	var best_margin := -INF

	while head < queue.size():
		var tile := queue[head]
		head += 1
		var key := _tile_key(tile)
		var arrival_time: float = visited[key]
		var threatened: bool = simulated_matrix.has(key)
		if not threatened:
			return tile
		var explosion_time: float = simulated_matrix[key]
		var safety_margin := explosion_time - arrival_time
		if safety_margin > min_safety_margin_ms and safety_margin > best_margin:
			best_margin = safety_margin
			best_tile = tile
		if arrival_time >= explosion_time:
			continue
		for dir in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var next: Vector2i = tile + dir
			if not grid_sampler.is_tile_walkable(next):
				continue
			var next_key := _tile_key(next)
			var next_time: float = arrival_time + msec_per_tile
			if visited.has(next_key) and visited[next_key] <= next_time:
				continue
			# Only traverse if the neighbor will still be safe to enter at next_time
			var neighbor_ok := true
			if simulated_matrix.has(next_key):
				var next_lethal: float = simulated_matrix[next_key]
				neighbor_ok = next_time < next_lethal
			if neighbor_ok:
				visited[next_key] = next_time
				queue.append(next)

	return best_tile

func _coerce_to_tile(value) -> Vector2i:
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	return INVALID_TILE

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

func _debug(message: String) -> void:
	if debug_logging:
		print("[BTCanSafelyPlant] ", message)
