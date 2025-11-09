extends Node

## Improved AI Controller with Intelligent Decision Making
## Uses DangerMapper, UtilityScorer, and BombPlanner for smart, safe gameplay
## NO MORE SUICIDES - AI always ensures escape routes exist

const Constants = preload("res://shared/constants.gd")
const PersonalityResource = preload("res://server/shared/ai/ai_personalities.gd")
const DangerMapperResource = preload("res://server/shared/ai/danger_mapper.gd")
const UtilityScorerResource = preload("res://server/shared/ai/utility_scorer.gd")
const BombPlannerResource = preload("res://server/shared/ai/bomb_planner.gd")
const DebugVisualizerResource = preload("res://server/shared/ai/ai_debug_visualizer.gd")
const ObserverResource = preload("res://server/shared/ai/ai_observer.gd")

# === Phase 1: Diagnostic Flags ===
var debug_enabled: bool = false
var debug_action_distribution: Dictionary = {}
var debug_decision_count: int = 0
var debug_emergency_count: int = 0
var debug_replanning_count: int = 0
var debug_last_log_time: float = 0.0
const DEBUG_LOG_INTERVAL: float = 3.0  # Log every 3 seconds

# Core systems
var observer
var danger_mapper: DangerMapper
var utility_scorer: UtilityScorer
var bomb_planner: BombPlanner
var debug_visualizer: AIDebugVisualizer

# Configuration
var personality_type: int
var personality_weights: Dictionary

# Decision state
var last_decision_time: float = 0.0
var decision_interval: float = 0.1
var current_action: Dictionary = {}
var current_path: Array = []
var path_update_interval: float = 0.3
var last_path_update: float = 0.0

# Emergency state
var in_emergency: bool = false
var emergency_target: Vector2i = Vector2i(-1, -1)

# A* pathfinding
var astar: AStar2D
var tile_to_id: Dictionary = {}
var astar_initialized: bool = false
var last_astar_build: float = 0.0

# Adaptive targeting and memory
var opponent_profiles: Dictionary = {}
var priority_targets: Array = []
var dynamic_aggression_bias: float = 1.0
var dynamic_item_bias: float = 1.0
var last_profile_update: float = 0.0
const PROFILE_UPDATE_INTERVAL: float = 0.2

var latest_game_state: Dictionary = {}

func _init(game_instance: Node2D, personality: int = 0):
	observer = ObserverResource.new(game_instance)

	personality_type = personality
	personality_weights = PersonalityResource.get_weights(personality)

	decision_interval = clamp(personality_weights.reaction_delay * 0.6, 0.02, 0.12)
	path_update_interval = clamp(personality_weights.get("pathfinding_frequency", 0.3) * 0.5, 0.05, 0.25)

	# Initialize new AI systems
	danger_mapper = DangerMapperResource.new(game_instance, observer)
	bomb_planner = BombPlannerResource.new(game_instance, observer, danger_mapper, personality_weights)
	utility_scorer = UtilityScorerResource.new(game_instance, observer, danger_mapper, personality_weights)
	utility_scorer.set_bomb_planner(bomb_planner)

	# Initialize A* for pathfinding
	astar = AStar2D.new()

	print("[ImprovedAI] Initialized with personality: ", PersonalityResource.get_personality_name(personality))

