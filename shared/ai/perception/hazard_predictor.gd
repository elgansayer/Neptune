extends Resource
class_name HazardPredictor

const Constants = preload("res://shared/constants.gd")
const BombForecast = preload("res://shared/ai/perception/bomb_threat_forecast.gd")

## Tracks bomb danger windows with chain reaction simulation (Tactical Doctrine v1.0)

var _game_instance: Node
var _grid_sampler
var _default_buffer := 0.1 # 0.1s doctrine standard
var _danger_cache := {}
var _threat_matrix := {} # Full ThreatMatrix: tile_key -> time_to_lethal
var _safety_map := {} # SafetyMap: tile_key -> time_to_reach_safety
var _safety_map_ready := false
var _current_time := 0.0

func configure(instance: Node, sampler, default_buffer: float = 0.1) -> void:
	_game_instance = instance
	_grid_sampler = sampler
	_default_buffer = default_buffer

func refresh(current_time: float, force_observation: bool = true,
		shared_milliseconds: Variant = null, shared_time_msec: float = -INF) -> void:
	if force_observation and is_instance_valid(_game_instance) and _game_instance.has_method("refresh"):
		_game_instance.refresh(true)
	_current_time = current_time
	_danger_cache.clear()
	_threat_matrix.clear()
	_safety_map.clear()
	_safety_map_ready = false
	
	if _game_instance == null:
		return
	
	# A production manager already computed this public forecast for the same
	# observation/clock phase. Reuse its values without aliasing or mutating it.
	# Timestamp mismatch and standalone calls retain the independent build path.
	var milliseconds: Dictionary
	if not force_observation and shared_milliseconds is Dictionary and is_finite(shared_time_msec) and absf(shared_time_msec - current_time * 1000.0) <= 0.000001:
		milliseconds = shared_milliseconds
	else:
		milliseconds = BombForecast.build(_game_instance, _grid_sampler, current_time * 1000.0)
	for key in milliseconds:
		_threat_matrix[key] = milliseconds[key] / 1000.0
	_danger_cache = _threat_matrix.duplicate()

	# The active policy uses its time-aware planner; legacy SafetyMap consumers
	# construct this full-map BFS only when they actually ask for it.

func get_time_to_safety(tile: Vector2i, current_time: float) -> float:
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time == -INF:
		return 0.0
	return max(danger_time - current_time, 0.0)

func is_tile_safe(tile: Vector2i, current_time: float, buffer: float = -1.0) -> bool:
	if buffer < 0.0:
		buffer = _default_buffer
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time == -INF:
		return true
	return current_time + buffer < danger_time

func is_tile_threatened(tile: Vector2i) -> bool:
	"""Check if tile has any threat registered, regardless of time"""
	return _danger_cache.has(_tile_key(tile))

func find_escape_tiles(from_tile: Vector2i, current_time: float, max_distance: int = 6) -> Array[Vector2i]:
	if _grid_sampler == null:
		return []
	var queue: Array[Vector2i] = [from_tile]
	var head := 0
	var visited := {}
	visited[_tile_key(from_tile)] = 0
	var safe_tiles: Array[Vector2i] = []
	while head < queue.size():
		var current: Vector2i = queue[head]
		head += 1
		var depth: int = visited.get(_tile_key(current), 0)
		if is_tile_safe(current, current_time):
			safe_tiles.append(current)
			if safe_tiles.size() >= 3:
				break
		if depth >= max_distance:
			continue
		for neighbor in _grid_sampler.get_cardinal_neighbors(current):
			if not _grid_sampler.is_tile_walkable(neighbor):
				continue
			var key = _tile_key(neighbor)
			if visited.has(key):
				continue
			visited[key] = depth + 1
			queue.append(neighbor)
	return safe_tiles

func _project_bomb_tiles(bomb) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	if _grid_sampler == null:
		return tiles
	var origin = bomb.get_tile_position()
	if not _grid_sampler.is_in_bounds(origin):
		return tiles
	tiles.append(origin)
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]
	for dir in directions:
		for step in range(1, bomb.explosion_range + 1):
			var tile = origin + dir * step
			if not _grid_sampler.is_in_bounds(tile):
				break
			var tile_type = _game_instance.get_tile_type(tile)
			if tile_type == 1 or tile_type == 3:  # Hard wall or hurry block
				break
			tiles.append(tile)
			if tile_type == 2:
				break
	return tiles

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

## Core Algorithm: SafetyMap (Doctrine Section 4.1)
func _build_safety_map() -> void:
	_safety_map_ready = true
	if _grid_sampler == null:
		return
	
	# Multi-source BFS from all safe tiles
	var queue: Array[Vector2i] = []
	var head := 0
	
	# Identify Safe Havens (tiles with no threat)
	var map_bounds = _grid_sampler.get_map_bounds()
	for x in range(map_bounds.x):
		for y in range(map_bounds.y):
			var tile = Vector2i(x, y)
			if not _grid_sampler.is_tile_walkable(tile):
				continue
			var key = _tile_key(tile)
			var threat_time = _threat_matrix.get(key, INF)
			if threat_time == INF:
				# This is a Safe Haven
				_safety_map[key] = 0.0
				queue.append(tile)
	
	# Propagate safety values via BFS
	var base_speed = 2.5 # tiles per second (default player speed)
	var time_per_tile = 1.0 / base_speed
	
	while head < queue.size():
		var current = queue[head]
		head += 1
		var current_key = _tile_key(current)
		var t_current = _safety_map.get(current_key, INF)
		
		for neighbor in _grid_sampler.get_cardinal_neighbors(current):
			if not _grid_sampler.is_tile_walkable(neighbor):
				continue
			var neighbor_key = _tile_key(neighbor)
			
			# Check if unvisited
			if _safety_map.has(neighbor_key):
				continue
			
			# Calculate time to reach safety from this tile
			var t_neighbor = t_current + time_per_tile
			_safety_map[neighbor_key] = t_neighbor
			queue.append(neighbor)

## Check if bot at tile is in mortal danger (Doctrine survival check)
func is_in_mortal_danger(tile: Vector2i, current_time: float, buffer: float = 0.1) -> bool:
	if not _safety_map_ready:
		_build_safety_map()
	var key = _tile_key(tile)
	var threat_time = _threat_matrix.get(key, INF)
	var safety_time = _safety_map.get(key, INF)
	
	# If no escape route exists, bot is trapped
	if safety_time == INF:
		return threat_time < INF
	
	# If no threat, bot is safe
	if threat_time == INF:
		return false
	
	# Compare: time until explosion vs time to reach safety
	return threat_time <= current_time + safety_time + buffer

## Get time to reach nearest safety from tile
func get_safety_time(tile: Vector2i) -> float:
	if not _safety_map_ready:
		_build_safety_map()
	return _safety_map.get(_tile_key(tile), INF)
