@tool
extends BTAction
class_name BTMoveToCell

## Moves the entity toward a target cell
## Sets the input direction and returns RUNNING until destination is reached

@export var cell_var: StringName = &"target_cell"  ## Blackboard variable containing target cell
@export var reach_threshold: float = 0.3  ## Distance threshold (in tiles) to consider destination reached
@export var clear_on_success: bool = true  ## Clear target_cell from blackboard when reached

func _generate_name() -> String:
	return "MoveToCell(%s)" % cell_var

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var target_cell = blackboard.get_var(cell_var)
	
	if not player:
		push_warning("[BTMoveToCell] Missing player in blackboard")
		return FAILURE
	
	if target_cell == null:
		push_warning("[BTMoveToCell] No target cell set in blackboard variable '%s'" % cell_var)
		return FAILURE
	
	# Convert to Vector2i if needed
	if not target_cell is Vector2i:
		if target_cell is Vector2:
			target_cell = Vector2i(int(target_cell.x), int(target_cell.y))
		else:
			push_warning("[BTMoveToCell] Invalid target cell type: %s" % target_cell)
			return FAILURE
	
	# Calculate target world position (center of tile)
	var target_pos = Vector2(
		target_cell.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		target_cell.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	# Calculate direction to target
	var direction = (target_pos - player.position).normalized()
	
	# Set player input (this will be processed by CharacterBody2D movement)
	player.set_input(direction.x, direction.y)
	
	# Check if we've reached the destination
	var distance = player.position.distance_to(target_pos)
	var threshold_pixels = GameConfig.TILE_SIZE * reach_threshold
	
	if distance < threshold_pixels:
		# Reached destination
		if clear_on_success:
			blackboard.set_var(cell_var, null)
		
		# Stop movement
		player.set_input(0.0, 0.0)
		
		return SUCCESS
	
	# Still moving
	return RUNNING
