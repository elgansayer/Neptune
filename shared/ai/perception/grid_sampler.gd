extends Resource
class_name GridSampler

## Provides tile/world conversions plus walkability + occupancy info from the live GameInstance.

var debug_logging := false
var navigation_region: NavigationRegion2D
var tile_size := 16.0  # Saturn Bomberman native

var _game_instance: Node
var _map_size := Vector2i.ZERO
const TimedPathfinder = preload("res://shared/ai/pathfinding/danger_aware_astar.gd")

var _astar: DangerAwareAStar
var _last_timed_route: Dictionary = {}

func configure(instance: Node, region: NavigationRegion2D = null, new_tile_size: float = GameConfig.TILE_SIZE) -> void:
	_game_instance = instance
	navigation_region = region
	tile_size = new_tile_size
	_update_map_size()

func _update_map_size() -> void:
	if _game_instance and _game_instance.game_map.size() > 0:
		var size: Vector2i = _game_instance.get_map_dimensions() if _game_instance.has_method("get_map_dimensions") else Vector2i(_game_instance.game_map[0].size(), _game_instance.game_map.size())
		if size != _map_size or _astar == null:
			_map_size = size
			_init_astar()

func _init_astar() -> void:
	_astar = TimedPathfinder.new()
	_astar.region = Rect2i(0, 0, _map_size.x, _map_size.y)
	_astar.cell_size = Vector2(tile_size, tile_size)
	_astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	_astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	_astar.default_estimate_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	_astar.update()

func world_to_tile(world_position: Vector2) -> Vector2i:
	return Vector2i(int(floor(world_position.x / tile_size)), int(floor(world_position.y / tile_size)))

func tile_to_world_center(tile_position: Vector2i) -> Vector2:
	return Vector2(
		tile_position.x * tile_size + tile_size * 0.5,
		tile_position.y * tile_size + tile_size * 0.5
	)

func is_in_bounds(tile_position: Vector2i) -> bool:
	if _map_size == Vector2i.ZERO or _game_instance.has_method("get_map_dimensions") and _game_instance.get_map_dimensions() != _map_size:
		_update_map_size()
	return tile_position.x >= 0 and tile_position.x < _map_size.x \
		and tile_position.y >= 0 and tile_position.y < _map_size.y

func is_tile_walkable(tile_position: Vector2i, allow_soft_block: bool = false) -> bool:
	if not is_in_bounds(tile_position):
		return false
	if _game_instance == null:
		return true
	var tile_type = _game_instance.get_tile_type(tile_position)
	if tile_type == 0:
		return true
	if tile_type == 2 and allow_soft_block:
		return true
	return false

func is_tile_safe_for_target(tile_position: Vector2i) -> bool:
	"""Check if tile is safe to use as a movement/farming target (no bombs)"""
	if not is_tile_walkable(tile_position):
		return false
	
	# Check for bombs at this position
	if "bombs" in _game_instance:
		for bomb_id in _game_instance.bombs:
			var bomb = _game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == tile_position:
					return false  # Bomb present - not safe for targeting!
	
	return true

func is_tile_occupied(tile_position: Vector2i, ignore_player: Node = null) -> bool:
	if _game_instance == null:
		return false
	for peer_id in _game_instance.players:
		var player = _game_instance.players[peer_id]
		if not is_instance_valid(player) or is_instance_valid(ignore_player) and player.peer_id == ignore_player.peer_id:
			continue
		if player.is_dead:
			continue
		if player.get_tile_position() == tile_position:
			return true
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		if bomb.get_tile_position() == tile_position:
			return true
	return false

func get_cardinal_neighbors(tile_position: Vector2i) -> Array[Vector2i]:
	var neighbors: Array[Vector2i] = []
	var offsets = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]
	for offset in offsets:
		var candidate = tile_position + offset
		if is_in_bounds(candidate):
			neighbors.append(candidate)
	return neighbors


