@tool
extends BTAction
class_name BTFindFarmingSpot

## Finds a nearby soft block position that has an escape route
## Sets target_cell in blackboard for safe bomb placement

@export var search_radius: int = 5 ## How far to search for soft blocks
@export var target_cell_var: StringName = &"target_cell" ## Where to store the target

const INVALID_TILE := Vector2i(-1, -1)

func _generate_name() -> String:
	return "FindFarmingSpot(radius=%d)" % search_radius

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	
	if not player or not game_instance or not grid_sampler or not bomb_safety_checker:
		return FAILURE
	
	var current_tile = player.get_tile_position()
	var bomb_range = player.bomb_range
	var current_time_msec = Time.get_ticks_msec()

	# If we already have a valid farming target, reuse it to avoid expensive rescans every tick
	var existing_target = _coerce_to_tile(blackboard.get_var(target_cell_var))
	if _is_valid_target(existing_target, grid_sampler, bomb_range):
		return SUCCESS
	
	# Search nearby tiles for soft blocks
	var best_spot: Vector2i = INVALID_TILE
	var best_score: float = 0.0
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			if dx == 0 and dy == 0:
				continue
			
			var check_tile = current_tile + Vector2i(dx, dy)
			
			# Must be walkable
			if not grid_sampler.is_tile_walkable(check_tile):
				continue
			
			# Count soft blocks in bomb range - skip if none
			var soft_blocks_hit = _count_soft_blocks_in_range(check_tile, bomb_range, grid_sampler)
			if soft_blocks_hit == 0:
				continue
			
			# Check if we can reach this tile
			var path = grid_sampler.find_path(current_tile, check_tile, 15, player)
			if path.is_empty() and check_tile != current_tile:
				continue
			
			# CRITICAL: Check if there's ALREADY a safe tile nearby (without planting bomb)
			# This ensures we're not in a dead-end surrounded by soft blocks
			var has_nearby_safety = _has_safe_tile_nearby(check_tile, grid_sampler, current_time_msec)
			if not has_nearby_safety:
				continue
			
			# Check if we can safely plant a bomb HERE (at check_tile) and escape
			# IMPORTANT: bot_pos is check_tile because that's where we'll be when planting
			if not bomb_safety_checker.can_safely_plant_bomb(
				check_tile, # Where the bot will be standing when planting
				check_tile, # Where the bomb will be planted
				bomb_range,
				5.0, # bot speed
				current_time_msec
			):
				continue
			
			# Score: prioritize closer tiles with more soft blocks
			var distance = abs(dx) + abs(dy)
			var score = (soft_blocks_hit * 10.0) - (distance * 0.5)
			
			if score > best_score:
				best_score = score
				best_spot = check_tile
	
	# If we found a good spot, store it
	if best_spot != INVALID_TILE:
		blackboard.set_var(target_cell_var, best_spot)
		print("[BTFindFarmingSpot] Found farming spot at ", best_spot, " (score: ", best_score, ")")
		return SUCCESS
	
	# No good farming spot found
	print("[BTFindFarmingSpot] No safe farming spots found")
	return FAILURE

func _count_soft_blocks_in_range(center: Vector2i, bomb_range: int, grid_sampler) -> int:
	var count = 0
	
	# Check horizontal (right)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check horizontal (left)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(-dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (down)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (up)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, -dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	return count

func _has_safe_tile_nearby(position: Vector2i, grid_sampler, current_time_msec: float) -> bool:
	"""Check if there's at least one safe tile within reasonable distance (no threats, walkable)"""
	var ai_manager = blackboard.get_var("ai_manager")
	if not ai_manager:
		return false
	
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var max_distance = 4 # tiles
	
	# Check if ANY nearby tile is safe (not in threat matrix and walkable)
	for dx in range(-max_distance, max_distance + 1):
		for dy in range(-max_distance, max_distance + 1):
			var check_pos = position + Vector2i(dx, dy)
			
			if not grid_sampler.is_tile_walkable(check_pos):
				continue
			
			var tile_key = "%d,%d" % [check_pos.x, check_pos.y]
			
			# If this tile is not in the threat matrix, it's safe
			if not threat_matrix.has(tile_key):
				return true
	
	# No safe tiles found nearby - we're in a danger zone
	return false

func _coerce_to_tile(value) -> Vector2i:
	if value == null:
		return INVALID_TILE
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	if typeof(value) == TYPE_DICTIONARY and value.has("x") and value.has("y"):
		return Vector2i(int(value.x), int(value.y))
	return INVALID_TILE

func _is_valid_target(tile: Vector2i, grid_sampler, bomb_range: int) -> bool:
	if tile == INVALID_TILE:
		return false
	if not grid_sampler.is_tile_walkable(tile):
		return false
	if _count_soft_blocks_in_range(tile, bomb_range, grid_sampler) == 0:
		return false
	return true
