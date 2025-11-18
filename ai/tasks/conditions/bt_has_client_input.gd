@tool
extends BTCondition
class_name BTHasClientInput

## Checks if there is client input available in the input buffer
## Used for player-controlled entities to determine if action should be taken

@export var input_action: String = "action_pressed"  ## Specific input to check for
@export var check_any: bool = false  ## Check for any input instead of specific action

func _generate_name() -> String:
	if check_any:
		return "HasAnyInput"
	return "HasInput(%s)" % input_action

func _tick(delta: float) -> int:
	if check_any:
		# Check if input buffer has any input
		var input_buffer = blackboard.get_var("input_buffer")
		if input_buffer and input_buffer.has_input():
			return SUCCESS
		return FAILURE
	else:
		# Check for specific input action
		var input_val = blackboard.get_var(input_action, false)
		if input_val:
			return SUCCESS
		return FAILURE
