extends BTNode
class_name BTCollectPowerUpNode

## Chooses the closest safe power-up tile and sets it as the movement goal.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var game_instance = blackboard.get("game_instance")
	var grid_sampler: GridSampler = blackboard.get("grid_sampler")
	var hazard_predictor: HazardPredictor = blackboard.get("hazard_predictor")
	var current_tile: Vector2i = blackboard.get("current_tile")
	if game_instance == null or grid_sampler == null or current_tile == null:
		return false
	var best_tile: Vector2i
	var best_score := INF
	var now = blackboard.get("time", 0.0)
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		if not is_instance_valid(powerup):
			continue
		var tile = powerup.get_tile_position()
		if not grid_sampler.is_tile_walkable(tile, true):
			continue
		if hazard_predictor and not hazard_predictor.is_tile_safe(tile, now):
			continue
		var distance := grid_sampler.get_manhattan_distance(current_tile, tile)
		if distance < best_score:
			best_score = distance
			best_tile = tile
	if best_tile == null:
		return false
	blackboard["goal_tile"] = best_tile
	blackboard["behavior"] = "collect"
	return true
