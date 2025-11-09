extends Node

## Improved AI Controller with Intelligent Decision Making
## Uses DangerMapper, UtilityScorer, and BombPlanner for smart, safe gameplay
## NO MORE SUICIDES - AI always ensures escape routes exist

const Constants = preload("res://shared/constants.gd")
const PersonalityResource = preload("res://shared/ai/ai_personalities.gd")
const DangerMapperResource = preload("res://shared/ai/danger_mapper.gd")
const UtilityScorerResource = preload("res://shared/ai/utility_scorer.gd")
const BombPlannerResource = preload("res://shared/ai/bomb_planner.gd")
const DebugVisualizerResource = preload("res://shared/ai/ai_debug_visualizer.gd")
const ObserverResource = preload("res://shared/ai/ai_observer.gd")

# === Phase 1: Diagnostic Flags ===
var debug_enabled: bool = false
var debug_action_distribution: Dictionary = {}
var debug_decision_count: int = 0
var debug_emergency_count: int = 0
var debug_replanning_count: int = 0
var debug_last_log_time: float = 0.0
const DEBUG_LOG_INTERVAL: float = 3.0  # Log every 3 seconds

# Core systems
var game_instance: Node2D
var observer
var danger_mapper
var utility_scorer
var bomb_planner
var debug_visualizer

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

# Phase 5: Hybrid navigation and steering
var target_velocity: Vector2 = Vector2.ZERO
var current_velocity: Vector2 = Vector2.ZERO
var steering_force: Vector2 = Vector2.ZERO
const MAX_STEERING_FORCE: float = 400.0
const VELOCITY_SMOOTHING: float = 0.15  # Lower = smoother
const ARRIVAL_RADIUS: float = 8.0  # Pixels - slow down when close to target

# Phase 5: Replanning triggers
var last_bomb_count: int = 0
var last_danger_snapshot: float = 0.0
var force_replan: bool = false
const DANGER_SPIKE_THRESHOLD: float = 0.3  # Trigger replan if danger increases by this much

var latest_game_state: Dictionary = {}

func _init(game_inst: Node2D, personality: int = 0):
	game_instance = game_inst
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
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "NULL_OR_DEAD"}
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var current_tile = ai_player.get_tile_position()
	
	# Debug: Check if observer/danger_mapper exist
	if observer == null:
		print("[ImprovedAI] ERROR: observer is null!")
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "NO_OBSERVER"}
	if danger_mapper == null:
		print("[ImprovedAI] ERROR: danger_mapper is null!")
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "NO_DANGER_MAPPER"}
	
	latest_game_state = observer.get_world_state()
	
	# Update danger map
	danger_mapper.update(current_time)
	_update_dynamic_state(latest_game_state, ai_player, current_time)

	# Phase 5: Check for replanning triggers
	_check_replanning_triggers(current_tile, current_time)
	# Phase 5: Check for replanning triggers
	_check_replanning_triggers(current_tile, current_time)

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
	
	# Phase 5: Force replan if triggered
	var should_replan = force_replan or (current_time - last_decision_time >= decision_interval)
	force_replan = false

	# Regular decision making (throttled unless forced)
	if not should_replan:
		# Continue executing current action
		return _execute_current_action(ai_player, current_tile, current_time)
	
	last_decision_time = current_time
	
	# Score all available actions
	var action_scores = utility_scorer.score_all_actions(ai_player, current_time)

	if action_scores.is_empty():
		# Fallback: just try to stay safe
		print("[ImprovedAI] WARNING: No action scores, using emergency fallback")
		return _emergency_fallback(ai_player, current_tile, current_time)

	# Pick the highest-value action that is actually viable right now
	var best_action = _choose_viable_action(action_scores, ai_player, current_tile, current_time)
	if best_action.is_empty():
		print("[ImprovedAI] WARNING: No viable action found, using emergency fallback")
		return _emergency_fallback(ai_player, current_tile, current_time)

	current_action = best_action
	
	# Debug: Log best action
	if Engine.get_physics_frames() % 30 == 0:  # Log more frequently for debugging
		var action_name = "UNKNOWN"
		if best_action.get("action") is int and best_action.action >= 0 and best_action.action < utility_scorer.ActionType.size():
			action_name = utility_scorer.ActionType.keys()[best_action.action]
		print("[ImprovedAI] Best action: ", action_name, " | Score: ", "%.2f" % best_action.get("score", 0.0), " | Target: ", best_action.get("target_tile", "none"), " | Reasoning: ", best_action.get("reasoning", "N/A"))

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
		var reasoning_text = str(best_action.get("action", "UNKNOWN"))
		if best_action.get("action") is int and best_action.action >= 0 and best_action.action < utility_scorer.ActionType.size():
			reasoning_text = utility_scorer.ActionType.keys()[best_action.action]
		
		debug_visualizer.update_reasoning(reasoning_text)
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
		if Engine.get_physics_frames() % 60 == 0:
			print("[ImprovedAI] Moving from ", current_tile, " to ", target_tile, " direction: ", direction)
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

	# Phase 6: Classify behavior roles
	_classify_behavior_roles()
	
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
		"power": profile.power_level,
		"behavior_role": profile.get("behavior_role", "balanced"),
		"role_confidence": profile.get("role_confidence", 0.0)
	})

	priority_targets.sort_custom(func(a, b):
		return a.get("score", 0.0) > b.get("score", 0.0)
	)

