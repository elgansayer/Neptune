extends "res://shared/ai/behavior_tree/nodes/base_node.gd"
class_name BTEscapeNode

## Locates the nearest safe tile when the bot is standing in danger.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var hazard_predictor = blackboard.get("hazard_predictor")
	var ai_manager = blackboard.get("ai_manager")
	var current_tile: Vector2i = blackboard.get("current_tile")
	if hazard_predictor == null or current_tile == null:
		return false
	
	var now = blackboard.get("time", 0.0)
	var buffer = blackboard.get("danger_buffer", 0.1)
	
	# Use new is_in_mortal_danger check
	if not hazard_predictor.is_in_mortal_danger(current_tile, now, buffer):
		return false  # Not in danger, no need to escape
	
	# Use AIManager pathfinder to find safe path
	if ai_manager != null and ai_manager.pathfinder != null:
		var current_time_msec := Time.get_ticks_msec()
		var pathfinder = ai_manager.pathfinder
		pathfinder.threat_matrix_ref = ai_manager.get_current_threat_matrix()
		pathfinder.path_start_time_msec = current_time_msec
		pathfinder.path_start_pos = current_tile
		pathfinder.bot_speed_msec_per_tile = 200.0
		
		# Find any safe tile (tiles with no threat)
		var escape_radius = int(blackboard.get("escape_radius", 8))
		var escape_tiles = hazard_predictor.find_escape_tiles(current_tile, now, escape_radius)
		
		if not escape_tiles.is_empty():
			# Verify path exists using time-aware pathfinder
			for safe_tile in escape_tiles:
				var path = pathfinder.get_point_path(current_tile, safe_tile)
				if not path.is_empty():
					blackboard["goal_tile"] = safe_tile
					blackboard["behavior"] = "escape"
					return true
	
	# Fallback to old method
	var escape_radius = int(blackboard.get("escape_radius", 8))
	var escape_tiles = hazard_predictor.find_escape_tiles(current_tile, now, escape_radius)
	if escape_tiles.is_empty():
		return false
	blackboard["goal_tile"] = escape_tiles[0]
	blackboard["behavior"] = "escape"
	return true
