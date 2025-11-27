@tool
extends BTAction
class_name BTExecuteTactic

## Executes the chosen tactic from tactical assessment
## Implements specific attack patterns for each strategy

@export var tactic_var: StringName = &"tactical_plan"  ## Blackboard var with chosen tactic
@export var target_var: StringName = &"tactic_target_cell"  ## Output: where to move/place bomb

func _generate_name() -> String:
	return "ExecuteTactic (%s)" % tactic_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var tactic = blackboard.get_var(tactic_var, "NONE")
	if tactic == "NONE":
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var target_tile: Vector2i = player_tile
	
	# Execute the chosen tactic
	match tactic:
		"ONE_TILE_TRAP":
			target_tile = _execute_one_tile_trap(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"CHOKE_POINT":
			target_tile = _execute_choke_point(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"SPACE_DENIAL":
			target_tile = _execute_space_denial(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"AGGRESSIVE_CHASE":
			target_tile = _execute_aggressive_chase(player_tile, opponent_tile, grid_sampler)
		
		"DEFENSIVE_RETREAT":
			# Handled by escape sequence
			return FAILURE
		
		"WAIT_FOR_DEATH":
			target_tile = _execute_wait_safe(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"PREDICTIVE_INTERCEPT":
			target_tile = _execute_predictive_intercept(player_tile, opponent_tile, nearest, grid_sampler)
	
	if target_tile == Vector2i.ZERO or target_tile == Vector2i(-1, -1):
		return FAILURE
	
	blackboard.set_var(target_var, target_tile)
	blackboard.set_var("tactic_executed", tactic)
	print("[ExecuteTactic] ✓ Executing ", tactic, " → ", target_tile)
	return SUCCESS

## The "Kiss" - trap opponent on one tile, then bomb that tile
func _execute_one_tile_trap(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find the opponent's only escape route
	var escape_tile = _find_only_escape(opponent_tile, grid_sampler, ai_manager)
	if escape_tile == Vector2i.ZERO:
		# No single escape found - try to block ANY escape route
		var routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
		if routes.size() > 0:
			escape_tile = routes[0]
		else:
			# Opponent has no escapes - they're trapped! Place bomb near them
			return _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
	
	# CRITICAL FIX: Position ourselves to bomb the escape route, not the opponent!
	var intercept_tile = _get_bomb_placement_for_target(escape_tile, player_tile, grid_sampler)
	print("[OneTileTrap] 💋 Blocking escape route: %s (bomb pos: %s)" % [escape_tile, intercept_tile])
	return intercept_tile

## Block one of two escape routes, forcing opponent into trap
func _execute_choke_point(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	var escape_routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
	if escape_routes.size() < 2:
		return opponent_tile
	
	# Choose the escape route closest to us to block
	var best_route = escape_routes[0]
	var best_dist = grid_sampler.get_manhattan_distance(player_tile, best_route)
	
	for route in escape_routes:
		var dist = grid_sampler.get_manhattan_distance(player_tile, route)
		if dist < best_dist:
			best_dist = dist
			best_route = route
	
	print("[ChokePoint] 🕷️ Blocking escape: ", best_route)
	return _get_bomb_placement_for_target(best_route, player_tile, grid_sampler)

## Cut off opponent's movement path
func _execute_space_denial(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find midpoint between us and opponent
	var direction = opponent_tile - player_tile
	var midpoint = player_tile + Vector2i(direction.x / 2, direction.y / 2)
	
	# Adjust to walkable tile
	if not grid_sampler.is_tile_walkable(midpoint):
		# Try adjacent tiles
		for offset in [Vector2i.ZERO, Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var check = midpoint + offset
			if grid_sampler.is_tile_walkable(check):
				midpoint = check
				break
	
	print("[SpaceDenial] 🚫 Cutting off path at: ", midpoint)
	return midpoint

## Chase aggressively with multiple bombs
func _execute_aggressive_chase(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler) -> Vector2i:
	# Move directly toward opponent
	var direction = opponent_tile - player_tile
	var next_tile = player_tile
	
	if abs(direction.x) > abs(direction.y):
		next_tile += Vector2i(sign(direction.x), 0)
	else:
		next_tile += Vector2i(0, sign(direction.y))
	
	if grid_sampler.is_tile_walkable(next_tile):
		return next_tile
	return player_tile

## Stay safe while opponent dies
func _execute_wait_safe(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find safe position away from opponent's danger zone
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for radius in range(1, 5):
		for offset_x in range(-radius, radius + 1):
			for offset_y in range(-radius, radius + 1):
				var check_tile = player_tile + Vector2i(offset_x, offset_y)
				var key = "%d,%d" % [check_tile.x, check_tile.y]
				
				# CRITICAL FIX: Use is_tile_safe_for_target which checks for bombs!
				if grid_sampler.is_tile_safe_for_target(check_tile) and not threat_matrix.has(key):
					var dist_to_opponent = grid_sampler.get_manhattan_distance(check_tile, opponent_tile)
					if dist_to_opponent >= 4:  # Stay away from danger
						return check_tile
	
	return player_tile

## Standard predictive chase - intercept where opponent is GOING, not where they ARE
func _execute_predictive_intercept(player_tile: Vector2i, opponent_tile: Vector2i, opponent_data: Dictionary, grid_sampler) -> Vector2i:
	# Use velocity to predict 2-3 tiles ahead
	var velocity: Vector2 = opponent_data.get("velocity", Vector2.ZERO)
	if velocity.length() < 10.0:
		# Opponent stationary - find best blocking position around them
		return _find_best_blocking_position(player_tile, opponent_tile, grid_sampler)
	
	var prediction_distance = 2
	var direction = velocity.normalized()
	var predicted = opponent_tile
	
	for i in range(prediction_distance):
		var next: Vector2i
		if abs(direction.x) > abs(direction.y):
			next = predicted + Vector2i(sign(direction.x), 0)
		else:
			next = predicted + Vector2i(0, sign(direction.y))
		
		if not grid_sampler.is_tile_walkable(next):
			break
		predicted = next
	
	# Instead of moving to predicted position, find a blocking position AHEAD of it
	var blocking_pos = _find_best_blocking_position(player_tile, predicted, grid_sampler)
	print("[PredictiveIntercept] Opponent heading to %s, blocking at %s" % [predicted, blocking_pos])
	return blocking_pos

## Find the best position to place a bomb that blocks opponent's movement
func _find_best_blocking_position(player_tile: Vector2i, target_tile: Vector2i, grid_sampler) -> Vector2i:
	# Check tiles adjacent to target that we can reach
	var best_pos = target_tile  # Fallback
	var best_score = -1000
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = target_tile + dir
		# CRITICAL: Use is_tile_safe_for_target to avoid bombs!
		if not grid_sampler.is_tile_safe_for_target(check_tile):
			continue
		
		# Score based on distance from us (closer = better) and blocking potential
		var dist_from_us = grid_sampler.get_manhattan_distance(player_tile, check_tile)
		var dist_from_target = 1  # Adjacent
		
		# Prefer positions that are closer to us
		var score = 10 - dist_from_us
		
		# Bonus for positions that create corridor (more adjacent walls)
		var walls_nearby = 0
		for wall_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var wall_check = check_tile + wall_dir
			if not grid_sampler.is_tile_walkable(wall_check):
				walls_nearby += 1
		score += walls_nearby  # More walls = better trap position
		
		if score > best_score:
			best_score = score
			best_pos = check_tile
	
	return best_pos

## Helper: Find opponent's only escape route
func _find_only_escape(tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	var routes = _find_escape_routes(tile, grid_sampler, ai_manager)
	return routes[0] if routes.size() == 1 else Vector2i.ZERO

## Helper: Find all escape routes
func _find_escape_routes(tile: Vector2i, grid_sampler, ai_manager) -> Array[Vector2i]:
	var routes: Array[Vector2i] = []
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check = tile + dir
		if grid_sampler.is_tile_walkable(check):
			var key = "%d,%d" % [check.x, check.y]
			if not threat_matrix.has(key):
				routes.append(check)
	
	return routes

## Helper: Find best position to bomb a target tile
func _get_bomb_placement_for_target(target: Vector2i, our_pos: Vector2i, grid_sampler) -> Vector2i:
	# Check if we can bomb from adjacent tile
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var placement = target + dir
		if grid_sampler.is_tile_walkable(placement):
			var dist = grid_sampler.get_manhattan_distance(our_pos, placement)
			if dist <= 3:  # Close enough to reach
				return placement
	
	# Fallback: move toward target
	return target
