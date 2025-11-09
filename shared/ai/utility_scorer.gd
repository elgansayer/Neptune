extends Node
class_name UtilityScorer

## Utility-Based Action Scoring System
## Evaluates potential actions and returns scores based on tactical value
## Works with personality weights to create varied behavior

const Constants = preload("res://shared/constants.gd")

# References
var game_instance: Node2D
var observer
var danger_mapper  # DangerMapper instance
var personality_weights: Dictionary

# Action types
enum ActionType {
	MOVE_TO_POWERUP,
	ATTACK_PLAYER,
	DESTROY_BLOCKS,
	ESCAPE_DANGER,
	PLACE_BOMB,
	REPOSITION_STRATEGIC,
	WAIT_AMBUSH,
	CHAIN_BOMB_SETUP
}

func _init(game_ref: Node2D, obs_ref, danger_ref, personality: Dictionary):
	game_instance = game_ref
	observer = obs_ref
	danger_mapper = danger_ref
	personality_weights = personality

## Main scoring function - evaluates all possible actions
func score_all_actions(ai_player: Node2D, current_time: float) -> Array:
	var current_tile = ai_player.get_tile_position()
	var scores: Array = []
	
	# Score: Escape danger (highest priority)
	var escape_score = score_escape_danger(current_tile, current_time)
	if escape_score.score > 0:
		scores.append(escape_score)
	
	# Score: Attack nearby players
	var attack_score = score_attack_opportunity(ai_player, current_tile, current_time)
	if attack_score.score > 0:
		scores.append(attack_score)
	
	# Score: Collect power-ups
	var powerup_score = score_powerup_collection(current_tile, ai_player, current_time)
	if powerup_score.score > 0:
		scores.append(powerup_score)
	
	# Score: Destroy blocks
	var block_score = score_block_destruction(current_tile, ai_player, current_time)
	if block_score.score > 0:
		scores.append(block_score)
	
	# Score: Chain bomb setup
	var chain_score = score_chain_bomb_setup(current_tile, ai_player, current_time)
	if chain_score.score > 0:
		scores.append(chain_score)
	
	# Score: Strategic repositioning
	var reposition_score = score_strategic_reposition(current_tile, current_time)
	if reposition_score.score > 0:
		scores.append(reposition_score)
	
	# Score: Ambush setup (for trapper personalities)
	if personality_weights.get("trap_bonus", 0) > 0:
		var ambush_score = score_ambush_setup(current_tile, current_time)
		if ambush_score.score > 0:
			scores.append(ambush_score)
	
	# Sort by score (highest first)
	scores.sort_custom(func(a, b): return a.score > b.score)
	
	return scores

## Score escaping from immediate danger
func score_escape_danger(current_tile: Vector2i, current_time: float) -> Dictionary:
	var danger_level = danger_mapper.get_danger_at_tile(current_tile, current_time, 1.0)
	
	# Not in danger
	if danger_level < 0.3:
		return {"score": 0.0, "action": ActionType.ESCAPE_DANGER}
	
	# Critical danger - maximum priority
	var time_until = danger_mapper.get_time_until_explosion(current_tile, current_time)
	
	var base_score = 1000.0  # Highest priority
	
	# Increase score as time decreases (more urgent)
	if time_until < 0.5:
		base_score = 2000.0  # EMERGENCY!
	elif time_until < 1.0:
		base_score = 1500.0  # Very urgent
	
	# Find escape routes
	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	
	# If no escapes, score is still high (try anyway)
	if escape_info.safe_count == 0:
		return {
			"score": base_score * 0.8,  # Slightly lower (may be trapped)
			"action": ActionType.ESCAPE_DANGER,
			"target_tile": null,  # Will try random direction
			"urgency": "CRITICAL"
		}
	
	# Get best escape route
	var best_route = escape_info.best_route
	
	return {
		"score": base_score,
		"action": ActionType.ESCAPE_DANGER,
		"target_tile": best_route.tile,
		"direction": best_route.direction,
		"urgency": "HIGH" if time_until < 1.0 else "MEDIUM"
	}

