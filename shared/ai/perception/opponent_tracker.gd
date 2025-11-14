extends Resource
class_name OpponentTracker

## Tracks opponent positions, last-seen tiles, and aggression cues for BT consumption.

var opponents := {}

func reset() -> void:
	opponents.clear()

func update_from_players(player_nodes: Array) -> void:
	for player in player_nodes:
		if player == null:
			continue
		var player_id := player.player_id if player.has_method("player_id") else player.get_instance_id()
		opponents[player_id] = {
			"position": player.position,
			"tile": player.get_tile_position() if player.has_method("get_tile_position") else Vector2i.ZERO,
			"is_dead": player.is_dead if "is_dead" in player else false,
			"has_power_glove": player.has_power_glove if "has_power_glove" in player else false
		}

func get_nearest_opponent(from_position: Vector2) -> Dictionary:
	var best := {}
	var best_dist := INF
	for opponent in opponents.values():
		if opponent.get("is_dead", false):
			continue
		var dist := from_position.distance_to(opponent.get("position", from_position))
		if dist < best_dist:
			best_dist = dist
			best = opponent
	return best
