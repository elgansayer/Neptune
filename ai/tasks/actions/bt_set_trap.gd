@tool
extends BTAction
class_name BTSetTrap

## Strategic trap-setting behavior for killing opponents
## Identifies choke points, predicts opponent escape routes, and places bombs to corner them
## Best used by Aggressive, Strategic, and Trapper personalities

@export var target_tile_var: StringName = &"trap_target_cell"  ## Blackboard variable to store trap position
@export var min_choke_score: float = 0.6  ## Minimum choke point quality (0.0-1.0)
@export var prediction_lookahead: int = 3  ## How many tiles ahead to predict opponent movement
@export var require_opponent_nearby: bool = true  ## Only set traps if opponent is close

func _generate_name() -> String:
	return "SetTrap → %s (choke≥%.1f)" % [target_tile_var, min_choke_score]

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Find nearest opponent (excluding self)
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	if nearest == null or nearest.is_empty():
		# No opponent to trap - don't waste time looking for trap positions
		print("[BTSetTrap] No opponent found - skipping trap logic")
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var opponent_velocity = nearest.get("velocity", Vector2.ZERO)
	
	# Check if opponent is within reasonable range
	if require_opponent_nearby:
		var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
		if distance > 8:
			# Too far away to trap effectively
			return FAILURE
	
	# Predict where opponent is heading
	var predicted_tiles = _predict_opponent_path(opponent_tile, opponent_velocity, prediction_lookahead, grid_sampler, ai_manager)
	
	# Find best trap position (choke point that blocks opponent's escape)
	var best_trap_pos: Vector2i = Vector2i.ZERO
	var best_trap_score: float = 0.0
	
	# Check tiles near opponent's predicted path
	for predicted_tile in predicted_tiles:
		# Consider tiles around the predicted position
		for offset in [Vector2i.ZERO, Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var trap_candidate = predicted_tile + offset
			
			# Skip if not walkable
			if not grid_sampler.is_tile_walkable(trap_candidate):
				continue
			
			# Skip if too far from player
			var distance_to_trap = grid_sampler.get_manhattan_distance(player_tile, trap_candidate)
			if distance_to_trap > 4:
				continue
			
			# Calculate trap effectiveness score
			var score = _evaluate_trap_position(
				trap_candidate,
				opponent_tile,
				player.bomb_range if player else 2,
				grid_sampler,
				ai_manager
			)
			
			if score > best_trap_score and score >= min_choke_score:
				best_trap_score = score
				best_trap_pos = trap_candidate
	
	# Did we find a good trap spot?
	if best_trap_score >= min_choke_score:
		blackboard.set_var(target_tile_var, best_trap_pos)
		blackboard.set_var("trap_score", best_trap_score)
		blackboard.set_var("trap_target_opponent", nearest)
		
		print("[BTSetTrap] ✓ Trap position found at ", best_trap_pos, " (score=%.2f)" % best_trap_score)
		return SUCCESS
	
	# No good trap opportunity
	return FAILURE

## Predict opponent's next few tiles based on velocity and walkability
func _predict_opponent_path(
	start_tile: Vector2i,
	velocity: Vector2,
	lookahead: int,
	grid_sampler,
	ai_manager
) -> Array[Vector2i]:
	var predicted: Array[Vector2i] = [start_tile]
	
	if velocity.length() < 0.1:
		# Opponent is stationary
		return predicted
	
	# Normalize velocity to get direction
	var direction = velocity.normalized()
	var current = start_tile
	
	for i in range(lookahead):
		# Convert velocity to tile direction
		var next: Vector2i
		if abs(direction.x) > abs(direction.y):
			next = current + Vector2i(sign(direction.x), 0)
		else:
			next = current + Vector2i(0, sign(direction.y))
		
		# Check if walkable
		if not grid_sampler.is_tile_walkable(next):
			break
		
		predicted.append(next)
		current = next
	
	return predicted

## Evaluate how effective a trap position would be
## Returns score 0.0-1.0 based on:
## - Choke point quality (limited exits)
## - Blast coverage of opponent escape routes
## - Blocks optimal path
func _evaluate_trap_position(
	trap_pos: Vector2i,
	opponent_pos: Vector2i,
	bomb_range: int,
	grid_sampler,
	ai_manager
) -> float:
	var score: float = 0.0
	
	# 1. Check how many escape routes opponent would have AFTER this bomb
	var blast_tiles = _get_blast_tiles(trap_pos, bomb_range, grid_sampler)
	var opponent_exits = _count_safe_exits(opponent_pos, blast_tiles, grid_sampler, ai_manager)
	
	# Fewer exits = better trap (inverse relationship)
	if opponent_exits == 0:
		score += 1.0  # Perfect trap! No escape
	elif opponent_exits == 1:
		score += 0.8  # Excellent - only one exit
	elif opponent_exits == 2:
		score += 0.6  # Good - limited options
	elif opponent_exits == 3:
		score += 0.4  # Mediocre
	else:
		score += 0.2  # Weak trap - many exits
	
	# 2. Bonus if trap blocks optimal path between opponent and their likely destination
	# (future enhancement: analyze power-up locations, safe zones)
	
	# 3. Check if trap position is a natural choke point (corridor, corner)
	var walkable_neighbors = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		if grid_sampler.is_tile_walkable(trap_pos + dir):
			walkable_neighbors += 1
	
	# Fewer walkable neighbors = tighter choke point
	if walkable_neighbors <= 2:
		score += 0.3  # Corner or corridor
	elif walkable_neighbors == 3:
		score += 0.1  # T-junction
	
	# 4. Penalty if trap would also endanger us
	var trap_distance = grid_sampler.get_manhattan_distance(trap_pos, opponent_pos)
	if trap_distance <= bomb_range:
		score += 0.2  # Trap will hit opponent directly
	
	# Normalize score
	return clamp(score / 1.5, 0.0, 1.0)

## Get all tiles that would be affected by bomb blast
func _get_blast_tiles(center: Vector2i, range_val: int, grid_sampler) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = [center]
	
	# Check 4 cardinal directions
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for distance in range(1, range_val + 1):
			var check_tile = center + (dir * distance)
			
			# Stop at walls
			if not grid_sampler.is_tile_walkable(check_tile):
				break
			
			tiles.append(check_tile)
	
	return tiles

## Count how many safe exits opponent has from their position
func _count_safe_exits(
	opponent_pos: Vector2i,
	blast_tiles: Array[Vector2i],
	grid_sampler,
	ai_manager
) -> int:
	var safe_exits: int = 0
	
	# Check all 4 cardinal directions
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var exit_tile = opponent_pos + dir
		
		# Must be walkable
		if not grid_sampler.is_tile_walkable(exit_tile):
			continue
		
		# Must not be in blast zone
		if exit_tile in blast_tiles:
			continue
		
		# Must not lead into existing danger
		var key = "%d,%d" % [exit_tile.x, exit_tile.y]
		if ai_manager.get_current_threat_matrix().has(key):
			continue
		
		safe_exits += 1
	
	return safe_exits
