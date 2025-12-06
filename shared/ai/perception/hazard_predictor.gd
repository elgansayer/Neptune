extends Resource
class_name HazardPredictor

const Constants = preload("res://shared/constants.gd")

## Tracks bomb danger windows with chain reaction simulation (Tactical Doctrine v1.0)

var _game_instance: Node
var _grid_sampler
var _default_buffer := 0.1 # 0.1s doctrine standard
var _danger_cache := {}
var _threat_matrix := {} # Full ThreatMatrix: tile_key -> time_to_lethal
var _safety_map := {} # SafetyMap: tile_key -> time_to_reach_safety
var _current_time := 0.0

func configure(instance: Node, sampler, default_buffer: float = 0.1) -> void:
	_game_instance = instance
	_grid_sampler = sampler
	_default_buffer = default_buffer

func refresh(current_time: float) -> void:
	_current_time = current_time
	_danger_cache.clear()
	_threat_matrix.clear()
	_safety_map.clear()
	
	if _game_instance == null:
		return
	
	# CRITICAL: Include active explosion tiles (tiles currently on fire!)
	# These are IMMEDIATELY lethal - bot will die if it walks into them.
	if "active_explosion_tiles" in _game_instance:
		for tile_key in _game_instance.active_explosion_tiles:
			# Active explosions are treated as immediately lethal (current_time = now)
			_threat_matrix[tile_key] = current_time
			_danger_cache[tile_key] = current_time
	
	# Build ThreatMatrix with chain reaction simulation (future explosions)
	_build_threat_matrix_with_chains(current_time)
	
	# Build SafetyMap for escape route analysis
	_build_safety_map()

func get_time_to_safety(tile: Vector2i, current_time: float) -> float:
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time <= 0.0:
		return 0.0
	return max(danger_time - current_time, 0.0)

func is_tile_safe(tile: Vector2i, current_time: float, buffer: float = -1.0) -> bool:
	if buffer < 0.0:
		buffer = _default_buffer
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time <= 0.0:
		return true
	return current_time + buffer < danger_time

func is_tile_threatened(tile: Vector2i) -> bool:
	"""Check if tile has any threat registered, regardless of time"""
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	return danger_time > 0.0

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

## Core Algorithm: ThreatMatrix with Chain Reactions (Doctrine Section 3.1)
func _build_threat_matrix_with_chains(current_time: float) -> void:
	# 1. Initialize ThreatMatrix with Infinity
	# (Using sparse dict - only store dangerous tiles)
	# 2. Create bomb queue sorted by explosion time
	var bomb_queue := []
	var bomb_times := {} # bomb_id -> explosion_time (for chain updates)
	
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		var fuse_remaining = max(Constants.BOMB_TIMER - bomb.explosion_timer, 0.0)
		var explosion_time = current_time + fuse_remaining
		bomb_times[bomb_id] = explosion_time
		bomb_queue.append({"bomb": bomb, "time": explosion_time, "id": bomb_id})
	
	# Sort by explosion time (ascending)
	bomb_queue.sort_custom(func(a, b): return a.time < b.time)
	
	# 3. Process queue with chain reactions
	var processed := {}
	for bomb_data in bomb_queue:
		var bomb = bomb_data.bomb
		var bomb_id = bomb_data.id
		var t_explode = bomb_times.get(bomb_id, bomb_data.time) # Use updated time if chained
		
		if processed.has(bomb_id):
			continue
		processed[bomb_id] = true
		
		var origin = bomb.get_tile_position()
		if not _grid_sampler.is_in_bounds(origin):
			continue
		
		# Mark bomb tile
		_set_threat(origin, t_explode)
		
		# Project blasts in 4 directions
		var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]
		for dir in directions:
			for step in range(1, bomb.explosion_range + 1):
				var tile = origin + dir * step
				
				# Check bounds
				if not _grid_sampler.is_in_bounds(tile):
					break
				
				var tile_type = _game_instance.get_tile_type(tile)
				
				# Indestructible wall or hurry block stops blast
				if tile_type == 1 or tile_type == 3:
					break
				
				# CRITICAL FIX: Do NOT stop blast just because there's an earlier threat!
				# Explosions pass through empty space even if another explosion happened there earlier.
				# Only walls and blocks stop blasts.
				# var existing_threat = _threat_matrix.get(_tile_key(tile), INF)
				# if existing_threat <= t_explode:
				# 	break
				
				# Mark this tile as dangerous
				_set_threat(tile, t_explode)
				
				# Check for chain reaction (bomb at this tile)
				var other_bomb_id = _find_bomb_at_tile(tile)
				if other_bomb_id != null and other_bomb_id != bomb_id:
					var other_time = bomb_times.get(other_bomb_id, INF)
					if other_time > t_explode:
						# Chain reaction! Update explosion time
						bomb_times[other_bomb_id] = t_explode
						# Resort queue (simple re-process on next iteration)
				
				# Destructible wall stops blast (but tile itself is marked)
				if tile_type == 2:
					break
	
	# Copy to legacy cache for compatibility
	_danger_cache = _threat_matrix.duplicate()

func _set_threat(tile: Vector2i, time: float) -> void:
	var key = _tile_key(tile)
	var current = _threat_matrix.get(key, INF)
	_threat_matrix[key] = min(current, time)

func _find_bomb_at_tile(tile: Vector2i):
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and not bomb.has_exploded:
			if bomb.get_tile_position() == tile:
				return bomb_id
	return null

## Core Algorithm: SafetyMap (Doctrine Section 4.1)
func _build_safety_map() -> void:
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
	return threat_time <= (safety_time + buffer)

## Get time to reach nearest safety from tile
func get_safety_time(tile: Vector2i) -> float:
	return _safety_map.get(_tile_key(tile), INF)
