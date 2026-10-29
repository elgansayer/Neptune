@tool
extends BTCondition
class_name BTHasEscapeGracePeriod

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## CRITICAL SAFETY CHECK: Prevents bot from planting another bomb
## during the grace period after planting the previous bomb.
## This ensures bot ESCAPES after planting instead of planting repeatedly and dying.

@export var grace_period_ms: float = 800.0 ## Milliseconds after bomb plant where NO new bombs allowed
@export var debug_logging: bool = false

func _generate_name() -> String:
	return "HasEscapeGracePeriod"

func _tick(_delta: float) -> int:
	var last_bomb_placed_time = blackboard.get_var("last_bomb_placed_time", -9999.0)
	
	if last_bomb_placed_time < 0:
		# Never placed a bomb, no grace period active
		return SUCCESS
	
	var current_time = SimulationTime.seconds(blackboard)
	var time_since_plant = (current_time - last_bomb_placed_time) * 1000.0 # Convert to ms
	
	if time_since_plant < grace_period_ms:
		# Grace period still active - MUST escape, cannot plant
		if debug_logging:
			print("[BTHasEscapeGracePeriod] ⚠ Grace period active (%.0fms remaining)" % (grace_period_ms - time_since_plant))
		return FAILURE
	
	# Grace period expired, can plant again
	return SUCCESS
