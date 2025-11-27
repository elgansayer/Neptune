@tool
extends BTCondition
class_name BTHasOpponent

## Checks if an opponent is detected within range
## Uses OpponentTracker to find nearest enemy

@export var max_distance: float = -1.0 ## Maximum detection range (-1 = unlimited)
@export var store_in_blackboard: bool = true ## Whether to store opponent data for later use

func _generate_name() -> String:
	if max_distance > 0:
		return "HasOpponent (range: %.0f)" % max_distance
	return "HasOpponent"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	
	if not player or not opponent_tracker:
		# print("[BTHasOpponent] FAILURE: Missing player or opponent_tracker")
		return FAILURE
	
	var all_opponents = opponent_tracker.get_all_opponents()
	# print("[BTHasOpponent] Total tracked opponents: ", all_opponents.size())
	
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		# print("[BTHasOpponent] FAILURE: No opponents found (after excluding self peer_id=", player.peer_id, ")")
		blackboard.set_var("nearest_opponent", null)
		blackboard.set_var("opponent_tile", null)
		# print("[BTHasOpponent] No opponents found (peer_id=", player.peer_id, ")")
		return FAILURE
	
	# Get grid_sampler and player_tile for distance and reachability checks
	var grid_sampler = blackboard.get_var("grid_sampler")
	var player_tile = player.get_tile_position()
	var opponent_tile = nearest.get("tile", null)
	
	if opponent_tile == null:
		return FAILURE
	
	# Check distance if max_distance is set
	if max_distance > 0 and grid_sampler:
		var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
		# print("[BTHasOpponent] Found opponent at distance ", distance, " (max=", max_distance, ")")
		if distance > max_distance:
			blackboard.set_var("nearest_opponent", null)
			blackboard.set_var("opponent_tile", null)
			# print("[BTHasOpponent] Opponent too far away")
			return FAILURE
	
	# NOTE: We DO NOT check path here anymore!
	# Bots should ALWAYS know about opponents, even if blocked by soft blocks.
	# This allows tactical assessment to decide whether to:
	# 1. Attack directly if path exists
	# 2. Farm TOWARD the opponent if blocked
	# The tactical system handles this, not the opponent detection.
	
	# Store path availability in blackboard for tactical decisions
	var has_path = false
	if grid_sampler:
		var path_to_opponent = grid_sampler.find_path(player_tile, opponent_tile, 40, player, false)
		has_path = not path_to_opponent.is_empty()
	blackboard.set_var("path_to_opponent", has_path)
	
	# Store opponent data in blackboard for subsequent nodes
	if store_in_blackboard:
		blackboard.set_var("nearest_opponent", nearest)
		blackboard.set_var("opponent_tile", nearest.get("tile"))
	
	# print("[BTHasOpponent] ✓ Opponent detected! ", nearest.get("name"), " at ", nearest.get("tile"))
	return SUCCESS
