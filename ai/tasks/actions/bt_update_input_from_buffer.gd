@tool
extends BTAction
class_name BTUpdateInputFromBuffer

## Reads the latest input from the input buffer and stores it in the blackboard
## This allows the BT to process client inputs frame-by-frame
## Essential for player-controlled entities in authoritative server architecture

@export var peek_only: bool = true ## If true, don't consume input (just read it)

func _generate_name() -> String:
	return "UpdateInputFromBuffer" if peek_only else "ConsumeInputFromBuffer"

func _tick(delta: float) -> int:
	var input_buffer = blackboard.get_var("input_buffer")
	var player = blackboard.get_var("player")
	
	if not input_buffer:
		push_warning("[BTUpdateInputFromBuffer] Missing input_buffer in blackboard")
		return FAILURE
	
	if not player:
		push_warning("[BTUpdateInputFromBuffer] Missing player in blackboard")
		return FAILURE
	
	# Skip for AI bots - they control input directly, not via buffer
	if player.is_bot:
		return SUCCESS
	
	# Get input (peek or consume based on setting)
	var input_data: Dictionary
	if peek_only:
		input_data = input_buffer.peek_latest()
	else:
		input_data = input_buffer.consume_latest()
	
	if input_data.is_empty():
		# No input available, set neutral state
		player.set_input(0.0, 0.0)
		_clear_input_blackboard_vars()
		return SUCCESS
	
	# Extract input values
	var input_x = input_data.get("input_x", 0.0)
	var input_y = input_data.get("input_y", 0.0)
	var action_pressed = input_data.get("action_pressed", false)
	var action_released = input_data.get("action_released", false)
	var place_bomb = input_data.get("place_bomb", false)
	
	# Set movement input on player
	player.set_input(input_x, input_y)
	
	# Store input state in blackboard for other nodes to use
	blackboard.set_var("input_x", input_x)
	blackboard.set_var("input_y", input_y)
	blackboard.set_var("action_pressed", action_pressed)
	blackboard.set_var("action_released", action_released)
	blackboard.set_var("place_bomb", place_bomb)
	blackboard.set_var("has_input", true)
	
	return SUCCESS

func _clear_input_blackboard_vars():
	"""Clear input-related blackboard variables"""
	blackboard.set_var("input_x", 0.0)
	blackboard.set_var("input_y", 0.0)
	blackboard.set_var("action_pressed", false)
	blackboard.set_var("action_released", false)
	blackboard.set_var("place_bomb", false)
	blackboard.set_var("has_input", false)
