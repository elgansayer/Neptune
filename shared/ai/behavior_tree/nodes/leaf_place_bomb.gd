extends BTNode
class_name BTPlaceBombNode

## Requests bomb placement when BombPlanner and personality gates approve.

func tick(blackboard: Dictionary, _delta: float) -> bool:
	var bomb_planner: BombPlanner = blackboard.get("bomb_planner")
	var player = blackboard.get("player")
	if bomb_planner == null or player == null:
		return true
	if not player.can_place_bomb():
		return true
	var current_tile: Vector2i = blackboard.get("current_tile")
	var opponent_tile: Vector2i = blackboard.get("opponent_tile")
	var now = blackboard.get("time", 0.0)
	if opponent_tile != null and not bomb_planner.should_attack_target(current_tile, opponent_tile, player.bomb_range):
		return true
	if not bomb_planner.can_place_bomb_safely(current_tile, player, now):
		return true
	blackboard["request_bomb"] = true
	return true