## Main decision function
func decide_action(ai_player: Node2D) -> Dictionary:
	if ai_player == null or (ai_player.has_method("is_dead") and ai_player.is_dead):
		return {"direction": Vector2.ZERO, "place_bomb": false}
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var current_tile = ai_player.get_tile_position()
	latest_game_state = observer.get_world_state()
	
	# Update danger map
	danger_mapper.update(current_time)
	_update_dynamic_state(latest_game_state, ai_player, current_time)
	utility_scorer.set_context({
		"opponent_profiles": opponent_profiles,
		"priority_targets": priority_targets,
		"aggression_bias": dynamic_aggression_bias,
		"item_focus_bias": dynamic_item_bias,
		"game_state": latest_game_state,
		"current_position": current_tile,
		"current_time": current_time
	})
	
	# EMERGENCY CHECK: Are we in immediate danger?
	if danger_mapper.is_emergency_danger(current_tile, current_time):
		return _handle_emergency_escape(ai_player, current_tile, current_time)
	
	in_emergency = false
	
	# Regular decision making (throttled)
	if current_time - last_decision_time < decision_interval:
		# Continue executing current action
		return _execute_current_action(ai_player, current_tile, current_time)
	
	last_decision_time = current_time
	
	# Score all available actions
	var action_scores = utility_scorer.score_all_actions(ai_player, current_time)

	if action_scores.is_empty():
		# Fallback: just try to stay safe
		return _emergency_fallback(ai_player, current_tile, current_time)

	# Pick the highest-value action that is actually viable right now
	var best_action = _choose_viable_action(action_scores, ai_player, current_tile, current_time)
	if best_action.is_empty():
		return _emergency_fallback(ai_player, current_tile, current_time)

	current_action = best_action
	
	# Phase 1: Track action distribution
	if debug_enabled:
		var action_name = best_action.get("action", "UNKNOWN")
		if not debug_action_distribution.has(action_name):
			debug_action_distribution[action_name] = 0
		debug_action_distribution[action_name] += 1
		debug_decision_count += 1

	# Convert action to movement
	var decision = _action_to_decision(best_action, ai_player, current_tile, current_time)
	
	# Update debug visualization
	if debug_visualizer != null:
		debug_visualizer.update_reasoning(decision.get("reasoning", "Unknown"))
		debug_visualizer.update_target(best_action.get("target_tile", Vector2i(-1, -1)))
		debug_visualizer.update_path(current_path)
	
	# Phase 1: Periodic diagnostic logging
	if debug_enabled and (current_time - debug_last_log_time) >= DEBUG_LOG_INTERVAL:
		_log_diagnostics(current_time)
		debug_last_log_time = current_time
	
	return decision

