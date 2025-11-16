@tool
extends BTAction
class_name BTFindEscapeRoute

## Finds a safe escape route from danger using the AI pathfinder
## Sets target_cell in blackboard if a safe path is found

@export var escape_radius: int = 8  ## How far to search for safety
@export var target_cell_var: StringName = &"target_cell"  ## Where to store the escape destination

func _generate_name() -> String:
	return "FindEscapeRoute"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var ai_manager = blackboard.get_var("ai_manager")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player or not game_instance or not ai_manager or not grid_sampler:
		push_warning("[BTFindEscapeRoute] Missing required blackboard variables")
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	# Find nearest safe tile (not in threat matrix)
	var best_safe_tile: Vector2i = Vector2i(-1, -1)
	var best_distance: int = 999999
	
	for radius in range(1, escape_radius + 1):
		for dx in range(-radius, radius + 1):
			for dy in range(-radius, radius + 1):
				if abs(dx) + abs(dy) != radius:  # Only check tiles at exact radius (diamond pattern)
					continue
				
				var check_tile = player_tile + Vector2i(dx, dy)
				
				# Must be walkable
				if not grid_sampler.is_tile_walkable(check_tile):
					continue
				
				# Must not be in threat matrix (safe from explosions)
				var tile_key = "%d,%d" % [check_tile.x, check_tile.y]
				if threat_matrix.has(tile_key):
					continue
				
				# Must be reachable
				var path = grid_sampler.find_path(player_tile, check_tile, escape_radius, player)
				if path.is_empty():
					continue
				
				# Found a safe tile - prefer closest
				var distance = abs(dx) + abs(dy)
				if distance < best_distance:
					best_distance = distance
					best_safe_tile = check_tile
		
		# If we found a safe tile at this radius, use it (prefer closer tiles)
		if best_safe_tile != Vector2i(-1, -1):
			break
	
	if best_safe_tile != Vector2i(-1, -1):
		# Found an escape route
		blackboard.set_var(target_cell_var, best_safe_tile)
		blackboard.set_var("escape_route_found", true)
		print("[BTFindEscapeRoute] Found escape route to ", best_safe_tile, " (distance: ", best_distance, ")")
		return SUCCESS
	
	# No escape route found
	blackboard.set_var("escape_route_found", false)
	print("[BTFindEscapeRoute] No escape route found!")
	return FAILURE
