extends Node
class_name UtilityScorer

const Constants = preload("res://shared/constants.gd")

var game_instance: Node2D
var observer
var danger_mapper
var personality_weights: Dictionary
var bomb_planner

var context_opponent_profiles: Dictionary = {}
var priority_targets: Array = []
var aggression_multiplier: float = 1.0
var item_multiplier: float = 1.0
var latest_state: Dictionary = {}

# Phase 3: Action history and hysteresis
var last_action_type: int = -1
var last_action_time: float = 0.0
var action_cooldowns: Dictionary = {}  # action_type -> cooldown_end_time
var last_position: Vector2i = Vector2i(-999, -999)
var position_stuck_time: float = 0.0
var idle_penalty_multiplier: float = 1.0
const MIN_ACTION_SCORE: float = 0.05  # Guaranteed minimum to prevent deadlock
const STUCK_THRESHOLD: float = 1.5  # Seconds at same position = stuck

enum ActionType {
	MOVE_TO_POWERUP,
	ATTACK_PLAYER,
	DESTROY_BLOCKS,
	ESCAPE_DANGER,
	PLACE_BOMB,
	REPOSITION_STRATEGIC,
	WAIT_AMBUSH,
	CHAIN_BOMB_SETUP,
	PRESSURE_TARGET,
	DENY_POWERUP,
	CUT_OFF_CHOKE,
	SHADOW_TARGET,
	# Phase 3: New action types
	FLANK_OPPONENT,
	KITE_DANGER,
	EXPLORE_MAP,
	CONTROL_CENTER
}

func _init(game_ref: Node2D, obs_ref, danger_ref, personality: Dictionary):
	game_instance = game_ref
	observer = obs_ref
	danger_mapper = danger_ref
	personality_weights = personality
	bomb_planner = null

func set_bomb_planner(planner_ref) -> void:
	bomb_planner = planner_ref

func set_context(context: Dictionary) -> void:
	if context.is_empty():
		return
	context_opponent_profiles = context.get("opponent_profiles", {})
	priority_targets = context.get("priority_targets", [])
	aggression_multiplier = context.get("aggression_bias", 1.0)
	item_multiplier = context.get("item_focus_bias", 1.0)
	latest_state = context.get("game_state", {})
	
	# Phase 3: Track idle time
	var current_pos = context.get("current_position", Vector2i(-999, -999))
	var current_time = context.get("current_time", 0.0)
	if current_pos == last_position:
		if position_stuck_time == 0.0:
			position_stuck_time = current_time
		elif (current_time - position_stuck_time) > STUCK_THRESHOLD:
			idle_penalty_multiplier = 0.3  # Penalize repeated actions
	else:
		last_position = current_pos
		position_stuck_time = 0.0
		idle_penalty_multiplier = 1.0

