@tool
extends BTCondition
class_name BTIsAtTarget

## Checks if the bot is currently at the target cell

@export var target_cell_var: StringName = &"target_cell"

func _generate_name() -> String:
	return "IsAtTarget(%s)" % target_cell_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var target_tile = _coerce_to_tile(blackboard.get_var(target_cell_var))
	
	if not player:
		return FAILURE
	
	if target_tile == Vector2i(-1, -1):
		return FAILURE
	
	var current_tile = player.get_tile_position()
	
	if current_tile == target_tile:
		return SUCCESS
	else:
		return FAILURE

func _coerce_to_tile(value) -> Vector2i:
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	return Vector2i(-1, -1)
