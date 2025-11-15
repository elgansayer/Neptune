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
	
	if not player or not game_instance or not ai_manager:
		push_warning("[BTFindEscapeRoute] Missing required blackboard variables")
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var current_time_msec = Time.get_ticks_msec()
	
	# Use danger-aware pathfinder to find safe cell
	if ai_manager.pathfinder:
		var escape_cell = ai_manager.pathfinder.find_nearest_safe_cell(
			player_tile,
			current_time_msec,
			escape_radius
		)
		
		if escape_cell and escape_cell != player_tile:
			# Found an escape route
			blackboard.set_var(target_cell_var, escape_cell)
			blackboard.set_var("escape_route_found", true)
			return SUCCESS
	
	# No escape route found
	blackboard.set_var("escape_route_found", false)
	return FAILURE