func score_all_actions(ai_player: Node2D, current_time: float) -> Array:
	var current_tile = ai_player.get_tile_position()
	var scores: Array = []

	var escape_score = score_escape_danger(current_tile, current_time)
	if escape_score.get("score", 0.0) > 0:
		scores.append(escape_score)

	var attack_score = score_attack_opportunity(ai_player, current_tile, current_time)
	if attack_score.get("score", 0.0) > 0:
		scores.append(attack_score)

	var pressure_score = score_pressure_position(ai_player, current_tile, current_time)
	if pressure_score.get("score", 0.0) > 0:
		scores.append(pressure_score)

	var shadow_score = score_shadow_tracking(ai_player, current_tile, current_time)
	if shadow_score.get("score", 0.0) > 0:
		scores.append(shadow_score)

	var cutoff_score = score_cutoff_trap(ai_player, current_tile, current_time)
	if cutoff_score.get("score", 0.0) > 0:
		scores.append(cutoff_score)

	var powerup_score = score_powerup_collection(current_tile, ai_player, current_time)
	if powerup_score.get("score", 0.0) > 0:
		scores.append(powerup_score)

	var denial_score = score_powerup_denial(ai_player, current_tile, current_time)
	if denial_score.get("score", 0.0) > 0:
		scores.append(denial_score)

	var block_score = score_block_destruction(current_tile, ai_player, current_time)
	if block_score.get("score", 0.0) > 0:
		scores.append(block_score)

	var chain_score = score_chain_bomb_setup(current_tile, ai_player, current_time)
	if chain_score.get("score", 0.0) > 0:
		scores.append(chain_score)

	var reposition_score = score_strategic_reposition(current_tile, current_time)
	if reposition_score.get("score", 0.0) > 0:
		scores.append(reposition_score)
	
	# Phase 3: New tactical actions
	var flank_score = score_flank_opponent(ai_player, current_tile, current_time)
	if flank_score.get("score", 0.0) > 0:
		scores.append(flank_score)
	
	var kite_score = score_kite_danger(ai_player, current_tile, current_time)
	if kite_score.get("score", 0.0) > 0:
		scores.append(kite_score)
	
	var explore_score = score_explore_map(current_tile, current_time)
	if explore_score.get("score", 0.0) > 0:
		scores.append(explore_score)
	
	var control_score = score_control_center(current_tile, current_time)
	if control_score.get("score", 0.0) > 0:
		scores.append(control_score)

	if personality_weights.get("trap_bonus", 0) > 0:
		var ambush_score = score_ambush_setup(current_tile, current_time)
		if ambush_score.get("score", 0.0) > 0:
			scores.append(ambush_score)

	scores.sort_custom(func(a, b): return a.get("score", 0.0) > b.get("score", 0.0))
	
	# Phase 3: Apply cooldowns and hysteresis
	scores = _apply_cooldowns(scores, current_time)
	
	# Phase 6: Apply role-based modifiers
	var primary_target = _get_primary_target()
	if not primary_target.is_empty():
		var target_role = primary_target.get("behavior_role", "balanced")
		var role_confidence = primary_target.get("role_confidence", 0.0)
		for action_dict in scores:
			var action_type = action_dict.get("action", -1)
			var role_mod = _get_role_modifier(action_type, target_role, role_confidence)
			action_dict["score"] = action_dict.get("score", 0.0) * role_mod
	
	# Phase 3: Guaranteed non-zero fallback to prevent deadlock
	if scores.is_empty() or scores[0].get("score", 0.0) < MIN_ACTION_SCORE:
		var fallback = _generate_fallback_action(current_tile, current_time)
		if not scores.is_empty():
			scores[0] = fallback
		else:
			scores.append(fallback)
	
	return scores

func score_escape_danger(current_tile: Vector2i, current_time: float) -> Dictionary:
	var danger_level = danger_mapper.get_danger_at_tile(current_tile, current_time, 1.0)
	if danger_level < 0.3:
		return {"score": 0.0, "action": ActionType.ESCAPE_DANGER}

	var time_until = danger_mapper.get_time_until_explosion(current_tile, current_time)
	var base_score = 1000.0
	if time_until < 0.5:
		base_score = 2000.0
	elif time_until < 1.0:
		base_score = 1500.0

	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	if escape_info.safe_count == 0:
		return {
			"score": base_score * 0.8,
			"action": ActionType.ESCAPE_DANGER,
			"target_tile": null,
			"urgency": "CRITICAL"
		}

	return {
		"score": base_score,
		"action": ActionType.ESCAPE_DANGER,
		"target_tile": escape_info.best_route.tile,
		"direction": escape_info.best_route.direction,
		"urgency": "HIGH" if time_until < 1.0 else "MEDIUM"
	}

