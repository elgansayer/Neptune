@tool
extends BTCondition
class_name BTIsCellWalkable

## Checks if a specific cell is walkable (not a wall or obstacle)
## Uses GridSampler to query map state

@export var cell_var: StringName = &"target_cell"  ## Blackboard variable containing the cell to check

func _generate_name() -> String:
	return "IsCellWalkable(%s)" % cell_var

func _tick(delta: float) -> int:
	var grid_sampler = blackboard.get_var("grid_sampler")
	var cell = blackboard.get_var(cell_var)
	
	if not grid_sampler:
		push_warning("[BTIsCellWalkable] Missing grid_sampler in blackboard")
		return FAILURE
	
	if cell == null:
		push_warning("[BTIsCellWalkable] Cell variable '%s' not found in blackboard" % cell_var)
		return FAILURE
	
	# Ensure cell is Vector2i
	if not cell is Vector2i:
		if cell is Vector2:
			cell = Vector2i(int(cell.x), int(cell.y))
		else:
			push_warning("[BTIsCellWalkable] Cell is not a valid position: %s" % cell)
			return FAILURE
	
	if grid_sampler.is_tile_walkable(cell):
		return SUCCESS
	else:
		return FAILURE
