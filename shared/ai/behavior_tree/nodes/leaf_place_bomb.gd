extends "res://shared/ai/behavior_tree/nodes/base_node.gd"
class_name BTPlaceBombNode

## Requests bomb placement when BombPlanner and personality gates approve.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var bomb_planner = blackboard.get("bomb_planner")
	var bomb_safety_checker = blackboard.get("bomb_safety_checker")
	var player = blackboard.get("player")
	
	if player == null or not player.can_place_bomb():
		return true
	
	var current_tile: Vector2i = blackboard.get("current_tile")
	var opponent_tile: Vector2i = blackboard.get("opponent_tile")
	var now = blackboard.get("time", 0.0)
	var current_time_msec := Time.get_ticks_msec()
	
	# Use new BombSafetyChecker for suicide prevention
	if bomb_safety_checker != null:
		var is_safe: bool = bomb_safety_checker.can_safely_plant_bomb(
			current_tile, current_tile, player.bomb_range,
			5.0, current_time_msec
		)
		if not is_safe:
			return true  # Abort - would be suicide
	
	# Check if we should attack target
	if bomb_planner != null:
		if opponent_tile != null and not bomb_planner.should_attack_target(current_tile, opponent_tile, player.bomb_range):
			return true
		
		# Plan escape route
		var escape_tile = bomb_planner.plan_escape_after_bomb(current_tile, player, now)
		if escape_tile == null:
			return true  # No escape route
		
		blackboard["goal_tile"] = escape_tile
	
	# Place the bomb
	blackboard["request_bomb"] = true
	blackboard["behavior"] = "escape_after_bomb"
	
	return true