func find_path(start_tile: Vector2i, goal_tile: Vector2i, max_depth: int = 30, ignore_player: Node = null, avoid_threats: bool = false, current_time_msec: float = -INF, msec_per_tile: float = 200.0, safe_goals: Dictionary = {}) -> Array[Vector2i]:
	_last_timed_route = {"status": "unreachable", "cells": [], "arrivals": [], "departures": [], "expanded": 0}
	if start_tile == goal_tile and safe_goals.is_empty():
		return []
		
	if _astar == null or _map_size == Vector2i.ZERO:
		_update_map_size()
		if _astar == null: # Should be initialized by _update_map_size
			print("[GridSampler] ERROR: _astar is null after _update_map_size!")
			return []
	
	# DEBUG: Check if tiles are in bounds
	if not is_in_bounds(start_tile):
		print("[GridSampler] ERROR: start_tile ", start_tile, " out of bounds! map_size=", _map_size)
		return []
	if not is_in_bounds(goal_tile):
		print("[GridSampler] ERROR: goal_tile ", goal_tile, " out of bounds! map_size=", _map_size)
		return []
			
	# 1. Reset grid solids based on static map (walls/soft blocks)
	# We iterate the map to ensure dynamic soft block changes are reflected
	# Optimization: We could track soft block changes, but for this map size, iteration is fast enough
	var terrain: Array = _game_instance.game_map
	for x in range(_map_size.x):
		for y in range(_map_size.y):
			var pos = Vector2i(x, y)
			# 0 = Empty (Walkable), 1 = Hard Block (Solid), 2 = Soft Block (Solid)
			var tile_type = terrain[y][x]
			var is_solid = (tile_type != 0)
			_astar.set_point_solid(pos, is_solid)
	
	# 2. Mark other players as solid obstacles
	for peer_id in _game_instance.players:
		var p = _game_instance.players[peer_id]
		if is_instance_valid(p) and (not is_instance_valid(ignore_player) or p.peer_id != ignore_player.peer_id) and not p.is_dead:
			var p_pos = p.get_tile_position()
			# Players may overlap during movement. Occupancy cannot prevent
			# departure from the current tile: Godot 4.7 rejects solid starts.
			# Static terrain remains solid from the map pass above.
			if is_in_bounds(p_pos) and p_pos != start_tile and (p_pos != goal_tile or current_time_msec != -INF):
				_astar.set_point_solid(p_pos, true)
	
	
	# 3. Mark bombs as solid obstacles (bots need to path around them)
	# Exception: Allow walking through the bot's OWN bomb tile (collision exception exists)
	if "bombs" in _game_instance:
		for bomb_id in _game_instance.bombs:
			var bomb = _game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				var bomb_tile = bomb.get_tile_position()
				# Allow walking through start tile (might be own bomb) and goal tile
				if bomb_tile != start_tile and (bomb_tile != goal_tile or current_time_msec != -INF):
					if is_in_bounds(bomb_tile):
						_astar.set_point_solid(bomb_tile, true)
	
	# 4. Mark threats if requested
	if avoid_threats and current_time_msec == -INF and _game_instance.ai_manager:
		var threat_matrix = _game_instance.ai_manager.get_current_threat_matrix()
		for tile_key in threat_matrix:
			var parts = tile_key.split(",")
			if parts.size() == 2:
				var tile = Vector2i(int(parts[0]), int(parts[1]))
				# Don't block start tile (we need to leave it)
				# Don't block goal tile (we decided to go there, presumably it's safe or we accept the risk)
				if tile != start_tile and tile != goal_tile:
					if is_in_bounds(tile):
						_astar.set_point_solid(tile, true)
	
	# 4. Get the path
	var path: Array[Vector2i]
	if current_time_msec != -INF:
		_astar.threat_matrix_ref = _game_instance.ai_manager.get_current_threat_matrix() if _game_instance.ai_manager else {}
		_astar.use_hazard_intervals = _game_instance.ai_manager != null and "hazard_intervals" in _game_instance.ai_manager
		_astar.hazard_intervals_ref = _game_instance.ai_manager.hazard_intervals if _astar.use_hazard_intervals else {}
		_astar.allow_wait = not is_instance_valid(ignore_player) or ignore_player.active_virus != ServerPlayer.VirusType.UNSTOPPABLE
		_astar.use_start_world_position = is_instance_valid(ignore_player) and ignore_player.get_tile_position() == start_tile
		if _astar.use_start_world_position:
			_astar.start_world_position = ignore_player.position
		_astar.path_start_time_msec = current_time_msec
		_astar.bot_speed_msec_per_tile = msec_per_tile
		_last_timed_route = _astar.get_timed_route(start_tile, goal_tile, max_depth, safe_goals, not safe_goals.is_empty())
		path.assign(_last_timed_route.cells)
	else:
		path = _astar.get_id_path(start_tile, goal_tile)
	
	# DEBUG: If path is empty, check why
	if debug_logging and path.is_empty() and start_tile != goal_tile:
		var start_solid = _astar.is_point_solid(start_tile)
		var goal_solid = _astar.is_point_solid(goal_tile)
		if start_solid or goal_solid:
			print("[GridSampler] Path FAILED: start_solid=", start_solid, " goal_solid=", goal_solid, " start=", start_tile, " goal=", goal_tile)
	
	if debug_logging:
		print("[GridSampler] Path from ", start_tile, " to ", goal_tile, ": ", path)
	
	# AStarGrid2D returns path including start point.
	# Remove the start point since we're already there
	if path.size() > 0 and path[0] == start_tile:
		path.remove_at(0)
		if not _last_timed_route.cells.is_empty():
			_last_timed_route.cells.remove_at(0)
			_last_timed_route.arrivals.remove_at(0)
			_last_timed_route.departures.remove_at(0)
	
	return path

func find_timed_route(start_tile: Vector2i, goal_tile: Vector2i, max_depth: int, ignore_player: Node, current_time_msec: float, msec_per_tile: float) -> Dictionary:
	find_path(start_tile, goal_tile, max_depth, ignore_player, false, current_time_msec, msec_per_tile)
	return _last_timed_route.duplicate(true)

func find_timed_escape_route(start_tile: Vector2i, max_depth: int, ignore_player: Node, current_time_msec: float, msec_per_tile: float) -> Dictionary:
	var goals := {}
	for x in range(_map_size.x):
		for y in range(_map_size.y):
			var cell := Vector2i(x, y)
			if cell != start_tile and get_manhattan_distance(start_tile, cell) <= max_depth and is_tile_safe_for_target(cell):
				goals[cell] = true
	if goals.is_empty():
		return {"status": "unreachable", "cells": [], "arrivals": [], "departures": [], "expanded": 0}
	find_path(start_tile, start_tile, max_depth, ignore_player, false, current_time_msec, msec_per_tile, goals)
	return _last_timed_route.duplicate(true)

func get_manhattan_distance(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)

func get_map_bounds() -> Vector2i:
	if _map_size == Vector2i.ZERO:
		_update_map_size()
	return _map_size

func get_tile_type(tile_position: Vector2i) -> int:
	if _game_instance == null:
		return 0 # Default to empty
	return _game_instance.get_tile_type(tile_position)

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
