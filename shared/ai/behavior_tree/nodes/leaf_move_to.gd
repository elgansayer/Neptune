extends BTNode
class_name BTMoveToNode

## Requests a grid path and maps it to a normalized move vector for the player.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var grid_sampler: GridSampler = blackboard.get("grid_sampler")
	var goal_tile: Vector2i = blackboard.get("goal_tile")
	var current_tile: Vector2i = blackboard.get("current_tile")
	var player = blackboard.get("player")
	if grid_sampler == null or goal_tile == null or current_tile == null or player == null:
		return false
	if goal_tile == current_tile:
		blackboard["move_vector"] = Vector2.ZERO
		return true
	var depth := int(blackboard.get("path_depth", 40))
	var path: Array = grid_sampler.find_path(current_tile, goal_tile, depth, player)
	if path.is_empty():
		return false
	var next_tile: Vector2i = path[0]
	blackboard["next_tile"] = next_tile
	var next_world = grid_sampler.tile_to_world_center(next_tile)
	var current_world: Vector2 = blackboard.get("current_world", next_world)
	var move_vec := (next_world - current_world)
	if move_vec.length() < 0.01:
		return false
	blackboard["move_vector"] = move_vec.normalized()
	return true