func score_attack_opportunity(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	var base_score = personality_weights.get("aggression", 500.0) / 100.0
	var target_data = _get_primary_target()
	var target_player = null
	if not target_data.is_empty():
		target_player = _resolve_player_by_id(target_data.player_id)
	var opponent_tile = current_tile
	var distance = INF

	if target_player != null:
		opponent_tile = target_player.get_tile_position()
		distance = _manhattan_distance(current_tile, opponent_tile)
	else:
		for peer_id in game_instance.players:
			var player = game_instance.players[peer_id]
			if player == ai_player or (player.has_method("is_dead") and player.is_dead):
				continue
			var tile_pos = player.get_tile_position()
			var dist = _manhattan_distance(current_tile, tile_pos)
			if dist < distance:
				distance = dist
				opponent_tile = tile_pos
				target_player = player

	if target_player == null or distance > 10:
		return {"score": 0.0, "action": ActionType.ATTACK_PLAYER}

	var distance_factor = max(0.0, 1.0 - (float(distance) / 10.0))
	var score = base_score * 18.0 * distance_factor

	if ai_player.can_place_bomb():
		var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
		if opponent_tile in simulation.affected_tiles:
			score += 12.0
		if simulation.traps_players > 0:
			score += personality_weights.get("trap_bonus", 500.0) / 40.0

	if not target_data.is_empty():
		var predicted_tile: Vector2i = target_data.get("predicted_tile", opponent_tile)
		var prediction_distance = _manhattan_distance(current_tile, predicted_tile)
		score += max(0.0, 14.0 - prediction_distance * 1.5)

	score = _apply_bias(score, true, false)
	return {
		"score": score,
		"action": ActionType.ATTACK_PLAYER,
		"target_tile": opponent_tile,
		"target_player": target_player,
		"distance": distance
	}

func score_pressure_position(_ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	if priority_targets.is_empty():
		return {"score": 0.0, "action": ActionType.PRESSURE_TARGET}

	var best_score = 0.0
	var best_tile = Vector2i(-1, -1)
	var evaluation_targets = priority_targets.slice(0, min(3, priority_targets.size()))

	for target in evaluation_targets:
		var profile: Dictionary = context_opponent_profiles.get(target.player_id, {})
		var anchor_tile: Vector2i = target.get("predicted_tile", target.get("tile", current_tile))
		var ring_tiles = _candidate_tiles_around(anchor_tile, 2)

		for candidate in ring_tiles:
			if not observer._is_tile_valid(candidate) or not observer._is_tile_walkable(candidate):
				continue
			var danger = danger_mapper.get_danger_at_tile(candidate, current_time, 1.5)
			if danger > 0.65:
				continue
			var distance = float(_manhattan_distance(current_tile, candidate))
			if distance == 0.0:
				continue
			var escape_info = danger_mapper.calculate_escape_routes(candidate, current_time)
			var proximity = max(0.0, 16.0 - distance * 2.0)
			var control_bonus = escape_info.safe_count * 2.5
			var pressure = (proximity + control_bonus + profile.get("aggression", 0.0) * 0.4) * aggression_multiplier
			pressure -= danger * 28.0
			if pressure > best_score:
				best_score = pressure
				best_tile = candidate

	if best_tile == Vector2i(-1, -1):
		return {"score": 0.0, "action": ActionType.PRESSURE_TARGET}

	return {
		"score": best_score,
		"action": ActionType.PRESSURE_TARGET,
		"target_tile": best_tile
	}

func score_shadow_tracking(_ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	if priority_targets.is_empty():
		return {"score": 0.0, "action": ActionType.SHADOW_TARGET}
	var target = priority_targets[0]
	var profile: Dictionary = context_opponent_profiles.get(target.player_id, {})
	var velocity: Vector2 = profile.get("velocity", Vector2.ZERO)
	if velocity.length() < 5.0:
		return {"score": 0.0, "action": ActionType.SHADOW_TARGET}

	var offset: Vector2i = _vector_to_tile_offset(velocity)
	if offset == Vector2i.ZERO:
		offset = Vector2i(0, 1)
	var target_tile: Vector2i = profile.get("tile", current_tile) - offset * 2
	if not observer._is_tile_walkable(target_tile):
		target_tile = profile.get("tile", current_tile) - offset
	if not observer._is_tile_walkable(target_tile):
		return {"score": 0.0, "action": ActionType.SHADOW_TARGET}

	var danger = danger_mapper.get_danger_at_tile(target_tile, current_time, 1.0)
	if danger > 0.75:
		return {"score": 0.0, "action": ActionType.SHADOW_TARGET}

	var distance = float(_manhattan_distance(current_tile, target_tile))
	var closeness = max(0.0, 12.0 - distance * 1.4)
	var score = (closeness + profile.get("power_level", 0.0) * 0.3) * aggression_multiplier
	return {
		"score": score,
		"action": ActionType.SHADOW_TARGET,
		"target_tile": target_tile
	}

func score_cutoff_trap(ai_player: Node2D, _current_tile: Vector2i, current_time: float) -> Dictionary:
	if bomb_planner == null or not ai_player.can_place_bomb() or priority_targets.is_empty():
		return {"score": 0.0, "action": ActionType.CUT_OFF_CHOKE}

	var best_plan: Dictionary = {}
	var best_score = 0.0
	for target in priority_targets.slice(0, min(2, priority_targets.size())):
		var profile = context_opponent_profiles.get(target.player_id, {})
		var plan = bomb_planner.plan_target_trap(profile, ai_player, current_time)
		if plan.get("success", false):
			var score = _apply_bias(plan.value, true, false)
			if score > best_score:
				best_score = score
				best_plan = plan

	if best_plan.is_empty():
		return {"score": 0.0, "action": ActionType.CUT_OFF_CHOKE}

	return {
		"score": best_score,
		"action": ActionType.CUT_OFF_CHOKE,
		"target_tile": best_plan.bomb_tile,
		"place_bomb": true,
		"bomb_tile": best_plan.bomb_tile,
		"bomb_safety": best_plan.safety,
		"escape_tile": best_plan.escape_tile
	}

func score_powerup_collection(current_tile: Vector2i, _ai_player: Node2D, current_time: float) -> Dictionary:
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

	var path_danger = danger_mapper.get_danger_at_tile(best_powerup.tile, current_time, 1.0)
	var base_score = max(0.0, best_powerup.value / 55.0)
	if path_danger > 0.4:
		base_score *= 0.4

	var opponent_distance = _nearest_opponent_distance(best_powerup.tile)
	if opponent_distance < best_powerup.distance:
		base_score *= 1.6

	base_score = _apply_bias(base_score, false, true)
	return {
		"score": base_score,
		"action": ActionType.MOVE_TO_POWERUP,
		"target_tile": best_powerup.tile,
		"powerup_type": best_powerup.type,
		"distance": best_powerup.distance
	}

func score_powerup_denial(_ai_player: Node2D, current_tile: Vector2i, _current_time: float) -> Dictionary:
	if not game_instance.get("powerups"):
		return {"score": 0.0, "action": ActionType.DENY_POWERUP}

	var best = {"score": 0.0}
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		if powerup.collected or powerup.destroyed:
			continue
		var tile = powerup.get_tile_position()
		var ai_distance = _manhattan_distance(current_tile, tile)
		var closest_target = _closest_target_to_tile(tile)
		if closest_target.is_empty():
			continue
		var opponent_steps = closest_target.distance
		if ai_distance > opponent_steps + 2:
			continue
		var score = (closest_target.profile.get("power_level", 1.0) + 8.0) / max(1.0, float(ai_distance))
		score = _apply_bias(score * 2.2, false, true)
		if score > best.get("score", 0.0):
			best = {
				"score": score,
				"action": ActionType.DENY_POWERUP,
				"target_tile": tile
			}

	if best.get("score", 0.0) == 0.0:
		return {"score": 0.0, "action": ActionType.DENY_POWERUP}
	return best

func score_block_destruction(current_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	if not ai_player.can_place_bomb():
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}
	var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
	if simulation.blocks_destroyed == 0:
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}
	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	if escape_info.safe_count == 0:
		return {"score": 0.0, "action": ActionType.DESTROY_BLOCKS}
	var base_score = simulation.blocks_destroyed * 12.0
	if simulation.creates_chain:
		base_score += 24.0
	base_score = _apply_bias(base_score, false, false)
	return {
		"score": base_score,
		"action": ActionType.DESTROY_BLOCKS,
		"target_tile": current_tile,
		"blocks_destroyed": simulation.blocks_destroyed,
		"creates_chain": simulation.creates_chain,
		"place_bomb": true
	}

func score_chain_bomb_setup(current_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	if not ai_player.can_place_bomb():
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}
	var chain_bonus = personality_weights.get("chain_setup_bonus", 0.0)
	if chain_bonus < 100.0:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}

	var nearby_bombs = []
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		var bomb_tile = bomb.get_tile_position()
		var distance = _manhattan_distance(current_tile, bomb_tile)
		if distance > 0 and distance <= ai_player.bomb_range + bomb.explosion_range:
			nearby_bombs.append(bomb)

	if nearby_bombs.is_empty():
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}

	var simulation = danger_mapper.simulate_bomb_placement(current_tile, ai_player.bomb_range, current_time)
	if not simulation.creates_chain:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}

	var escape_info = danger_mapper.calculate_escape_routes(current_tile, current_time)
	if escape_info.safe_count < 2:
		return {"score": 0.0, "action": ActionType.CHAIN_BOMB_SETUP}

	var score = _apply_bias(28.0 + simulation.blocks_destroyed * 6.0, true, false)
	return {
		"score": score,
		"action": ActionType.CHAIN_BOMB_SETUP,
		"target_tile": current_tile,
		"chain_length": nearby_bombs.size() + 1,
		"place_bomb": true
	}

