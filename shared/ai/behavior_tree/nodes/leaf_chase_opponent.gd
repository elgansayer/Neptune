extends "res://shared/ai/behavior_tree/nodes/base_node.gd"
class_name BTChaseOpponentNode

## Targets the nearest living opponent and selects a goal tile toward them.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var opponent_tracker = blackboard.get("opponent_tracker")
	var grid_sampler = blackboard.get("grid_sampler")
	var player = blackboard.get("player")
	var current_tile: Vector2i = blackboard.get("current_tile")
	if opponent_tracker == null or grid_sampler == null or player == null or current_tile == null:
		return false
	var opponent = blackboard.get("nearest_opponent")
	if opponent == null or opponent.is_empty():
		opponent = opponent_tracker.get_nearest_opponent(player.position)
	if opponent.is_empty():
		return false
	var tile: Vector2i = opponent.get("tile", current_tile)
	if not grid_sampler.is_in_bounds(tile):
		return false
	if not grid_sampler.is_tile_walkable(tile, true):
		var fallback := _find_adjacent_walkable(tile, grid_sampler)
		if fallback == Vector2i(-9999, -9999):
			return false
		tile = fallback
	blackboard["goal_tile"] = tile
	blackboard["opponent_tile"] = tile
	blackboard["behavior"] = "attack"
	return true

func _find_adjacent_walkable(tile: Vector2i, sampler) -> Vector2i:
	for neighbor in sampler.get_cardinal_neighbors(tile):
		if sampler.is_tile_walkable(neighbor):
			return neighbor
	return Vector2i(-9999, -9999)  # Invalid position marker