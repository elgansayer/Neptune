extends Resource
class_name BombSafetyChecker

## Time-aware BFS for suicide prevention
## Checks if bot can reach safety before being killed by its own bomb
## Based on Bomberman AI Doctrine - Godot-Specific suicide check

const Constants = preload("res://shared/constants.gd")

var _ai_manager = null
var _grid_sampler = null
var debug_logging: bool = false

# Safety tuning parameters
var safety_buffer_msec: float = 300.0 # Conservative buffer (increased from implicit 0)
var movement_delay_msec: float = 150.0 # Time before bot actually starts moving after decision

func configure(ai_manager, grid_sampler) -> void:
	_ai_manager = ai_manager
	_grid_sampler = grid_sampler

## Core suicide check: Can bot safely plant bomb at position and escape?
## Returns true if safe escape route exists, false if bot would die
func can_safely_plant_bomb(
	bot_pos: Vector2i,
	plant_pos: Vector2i,
	bomb_range: int,
	bot_speed_tiles_per_sec: float = 5.0,
	current_time_msec: float = 0.0
) -> bool:
	if _ai_manager == null or _grid_sampler == null:
		if debug_logging:
			print("  [BombSafetyChecker] Missing dependencies")
		return false
	
	# Get simulated threat matrix with hypothetical bomb
	var future_threat_matrix: Dictionary = _ai_manager.simulate_threat_matrix(
		plant_pos,
		bomb_range,
		current_time_msec
	)
	
	if debug_logging:
		print("  [BombSafetyChecker] Checking plant at ", plant_pos, " range=", bomb_range, " threat_tiles=", future_threat_matrix.size())
	
	# Constants for BFS with safety buffers
	var bomb_fuse_time_sec := 3.0
	var time_to_explode_msec := current_time_msec + (bomb_fuse_time_sec * 1000.0)
	var msec_per_tile := (1.0 / bot_speed_tiles_per_sec) * 1000.0
	
	# SAFETY: Account for movement delay and safety margin
	var effective_start_time := current_time_msec + movement_delay_msec
	
	# CRITICAL: Maximum time we can search (bomb explodes at this time)
	var max_search_time := time_to_explode_msec - safety_buffer_msec
	
	# BFS queue and visited tracking
	var queue: Array[Vector2i] = [bot_pos]
	var visited: Dictionary = {_tile_key(bot_pos): effective_start_time} # tile_key -> arrival_time_msec (with delay)
	var head := 0
	
	# CRITICAL: The bomb position will be blocked after placement
	# We must move AWAY from it and cannot return through it
	var bomb_tile_key := _tile_key(plant_pos)
	
	while head < queue.size():
		var current_pos := queue[head]
		head += 1
		
		var current_key := _tile_key(current_pos)
		var current_arrival_time: float = visited[current_key]
		
		# CRITICAL: Stop exploring if we can't reach this tile before bomb explodes
		if current_arrival_time >= max_search_time:
			continue
		
		# 1. IS THIS TILE A SAFE HAVEN?
		if not future_threat_matrix.has(current_key):
			# SUCCESS! Found a tile that never explodes AND we can reach it in time
			if debug_logging:
				print("  [BombSafetyChecker] ✓ Safe haven found at ", current_pos, " (arrival=", current_arrival_time, "ms, bomb_explodes=", time_to_explode_msec, "ms)")
			return true
		
		# 2. IF NOT, CAN WE PASS THROUGH SAFELY?
		var tile_lethal_time: float = future_threat_matrix[current_key]
		
		# Only explore further if we're still alive on this tile
		if current_arrival_time < tile_lethal_time:
			# Check all 4 cardinal directions
			for dir: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
				var next_pos := current_pos + dir
				var next_key := _tile_key(next_pos)
				var next_arrival_time := current_arrival_time + msec_per_tile
				
				# CRITICAL: Bomb blocks the tile - cannot move through bomb position
				if next_key == bomb_tile_key:
					continue
				
				# Check for walls (using grid sampler)
				if not _grid_sampler.is_tile_walkable(next_pos):
					continue
				
				# Is this a worse path than one already found?
				if visited.has(next_key) and visited[next_key] <= next_arrival_time:
					continue
				
				# CRITICAL FIX: We must arrive at the NEXT tile before ITS lethal time too
				var next_safe := true
				if future_threat_matrix.has(next_key):
					var next_lethal: float = future_threat_matrix[next_key] - safety_buffer_msec
					next_safe = next_arrival_time < next_lethal
				# Also ensure we leave current before it explodes
				var leave_current_safe := next_arrival_time <= tile_lethal_time
				if leave_current_safe and next_safe:
					visited[next_key] = next_arrival_time
					queue.append(next_pos)
	
	# Queue exhausted - no safe escape route found
	if debug_logging:
		print("  [BombSafetyChecker] ✗ No escape found (explored ", visited.size(), " tiles)")
	return false

