extends Resource
class_name OpeningGambit

## Opening Gambit: Spawn analysis and optimal first bomb placement
## Analyzes spawn pocket, scores blast efficiency, and plans chained actions
## Based on Bomberman AI Doctrine - Opening Strategy

const Constants = preload("res://shared/constants.gd")

var _ai_manager = null
var _grid_sampler = null
var _bomb_safety_checker = null

# Cache for current planning
var _spawn_pos: Vector2i = Vector2i.ZERO
var _first_target_pos: Vector2i = Vector2i.ZERO
var _second_target_pos: Vector2i = Vector2i.ZERO
var _has_analyzed_spawn := false

func configure(ai_manager, grid_sampler, safety_checker) -> void:
	_ai_manager = ai_manager
	_grid_sampler = grid_sampler
	_bomb_safety_checker = safety_checker

## T=0.00s: Analyze spawn pocket and find optimal first bomb position
func analyse_spawn_pocket(spawn_pos: Vector2i, bomb_range: int) -> Vector2i:
	_spawn_pos = spawn_pos
	_has_analyzed_spawn = true
	
	# 1. NEIGHBOUR SCAN - identify exits vs walls
	var exits: Array[Vector2i] = []
	var directions := [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
	
	for dir: Vector2i in directions:
		var neighbor := spawn_pos + dir
		if not _grid_sampler.is_tile_walkable(neighbor):
			continue  # This is a wall (hard or soft)
		exits.append(neighbor)
	
	if exits.is_empty():
		# No valid exits (shouldn't happen in standard maps)
		return spawn_pos
	
	# 2. BLAST EFFICIENCY CALCULATION - score each exit
	var best_score := -1.0
	var best_pos: Vector2i = exits[0]
	
	for exit_pos in exits:
		var score := _calculate_blast_efficiency(exit_pos, bomb_range)
		if score > best_score:
			best_score = score
			best_pos = exit_pos
	
	_first_target_pos = best_pos
	print("[OpeningGambit] Spawn analysis complete. Best first target: ", best_pos, " (score: ", best_score, ")")
	return best_pos

## Calculate blast efficiency score for bombing from position
func _calculate_blast_efficiency(bomb_pos: Vector2i, range_val: int) -> float:
	var score := 0.0
	
	# Get all tiles that would be hit by blast
	var blast_tiles := _get_blast_tiles(bomb_pos, range_val)
	
	# Count destructible walls directly hit
	var walls_destroyed: Array[Vector2i] = []
	for tile: Vector2i in blast_tiles:
		var tile_type: int = _grid_sampler.get_tile_type(tile)
		if tile_type == 2:  # Soft wall
			score += 1.0
			walls_destroyed.append(tile)
	
	# CLUSTER BONUS: Check neighbors of destroyed walls for more walls
	for wall_tile in walls_destroyed:
		var cluster_size := _count_adjacent_walls(wall_tile)
		if cluster_size > 0:
			# Bonus points for revealing larger clusters
			score += cluster_size * 0.5
	
	return score

## Count adjacent soft walls around a tile (cluster detection)
func _count_adjacent_walls(tile: Vector2i) -> int:
	var count := 0
	var directions := [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
	
	for dir: Vector2i in directions:
		var neighbor := tile + dir
		var tile_type: int = _grid_sampler.get_tile_type(neighbor)
		if tile_type == 2:  # Soft wall
			count += 1
	
	return count

## Get all tiles affected by bomb blast (copied from AIManager for consistency)
func _get_blast_tiles(center: Vector2i, range_val: int) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	tiles.append(center)
	
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	var map_bounds: Vector2i = _grid_sampler.get_map_bounds()
	
	for dir: Vector2i in directions:
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			# Check bounds
			if tile.x < 0 or tile.x >= map_bounds.x or tile.y < 0 or tile.y >= map_bounds.y:
				break
			
			var tile_type: int = _grid_sampler.get_tile_type(tile)
			
			# Hard wall or hurry block stops blast completely
			if tile_type == 1 or tile_type == 3:
				break
			
			tiles.append(tile)
			
			# Soft wall stops blast after hitting it
			if tile_type == 2:
				break
	
	return tiles

## T=0.22s: Calculate chained action - plan NEXT bomb before current explodes
func calculate_chained_action(current_pos: Vector2i, bomb_range: int, current_time_msec: float) -> Dictionary:
	# Simulate future map state after first bomb explodes
	var simulated_walls := _simulate_future_walls(_first_target_pos, bomb_range)
	
	# Find best next target using simulated state
	var best_score := -1.0
	var best_next_pos: Vector2i = current_pos
	
	# Check tiles that will become available after blast
	for tile: Vector2i in simulated_walls:
		# This tile will be cleared - is it a good bombing position?
		var score := _calculate_blast_efficiency_simulated(tile, bomb_range, simulated_walls)
		if score > best_score:
			best_score = score
			best_next_pos = tile
	
	_second_target_pos = best_next_pos
	
	return {
		"next_target": best_next_pos,
		"score": best_score,
		"can_path_now": _can_path_to_target(current_pos, best_next_pos, current_time_msec)
	}

## Simulate which walls will be cleared after bomb at position explodes
func _simulate_future_walls(bomb_pos: Vector2i, range_val: int) -> Array[Vector2i]:
	var cleared_tiles: Array[Vector2i] = []
	var blast_tiles := _get_blast_tiles(bomb_pos, range_val)
	
	for tile: Vector2i in blast_tiles:
		var tile_type: int = _grid_sampler.get_tile_type(tile)
		if tile_type == 2:  # Soft wall that will be destroyed
			cleared_tiles.append(tile)
	
	return cleared_tiles

## Calculate blast efficiency using simulated future state
func _calculate_blast_efficiency_simulated(bomb_pos: Vector2i, range_val: int, simulated_cleared: Array[Vector2i]) -> float:
	var score := 0.0
	
	# Temporarily treat simulated tiles as walkable
	var blast_tiles := _get_blast_tiles_simulated(bomb_pos, range_val, simulated_cleared)
	
	for tile: Vector2i in blast_tiles:
		# Skip tiles that will already be cleared
		if tile in simulated_cleared:
			continue
		
		var tile_type: int = _grid_sampler.get_tile_type(tile)
		if tile_type == 2:  # Still-existing soft wall
			score += 1.0
	
	return score

## Get blast tiles accounting for simulated cleared walls
func _get_blast_tiles_simulated(center: Vector2i, range_val: int, cleared: Array[Vector2i]) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	tiles.append(center)
	
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	var map_bounds: Vector2i = _grid_sampler.get_map_bounds()
	
	for dir: Vector2i in directions:
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			if tile.x < 0 or tile.x >= map_bounds.x or tile.y < 0 or tile.y >= map_bounds.y:
				break
			
			# Check if tile is cleared in simulation
			if tile in cleared:
				tiles.append(tile)
				continue
			
			var tile_type: int = _grid_sampler.get_tile_type(tile)
			
			if tile_type == 1 or tile_type == 3:  # Hard wall or hurry block
				break
			
			tiles.append(tile)
			
			if tile_type == 2:  # Soft wall
				break
	
	return tiles

## Check if path to target exists with current threats
func _can_path_to_target(from_pos: Vector2i, to_pos: Vector2i, current_time_msec: float) -> bool:
	if _ai_manager == null or _ai_manager.pathfinder == null:
		return false
	
	# Configure pathfinder for time-aware query
	var pathfinder = _ai_manager.pathfinder
	pathfinder.threat_matrix_ref = _ai_manager.get_current_threat_matrix()
	pathfinder.path_start_time_msec = current_time_msec
	pathfinder.path_start_pos = from_pos
	pathfinder.bot_speed_msec_per_tile = 200.0  # Default speed
	
	# Try to find path
	var path: PackedVector2Array = pathfinder.get_timed_point_path(from_pos, to_pos)
	return not path.is_empty()

## Get cached first target (after spawn analysis)
func get_first_target() -> Vector2i:
	return _first_target_pos

## Get cached second target (after chained calculation)
func get_second_target() -> Vector2i:
	return _second_target_pos

## Check if spawn has been analyzed
func has_analyzed_spawn() -> bool:
	return _has_analyzed_spawn
