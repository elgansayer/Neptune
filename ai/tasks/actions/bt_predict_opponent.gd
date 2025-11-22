@tool
extends BTAction
class_name BTPredictOpponent

## Predicts opponent movement and positions bot to intercept or corner them
## Uses velocity analysis and behavioral patterns to anticipate player actions
## Outputs an intercept position for the bot to move toward

@export var target_tile_var: StringName = &"intercept_cell"  ## Blackboard variable to store intercept position
@export var prediction_distance: int = 5  ## How far ahead to predict (tiles)
@export var intercept_strategy: String = "BLOCK_PATH"  ## Strategy: BLOCK_PATH, CORNER, CHASE
@export var min_opponent_speed: float = 10.0  ## Minimum opponent speed to attempt prediction

func _generate_name() -> String:
	return "PredictOpponent → %s (%s)" % [target_tile_var, intercept_strategy]

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Get nearest opponent with velocity data (excluding self)
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	if nearest == null or nearest.is_empty():
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var opponent_velocity: Vector2 = nearest.get("velocity", Vector2.ZERO)
	var opponent_behavior: String = nearest.get("behavior_pattern", "NEUTRAL")
	
	# Check if opponent is moving fast enough to predict
	if opponent_velocity.length() < min_opponent_speed:
		# Opponent is stationary or moving too slowly - use current position
		blackboard.set_var(target_tile_var, opponent_tile)
		return SUCCESS
	
	# Predict opponent's future position
	var predicted_pos = _predict_opponent_position(
		opponent_tile,
		opponent_velocity,
		prediction_distance,
		opponent_behavior,
		grid_sampler,
		ai_manager
	)
	
	# Calculate intercept position based on strategy
	var intercept_pos: Vector2i
	
	match intercept_strategy:
		"BLOCK_PATH":
			# Position ourselves between opponent and their destination
			intercept_pos = _calculate_block_position(
				player_tile,
				opponent_tile,
				predicted_pos,
				grid_sampler
			)
		
		"CORNER":
			# Try to corner opponent against wall or danger zone
			intercept_pos = _calculate_corner_position(
				player_tile,
				opponent_tile,
				predicted_pos,
				grid_sampler,
				ai_manager
			)
		
		"CHASE":
			# Direct chase toward predicted position
			intercept_pos = predicted_pos
		
		_:
			# Default to chase
			intercept_pos = predicted_pos
	
	# Validate intercept position
	if not grid_sampler.is_tile_walkable(intercept_pos):
		# Fallback to opponent's current position
		intercept_pos = opponent_tile
	
	# Store in blackboard
	blackboard.set_var(target_tile_var, intercept_pos)
	blackboard.set_var("predicted_opponent_pos", predicted_pos)
	blackboard.set_var("intercept_strategy_used", intercept_strategy)
	
	print("[BTPredictOpponent] Intercept calculated: ", intercept_pos, " (strategy=", intercept_strategy, ")")
	return SUCCESS

## Predict where opponent will be after N tiles of movement
func _predict_opponent_position(
	current_tile: Vector2i,
	velocity: Vector2,
	distance: int,
	behavior: String,
	grid_sampler,
	ai_manager
) -> Vector2i:
	# Normalize velocity to get direction
	var direction = velocity.normalized()
	var predicted = current_tile
	
	# Account for behavioral tendencies
	var actual_distance = distance
	if behavior == "AGGRESSIVE":
		actual_distance = int(distance * 1.2)  # Aggressive players move more
	elif behavior == "DEFENSIVE":
		actual_distance = int(distance * 0.7)  # Defensive players are more cautious
	
	# Simulate movement forward
	for i in range(actual_distance):
		var next_tile: Vector2i
		
		# Convert velocity to tile direction
		if abs(direction.x) > abs(direction.y):
			next_tile = predicted + Vector2i(sign(direction.x), 0)
		else:
			next_tile = predicted + Vector2i(0, sign(direction.y))
		
		# Check if walkable and safe
		if not grid_sampler.is_tile_walkable(next_tile):
			break
		
		# Avoid predicting into known danger zones
		var key = "%d,%d" % [next_tile.x, next_tile.y]
		if ai_manager.get_current_threat_matrix().has(key):
			break
		
		predicted = next_tile
	
	return predicted

## Calculate position to block opponent's path
func _calculate_block_position(
	player_tile: Vector2i,
	opponent_tile: Vector2i,
	predicted_tile: Vector2i,
	grid_sampler
) -> Vector2i:
	# Find midpoint between opponent's current and predicted position
	var path_vector = predicted_tile - opponent_tile
	var midpoint = opponent_tile + Vector2i(path_vector.x / 2, path_vector.y / 2)
	
	# Check if we can reach midpoint
	if grid_sampler.is_tile_walkable(midpoint):
		var distance = grid_sampler.get_manhattan_distance(player_tile, midpoint)
		var opponent_distance = grid_sampler.get_manhattan_distance(opponent_tile, midpoint)
		
		# Only block if we can get there first or at same time
		if distance <= opponent_distance + 1:
			return midpoint
	
	# Fallback: try to get ahead of opponent
	if grid_sampler.is_tile_walkable(predicted_tile):
		return predicted_tile
	
	# Last resort: move toward opponent
	return opponent_tile

## Calculate position to corner opponent against obstacles
func _calculate_corner_position(
	player_tile: Vector2i,
	opponent_tile: Vector2i,
	predicted_tile: Vector2i,
	grid_sampler,
	ai_manager
) -> Vector2i:
	# Look for nearby walls or danger zones that could trap opponent
	var best_corner_pos = predicted_tile
	var best_corner_score = 0.0
	
	# Check tiles around predicted position
	for offset_x in range(-2, 3):
		for offset_y in range(-2, 3):
			if offset_x == 0 and offset_y == 0:
				continue
			
			var check_tile = predicted_tile + Vector2i(offset_x, offset_y)
			
			if not grid_sampler.is_tile_walkable(check_tile):
				continue
			
			# Score based on how cornered opponent would be
			var corner_score = _evaluate_corner_quality(
				check_tile,
				predicted_tile,
				grid_sampler,
				ai_manager
			)
			
			# Prefer positions closer to us
			var distance_to_us = grid_sampler.get_manhattan_distance(player_tile, check_tile)
			corner_score -= distance_to_us * 0.1
			
			if corner_score > best_corner_score:
				best_corner_score = corner_score
				best_corner_pos = check_tile
	
	return best_corner_pos

## Evaluate how well a position corners the opponent
func _evaluate_corner_quality(
	our_pos: Vector2i,
	opponent_pos: Vector2i,
	grid_sampler,
	ai_manager
) -> float:
	var score: float = 0.0
	
	# Count walls around opponent
	var walls_near_opponent = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		if not grid_sampler.is_tile_walkable(opponent_pos + dir):
			walls_near_opponent += 1
	
	# More walls = better corner
	score += walls_near_opponent * 2.0
	
	# Check if we'd be blocking their best escape route
	var direction_to_us = our_pos - opponent_pos
	var escape_directions = [
		Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT
	]
	
	for escape_dir in escape_directions:
		var escape_tile = opponent_pos + escape_dir
		if not grid_sampler.is_tile_walkable(escape_tile):
			continue
		
		# If this escape route leads toward us, we're blocking it
		var dot_product = escape_dir.x * direction_to_us.x + escape_dir.y * direction_to_us.y
		if dot_product > 0:
			score += 1.5
	
	return score