## Score attacking nearby players
func score_attack_opportunity(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	var base_score = personality_weights.get("aggression", 500.0) / 100.0  # Convert to 0-10 range
	
	# Find nearest opponent
	var nearest_opponent = null
	var nearest_distance = INF
	
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		if player == ai_player or (player.has_method("is_dead") and player.is_dead):
			continue
		
		var opponent_tile = player.get_tile_position()
		var distance = abs(opponent_tile.x - current_tile.x) + abs(opponent_tile.y - current_tile.y)
		
		if distance < nearest_distance:
			nearest_distance = distance
			nearest_opponent = player
	
	# No opponents nearby
	if nearest_opponent == null or nearest_distance > 8:
		return {"score": 0.0, "action": ActionType.ATTACK_PLAYER}
	
	var opponent_tile = nearest_opponent.get_tile_position()
	
	# Score decreases with distance
	var distance_factor = 1.0 - (nearest_distance / 8.0)
	var score = base_score * 15.0 * distance_factor  # Scale to ~15 points at close range
	
	# Check if we can place a bomb to trap opponent
	if ai_player.can_place_bomb():
		var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
		
		# Bonus if opponent is in blast radius
		if opponent_tile in simulation.affected_tiles:
			score += 10.0
		
		# Big bonus if we can trap them
		if simulation.traps_players > 0:
			score += personality_weights.get("trap_bonus", 500.0) / 50.0  # +10 typical
	
	return {
		"score": score,
		"action": ActionType.ATTACK_PLAYER,
		"target_tile": opponent_tile,
		"target_player": nearest_opponent,
		"distance": nearest_distance
	}

## Score collecting power-ups
func score_powerup_collection(current_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	var powerup_weights = personality_weights.get("powerup_utility_weights", {
		"max_bombs": 600.0,
		"explosion_range": 600.0,
		"speed": 600.0,
		"bomb_kicker": 400.0,
		"power_glove": 400.0
	})
	
	var best_powerup = observer.find_valuable_powerup(current_tile, powerup_weights)
	
	if best_powerup.tile == Vector2i(-1, -1):
		return {"score": 0.0, "action": ActionType.MOVE_TO_POWERUP}
	
	# Base score from powerup value
	var base_score = best_powerup.value / 75.0  # Convert to ~8 points for typical powerup
	
	# Reduce score if path is dangerous
	var path_danger = danger_mapper.get_danger_at_tile(best_powerup.tile, current_time, 1.0)
	if path_danger > 0.5:
		base_score *= 0.3  # Risky to collect
	
	# Greedy personality prioritizes powerups more
	if personality_weights.has("powerup_priority_bonus"):
		base_score *= 1.5
	
	return {
		"score": base_score,
		"action": ActionType.MOVE_TO_POWERUP,
		"target_tile": best_powerup.tile,
		"powerup_type": best_powerup.type,
		"distance": best_powerup.distance
	}

## Score destroying blocks
func score_block_destruction(current_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	if not ai_player.can_place_bomb():
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}
	
	# Check if placing bomb here would destroy blocks
	var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
	
	if simulation.blocks_destroyed == 0:
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}
	
	# Score based on number of blocks
	var base_score = simulation.blocks_destroyed * 10.0  # 10 points per block
	
	# Check if we have escape route after placing bomb
	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	if escape_info.safe_count == 0:
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}  # Would trap ourselves
	
	# Bonus for chain reactions
	if simulation.creates_chain:
		base_score += 20.0
	
	return {
		"score": base_score,
		"action": ActionType.DESTROY_BLOCKS,
		"target_tile": current_tile,
		"blocks_destroyed": simulation.blocks_destroyed,
		"creates_chain": simulation.creates_chain,
		"place_bomb": true
	}

## Score setting up chain bomb reactions
func score_chain_bomb_setup(current_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	if not ai_player.can_place_bomb():
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}
	
	# Only strategic personalities actively pursue chains
	var chain_bonus = personality_weights.get("chain_setup_bonus", 0.0)
	if chain_bonus < 100.0:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}
	
	# Check if there are existing bombs nearby to chain with
	var nearby_bombs = []
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		var bomb_tile = bomb.get_tile_position()
		var distance = abs(bomb_tile.x - current_tile.x) + abs(bomb_tile.y - current_tile.y)
		
		if distance > 0 and distance <= ai_player.bomb_range + bomb.explosion_range:
			nearby_bombs.append(bomb)
	
	if nearby_bombs.is_empty():
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}
	
	# Simulate chain reaction value
	var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
	
	if not simulation.creates_chain:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}
	
	# Check escape routes
	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	if escape_info.safe_count < 2:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}  # Too risky
	
	# High score for successful chain setup
	var score = 25.0 + (simulation.blocks_destroyed * 5.0)
	
	return {
		"score": score,
		"action": ActionType.CHAIN_BOMB_SETUP,
		"target_tile": current_tile,
		"chain_length": nearby_bombs.size() + 1,
		"place_bomb": true
	}