## Detailed safety check that returns escape info and margin
func check_plant_safety_detailed(
	bot_pos: Vector2i,
	plant_pos: Vector2i,
	bomb_range: int,
	bot_speed_tiles_per_sec: float = 5.0,
	current_time_msec: float = 0.0
) -> Dictionary:
	"""Returns {safe: bool, escape_tile: Vector2i, margin_ms: float, explored_tiles: int}"""
	
	if _ai_manager == null or _grid_sampler == null:
		return {"safe": false, "explored_tiles": 0}
	
	var future_threat_matrix: Dictionary = _ai_manager.simulate_threat_matrix(
		plant_pos,
		bomb_range,
		current_time_msec
	)
	
	var bomb_fuse_time_sec := 3.0
	var time_to_explode_msec := current_time_msec + (bomb_fuse_time_sec * 1000.0)
	var msec_per_tile := (1.0 / bot_speed_tiles_per_sec) * 1000.0
	
	# SAFETY: Account for movement delay
	var effective_start_time := current_time_msec + movement_delay_msec
	var max_search_time := time_to_explode_msec - safety_buffer_msec
	
	var queue: Array[Vector2i] = [bot_pos]
	var visited: Dictionary = {_tile_key(bot_pos): effective_start_time} # Start with movement delay
	var head := 0
	var best_escape: Vector2i = Vector2i(-1, -1)
	var best_margin: float = - INF
	
	# CRITICAL: The bomb position will be blocked after placement
	var bomb_tile_key := _tile_key(plant_pos)
	
	while head < queue.size():
		var current_pos := queue[head]
		head += 1
		
		var current_key := _tile_key(current_pos)
		var current_arrival_time: float = visited[current_key]
		
		# Stop exploring if we can't reach this tile before bomb explodes
		if current_arrival_time >= max_search_time:
			continue
		
		# Check if this is a safe haven
		if not future_threat_matrix.has(current_key):
			return {
				"safe": true,
				"escape_tile": current_pos,
				"margin_ms": INF,
				"explored_tiles": visited.size()
			}
		
		# Track best marginal option even if not perfectly safe
		var tile_lethal_time: float = future_threat_matrix[current_key]
		var margin = tile_lethal_time - current_arrival_time
		if margin > best_margin:
			best_margin = margin
			best_escape = current_pos
		
		# Continue BFS if we can still traverse this tile
		if current_arrival_time < tile_lethal_time:
			for dir: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
				var next_pos := current_pos + dir
				var next_key := _tile_key(next_pos)
				var next_arrival_time := current_arrival_time + msec_per_tile
				
				# CRITICAL: Bomb blocks the tile - cannot move through bomb position
				if next_key == bomb_tile_key:
					continue
				
				if not _grid_sampler.is_tile_walkable(next_pos):
					continue
				
				if visited.has(next_key) and visited[next_key] <= next_arrival_time:
					continue
				
				var next_safe := true
				if future_threat_matrix.has(next_key):
					var next_lethal: float = future_threat_matrix[next_key] - safety_buffer_msec
					next_safe = next_arrival_time < next_lethal
				var leave_current_safe := next_arrival_time <= tile_lethal_time
				if leave_current_safe and next_safe:
					visited[next_key] = next_arrival_time
					queue.append(next_pos)
	
	# No perfect safe haven found - return best marginal option
	return {
		"safe": false,
		"escape_tile": best_escape,
		"margin_ms": best_margin if best_margin > -INF else 0.0,
		"explored_tiles": visited.size()
	}

## Tile key helper
func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
