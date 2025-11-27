@tool
extends BTAction
class_name BTDefensiveKick

## Kicks a threatening bomb AWAY from the player to safety
## Used when in danger - kick the bomb instead of running!
## Requires: has_bomb_kicker = true

@export var threat_check_radius: int = 3 ## How close a bomb must be to be considered a threat
@export var min_kick_distance: int = 2 ## Minimum tiles the bomb must travel to be worth kicking

func _generate_name() -> String:
	return "DefensiveKick (threat radius=%d)" % threat_check_radius

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not game_instance or not grid_sampler:
		return FAILURE
	
	# Must have bomb kicker ability
	if not player.has_bomb_kicker:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Check if we're actually in danger
	var in_danger = blackboard.get_var("in_danger", false)
	if not in_danger and ai_manager:
		var threat_matrix = ai_manager.get_current_threat_matrix()
		var key = "%d,%d" % [player_tile.x, player_tile.y]
		in_danger = threat_matrix.has(key)
	
	if not in_danger:
		return FAILURE  # No need for defensive kick
	
	# Find adjacent bombs we can kick away
	var directions = [
		Vector2i(1, 0),   # Right
		Vector2i(-1, 0),  # Left
		Vector2i(0, 1),   # Down
		Vector2i(0, -1)   # Up
	]
	
	var best_kick: Dictionary = {}
	var best_score = -1.0
	
	for dir in directions:
		var bomb_tile = player_tile + dir
		var bomb = _get_bomb_at_tile(bomb_tile, game_instance)
		
		# Only kick planted bombs (bomb_state == 0)
		if bomb == null or bomb.bomb_state != 0:
			continue
		
		# Check if this bomb is threatening us
		var bomb_range = bomb.explosion_range if bomb.has_method("get") else 2
		var dist_to_bomb = 1  # Adjacent
		
		if dist_to_bomb > bomb_range:
			continue  # This bomb isn't threatening us
		
		# Try to kick it AWAY from us (opposite direction from where we are relative to bomb)
		# We want to kick it in the direction WE are facing (into the bomb)
		var kick_dir = Vector2(dir)  # Kick in direction from us to bomb
		
		# Score this defensive kick
		var score = _score_defensive_kick(bomb_tile, kick_dir, player_tile, grid_sampler, game_instance, bomb)
		
		if score > best_score:
			best_score = score
			best_kick = {
				"bomb": bomb,
				"bomb_tile": bomb_tile,
				"kick_dir": kick_dir,
				"score": score
			}
	
	if best_kick.is_empty() or best_score < 0.3:
		return FAILURE  # No good defensive kick available
	
	# Execute the kick by walking INTO the bomb
	var kick_dir = best_kick.kick_dir
	player.set_input(kick_dir.x, kick_dir.y)
	
	print("[BTDefensiveKick] 🛡️ DEFENSIVE KICK! Kicking bomb at %s away (score=%.2f)" % [
		best_kick.bomb_tile, best_score
	])
	
	# Mark that we're doing a defensive kick
	blackboard.set_var("defensive_kick_active", true)
	blackboard.set_var("defensive_kick_time", Time.get_ticks_msec())
	
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

func _score_defensive_kick(bomb_tile: Vector2i, kick_dir: Vector2, player_tile: Vector2i, grid_sampler, game_instance, bomb) -> float:
	"""Score how effective this defensive kick would be
	Higher score = better defensive value
	"""
	var score = 0.0
	var bomb_range = bomb.explosion_range if bomb.has_method("get") else 2
	
	# Check how far the bomb would travel
	var travel_distance = 0
	var final_tile = bomb_tile
	
	for i in range(1, 10):  # Check up to 10 tiles
		var check_tile = bomb_tile + Vector2i(kick_dir * float(i))
		var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
		
		if tile_type != 0:  # Not empty floor - bomb stops here
			break
		
		# Check for other bombs that would stop it
		if _get_bomb_at_tile(check_tile, game_instance) != null:
			break
		
		travel_distance = i
		final_tile = check_tile
	
	if travel_distance < min_kick_distance:
		return 0.0  # Bomb won't travel far enough to help
	
	# Calculate if we'd be safe after the kick
	var final_dist_from_player = abs(final_tile.x - player_tile.x) + abs(final_tile.y - player_tile.y)
	
	if final_dist_from_player > bomb_range:
		# We'd be completely safe! Excellent!
		score += 1.0
	elif final_dist_from_player > bomb_range - 1:
		# We'd be marginally safe
		score += 0.5
	else:
		# Still in danger even after kick - not great
		score += 0.2
	
	# Bonus for kicking far
	score += min(travel_distance / 6.0, 0.3)  # Up to 0.3 bonus for distance
	
	# Bonus for kicking toward open space (more travel = less likely to hit wall immediately)
	if travel_distance >= 3:
		score += 0.2
	
	# Check if kick would endanger opponents (bonus!)
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	if opponent_tracker:
		var nearest = opponent_tracker.get_nearest_opponent(Vector2(player_tile * 16), -1)  # -1 = any opponent
		if nearest and not nearest.is_empty():
			var opp_tile: Vector2i = nearest.get("tile", Vector2i(-99, -99))
			var opp_dist_from_final = abs(final_tile.x - opp_tile.x) + abs(final_tile.y - opp_tile.y)
			if opp_dist_from_final <= bomb_range:
				# Kick would endanger opponent! Great defensive+offensive value!
				score += 0.5
				print("[BTDefensiveKick] 💥 Kick would also threaten opponent at %s!" % opp_tile)
	
	return score