func score_strategic_reposition(current_tile: Vector2i, current_time: float) -> Dictionary:
	var base_score = 4.0
	var map_center = Vector2i(game_instance.game_map[0].size() / 2, game_instance.game_map.size() / 2)
	var distance_to_center = _manhattan_distance(current_tile, map_center)
	if distance_to_center > 4:
		base_score += 3.0

	var best_tile: Vector2i = current_tile
	var best_value = 0.0
	for dy in range(-3, 4):
		for dx in range(-3, 4):
			if dx == 0 and dy == 0:
				continue
			var tile = current_tile + Vector2i(dx, dy)
			if not observer._is_tile_valid(tile) or not observer._is_tile_walkable(tile):
				continue
			var danger = danger_mapper.get_danger_at_tile(tile, current_time, 1.0)
			if danger > 0.5:
				continue
			var value = max(0.0, 14.0 - float(_manhattan_distance(tile, map_center)))
			if value > best_value:
				best_value = value
				best_tile = tile

	if best_tile == current_tile:
		var fallback_tile = _find_nearest_safe_neighbor(current_tile, current_time, 5)
		if fallback_tile == current_tile:
			return {"score": 0.0, "action": ActionType.REPOSITION_STRATEGIC}
		best_tile = fallback_tile
		best_value = max(best_value, 2.0)

	return {
		"score": base_score + best_value * 0.5,
		"action": ActionType.REPOSITION_STRATEGIC,
		"target_tile": best_tile
	}

