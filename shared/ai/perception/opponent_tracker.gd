extends Resource
class_name OpponentTracker

var _tracked_opponents: Array[Dictionary] = []

## Tracks other players in the game from the perspective of an AI.

func reset() -> void:
	_tracked_opponents.clear()

func update_from_players(players: Array) -> void:
	_tracked_opponents.clear()
	for player in players:
		if not is_instance_valid(player):
			continue
		_tracked_opponents.append({
			"peer_id": player.peer_id,
			"name": player.player_name,
			"position": player.position,
			"tile": player.get_tile_position(),
			"is_dead": player.is_dead
		})

func get_nearest_opponent(from_position: Vector2) -> Dictionary:
	var best := {}
	var best_dist := INF
	for opponent in _tracked_opponents:
		if opponent.get("is_dead", false):
			continue
		var dist := from_position.distance_to(opponent.get("position", from_position))
		if dist < best_dist:
			best_dist = dist
			best = opponent
	return best