func _update_dynamic_biases(ai_player: Node2D) -> void:
	# Phase 6: Use per-opponent power gaps instead of global highest
	var power_gaps = _calculate_power_gaps(ai_player)
	var weight_mods = _apply_power_gap_biases(power_gaps)
	
	# Apply Phase 6 adaptive weights
	dynamic_item_bias = weight_mods.item_focus
	dynamic_aggression_bias = weight_mods.aggression
	
	# Store for utility scorer
	var my_power = _calculate_power_score(ai_player)
	var highest_opponent_power = 0.0
	var highest_aggression = 0.0
	for player_id in opponent_profiles.keys():
		var profile: Dictionary = opponent_profiles[player_id]
		highest_opponent_power = max(highest_opponent_power, profile.power_level)
		highest_aggression = max(highest_aggression, profile.aggression)

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
	debug_visualizer = DebugVisualizerResource.new()
	debug_visualizer.setup(danger_mapper, self, ai_player)
	parent_node.add_child(debug_visualizer)
	
	print("[ImprovedAI] Debug visualizer enabled")

## Get personality name
func get_personality_name() -> String:
	return PersonalityResource.get_personality_name(personality_type)

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

## Phase 5: Check for replanning triggers
func _check_replanning_triggers(current_tile: Vector2i, current_time: float) -> void:
	# Trigger 1: New bomb placed
	var current_bomb_count = game_instance.bombs.size() if game_instance.get("bombs") else 0
	if current_bomb_count != last_bomb_count:
		if current_bomb_count > last_bomb_count:
			# New bomb detected - force replan
			force_replan = true
		last_bomb_count = current_bomb_count
	
	# Trigger 2: Danger spike at current location
	var current_danger = danger_mapper.get_danger_at_tile(current_tile, current_time, 0.5)
	if current_danger - last_danger_snapshot > DANGER_SPIKE_THRESHOLD:
		# Significant danger increase - force replan
		force_replan = true
	last_danger_snapshot = current_danger

## Phase 5: Calculate steering force for smooth movement
func _calculate_steering(from_position: Vector2, target_position: Vector2) -> Vector2:
	var to_target = target_position - from_position
	var distance = to_target.length()
	
	if distance < 0.1:
		return Vector2.ZERO
	
	# Calculate desired velocity
	var desired_speed = Constants.BASE_SPEED
	
	# Arrival behavior - slow down when close
	if distance < ARRIVAL_RADIUS:
		desired_speed *= (distance / ARRIVAL_RADIUS)
	
	target_velocity = to_target.normalized() * desired_speed
	
	# Calculate steering force
	steering_force = (target_velocity - current_velocity).limit_length(MAX_STEERING_FORCE)
	
	# Apply steering with smoothing
	current_velocity = current_velocity.lerp(current_velocity + steering_force * VELOCITY_SMOOTHING, 0.3)
	current_velocity = current_velocity.limit_length(Constants.BASE_SPEED)
	
	return current_velocity

## Phase 5: Enhanced direction calculation with steering (overrides tile-based)
func _get_direction_with_steering(from_position: Vector2, target_position: Vector2) -> Vector2:
	var steering_velocity = _calculate_steering(from_position, target_position)
	return steering_velocity.normalized()