func score_ambush_setup(current_tile: Vector2i, _current_time: float) -> Dictionary:
	var trap_bonus = personality_weights.get("trap_bonus", 0.0)
	if trap_bonus < 100.0:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}

	var adjacent_walkable = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var neighbor = current_tile + dir
		if observer._is_tile_valid(neighbor) and observer._is_tile_walkable(neighbor):
			adjacent_walkable += 1

	if adjacent_walkable < 2 or adjacent_walkable > 3:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}

	var opponents_nearby = 0
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		if player.has_method("is_dead") and player.is_dead:
			continue
		var distance = _manhattan_distance(current_tile, player.get_tile_position())
		if distance <= 6:
			opponents_nearby += 1

	if opponents_nearby == 0:
		return {"score": 0.0, "action": ActionType.WAIT_AMBUSH}

	var score = (8.0 + opponents_nearby * 2.5) * aggression_multiplier
	return {
		"score": score,
		"action": ActionType.WAIT_AMBUSH,
		"target_tile": current_tile,
		"chokepoint": true
	}

func get_best_action(scores: Array) -> Dictionary:
	if scores.is_empty():
		return {"score": 0.0, "action": ActionType.REPOSITION_STRATEGIC, "target_tile": null}
	return scores[0]

func action_to_movement(action_data: Dictionary, ai_player: Node2D, _current_time: float) -> Dictionary:
	var current_tile = ai_player.get_tile_position()
	var direction = Vector2.ZERO
	var place_bomb = action_data.get("place_bomb", false)

	match action_data.action:
		ActionType.ESCAPE_DANGER:
			if action_data.has("direction"):
				direction = Vector2(action_data.direction)
			elif action_data.has("target_tile") and action_data.target_tile != null:
				var target = action_data.target_tile
				direction = Vector2(sign(target.x - current_tile.x), sign(target.y - current_tile.y))

		ActionType.ATTACK_PLAYER, ActionType.MOVE_TO_POWERUP, ActionType.DESTROY_BLOCKS, ActionType.CHAIN_BOMB_SETUP, ActionType.REPOSITION_STRATEGIC, ActionType.PRESSURE_TARGET, ActionType.DENY_POWERUP, ActionType.SHADOW_TARGET, ActionType.CUT_OFF_CHOKE:
			if action_data.has("target_tile") and action_data.target_tile != null:
				var tgt = action_data.target_tile
				var dx = tgt.x - current_tile.x
				var dy = tgt.y - current_tile.y
				if abs(dx) > abs(dy):
					direction = Vector2(sign(dx), 0)
				else:
					direction = Vector2(0, sign(dy))

		ActionType.WAIT_AMBUSH:
			direction = Vector2.ZERO
			if ai_player.can_place_bomb():
				for peer_id in game_instance.players:
					var player = game_instance.players[peer_id]
					if player == ai_player:
						continue
					var distance = _manhattan_distance(current_tile, player.get_tile_position())
					if distance <= 3:
						place_bomb = true
						break

	return {
		"direction": direction,
		"place_bomb": place_bomb,
		"reasoning": ActionType.keys()[action_data.action]
	}

func _apply_bias(score: float, aggressive: bool, item_focus: bool) -> float:
	var result = score
	if aggressive:
		result *= aggression_multiplier
	if item_focus:
		result *= item_multiplier
	return result

func _get_primary_target() -> Dictionary:
	if priority_targets.size() > 0:
		return priority_targets[0]
	return {}

func _resolve_player_by_id(player_id: String):
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		if str(player.player_id) == player_id:
			return player
	return null

func _nearest_opponent_distance(tile: Vector2i) -> int:
	var min_distance = INF
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		if player.has_method("is_dead") and player.is_dead:
			continue
		min_distance = min(min_distance, _manhattan_distance(tile, player.get_tile_position()))
	return min_distance

