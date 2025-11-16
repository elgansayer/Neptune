@tool
extends BTAction
class_name BTFindFarmingSpot

## Finds a nearby soft block position that has an escape route
## Sets target_cell in blackboard for safe bomb placement

@export var search_radius: int = 5  ## How far to search for soft blocks
@export var target_cell_var: StringName = &"target_cell"  ## Where to store the target

func _generate_name() -> String:
	return "FindFarmingSpot(radius=%d)" % search_radius

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var ai_manager = blackboard.get_var("ai_manager")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	
	if not player or not game_instance or not ai_manager or not bomb_safety_checker:
		return FAILURE
	
	var current_tile = player.get_tile_position()
	var bomb_range = player.bomb_range
	var current_time_msec = Time.get_ticks_msec()
	
	# Search nearby tiles for soft blocks
	var best_spot: Vector2i = Vector2i(-1, -1)
	var best_score: float = 0.0
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			if dx == 0 and dy == 0:
				continue
			
			var check_tile = current_tile + Vector2i(dx, dy)
			
			# Must be walkable
			if not ai_manager.grid_sampler.is_tile_walkable(check_tile):
				continue
			
			# Check if we can safely plant a bomb here and escape
			if not bomb_safety_checker.can_safely_plant_bomb(
				check_tile,
				check_tile,
				bomb_range,
				5.0,  # bot speed
				current_time_msec
			):
				continue
			
			# Count soft blocks in bomb range
			var soft_blocks_hit = _count_soft_blocks_in_range(check_tile, bomb_range, ai_manager)
			
			if soft_blocks_hit == 0:
				continue
			
			# Score: prioritize closer tiles with more soft blocks
			var distance = abs(dx) + abs(dy)
			var score = (soft_blocks_hit * 10.0) - (distance * 0.5)
			
			if score > best_score:
				best_score = score
				best_spot = check_tile
	
	# If we found a good spot, store it
	if best_spot != Vector2i(-1, -1):
		blackboard.set_var(target_cell_var, best_spot)
		return SUCCESS
	
	# No good farming spot found
	return FAILURE

func _count_soft_blocks_in_range(center: Vector2i, bomb_range: int, ai_manager) -> int:
	var count = 0
	var grid_sampler = ai_manager.grid_sampler
	
	# Check horizontal
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(dx, 0)
		if grid_sampler.is_tile_soft_block(tile):
			count += 1
		if not grid_sampler.is_tile_walkable(tile) and not grid_sampler.is_tile_soft_block(tile):
			break
	
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(-dx, 0)
		if grid_sampler.is_tile_soft_block(tile):
			count += 1
		if not grid_sampler.is_tile_walkable(tile) and not grid_sampler.is_tile_soft_block(tile):
			break
	
	# Check vertical
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, dy)
		if grid_sampler.is_tile_soft_block(tile):
			count += 1
		if not grid_sampler.is_tile_walkable(tile) and not grid_sampler.is_tile_soft_block(tile):
			break
	
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, -dy)
		if grid_sampler.is_tile_soft_block(tile):
			count += 1
		if not grid_sampler.is_tile_walkable(tile) and not grid_sampler.is_tile_soft_block(tile):
			break
	
	return count
