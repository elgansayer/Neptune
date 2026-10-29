extends Resource
class_name OpponentTracker

var _tracked_opponents: Array[Dictionary] = []
var _opponent_history: Dictionary = {} ## peer_id -> Array[Dictionary] (position history)
var _max_history_entries: int = 10 ## How many past positions to track
var _behavior_patterns: Dictionary = {} ## peer_id -> behavior classification
var _game_instance: Node

func configure(game: Node) -> void:
	_game_instance = game

## Tracks other players in the game from the perspective of an AI.
## Enhanced with velocity tracking, movement patterns, and behavioral analysis

func reset() -> void:
	_tracked_opponents.clear()
	_opponent_history.clear()
	_behavior_patterns.clear()

func update_from_players(players: Array) -> void:
	var current_time: float = _game_instance.get_simulation_time_sec()
	
	_tracked_opponents.clear()
	for player in players:
		if not is_instance_valid(player):
			continue
		
		# Skip if player is dead
		if player.is_dead:
			continue
		
		# Skip if player is a bot (only track real players and other bots)
		# We'll filter out self later in get_nearest_opponent
		
		var peer_id = player.peer_id
		var current_pos = player.position
		var current_tile = player.get_tile_position()
		
		# Calculate velocity from position history
		var velocity = _calculate_velocity(peer_id, current_pos, current_time)
		
		# Update position history
		_update_position_history(peer_id, current_pos, current_time)
		
		# Analyze behavioral pattern
		var behavior = _analyze_behavior_pattern(peer_id, velocity, current_tile, current_time)
		
		_tracked_opponents.append({
			"peer_id": peer_id,
			"name": player.player_name,
			"position": current_pos,
			"tile": current_tile,
			"velocity": velocity,
			"speed": velocity.length(),
			"is_dead": player.is_dead,
			"behavior_pattern": behavior,
			"time": current_time
		})

func get_nearest_opponent(from_position: Vector2, exclude_peer_id: int = -999999) -> Dictionary:
	var best := {}
	var best_dist := INF
	for opponent in _tracked_opponents:
		if opponent.get("is_dead", false):
			continue
		
		# Skip if this is the same peer (bot tracking itself)
		if opponent.get("peer_id") == exclude_peer_id:
			continue
		
		var dist := from_position.distance_to(opponent.get("position", from_position))
		if dist < best_dist:
			best_dist = dist
			best = opponent
	return best

## Calculate velocity from position history
func _calculate_velocity(peer_id: int, current_pos: Vector2, current_time: float) -> Vector2:
	if not _opponent_history.has(peer_id):
		return Vector2.ZERO
	
	var history = _opponent_history[peer_id]
	if history.size() < 2:
		return Vector2.ZERO
	
	# Get most recent historical position
	var prev_entry = history[-1]
	var prev_pos = prev_entry["position"]
	var prev_time = prev_entry["time"]
	
	var time_delta = current_time - prev_time
	if time_delta <= 0:
		return Vector2.ZERO
	
	var displacement = current_pos - prev_pos
	return displacement / time_delta

## Update position history for velocity calculation
func _update_position_history(peer_id: int, position: Vector2, time: float) -> void:
	if not _opponent_history.has(peer_id):
		_opponent_history[peer_id] = []
	
	var history = _opponent_history[peer_id]
	history.append({
		"position": position,
		"time": time
	})
	
	# Limit history size
	while history.size() > _max_history_entries:
		history.pop_front()

## Analyze opponent's behavior pattern (aggressive, defensive, neutral)
func _analyze_behavior_pattern(peer_id: int, velocity: Vector2, current_tile: Vector2i, current_time: float) -> String:
	if not _behavior_patterns.has(peer_id):
		_behavior_patterns[peer_id] = {
			"movement_samples": [],
			"last_classification": "NEUTRAL",
			"classification_time": 0.0
		}
	
	var pattern_data = _behavior_patterns[peer_id]
	var speed = velocity.length()
	
	# Store movement sample
	pattern_data["movement_samples"].append(speed)
	if pattern_data["movement_samples"].size() > 20:
		pattern_data["movement_samples"].pop_front()
	
	# Only reclassify every 2 seconds
	if current_time - pattern_data["classification_time"] < 2.0:
		return pattern_data["last_classification"]
	
	# Calculate average speed over recent samples
	var samples = pattern_data["movement_samples"]
	if samples.size() < 5:
		return "NEUTRAL"
	
	var avg_speed = 0.0
	for s in samples:
		avg_speed += s
	avg_speed /= samples.size()
	
	# Classify based on average speed and movement frequency
	var classification = "NEUTRAL"
	if avg_speed > 80.0:  # Fast movement = aggressive
		classification = "AGGRESSIVE"
	elif avg_speed < 30.0:  # Slow/cautious = defensive
		classification = "DEFENSIVE"
	
	pattern_data["last_classification"] = classification
	pattern_data["classification_time"] = current_time
	
	return classification

## Get opponent by peer_id
func get_opponent_by_id(peer_id: int) -> Dictionary:
	for opponent in _tracked_opponents:
		if opponent.get("peer_id") == peer_id:
			return opponent
	return {}

## Get all tracked opponents (including velocity data)
func get_all_opponents() -> Array[Dictionary]:
	return _tracked_opponents
