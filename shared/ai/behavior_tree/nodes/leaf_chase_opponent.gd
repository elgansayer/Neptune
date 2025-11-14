extends BTNode
class_name BTChaseOpponentNode

## Targets the nearest living opponent and selects a goal tile toward them.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var tracker: OpponentTracker = blackboard.get("opponent_tracker")
	var grid_sampler: GridSampler = blackboard.get("grid_sampler")
	var player = blackboard.get("player")
	var current_tile: Vector2i = blackboard.get("current_tile")
	if tracker == null or grid_sampler == null or player == null or current_tile == null:
		return false
	var opponent = blackboard.get("nearest_opponent")
	if opponent == null or opponent.is_empty():
		opponent = tracker.get_nearest_opponent(player.position)
	if opponent.is_empty():
		return false
	var tile: Vector2i = opponent.get("tile", current_tile)
	if not grid_sampler.is_in_bounds(tile):
		return false
	if not grid_sampler.is_tile_walkable(tile, true):
		var fallback := _find_adjacent_walkable(tile, grid_sampler)
		if fallback == null:
			return false
		tile = fallback
	blackboard["goal_tile"] = tile
	blackboard["opponent_tile"] = tile
	blackboard["behavior"] = "attack"
	return true

func _find_adjacent_walkable(tile: Vector2i, sampler: GridSampler) -> Vector2i:
	for neighbor in sampler.get_cardinal_neighbors(tile):
		if sampler.is_tile_walkable(neighbor):
			return neighbor
	return null
