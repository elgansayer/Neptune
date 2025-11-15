extends RefCounted
class_name InputBuffer

## Input buffer system for authoritative server player control
## Buffers client inputs received via RPC so that Behavior Trees can process them
## This decouples input reception (async RPC) from BT processing (sync physics frame)

const MAX_BUFFER_SIZE: int = 10  ## Maximum number of inputs to buffer

var inputs: Array[Dictionary] = []

## Add a new input to the buffer
func push_input(input_data: Dictionary) -> void:
	inputs.append(input_data)
	
	# Prevent buffer overflow
	if inputs.size() > MAX_BUFFER_SIZE:
		inputs.pop_front()  # Remove oldest input

## Get the latest input without removing it (peek)
func peek_latest() -> Dictionary:
	if inputs.is_empty():
		return {}
	return inputs.back()

## Get and remove the latest input (consume)
func consume_latest() -> Dictionary:
	if inputs.is_empty():
		return {}
	return inputs.pop_back()

## Check if there are any inputs in the buffer
func has_input() -> bool:
	return not inputs.is_empty()

## Get the number of buffered inputs
func size() -> int:
	return inputs.size()

## Clear all buffered inputs
func clear() -> void:
	inputs.clear()

## Get all inputs (for debugging)
func get_all() -> Array[Dictionary]:
	return inputs.duplicate()

## Remove old inputs (if implementing timestamp-based expiry)
func prune_old_inputs(max_age_ms: float) -> void:
	var current_time = Time.get_ticks_msec()
	
	# Filter out inputs older than max_age_ms
	inputs = inputs.filter(func(input_data):
		var timestamp = input_data.get("timestamp", current_time)
		return (current_time - timestamp) <= max_age_ms
	)