## Score strategic repositioning
func score_strategic_reposition(current_tile: Vector2i, current_time: float) -> Dictionary:
	# Low priority fallback action
	var base_score = 3.0
	
	# Find map center
	var map_center = Vector2i(
		game_instance.game_map[0].size() / 2,
		game_instance.game_map.size() / 2
	)
	
	# Move toward center if far away
	var distance_to_center = abs(map_center.x - current_tile.x) + abs(map_center.y - current_tile.y)
	
	if distance_to_center > 5:
		base_score += 2.0
	
	# Find a nearby tile that's safe and walkable
	var best_tile = null
	var best_value = 0.0
	
	for dy in range(-3, 4):
		for dx in range(-3, 4):
			if dx == 0 and dy == 0:
				continue
			
			var tile = current_tile + Vector2i(dx, dy)
			
			if not observer._is_tile_valid(tile):
				continue
			
			if not observer._is_tile_walkable(tile):
				continue
			
			# Prefer tiles closer to center
			var tile_distance_to_center = abs(map_center.x - tile.x) + abs(map_center.y - tile.y)
			var value = 10.0 - tile_distance_to_center
			
			if value > best_value:
				best_value = value
				best_tile = tile
	
	if best_tile == null:
		return {"score": 0.0, "action": ActionType.REPOSITION_STRATEGIC}
	
	return {
		"score": base_score,
		"action": ActionType.REPOSITION_STRATEGIC,
		"target_tile": best_tile
	}

## Score ambush setup (trapper personality)
func score_ambush_setup(current_tile: Vector2i, current_time: float) -> Dictionary:
	var trap_bonus = personality_weights.get("trap_bonus", 0.0)
	
	if trap_bonus < 100.0:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}
	
	# Find chokepoints (tiles with few adjacent walkable tiles)
	var adjacent_walkable = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var neighbor = current_tile + dir
		if observer._is_tile_valid(neighbor) and observer._is_tile_walkable(neighbor):
			adjacent_walkable += 1
	
	# Chokepoint if only 2-3 exits
	if adjacent_walkable < 2 or adjacent_walkable > 3:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}
	
	# Check if opponents are nearby (worth waiting)
	var opponents_nearby = 0
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		var player_tile = player.get_tile_position()
		var distance = abs(player_tile.x - current_tile.x) + abs(player_tile.y - current_tile.y)
		
		if distance <= 6:
			opponents_nearby += 1
	
	if opponents_nearby == 0:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}
	
	var score = 8.0 + (opponents_nearby * 2.0)
	
	return {
		"score": score,
		"action": ActionType.WAIT_AMBUSH,
		"target_tile": current_tile,
		"chokepoint": true
	}

## Get the best action from scored list
func get_best_action(scores: Array) -> Dictionary:
	if scores.is_empty():
		return {
			"score": 0.0,
			"action": ActionType.REPOSITION_STRATEGIC,
			"target_tile": null
		}
	
	return scores[0]

## Convert action to movement decision
func action_to_movement(action_data: Dictionary, ai_player: Node2D, current_time: float) -> Dictionary:
	var current_tile = ai_player.get_tile_position()
	var direction = Vector2.ZERO
	var place_bomb = action_data.get("place_bomb", false)
	
	match action_data.action:
		ActionType.ESCAPE_DANGER:
			if action_data.has("direction"):
				direction = Vector2(action_data.direction)
			elif action_data.has("target_tile") and action_data.target_tile != null:
				var target = action_data.target_tile
				var dx = target.x - current_tile.x
				var dy = target.y - current_tile.y
				direction = Vector2(sign(dx), sign(dy))
		
		ActionType.ATTACK_PLAYER, ActionType.MOVE_TO_POWERUP, ActionType.DESTROY_BLOCKS, \
		ActionType.CHAIN_BOMB_SETUP, ActionType.REPOSITION_STRATEGIC:
			if action_data.has("target_tile") and action_data.target_tile != null:
				var target = action_data.target_tile
				var dx = target.x - current_tile.x
				var dy = target.y - current_tile.y
				
				# Prefer one axis at a time (cleaner movement)
				if abs(dx) > abs(dy):
					direction = Vector2(sign(dx), 0)
				else:
					direction = Vector2(0, sign(dy))
		
		ActionType.WAIT_AMBUSH:
			direction = Vector2.ZERO
			# Check if opponent in range to bomb
			if ai_player.can_place_bomb():
				for peer_id in game_instance.players:
					var player = game_instance.players[peer_id]
					if player == ai_player:
						continue
					var player_tile = player.get_tile_position()
					var distance = abs(player_tile.x - current_tile.x) + abs(player_tile.y - current_tile.y)
					if distance <= 3:
						place_bomb = true
						break
	
	return {
		"direction": direction,
		"place_bomb": place_bomb,
		"reasoning": ActionType.keys()[action_data.action]
	}
