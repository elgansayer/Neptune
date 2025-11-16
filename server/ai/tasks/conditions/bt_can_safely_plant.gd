@tool
extends BTCondition
class_name BTCanSafelyPlant

## Checks if the bot can safely plant a bomb at their current position and escape
## Uses BombSafetyChecker to verify an escape route exists

func _generate_name() -> String:
	return "CanSafelyPlant"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	
	if not player or not bomb_safety_checker:
		return FAILURE
	
	var current_tile = player.get_tile_position()
	var bomb_range = player.bomb_range
	var current_time_msec = Time.get_ticks_msec()
	
	# Check if we can safely plant at current position and escape
	if bomb_safety_checker.can_safely_plant_bomb(
		current_tile,  # Bot's current position
		current_tile,  # Where bomb will be planted (same as bot position)
		bomb_range,
		5.0,  # bot speed (tiles per second)
		current_time_msec
	):
		return SUCCESS
	
	return FAILURE
