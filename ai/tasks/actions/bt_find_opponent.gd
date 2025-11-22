@tool
extends BTAction
class_name BTFindOpponent

## Finds nearest opponent and calculates path toward them
## Stores target tile for subsequent movement nodes

@export var target_tile_var: StringName = &"target_cell"  ## Blackboard variable to store target tile
@export var path_aggressive: bool = true  ## Move directly toward opponent vs flanking
@export var preferred_distance: int = 2  ## Ideal bomb placement distance from opponent

func _generate_name() -> String:
	return "FindOpponent → %s" % target_tile_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player or not opponent_tracker or not grid_sampler:
		return FAILURE
	
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	if nearest == null or nearest.is_empty():
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	if opponent_tile == null:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Calculate target position based on strategy
	var target: Vector2i
	
	if path_aggressive:
		# Move toward opponent to preferred bomb distance
		var direction = (opponent_tile - player_tile)
		var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
		
		if distance <= preferred_distance:
			# Already in good position, hold ground
			target = player_tile
		else:
			# Move closer (one step toward opponent)
			if abs(direction.x) > abs(direction.y):
				target = player_tile + Vector2i(sign(direction.x), 0)
			else:
				target = player_tile + Vector2i(0, sign(direction.y))
			
			# Validate target is walkable
			var ai_manager = blackboard.get_var("ai_manager")
			if ai_manager and not ai_manager.is_walkable(target):
				# Try alternate direction
				if abs(direction.x) > abs(direction.y):
					target = player_tile + Vector2i(0, sign(direction.y))
				else:
					target = player_tile + Vector2i(sign(direction.x), 0)
	else:
		# Flanking approach (not implemented yet, fallback to aggressive)
		target = opponent_tile
	
	# Store target in blackboard
	blackboard.set_var(target_tile_var, target)
	blackboard.set_var("chase_target", opponent_tile)  # Store actual opponent position
	
	return SUCCESS
