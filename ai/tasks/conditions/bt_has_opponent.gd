@tool
extends BTCondition
class_name BTHasOpponent

## Checks if an opponent is detected within range
## Uses OpponentTracker to find nearest enemy

@export var max_distance: float = -1.0  ## Maximum detection range (-1 = unlimited)
@export var store_in_blackboard: bool = true  ## Whether to store opponent data for later use

func _generate_name() -> String:
	if max_distance > 0:
		return "HasOpponent (range: %.0f)" % max_distance
	return "HasOpponent"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	
	if not player or not opponent_tracker:
		return FAILURE
	
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		blackboard.set_var("nearest_opponent", null)
		blackboard.set_var("opponent_tile", null)
		return FAILURE
	
	# Check distance if max_distance is set
	if max_distance > 0:
		var opponent_tile = nearest.get("tile", null)
		if opponent_tile == null:
			return FAILURE
		
		var player_tile = player.get_tile_position()
		var grid_sampler = blackboard.get_var("grid_sampler")
		
		if grid_sampler:
			var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
			if distance > max_distance:
				blackboard.set_var("nearest_opponent", null)
				blackboard.set_var("opponent_tile", null)
				return FAILURE
	
	# Store opponent data in blackboard for subsequent nodes
	if store_in_blackboard:
		blackboard.set_var("nearest_opponent", nearest)
		blackboard.set_var("opponent_tile", nearest.get("tile"))
	
	return SUCCESS
