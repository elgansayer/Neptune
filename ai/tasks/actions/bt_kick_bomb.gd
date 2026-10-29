@tool
extends BTAction
class_name BTKickBomb

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## Kicks a bomb toward an opponent or strategic direction
## Bot walks into a bomb to trigger the kick mechanic
## Requires: has_bomb_kicker = true

@export var kick_target_var: StringName = &"kick_target" ## Target tile to kick toward
@export var max_kick_distance: int = 6 ## Maximum tiles away to attempt kick

func _generate_name() -> String:
	return "KickBomb → %s" % kick_target_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player or not game_instance or not grid_sampler:
		return FAILURE
	
	# Must have bomb kicker ability
	if not player.has_bomb_kicker:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Get kick target (opponent position or strategic tile)
	var kick_target = blackboard.get_var(kick_target_var, null)
	if kick_target == null:
		# Try to get nearest opponent as default target
		var opponent_tracker = blackboard.get_var("opponent_tracker")
		if opponent_tracker:
			var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
			if nearest and not nearest.is_empty():
				kick_target = nearest.get("tile", null)
	
	if kick_target == null:
		return FAILURE
	
	# Find kickable bombs in cardinal directions
	var best_bomb = null
	var best_direction = Vector2.ZERO
	var best_score = -1.0
	
	var directions = [
		Vector2i(1, 0),   # Right
		Vector2i(-1, 0),  # Left
		Vector2i(0, 1),   # Down
		Vector2i(0, -1)   # Up
	]
	
	for dir in directions:
		# Check if there's a bomb adjacent to us in this direction
		var bomb_tile = player_tile + dir
		var bomb = _get_bomb_at_tile(bomb_tile, game_instance)
		
		# Check bomb_state instead of is_kicked (BombState.KICKED = 3, PLANTED = 0)
		if bomb == null or bomb.bomb_state != 0:
			continue
		
		# Calculate if kicking this bomb would move it toward the target
		var kick_dir = Vector2(dir)
		var score = _score_kick(bomb_tile, kick_dir, kick_target, grid_sampler, game_instance)
		
		if score > best_score:
			best_score = score
			best_bomb = bomb
			best_direction = kick_dir
	
	if best_bomb == null or best_score < 0.1:
		return FAILURE
	
	# To kick: we need to WALK INTO the bomb
	# Set input direction toward the bomb
	player.set_input(best_direction.x, best_direction.y, false, false)
	
	print("[BTKickBomb] ⚽ Kicking bomb at %s toward target %s (score=%.2f)" % [
		best_bomb.get_tile_position(), kick_target, best_score
	])
	
	# Store that we're attempting a kick for follow-up
	blackboard.set_var("last_kick_attempt", SimulationTime.milliseconds(blackboard))
	blackboard.set_var("kick_direction", best_direction)
	
	return SUCCESS

func _get_bomb_at_tile(tile: Vector2i, game_instance) -> Node:
	"""Find a bomb at the given tile position"""
	if not "bombs" in game_instance:
		return null
	
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and not bomb.has_exploded:
			if bomb.get_tile_position() == tile:
				return bomb
	return null

func _score_kick(bomb_tile: Vector2i, kick_dir: Vector2, target: Vector2i, grid_sampler, game_instance) -> float:
	"""Score how good this kick would be
	Returns 0-1 score based on:
	- Does the kick path lead toward the target?
	- Is the path clear for the bomb to travel?
	- Would the bomb's explosion hit the target?
	"""
	var score = 0.0
	
	# Check if kick direction aligns with target
	var to_target = Vector2(target - bomb_tile)
	if to_target.length() < 0.1:
		return 0.0  # Already at target, no point kicking
	
	var alignment = kick_dir.normalized().dot(to_target.normalized())
	if alignment < 0.5:
		return 0.0  # Kicking away from target
	
	score += alignment * 0.5  # Up to 0.5 for alignment
	
	# Check how far the bomb would travel in this direction
	var travel_distance = 0
	var current_tile = bomb_tile
	var bomb_range = 2  # Default bomb range
	
	for i in range(1, max_kick_distance + 1):
		var check_tile = bomb_tile + Vector2i(kick_dir * float(i))
		var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
		
		if tile_type != 0:  # Not empty floor
			break
		
		# Check for obstacles (other bombs, players would stop it)
		if _get_bomb_at_tile(check_tile, game_instance) != null:
			break
		
		travel_distance = i
		current_tile = check_tile
	
	if travel_distance == 0:
		return 0.0  # Bomb can't move
	
	# Check if final position would put target in blast range
	var final_dist_to_target = abs(current_tile.x - target.x) + abs(current_tile.y - target.y)
	if final_dist_to_target <= bomb_range:
		score += 0.5  # Target would be in blast!
	elif final_dist_to_target <= bomb_range + 2:
		score += 0.25  # Close to target
	
	return score
