extends Node
class_name ImprovedAIController

## Improved AI Controller with Intelligent Decision Making
## Uses DangerMapper, UtilityScorer, and BombPlanner for smart, safe gameplay
## NO MORE SUICIDES - AI always ensures escape routes exist

const Constants = preload("res://shared/constants.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")
const DangerMapper = preload("res://shared/ai/danger_mapper.gd")
const UtilityScorer = preload("res://shared/ai/utility_scorer.gd")
const BombPlanner = preload("res://shared/ai/bomb_planner.gd")
const AIDebugVisualizer = preload("res://shared/ai/ai_debug_visualizer.gd")

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
var decision_interval: float = 0.1  # Make decisions every 100ms
var current_action: Dictionary = {}
var current_path: Array = []
var path_update_interval: float = 0.3  # Replan path every 300ms
var last_path_update: float = 0.0

# Emergency state
var in_emergency: bool = false
var emergency_target: Vector2i = Vector2i(-1, -1)

# A* pathfinding
var astar: AStar2D
var tile_to_id: Dictionary = {}
var astar_initialized: bool = false
var last_astar_build: float = 0.0

func _init(game_instance: Node2D, personality: int = 0):
	var AIObserver_class = load("res://shared/ai/ai_observer.gd")
	observer = AIObserver_class.new(game_instance)
	
	personality_type = personality
	personality_weights = AIPersonality.get_weights(personality)
	
	# Initialize new AI systems
	danger_mapper = DangerMapper.new(game_instance, observer)
	utility_scorer = UtilityScorer.new(game_instance, observer, danger_mapper, personality_weights)
	bomb_planner = BombPlanner.new(game_instance, observer, danger_mapper, personality_weights)
	
	# Initialize A* for pathfinding
	astar = AStar2D.new()
	
	print("[ImprovedAI] Initialized with personality: ", AIPersonality.get_personality_name(personality))

## Main decision function
func decide_action(ai_player: Node2D) -> Dictionary:
	if ai_player == null or (ai_player.has_method("is_dead") and ai_player.is_dead):
		return {"direction": Vector2.ZERO, "place_bomb": false}
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var current_tile = ai_player.get_tile_position()
	
	# Update danger map
	danger_mapper.update(current_time)
	
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
	
	# Get best action
	var best_action = utility_scorer.get_best_action(action_scores)
	current_action = best_action
	
	# Convert action to movement
	var decision = _action_to_decision(best_action, ai_player, current_tile, current_time)
	
	# Update debug visualization
	if debug_visualizer != null:
		debug_visualizer.update_reasoning(decision.get("reasoning", "Unknown"))
		debug_visualizer.update_target(best_action.get("target_tile", Vector2i(-1, -1)))
		debug_visualizer.update_path(current_path)
	
	return decision

## Handle emergency escape (highest priority)
func _handle_emergency_escape(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	in_emergency = true
	
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
	
	if action_data.get("place_bomb", false):
		# Double-check safety before placing
		var safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
		if safety.safe:
			place_bomb = true
	
	# Get movement direction using pathfinding
	var target_tile = action_data.get("target_tile", null)
	var direction = Vector2.ZERO
	
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
func _calculate_astar_path(from_tile: Vector2i, to_tile: Vector2i, current_time: float) -> Array:
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