## Phase 6: Calculate per-opponent power gaps for adaptive strategy
func _calculate_power_gaps(ai_player: Node2D) -> Dictionary:
	var my_power = _calculate_power_score(ai_player)
	var gaps: Dictionary = {}
	
	for player_id in opponent_profiles.keys():
		var profile: Dictionary = opponent_profiles[player_id]
		var opponent_power = profile.power_level
		gaps[player_id] = {
			"gap": opponent_power - my_power,
			"ratio": opponent_power / max(0.1, my_power),
			"advantage": my_power > opponent_power
		}
	
	return gaps

## Phase 6: Adjust utility weights based on power dynamics
func _apply_power_gap_biases(power_gaps: Dictionary) -> Dictionary:
	var avg_gap = 0.0
	var num_stronger = 0
	var num_weaker = 0
	
	for player_id in power_gaps:
		var gap_data = power_gaps[player_id]
		avg_gap += gap_data.gap
		if gap_data.gap > 1.0:
			num_stronger += 1
		elif gap_data.gap < -1.0:
			num_weaker += 1
	
	if power_gaps.size() > 0:
		avg_gap /= power_gaps.size()
	
	var weight_mods = {
		"item_focus": 1.0,
		"aggression": 1.0,
		"retreat": 1.0,
		"trap": 1.0
	}
	
	# Outmatched: prioritize items, reduce aggression
	if avg_gap > 2.0 or num_stronger >= 2:
		weight_mods.item_focus = 2.8
		weight_mods.aggression = 0.4
		weight_mods.retreat = 1.6
		weight_mods.trap = 0.7
	
	# Dominant: aggressive trapping
	elif avg_gap < -2.0 or num_weaker >= 2:
		weight_mods.item_focus = 0.6
		weight_mods.aggression = 2.5
		weight_mods.retreat = 0.5
		weight_mods.trap = 2.2
	
	# Roughly even: balanced
	else:
		weight_mods.item_focus = 1.2
		weight_mods.aggression = 1.4
		weight_mods.retreat = 1.0
		weight_mods.trap = 1.3
	
	return weight_mods

## Phase 6: Classify opponent behavior roles for targeted counter-play
func _classify_behavior_roles() -> void:
	for player_id in opponent_profiles.keys():
		var profile: Dictionary = opponent_profiles[player_id]
		
		# Initialize counters if needed
		if not profile.has("bomb_placements"):
			profile.bomb_placements = 0
			profile.item_pickups = 0
			profile.aggressive_moves = 0
			profile.observation_window = 0.0
		
		# Classify based on observed patterns
		var window_size = max(1.0, profile.observation_window)
		var bomb_rate = profile.bomb_placements / window_size
		var item_rate = profile.item_pickups / window_size
		var aggression_rate = profile.aggressive_moves / window_size
		
		var role = "balanced"
		var confidence = 0.0
		
		# Pressurer: high aggression, frequent bombs
		if aggression_rate > 2.0 and bomb_rate > 1.5:
			role = "pressurer"
			confidence = min(1.0, (aggression_rate + bomb_rate) / 5.0)
		
		# Trapper: strategic bomb placement, moderate aggression
		elif bomb_rate > 1.0 and aggression_rate < 1.5:
			role = "trapper"
			confidence = min(1.0, bomb_rate / 2.0)
		
		# Item-hog: focuses on pickups, avoids confrontation
		elif item_rate > 1.2 and aggression_rate < 0.8:
			role = "item_hog"
			confidence = min(1.0, item_rate / 2.0)
		
		profile.behavior_role = role
		profile.role_confidence = confidence

## Phase 6: Adjust scoring weights based on opponent roles
func _get_role_counter_weights(target_role: String) -> Dictionary:
	match target_role:
		"pressurer":
			return {
				"retreat_bonus": 1.8,
				"kite_bonus": 2.2,
				"trap_bonus": 1.5,
				"approach_penalty": 0.6
			}
		"trapper":
			return {
				"retreat_bonus": 1.3,
				"flank_bonus": 2.0,
				"item_priority": 1.4,
				"cautious_advance": 1.6
			}
		"item_hog":
			return {
				"item_priority": 2.5,
				"pressure_bonus": 2.0,
				"trap_bonus": 1.8,
				"retreat_penalty": 0.7
			}
		_:
			return {
				"retreat_bonus": 1.0,
				"flank_bonus": 1.0,
				"item_priority": 1.0,
				"trap_bonus": 1.0
			}
