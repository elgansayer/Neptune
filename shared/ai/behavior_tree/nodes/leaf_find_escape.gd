extends BTNode
class_name BTEscapeNode

## Locates the nearest safe tile when the bot is standing in danger.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var hazard: HazardPredictor = blackboard.get("hazard_predictor")
	var current_tile: Vector2i = blackboard.get("current_tile")
	if hazard == null or current_tile == null:
		return false
	var now = blackboard.get("time", 0.0)
	var buffer = blackboard.get("danger_buffer", 0.5)
	if hazard.is_tile_safe(current_tile, now, buffer):
		return false
	var escape_radius = int(blackboard.get("escape_radius", 8))
	var escape_tiles = hazard.find_escape_tiles(current_tile, now, escape_radius)
	if escape_tiles.is_empty():
		return false
	blackboard["goal_tile"] = escape_tiles[0]
	blackboard["behavior"] = "escape"
	return true
