@tool
extends BTCondition
class_name BTMustEscapeNow

## CRITICAL: Returns SUCCESS if bot MUST escape immediately (just planted bomb)
## This is used to override farming/combat and force escape behavior

@export var mandatory_escape_duration_ms: float = 1000.0 ## How long escape is mandatory after planting
@export var debug_logging: bool = false

func _generate_name() -> String:
	return "MustEscapeNow"

func _tick(_delta: float) -> int:
	var last_bomb_placed_time = blackboard.get_var("last_bomb_placed_time", -9999.0)
	
	if last_bomb_placed_time < 0:
		# No bomb planted recently
		return FAILURE
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var time_since_plant = (current_time - last_bomb_placed_time) * 1000.0
	
	if time_since_plant < mandatory_escape_duration_ms:
		# MUST escape now!
		if debug_logging:
			print("[BTMustEscapeNow] ✓ Mandatory escape active (%.0fms remaining)" % (mandatory_escape_duration_ms - time_since_plant))
		return SUCCESS
	
	# Escape period over
	return FAILURE
