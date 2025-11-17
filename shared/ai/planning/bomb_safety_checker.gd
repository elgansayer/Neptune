extends Resource
class_name BombSafetyChecker

## Time-aware BFS for suicide prevention
## Checks if bot can reach safety before being killed by its own bomb
## Based on Bomberman AI Doctrine - Godot-Specific suicide check

const Constants = preload("res://shared/constants.gd")

var _ai_manager = null
var _grid_sampler = null
var debug_logging: bool = false

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
	
	# Constants for BFS
	var bomb_fuse_time_sec := 3.0
	var time_to_explode_msec := current_time_msec + (bomb_fuse_time_sec * 1000.0)
	var msec_per_tile := (1.0 / bot_speed_tiles_per_sec) * 1000.0
	
	# BFS queue and visited tracking
	var queue: Array[Vector2i] = [bot_pos]
	var visited: Dictionary = {_tile_key(bot_pos): current_time_msec}  # tile_key -> arrival_time_msec
	var head := 0
	
	while head < queue.size():
		var current_pos := queue[head]
		head += 1
		
		var current_key := _tile_key(current_pos)
		var current_arrival_time: float = visited[current_key]
		
		# 1. IS THIS TILE A SAFE HAVEN?
		if not future_threat_matrix.has(current_key):
			# SUCCESS! Found a tile that never explodes
			if debug_logging:
				print("  [BombSafetyChecker] ✓ Safe haven found at ", current_pos, " (arrival=", current_arrival_time, "ms)")
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
				
				# Check for walls (using grid sampler)
				if not _grid_sampler.is_tile_walkable(next_pos):
					continue
				
				# Is this a worse path than one already found?
				if visited.has(next_key) and visited[next_key] <= next_arrival_time:
					continue
				
				# CRITICAL FIX: We must arrive at the NEXT tile before ITS lethal time too
				var next_safe := true
				if future_threat_matrix.has(next_key):
					var next_lethal: float = future_threat_matrix[next_key]
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

## Tile key helper
func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