func _closest_target_to_tile(tile: Vector2i) -> Dictionary:
	var best = {"distance": INF}
	for target in priority_targets:
		var profile: Dictionary = context_opponent_profiles.get(target.player_id, {})
		var distance = _manhattan_distance(tile, profile.get("tile", tile))
		if distance < best.distance:
			best = {
				"player_id": target.player_id,
				"distance": distance,
				"profile": profile
			}
	if best.distance == INF:
		return {}
	return best

func _manhattan_distance(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)

func _candidate_tiles_around(center: Vector2i, radius: int) -> Array:
	var tiles: Array = []
	for dy in range(-radius, radius + 1):
		for dx in range(-radius, radius + 1):
			if abs(dx) + abs(dy) != radius:
				continue
			tiles.append(center + Vector2i(dx, dy))
	return tiles

func _vector_to_tile_offset(vec: Vector2) -> Vector2i:
	if abs(vec.x) > abs(vec.y):
		return Vector2i(sign(vec.x), 0)
	elif abs(vec.y) > 0.1:
		return Vector2i(0, sign(vec.y))
	return Vector2i.ZERO

func _find_nearest_safe_neighbor(origin: Vector2i, current_time: float, max_radius: int) -> Vector2i:
	var visited := {}
	visited[origin] = true
	var queue: Array = [{"tile": origin, "depth": 0}]
	var directions = [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
	while not queue.is_empty():
		var entry: Dictionary = queue.pop_front()
		var tile: Vector2i = entry.tile
		var depth: int = entry.depth
		if depth > 0:
			var danger = danger_mapper.get_danger_at_tile(tile, current_time, 0.6)
			if danger <= 0.7:
				return tile
		if depth >= max_radius:
			continue
		for dir in directions:
			var neighbor = tile + dir
			if visited.has(neighbor):
				continue
			if not observer._is_tile_valid(neighbor) or not observer._is_tile_walkable(neighbor):
				continue
			visited[neighbor] = true
			queue.push_back({"tile": neighbor, "depth": depth + 1})
	return origin

## Phase 3: Flank opponent by moving perpendicular to their facing
func score_flank_opponent(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	if priority_targets.is_empty():
		return {"score": 0.0, "action": ActionType.FLANK_OPPONENT}
	
	var best_target = priority_targets[0]
	var target_profile = context_opponent_profiles.get(best_target.player_id, {})
	var target_tile = target_profile.get("tile", Vector2i(-1, -1))
	
	if target_tile == Vector2i(-1, -1):
		return {"score": 0.0, "action": ActionType.FLANK_OPPONENT}
	
	var distance = _manhattan_distance(current_tile, target_tile)
	if distance > 8 or distance < 2:
		return {"score": 0.0, "action": ActionType.FLANK_OPPONENT}
	
	# Find perpendicular movement to target's predicted path
	var predicted_tile = target_profile.get("predicted_tile", target_tile)
	var target_vector = predicted_tile - target_tile
	
	# Perpendicular directions
	var perp_dirs = []
	if target_vector.x != 0:
		perp_dirs = [Vector2i(0, 1), Vector2i(0, -1)]
	else:
		perp_dirs = [Vector2i(1, 0), Vector2i(-1, 0)]
	
	var best_flank_tile = current_tile
	var best_flank_score = 0.0
	
	for dir in perp_dirs:
		for dist in range(1, 4):
			var flank_tile = current_tile + dir * dist
			if not observer._is_tile_valid(flank_tile) or not observer._is_tile_walkable(flank_tile):
				break
			
			var flank_danger = danger_mapper.get_danger_at_tile(flank_tile, current_time, 1.0)
			if flank_danger > 0.4:
				continue
			
			var flank_distance = _manhattan_distance(flank_tile, target_tile)
			if flank_distance >= 3 and flank_distance <= 6:
				var score = (7.0 - flank_distance) / 7.0
				if score > best_flank_score:
					best_flank_score = score
					best_flank_tile = flank_tile
	
	if best_flank_score > 0:
		var base_score = best_flank_score * 0.5 * aggression_multiplier * personality_weights.aggression
		return {
			"score": base_score * idle_penalty_multiplier,
			"action": ActionType.FLANK_OPPONENT,
			"target_tile": best_flank_tile,
			"place_bomb": false
		}
	
	return {"score": 0.0, "action": ActionType.FLANK_OPPONENT}

## Phase 3: Kite away from danger while maintaining offensive pressure
func score_kite_danger(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	var current_danger = danger_mapper.get_danger_at_tile(current_tile, current_time, 0.8)
	
	if current_danger < 0.25:
		return {"score": 0.0, "action": ActionType.KITE_DANGER}
	
	# Use danger gradient to find escape direction
	var danger_gradient = danger_mapper.get_danger_gradient(current_tile, current_time)
	if danger_gradient.length() < 0.01:
		return {"score": 0.0, "action": ActionType.KITE_DANGER}
	
	# Move away from danger
	var escape_vector = -danger_gradient
	var escape_dir = _vector_to_tile_offset(escape_vector)
	var kite_tile = current_tile + escape_dir
	
	if not observer._is_tile_valid(kite_tile) or not observer._is_tile_walkable(kite_tile):
		# Try perpendicular
		var perp = Vector2i(-escape_dir.y, escape_dir.x) if escape_dir.x != 0 else Vector2i(1, 0)
		kite_tile = current_tile + perp
		if not observer._is_tile_valid(kite_tile) or not observer._is_tile_walkable(kite_tile):
			return {"score": 0.0, "action": ActionType.KITE_DANGER}
	
	var kite_danger = danger_mapper.get_danger_at_tile(kite_tile, current_time, 1.2)
	
	# Only kite if it reduces danger
	if kite_danger >= current_danger:
		return {"score": 0.0, "action": ActionType.KITE_DANGER}
	
	var danger_reduction = current_danger - kite_danger
	var base_score = danger_reduction * 0.7 * personality_weights.get("caution", 0.5)
	
	return {
		"score": base_score * idle_penalty_multiplier,
		"action": ActionType.KITE_DANGER,
		"target_tile": kite_tile,
		"place_bomb": false
	}

## Phase 3: Explore unmapped/unseen areas
func score_explore_map(current_tile: Vector2i, current_time: float) -> Dictionary:
	# IMPORTANT: High priority at game start to escape corners
	var map_width = game_instance.game_map[0].size()
	var map_height = game_instance.game_map.size()
	var center = Vector2i(map_width / 2, map_height / 2)
	
	# Check if we're in a corner or edge (spawn area)
	var is_corner = (current_tile.x < 3 or current_tile.x > map_width - 4) and \
	                (current_tile.y < 3 or current_tile.y > map_height - 4)
	var is_edge = current_tile.x < 4 or current_tile.x > map_width - 5 or \
	              current_tile.y < 4 or current_tile.y > map_height - 5
	
	# Find tiles toward center or open space
	var best_explore_tile = current_tile
	var best_score_value = 0.0
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for dist in range(3, 10):  # Look further
			var explore_tile = current_tile + dir * dist
			if not observer._is_tile_valid(explore_tile) or not observer._is_tile_walkable(explore_tile):
				break
			
			var danger = danger_mapper.get_danger_at_tile(explore_tile, current_time, 1.5)
			if danger > 0.3:
				continue
			
			# Score based on distance from current position and moving toward center
			var distance_from_current = _manhattan_distance(current_tile, explore_tile)
			var distance_to_center = _manhattan_distance(explore_tile, center)
			var current_distance_to_center = _manhattan_distance(current_tile, center)
			
			# Prefer tiles that are: far from current position AND closer to center
			var tile_score = distance_from_current * 2.0
			if distance_to_center < current_distance_to_center:
				tile_score += 5.0  # Big bonus for moving toward center
			
			if tile_score > best_score_value:
				best_score_value = tile_score
				best_explore_tile = explore_tile
	
	if best_score_value > 0:
		# MUCH higher base score, especially if in corner
		var base_score = 1.5 * personality_weights.get("exploration", 0.3)  # 10x higher than before
		if is_corner:
			base_score *= 3.0  # Triple score if in corner - MUST escape
		elif is_edge:
			base_score *= 2.0  # Double if on edge
		
		return {
			"score": base_score * idle_penalty_multiplier,
			"action": ActionType.EXPLORE_MAP,
			"target_tile": best_explore_tile,
			"place_bomb": false
		}
	
	return {"score": 0.0, "action": ActionType.EXPLORE_MAP}

## Phase 3: Control center of map for strategic advantage
func score_control_center(current_tile: Vector2i, current_time: float) -> Dictionary:
	var map_width = game_instance.game_map[0].size()
	var map_height = game_instance.game_map.size()
	var center = Vector2i(map_width / 2, map_height / 2)
	
	var distance_to_center = _manhattan_distance(current_tile, center)
	
	# Only score if not already at center
	if distance_to_center <= 2:
		return {"score": 0.0, "action": ActionType.CONTROL_CENTER}
	
	# Find path toward center
	var direction = center - current_tile
	var move_dir = _vector_to_tile_offset(Vector2(direction))
	var center_tile = current_tile + move_dir
	
	if not observer._is_tile_valid(center_tile) or not observer._is_tile_walkable(center_tile):
		return {"score": 0.0, "action": ActionType.CONTROL_CENTER}
	
	var danger = danger_mapper.get_danger_at_tile(center_tile, current_time, 1.0)
	if danger > 0.4:
		return {"score": 0.0, "action": ActionType.CONTROL_CENTER}
	
	var base_score = 0.25 * personality_weights.get("aggression", 0.5) * aggression_multiplier
	
	return {
		"score": base_score * idle_penalty_multiplier,
		"action": ActionType.CONTROL_CENTER,
		"target_tile": center_tile,
		"place_bomb": false
	}

## Phase 3: Apply action cooldowns to prevent repetition
func _apply_cooldowns(scores: Array, current_time: float) -> Array:
	var filtered_scores = []
	
	for score_data in scores:
		var action_type = score_data.action
		
		# Check cooldown
		if action_cooldowns.has(action_type):
			if current_time < action_cooldowns[action_type]:
				# Still on cooldown, reduce score significantly
				score_data["score"] = score_data.get("score", 0.0) * 0.2
		
		# Penalize repeating same action
		if action_type == last_action_type:
			var time_since = current_time - last_action_time
			if time_since < 0.5:
				score_data["score"] = score_data.get("score", 0.0) * 0.4
		
		filtered_scores.append(score_data)
	
	# Update cooldown for chosen action
	if not filtered_scores.is_empty():
		var chosen = filtered_scores[0]
		last_action_type = chosen.action
		last_action_time = current_time
		
		# Set cooldown for aggressive actions
		if chosen.action in [ActionType.ATTACK_PLAYER, ActionType.PRESSURE_TARGET, ActionType.FLANK_OPPONENT]:
			action_cooldowns[chosen.action] = current_time + 0.3
	
	return filtered_scores

## Phase 3: Generate guaranteed fallback to prevent deadlock
func _generate_fallback_action(current_tile: Vector2i, current_time: float) -> Dictionary:
	# Per user request, prefer exploration over standing still.
	# Find a safe, explorable tile nearby.
	var explore_score = score_explore_map(current_tile, current_time)
	if explore_score.get("score", 0.0) > 0.0:
		explore_score["score"] = MIN_ACTION_SCORE * 2.5 # Boost score to ensure it's picked
		return explore_score

	# If exploration fails, find any safe adjacent tile to move to.
	var directions = [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
	directions.shuffle()
	
	for dir in directions:
		var fallback_tile = current_tile + dir
		if observer._is_tile_valid(fallback_tile) and observer._is_tile_walkable(fallback_tile):
			var danger = danger_mapper.get_danger_at_tile(fallback_tile, current_time, 0.5)
			if danger < 0.8:  # Accept moderate danger to escape deadlock
				return {
					"score": MIN_ACTION_SCORE * 2.0,
					"action": ActionType.EXPLORE_MAP,
					"target_tile": fallback_tile,
					"place_bomb": false,
					"reasoning": "FALLBACK_EXPLORE"
				}
	
	# Ultimate fallback: stay in place if truly trapped
	return {
		"score": MIN_ACTION_SCORE,
		"action": ActionType.REPOSITION_STRATEGIC,
		"target_tile": current_tile,
		"place_bomb": false,
		"reasoning": "FALLBACK_STUCK"
	}

## Phase 6: Apply role-based scoring modifiers
func _get_role_modifier(action_type: int, target_role: String, role_confidence: float) -> float:
	if role_confidence < 0.3:
		return 1.0  # Low confidence, don't modify
	
	var modifier = 1.0
	
	match action_type:
		ActionType.ESCAPE_DANGER:
			if target_role == "pressurer":
				modifier = 1.8
		ActionType.FLANK_OPPONENT:
			if target_role == "trapper":
				modifier = 2.0
		ActionType.ATTACK_PLAYER:
			if target_role == "item_hog":
				modifier = 2.0
			elif target_role == "pressurer":
				modifier = 0.6
		ActionType.PLACE_BOMB:
			if target_role == "item_hog" or target_role == "trapper":
				modifier = 1.8
		ActionType.MOVE_TO_POWERUP:
			if target_role == "item_hog":
				modifier = 2.5
			elif target_role == "trapper":
				modifier = 1.4
		ActionType.KITE_DANGER:
			if target_role == "pressurer":
				modifier = 2.2
	
	# Blend with confidence
	return lerp(1.0, modifier, role_confidence)