## Handle emergency escape (highest priority)
func _handle_emergency_escape(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	in_emergency = true
	
	# Phase 1: Track emergencies
	if debug_enabled:
		debug_emergency_count += 1
	
	# Plan emergency escape
	var escape_plan = bomb_planner.plan_emergency_escape(ai_player, current_time)
	
	if not escape_plan.emergency:
		# False alarm, return to normal
		in_emergency = false
		return decide_action(ai_player)
	
	emergency_target = escape_plan.escape_tile
	
	# Move directly toward escape tile
	var direction = _get_direction_to_tile(current_tile, emergency_target, ai_player.position, current_time)
	
	if debug_visualizer != null:
		debug_visualizer.update_reasoning("EMERGENCY ESCAPE!")
		debug_visualizer.update_target(emergency_target)
	
	return {
		"direction": direction,
		"place_bomb": false,
		"reasoning": "EMERGENCY_ESCAPE"
	}

## Convert high-level action to low-level decision
func _action_to_decision(action_data: Dictionary, ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# Check if we should place a bomb
	var place_bomb = false
	var target_tile = action_data.get("target_tile", null)
	var direction = Vector2.ZERO

	if action_data.get("place_bomb", false):
		var safety = action_data.get("bomb_safety")
		if safety == null:
			safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
		if safety.safe:
			place_bomb = true
			if action_data.has("escape_tile"):
				target_tile = action_data.escape_tile
		else:
			# If we can't safely bomb after all, bail out to emergency movement
			return _emergency_fallback(ai_player, current_tile, current_time)

	# Get movement direction using pathfinding or direct vector
	if target_tile != null and target_tile != Vector2i(-1, -1):
		direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
	elif action_data.has("direction"):
		# Direct direction provided (e.g., from escape action)
		direction = action_data.direction

	return {
		"direction": direction,
		"place_bomb": place_bomb,
		"reasoning": action_data.get("action", "UNKNOWN")
	}

## Execute current action (when not replanning)
func _execute_current_action(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	if current_action.is_empty():
		return {"direction": Vector2.ZERO, "place_bomb": false}
	
	# Phase 1: Check if we should replan (log it if so)
	if debug_enabled and (current_time - last_decision_time) >= decision_interval:
		debug_replanning_count += 1
	
	# Follow current path
	var target_tile = current_action.get("target_tile", null)
	var direction = Vector2.ZERO
	
	if target_tile != null and target_tile != Vector2i(-1, -1):
		direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
	
	return {
		"direction": direction,
		"place_bomb": false,  # Don't spam bombs
		"reasoning": "CONTINUING"
	}

## Get direction to target tile using A* pathfinding
func _get_direction_to_tile(from_tile: Vector2i, to_tile: Vector2i, from_position: Vector2, current_time: float) -> Vector2:
	if from_tile == to_tile:
		return Vector2.ZERO
	
	# Rebuild A* graph if needed
	_ensure_astar_ready(current_time)
	
	# Update path if needed
	if current_time - last_path_update > path_update_interval or current_path.is_empty():
		current_path = _calculate_astar_path(from_tile, to_tile, current_time)
		last_path_update = current_time
	
	# Follow path
	if current_path.is_empty():
		# No path found, try direct approach
		var dx = to_tile.x - from_tile.x
		var dy = to_tile.y - from_tile.y
		return Vector2(sign(dx), sign(dy)).normalized()
	
	# Get next waypoint
	var next_waypoint = current_path[0]
	var direction = (next_waypoint - from_position).normalized()
	
	# Check if we reached waypoint
	if from_position.distance_to(next_waypoint) < Constants.TILE_SIZE * 0.3:
		current_path.remove_at(0)  # Move to next waypoint
	
	return direction

## Calculate A* path avoiding danger
func _calculate_astar_path(from_tile: Vector2i, to_tile: Vector2i, _current_time: float) -> Array:
	var from_key = "%d,%d" % [from_tile.x, from_tile.y]
	var to_key = "%d,%d" % [to_tile.x, to_tile.y]
	
	if not tile_to_id.has(from_key) or not tile_to_id.has(to_key):
		return []
	
	var from_id = tile_to_id[from_key]
	var to_id = tile_to_id[to_key]
	
	# Get path
	var path_points = astar.get_point_path(from_id, to_id)
	
	# Convert to waypoints (skip first point as we're already there)
	var waypoints = []
	for i in range(1, path_points.size()):
		waypoints.append(path_points[i])
	
	return waypoints

## Ensure A* graph is built and updated
func _ensure_astar_ready(current_time: float) -> void:
	var game_state = observer.get_world_state()
	
	# Rebuild periodically or if not initialized
	if not astar_initialized or current_time - last_astar_build > 0.5:
		_build_astar_graph(game_state, current_time)
		last_astar_build = current_time
		astar_initialized = true

func _build_astar_graph(game_state: Dictionary, current_time: float) -> void:
	astar.clear()
	tile_to_id.clear()
	
	var map = game_state.get("map", [])
	if map.is_empty():
		return
	
	var point_id = 0
	
	# Add all walkable tiles
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			
			if not observer._is_tile_walkable(tile):
				continue
			
			var tile_key = "%d,%d" % [x, y]
			tile_to_id[tile_key] = point_id
			
			var tile_center = Vector2(
				x * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
				y * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
			)
			
			astar.add_point(point_id, tile_center)
			point_id += 1
	
	# Connect adjacent tiles with danger-aware weights
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]
			
			if not tile_to_id.has(tile_key):
				continue
			
			var from_id = tile_to_id[tile_key]
			
			# Check 4 directions
			for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				var neighbor = tile + dir
				var neighbor_key = "%d,%d" % [neighbor.x, neighbor.y]
				
				if not tile_to_id.has(neighbor_key):
					continue
				
				var to_id = tile_to_id[neighbor_key]
				
				# Calculate weight based on danger
				var danger = danger_mapper.get_danger_at_tile(neighbor, current_time, 1.0)
				var weight = 1.0
				
				if danger > 0.7:
					weight = 100.0  # Avoid high danger
				elif danger > 0.3:
					weight = 10.0  # Avoid medium danger
				
				astar.connect_points(from_id, to_id, true)
				astar.set_point_weight_scale(to_id, weight)

## Emergency fallback when no good actions
func _emergency_fallback(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# Try to find any safe tile
	var safe_tiles = danger_mapper.find_nearest_safe_tiles(current_tile, current_time, 8)
	
	if not safe_tiles.is_empty():
		var safe_tile = safe_tiles[0].tile
		var direction = _get_direction_to_tile(current_tile, safe_tile, ai_player.position, current_time)
		
		return {
			"direction": direction,
			"place_bomb": false,
			"reasoning": "FALLBACK_SAFETY"
		}
	
	# Last resort: random movement
	var random_dir = [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT][randi() % 4]
	return {
		"direction": random_dir,
		"place_bomb": false,
		"reasoning": "RANDOM_PANIC"
	}

## Choose best action that is currently viable (e.g., skip unsafe bomb placements)
func _choose_viable_action(actions: Array, ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	for action_entry in actions:
		if typeof(action_entry) != TYPE_DICTIONARY:
			continue
		var action_data: Dictionary = action_entry.duplicate(true)
		if action_data.is_empty():
			continue

		if action_data.get("place_bomb", false):
			var bomb_tile: Vector2i = action_data.get("bomb_tile", current_tile)
			if bomb_tile == Vector2i(-1, -1):
				bomb_tile = current_tile
			var safety = bomb_planner.can_place_bomb_safely(bomb_tile, ai_player, current_time)
			if not safety.safe:
				continue
			action_data["bomb_tile"] = bomb_tile
			action_data["bomb_safety"] = safety
			if safety.has("escape_route") and typeof(safety.escape_route) == TYPE_DICTIONARY:
				var route: Dictionary = safety.escape_route
				var escape_tile: Vector2i = bomb_tile
				if route.has("tiles") and route.tiles is Array and not route.tiles.is_empty():
					var tiles: Array = route.tiles
					escape_tile = tiles[tiles.size() - 1]
				elif route.has("direction") and route.direction is Vector2i:
					escape_tile = bomb_tile + route.direction
				action_data["escape_tile"] = escape_tile
				if action_data.has("target_tile"):
					if action_data.target_tile == bomb_tile:
						action_data["target_tile"] = escape_tile
				else:
					action_data["target_tile"] = escape_tile

		return action_data

	return {}

func _update_dynamic_state(game_state: Dictionary, ai_player: Node2D, current_time: float) -> void:
	if current_time - last_profile_update < PROFILE_UPDATE_INTERVAL:
		return
	last_profile_update = current_time

	var my_tile = ai_player.get_tile_position()
	var active_ids: Array = []
	var bombs_by_owner: Dictionary = {}
	if game_state.has("bombs"):
		for bomb_id in game_state.bombs:
			var bomb = game_state.bombs[bomb_id]
			if not is_instance_valid(bomb):
				continue
			var owner_id: String = str(bomb.owner_id)
			bombs_by_owner[owner_id] = bombs_by_owner.get(owner_id, 0) + 1

	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if not is_instance_valid(player):
			continue
		if player == ai_player:
			continue
		if player.has_method("is_dead") and player.is_dead:
			continue
		var player_id = str(player.player_id)
		active_ids.append(player_id)

		var profile: Dictionary = opponent_profiles.get(player_id, {
			"avg_distance": 999.0,
			"aggression": 0.0,
			"power_level": 0.0,
			"last_seen": 0.0,
			"bombs_seen": 0,
			"velocity": Vector2.ZERO,
			"tile": player.get_tile_position(),
			"predicted_tile": player.get_tile_position()
		})

		var player_tile: Vector2i = player.get_tile_position()
		var distance = float(abs(player_tile.x - my_tile.x) + abs(player_tile.y - my_tile.y))
		profile.avg_distance = lerp(profile.get("avg_distance", distance), distance, 0.45)

		var active_bombs: float = float(bombs_by_owner.get(player_id, 0))
		var bomb_capacity: float = max(1.0, float(player.max_bombs))
		var aggression_sample = clamp(active_bombs / bomb_capacity, 0.0, 1.5)
		profile.aggression = clamp(lerp(profile.get("aggression", 0.0), aggression_sample * 10.0, 0.5), 0.0, 15.0)

		var power_level = _calculate_power_score(player)
		profile.power_level = lerp(profile.get("power_level", power_level), power_level, 0.4)
		profile.bombs_seen = int(active_bombs)
		profile.tile = player_tile
		profile.last_seen = current_time
		var predicted_pos: Vector2 = observer.predict_opponent_position(player_id, 0.9)
		profile.predicted_tile = Vector2i(
			int(floor(predicted_pos.x / Constants.TILE_SIZE)),
			int(floor(predicted_pos.y / Constants.TILE_SIZE))
		)
		profile.velocity = observer.get_recent_velocity(player_id)

		opponent_profiles[player_id] = profile

	# Prune stale profiles
	for stored_id in opponent_profiles.keys():
		if stored_id not in active_ids:
			opponent_profiles.erase(stored_id)

	_update_priority_targets()
	_update_dynamic_biases(ai_player)

func _update_priority_targets() -> void:
	priority_targets.clear()
	for player_id in opponent_profiles.keys():
		var profile: Dictionary = opponent_profiles[player_id]
		var distance_factor = 1.0 / max(1.0, profile.avg_distance)
		var threat = profile.aggression * 0.6 + profile.power_level * 0.2 + distance_factor * 15.0
		priority_targets.append({
			"player_id": player_id,
			"score": threat,
			"tile": profile.tile,
			"predicted_tile": profile.predicted_tile,
			"aggression": profile.aggression,
			"power": profile.power_level
		})

	priority_targets.sort_custom(func(a, b):
		return a.score > b.score
	)

func _update_dynamic_biases(ai_player: Node2D) -> void:
	var my_power = _calculate_power_score(ai_player)
	var highest_opponent_power = 0.0
	var highest_aggression = 0.0
	for player_id in opponent_profiles.keys():
		var profile: Dictionary = opponent_profiles[player_id]
		highest_opponent_power = max(highest_opponent_power, profile.power_level)
		highest_aggression = max(highest_aggression, profile.aggression)

	var power_gap = clamp(highest_opponent_power - my_power, -5.0, 5.0)
	dynamic_item_bias = clamp(1.0 + power_gap * 0.35, 0.6, 4.5)

	var aggression_base = highest_aggression * 0.25
	if my_power > highest_opponent_power:
		aggression_base += 0.4
	dynamic_aggression_bias = clamp(1.0 + aggression_base, 0.7, 3.5)

func _calculate_power_score(player: Node2D) -> float:
	var max_bombs = _extract_float(player, "max_bombs", 1.0)
	var bomb_range = _extract_float(player, "bomb_range", 1.0)
	var speed_multiplier = _extract_float(player, "speed_multiplier", 1.0)
	return max_bombs * 0.6 + bomb_range * 0.45 + speed_multiplier * 0.4

func _extract_float(target: Object, property_name: String, fallback: float) -> float:
	var value = fallback
	if target.has_method("get"):
		value = target.get(property_name)
	if typeof(value) == TYPE_NIL:
		return fallback
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return float(value)
	return fallback

## Initialize debug visualizer
func setup_debug_visualizer(parent_node: Node2D, ai_player: Node2D) -> void:
	debug_visualizer = AIDebugVisualizer.new()
	debug_visualizer.setup(danger_mapper, self, ai_player)
	parent_node.add_child(debug_visualizer)
	
	print("[ImprovedAI] Debug visualizer enabled")

## Get personality name
func get_personality_name() -> String:
	return AIPersonality.get_personality_name(personality_type)

## Get current state for debugging
func get_current_state_name() -> String:
	if in_emergency:
		return "EMERGENCY"
	elif current_action.has("action"):
		return str(current_action.action)
	return "IDLE"

## Phase 1: Log diagnostic info
func _log_diagnostics(_current_time: float) -> void:
	if debug_decision_count == 0:
		return
	
	print("[ImprovedAI] === Diagnostics Report ===")
	print("  Decisions: ", debug_decision_count, " | Emergencies: ", debug_emergency_count, " | Replans: ", debug_replanning_count)
	print("  Decision Interval: ", decision_interval, "s | Path Update: ", path_update_interval, "s")
	print("  Dynamic Biases: Aggression=", "%.2f" % dynamic_aggression_bias, " Item=", "%.2f" % dynamic_item_bias)
	print("  Action Distribution:")
	for action in debug_action_distribution:
		var percentage = (debug_action_distribution[action] * 100.0) / debug_decision_count
		print("    ", action, ": ", debug_action_distribution[action], " (", "%.1f" % percentage, "%)")
	print("  Priority Targets: ", priority_targets.size())
	print("  Opponent Profiles: ", opponent_profiles.size())
