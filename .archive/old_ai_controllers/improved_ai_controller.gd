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
var decision_interval: float = 0.2  # Increased from 0.1 to reduce direction changes
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
# Strategic pathfinding (includes soft blocks as expensive paths)
var astar_strategic: AStar2D
var tile_to_id_strategic: Dictionary = {}
var astar_strategic_initialized: bool = false

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

# Position tracking for stuck detection
var position_history: Array = []  # Store last N positions
var position_history_size: int = 10  # Track last 10 positions
var stuck_threshold: float = 32.0  # If all positions within this radius, we're stuck
var stuck_counter: int = 0  # How many frames we've been stuck
var stuck_replan_threshold: int = 20  # Force replan after this many stuck frames

# Unreachable target tracking
var failed_targets: Dictionary = {}  # tile_key -> {fail_count, last_fail_time}
var max_target_failures: int = 1  # Abandon target immediately on first failure
var failed_target_timeout: float = 3.0  # Forget failed targets after 3 seconds

const DANGER_SPIKE_THRESHOLD: float = 0.3  # Trigger replan if danger increases by this much

# Spawn clearing phase
var spawn_clearing_phase: bool = true  # Start in spawn clearing mode
var spawn_position: Vector2i = Vector2i(-1, -1)  # Remember where we spawned
var spawn_blocks_to_clear: Array = []  # Soft blocks near spawn
var spawn_clearing_complete: bool = false
var spawn_stuck_tile: Vector2i = Vector2i(-1, -1)  # Track if stuck at same tile
var spawn_stuck_frames: int = 0  # How many frames stuck at this tile
const SPAWN_STUCK_BOMB_THRESHOLD: int = 90  # Increased from 30 to 90 (1.5 seconds instead of 0.5)
var last_stuck_bomb_time: float = 0.0  # Last time we did a stuck-bomb
const STUCK_BOMB_COOLDOWN: float = 2.5  # Bomb every 2.5 seconds when stuck

# Startup safety delay
var startup_time: float = 0.0
const STARTUP_SAFETY_DELAY: float = 2.0  # Wait 2 seconds before allowing any bombs

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
	astar_strategic = AStar2D.new()

	print("[ImprovedAI] Initialized with personality: ", PersonalityResource.get_personality_name(personality))

## Main decision function - Saturn Bomberman Style State Machine
func decide_action(ai_player: Node2D) -> Dictionary:
	if ai_player == null or (ai_player.has_method("is_dead") and ai_player.is_dead):
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "NULL_OR_DEAD"}
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var current_tile = ai_player.get_tile_position()
	
	# Initialize startup time on first call
	if startup_time == 0.0:
		startup_time = current_time
		print("[ImprovedAI] Starting up at time ", current_time, " - bombs disabled for ", STARTUP_SAFETY_DELAY, "s")
	
	# STARTUP SAFETY: Don't allow ANY bombs during initial safety period
	var time_since_startup = current_time - startup_time
	var allow_bombs = time_since_startup >= STARTUP_SAFETY_DELAY
	
	if not allow_bombs and Engine.get_physics_frames() % 120 == 0:
		print("[ImprovedAI] Startup safety active: ", time_since_startup, "/", STARTUP_SAFETY_DELAY, "s")
	
	# Ensure core systems exist
	if observer == null or danger_mapper == null:
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "NO_SYSTEMS"}
	
	# STUCK DETECTION: Check if we're oscillating in a small area
	_check_stuck_condition(ai_player.position)
	
	# Update world perception
	latest_game_state = observer.get_world_state()
	danger_mapper.update(current_time)
	_update_dynamic_state(latest_game_state, ai_player, current_time)
	_check_replanning_triggers(current_tile, current_time)
	
	# Update utility scorer context
	utility_scorer.set_context({
		"opponent_profiles": opponent_profiles,
		"priority_targets": priority_targets,
		"aggression_bias": dynamic_aggression_bias,
		"item_focus_bias": dynamic_item_bias,
		"game_state": latest_game_state,
		"current_position": current_tile,
		"current_time": current_time
	})
	
	# ========================================
	# SATURN BOMBERMAN STATE MACHINE
	# Priority Order: Spawn Clearing > Survival > Hunting > Power-Ups > Wandering
	# ========================================
	
	# PRIORITY 0: SPAWN CLEARING (Startup Phase)
	# Clear immediate area around spawn before doing anything else
	if spawn_clearing_phase and not spawn_clearing_complete:
		var spawn_action = _state_clear_spawn_area(ai_player, current_tile, current_time)
		if spawn_action.has("complete") and spawn_action.complete:
			spawn_clearing_complete = true
			spawn_clearing_phase = false
			print("[ImprovedAI] Spawn clearing COMPLETE - switching to normal gameplay")
		# VALIDATE before returning (includes startup safety check)
		return _validate_and_fix_action(spawn_action, ai_player, current_tile, current_time)
	
	# PRIORITY 1: SURVIVAL (Evading Danger)
	# If on a danger tile, ONLY goal is to reach safety
	var current_danger = danger_mapper.get_danger_at_tile(current_tile, current_time, 0.0)
	var is_in_danger = danger_mapper.is_emergency_danger(current_tile, current_time) or current_danger > 0.5
	
	if is_in_danger:
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] EVADING DANGER - danger level: %.2f" % current_danger)
		var action = _validate_and_fix_action(_state_evade_danger(ai_player, current_tile, current_time), ai_player, current_tile, current_time)
		if not allow_bombs and action.get("place_bomb", false):
			action.place_bomb = false
			action.reasoning = "STARTUP_SAFETY_OVERRIDE"
		return action
	
	# PRIORITY 2: HUNTING (Trap Players)
	# If safe, target nearest player and try to trap them
	var nearest_player = _find_nearest_player(current_tile)
	if nearest_player.has("tile") and nearest_player.distance < 8:  # Within reasonable range
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] HUNTING PLAYER - target: ", nearest_player.tile, " dist: ", nearest_player.distance)
		var action = _validate_and_fix_action(_state_hunt_player(ai_player, current_tile, current_time, nearest_player), ai_player, current_tile, current_time)
		if not allow_bombs and action.get("place_bomb", false):
			action.place_bomb = false
			action.reasoning = "STARTUP_SAFETY_OVERRIDE"
		return action
	
	# PRIORITY 3: POWER-UPS (Collect Items)
	# If safe and no good hunting target, collect power-ups
	var nearest_powerup = _find_nearest_powerup(current_tile, current_time)
	if nearest_powerup.has("tile") and nearest_powerup.tile != Vector2i(-1, -1):
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] COLLECTING POWERUP - target: ", nearest_powerup.tile)
		return _validate_and_fix_action(_state_collect_powerup(ai_player, current_tile, current_time, nearest_powerup), ai_player, current_tile, current_time)
	
	# PRIORITY 4: WANDERING (Explore / Break Blocks)
	# Default behavior when nothing else to do
	if Engine.get_physics_frames() % 60 == 0:
		print("[AI-STATE] WANDERING")
	return _validate_and_fix_action(_state_wander(ai_player, current_tile, current_time), ai_player, current_tile, current_time)

# ========================================
# STATE HANDLERS (Saturn Bomberman Style)
# ========================================

## STATE 1: Evade Danger
## Find nearest safe tile and move there immediately
func _state_evade_danger(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# Use existing emergency escape system
	var escape_plan = bomb_planner.plan_emergency_escape(ai_player, current_time)
	
	if not escape_plan.emergency:
		# False alarm, not actually in danger
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "FALSE_ALARM"}
	
	var escape_tile = escape_plan.escape_tile
	var direction = _get_direction_to_tile(current_tile, escape_tile, ai_player.position, current_time)
	
	return {
		"direction": direction,
		"place_bomb": false,  # Never bomb while evading
		"reasoning": "EVADING_DANGER"
	}

## STATE 2: Hunt Player
## Move toward player and attempt to trap them with bombs
func _state_hunt_player(ai_player: Node2D, current_tile: Vector2i, current_time: float, target_info: Dictionary) -> Dictionary:
	var target_tile = target_info.tile
	var target_distance = target_info.distance
	
	# Check if this target has failed before - if so, skip to next state immediately
	if _is_target_failed(target_tile, current_time):
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] Player target unreachable, switching to POWERUP state")
		# Clear the failed target and try next priority
		var nearest_powerup = _find_nearest_powerup(current_tile, current_time)
		if nearest_powerup.has("tile") and nearest_powerup.tile != Vector2i(-1, -1):
			return _state_collect_powerup(ai_player, current_tile, current_time, nearest_powerup)
		else:
			return _state_wander(ai_player, current_tile, current_time)
	
	# Try pathfinding to target
	var direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
	
	# If pathfinding failed, mark and switch states immediately
	if direction.length() < 0.01:
		_mark_target_failed(target_tile, current_time)
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] Hunt pathfinding failed, switching to POWERUP state")
		# Don't try fallback, just switch states
		var nearest_powerup = _find_nearest_powerup(current_tile, current_time)
		if nearest_powerup.has("tile") and nearest_powerup.tile != Vector2i(-1, -1):
			return _state_collect_powerup(ai_player, current_tile, current_time, nearest_powerup)
		else:
			return _state_wander(ai_player, current_tile, current_time)
	
	# Decide whether to place a trap bomb
	var should_bomb = false
	
	# Offensive bombing logic (Saturn Bomberman style - more aggressive)
	if target_distance <= 4 and ai_player.can_place_bomb():  # Increased from 3 to 4
		# Check if bombing would trap the target
		var bomb_safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
		if bomb_safety.safe:
			# Check if bomb would affect target
			var bomb_blast_tiles = _get_bomb_blast_tiles(current_tile, ai_player.bomb_range)
			var targets_player = false
			for blast_tile in bomb_blast_tiles:
				if _manhattan_distance(blast_tile, target_tile) <= 1:
					targets_player = true
					break
			
			# More aggressive: bomb if target in range (removed random roll)
			if targets_player:
				should_bomb = true
	
	return {
		"direction": direction,
		"place_bomb": should_bomb,
		"reasoning": "HUNTING_PLAYER"
	}

## STATE 3: Collect Power-Up
## Move toward nearest valuable power-up
func _state_collect_powerup(ai_player: Node2D, current_tile: Vector2i, current_time: float, powerup_info: Dictionary) -> Dictionary:
	var powerup_tile = powerup_info.tile
	
	# Check if this target has failed before - if so, skip to wandering immediately
	if _is_target_failed(powerup_tile, current_time):
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] Powerup unreachable, switching to WANDER state")
		return _state_wander(ai_player, current_tile, current_time)
	
	# Try pathfinding to powerup
	var direction = _get_direction_to_tile(current_tile, powerup_tile, ai_player.position, current_time)
	
	# If pathfinding failed, mark and switch to wandering immediately
	if direction.length() < 0.01:
		_mark_target_failed(powerup_tile, current_time)
		if Engine.get_physics_frames() % 30 == 0:
			print("[AI-STATE] Powerup pathfinding failed, switching to WANDER state")
		# Don't try fallback, just wander
		return _state_wander(ai_player, current_tile, current_time)
	
	# Break blocks on the way if needed
	var should_bomb = false
	if ai_player.can_place_bomb():
		# Check if there's a block in our path or nearby
		var next_tile = current_tile + Vector2i(int(direction.x), int(direction.y))
		var has_obstacle = false
		if observer._is_tile_valid(next_tile) and not observer._is_tile_walkable(next_tile):
			has_obstacle = true
		# Also check adjacent tiles for obstacles worth clearing
		if not has_obstacle:
			for check_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				var check_tile = current_tile + check_dir
				if observer._is_tile_valid(check_tile) and not observer._is_tile_walkable(check_tile):
					# Is this a soft block?
					if check_tile.y >= 0 and check_tile.y < game_instance.game_map.size():
						if check_tile.x >= 0 and check_tile.x < game_instance.game_map[0].size():
							if game_instance.game_map[check_tile.y][check_tile.x] == 2:  # Soft block
								has_obstacle = true
								break
		if has_obstacle:
			var bomb_safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
			if bomb_safety.safe:
				should_bomb = true
	
	return {
		"direction": direction,
		"place_bomb": should_bomb,
		"reasoning": "COLLECTING_POWERUP"
	}

## STATE 4: Wander
## Explore map, break blocks, move toward center
func _state_wander(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# First, try to find valid walkable directions
	var valid_directions = []
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var test_tile = current_tile + dir
		if observer._is_tile_valid(test_tile) and observer._is_tile_walkable(test_tile):
			var danger = danger_mapper.get_danger_at_tile(test_tile, current_time, 1.0)
			if danger < 0.5:  # Not too dangerous
				valid_directions.append(dir)
	
	# If trapped (no valid directions), try to break out with a bomb
	if valid_directions.is_empty():
		if ai_player.can_place_bomb():
			return {
				"direction": Vector2.ZERO,
				"place_bomb": true,
				"reasoning": "WANDERING_TRAPPED_BREAKING_OUT"
			}
		else:
			return _emergency_fallback(ai_player, current_tile, current_time)
	
	# Use exploration scoring to pick best direction
	var explore_score = utility_scorer.score_explore_map(current_tile, current_time)
	
	if explore_score.get("score", 0.0) > 0 and explore_score.has("target_tile"):
		var target_tile = explore_score.target_tile
		var direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
		
		# If pathfinding failed, pick a random valid direction (prioritize unexplored)
		if direction.length() < 0.01:
			# Shuffle for randomness
			valid_directions.shuffle()
			direction = Vector2(valid_directions[0])
			if Engine.get_physics_frames() % 30 == 0:
				print("[AI-STATE] Wander pathfinding failed, picking random valid direction: ", direction)
		
		# Occasionally break blocks while wandering (reduced to let bots explore more)
		var should_bomb = false
		if ai_player.can_place_bomb():
			# If stuck in corner (many blocked tiles nearby), bomb more aggressively
			var blocked_count = 0
			for check_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				var check_tile = current_tile + check_dir
				if not observer._is_tile_walkable(check_tile):
					blocked_count += 1
			
			# More aggressive bombing if surrounded (trapped in corner)
			var bomb_chance = 0.20  # REDUCED from 40% to 20% to let bots explore more
			
			if blocked_count >= 2:
				bomb_chance = 0.5  # Increased chance if trapped (reduced from 70% to 50%)
			
			if randf() < bomb_chance:
				var bomb_safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
				if Engine.get_physics_frames() % 60 == 0:
					print("[AI-WANDER-BOMB] Checking safety at ", current_tile, " blocked:", blocked_count, " safe:", bomb_safety.safe, " reason:", bomb_safety.get("reason", "unknown"))
				if bomb_safety.safe:
					should_bomb = true
					if Engine.get_physics_frames() % 60 == 0:
						print("[AI-WANDER-BOMB] Placing exploration bomb! (blocked:", blocked_count, ")")
		
		return {
			"direction": direction,
			"place_bomb": should_bomb,
			"reasoning": "WANDERING_EXPLORE"
		}
	
	# Fallback: pick a random valid direction
	valid_directions.shuffle()
	var random_dir = Vector2(valid_directions[0])
	return {
		"direction": random_dir,
		"place_bomb": false,
		"reasoning": "WANDERING_RANDOM"
	}

## STATE 0: Clear Spawn Area (Startup Phase) - STRATEGIC VERSION
## Plan bombing positions with escape routes, execute carefully
func _state_clear_spawn_area(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# Initialize spawn position on first call
	if spawn_position == Vector2i(-1, -1):
		spawn_position = current_tile
		print("[ImprovedAI-SPAWN] Starting STRATEGIC spawn clearing at ", spawn_position)
	
	# STEP 1: Check for immediate danger - ALWAYS prioritize survival FIRST
	var current_danger = danger_mapper.get_danger_at_tile(current_tile, current_time, 0.0)
	if current_danger > 0.3:
		print("[ImprovedAI-SPAWN] DANGER! Evading...")
		var safe_tiles = danger_mapper.find_nearest_safe_tiles(current_tile, current_time, 8)
		if not safe_tiles.is_empty():
			var safe_tile = safe_tiles[0].tile
			var direction = _get_direction_to_tile(current_tile, safe_tile, ai_player.position, current_time)
			return {"direction": direction, "place_bomb": false, "reasoning": "SPAWN_CLEAR_EVADE"}
		else:
			# No safe tiles found, try any walkable direction
			for try_dir in [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT]:
				var try_tile = current_tile + Vector2i(int(try_dir.x), int(try_dir.y))
				if observer._is_tile_valid(try_tile) and observer._is_tile_walkable(try_tile):
					return {"direction": try_dir, "place_bomb": false, "reasoning": "SPAWN_CLEAR_PANIC"}
			# Completely trapped
			return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "SPAWN_CLEAR_TRAPPED"}
	
	# STEP 2: Find best bombing position near spawn
	# Look for tiles adjacent to soft blocks + next to hard walls (safe corner positions)
	var best_bomb_position = _find_strategic_bomb_position(current_tile, spawn_position)
	
	# STEP 2.5: SIMPLIFIED APPROACH - Try bombing from current position first
	# This prevents endless pathfinding to unreachable positions
	var current_eval = _evaluate_bomb_position(current_tile, current_tile)
	if current_eval.score > 0 and ai_player.can_place_bomb():
		# Current position hits blocks! Try to bomb here
		var bomb_safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
		var time_since_startup = current_time - startup_time
		var in_startup_safety = time_since_startup < STARTUP_SAFETY_DELAY
		
		if bomb_safety.safe or (in_startup_safety and not bomb_safety.get("reason", "").contains("No bombs")):
			if in_startup_safety and not bomb_safety.safe:
				print("[ImprovedAI-SPAWN] Startup override: bombing from current position ", current_tile, " (hits ", current_eval.blocks_hit.size(), " blocks)")
			else:
				print("[ImprovedAI-SPAWN] Safe bomb from current position ", current_tile, " (hits ", current_eval.blocks_hit.size(), " blocks)")
			return {"direction": Vector2.ZERO, "place_bomb": true, "reasoning": "SPAWN_CLEAR_BOMB_HERE"}
	
	# STEP 3: Check if we're done clearing spawn area OR no good positions found
	if best_bomb_position == null or best_bomb_position.is_empty() or best_bomb_position.get("score", -1000) < 0:
		# No good positions - spawn clearing complete!
		print("[ImprovedAI-SPAWN] No more strategic bomb positions - spawn clearing COMPLETE!")
		return {"direction": Vector2.ZERO, "place_bomb": false, "complete": true, "reasoning": "SPAWN_CLEAR_COMPLETE"}
	
	var target_tile = best_bomb_position.position
	var blocks_hit = best_bomb_position.blocks_hit
	var escape_route = best_bomb_position.escape_tile
	
	# STEP 4: Are we at the bombing position?
	if current_tile == target_tile:
		# YES! But double-check safety before executing
		if ai_player.can_place_bomb():
			var bomb_safety = bomb_planner.can_place_bomb_safely(current_tile, ai_player, current_time)
			# During spawn clearing, be more aggressive since startup safety provides backup
			var time_since_startup = current_time - startup_time
			var in_startup_safety = time_since_startup < STARTUP_SAFETY_DELAY
			
			if bomb_safety.safe or (in_startup_safety and not bomb_safety.get("reason", "").contains("No bombs")):
				# Either it's safe OR we're in startup period and have bombs available
				if in_startup_safety and not bomb_safety.safe:
					print("[ImprovedAI-SPAWN] Startup override: bombing anyway at ", target_tile, " (protected by startup delay)")
				else:
					print("[ImprovedAI-SPAWN] EXECUTING PLAN: Bombing from ", target_tile, " hitting ", blocks_hit.size(), " blocks, escape to ", escape_route)
				return {"direction": Vector2.ZERO, "place_bomb": true, "reasoning": "SPAWN_CLEAR_EXECUTE"}
			else:
				print("[ImprovedAI-SPAWN] ABORT: Position ", target_tile, " unsafe - reason: ", bomb_safety.get("reason", "unknown"))
				_mark_target_failed(target_tile, current_time)
				return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "SPAWN_CLEAR_ABORT"}
		else:
			# Waiting for bomb cooldown
			print("[ImprovedAI-SPAWN] At position, waiting for bomb...")
			return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "SPAWN_CLEAR_WAIT"}
	
	# STEP 5: Move to the strategic bombing position
	var direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
	if direction.length() < 0.01:
		# Regular pathfinding failed - try STRATEGIC pathfinding that can see through soft blocks
		_ensure_astar_ready(current_time)  # Ensures both graphs are built
		var strategic_path = _calculate_strategic_path(current_tile, target_tile, current_time)
		
		if not strategic_path.is_empty():
			# Strategic path found! Check if NEXT tile (in path direction) is a soft block
			var first_waypoint = strategic_path[0]
			var direction_to_waypoint = (first_waypoint - ai_player.position).normalized()
			
			# Determine next tile in CARDINAL direction (no diagonals)
			var next_tile = current_tile
			if abs(direction_to_waypoint.x) > abs(direction_to_waypoint.y):
				next_tile = current_tile + Vector2i(int(sign(direction_to_waypoint.x)), 0)
			else:
				next_tile = current_tile + Vector2i(0, int(sign(direction_to_waypoint.y)))
			
			# Is the next tile a soft block we need to destroy?
			var game_state = observer.get_world_state()
			var map = game_state.get("map", [])
			if not map.is_empty() and next_tile.y >= 0 and next_tile.y < map.size() and next_tile.x >= 0 and next_tile.x < map[next_tile.y].size():
				var tile_type = map[next_tile.y][next_tile.x]
				if Engine.get_physics_frames() % 60 == 0:
					print("[ImprovedAI-SPAWN] Strategic path: current=", current_tile, " next=", next_tile, " type=", tile_type, " waypoint=", first_waypoint)
				
				if tile_type == 2:  # Soft block blocking our path!
					# Bomb it if we can
					if ai_player.can_place_bomb():
						print("[ImprovedAI-SPAWN] Soft block at ", next_tile, " blocking path to ", target_tile, " - BOMBING!")
						return {"direction": Vector2.ZERO, "place_bomb": true, "reasoning": "SPAWN_CLEAR_PATH_BOMB"}
					else:
						if Engine.get_physics_frames() % 60 == 0:
							print("[ImprovedAI-SPAWN] Waiting for bomb to clear path at ", next_tile)
						return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "SPAWN_CLEAR_PATH_WAIT"}
			
			# Not a soft block - we can move toward it
			direction = direction_to_waypoint
			if Engine.get_physics_frames() % 60 == 0:
				print("[ImprovedAI-SPAWN] Using strategic path, moving toward ", next_tile)
		else:
			# Even strategic pathfinding failed - this position is truly unreachable
			_mark_target_failed(target_tile, current_time)
			if Engine.get_physics_frames() % 60 == 0:
				print("[ImprovedAI-SPAWN] Position ", target_tile, " unreachable even strategically")
			# Try cardinal direction as last resort
			var delta = target_tile - current_tile
			if abs(delta.x) > abs(delta.y):
				direction = Vector2(sign(delta.x), 0)
			else:
				direction = Vector2(0, sign(delta.y))
	
	if Engine.get_physics_frames() % 60 == 0:
		print("[ImprovedAI-SPAWN] Moving to strategic position ", target_tile, " (will hit ", blocks_hit.size(), " blocks)")
	
	return {"direction": direction, "place_bomb": false, "reasoning": "SPAWN_CLEAR_APPROACH"}

## Find best strategic bomb position for spawn clearing
## Returns: {position: Vector2i, blocks_hit: Array, escape_tile: Vector2i, score: float} or empty dict
func _find_strategic_bomb_position(current_tile: Vector2i, spawn_tile: Vector2i) -> Dictionary:
	var best_position = {}
	var best_score = -1000
	var positions_checked = 0
	
	# Search 4-tile radius around spawn for bombing positions
	for dy in range(-4, 5):
		for dx in range(-4, 5):
			var candidate = spawn_tile + Vector2i(dx, dy)
			
			# Must be valid and walkable
			if not observer._is_tile_valid(candidate) or not observer._is_tile_walkable(candidate):
				continue
			
			# Skip if we've already failed to reach this position
			if _is_target_failed(candidate, 0):
				continue
			
			positions_checked += 1
			
			# Evaluate this position
			var eval = _evaluate_bomb_position(candidate, current_tile)
			if eval.score > best_score:
				best_score = eval.score
				best_position = eval
	
	if positions_checked > 0:
		print("[ImprovedAI-SPAWN] Evaluated ", positions_checked, " positions, best score: ", best_score, " hits ", best_position.get("blocks_hit", []).size(), " blocks")
	
	return best_position

## Evaluate a tile as a bombing position
func _evaluate_bomb_position(tile: Vector2i, current_pos: Vector2i) -> Dictionary:
	var score = 0.0
	var blocks_hit = []
	var has_escape = false
	var escape_tile = Vector2i(-1, -1)
	
	# Check all 4 directions for soft blocks in bomb range
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for dist in range(1, 4):  # Bomb range (typically 2-3, check up to 3)
			var check_tile = tile + (dir * dist)
			if not observer._is_tile_valid(check_tile):
				break
			
			# Hit a hard wall - stop checking this direction
			if check_tile.y >= 0 and check_tile.y < game_instance.game_map.size():
				if check_tile.x >= 0 and check_tile.x < game_instance.game_map[0].size():
					var tile_type = game_instance.game_map[check_tile.y][check_tile.x]
					if tile_type == 1:  # Hard wall
						break
					elif tile_type == 2:  # Soft block - TARGET!
						blocks_hit.append(check_tile)
						score += 10.0  # Value per block
						break  # Can't hit blocks behind this one
	
	# Must hit at least one block to be useful
	if blocks_hit.is_empty():
		return {"position": tile, "score": -1000, "blocks_hit": [], "escape_tile": Vector2i(-1, -1)}
	
	# Check for escape routes (tiles we can run to after bombing)
	for escape_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var escape_check = tile + escape_dir
		if observer._is_tile_valid(escape_check) and observer._is_tile_walkable(escape_check):
			# During spawn clearing, any walkable adjacent tile is good enough
			# (we'll handle danger evasion separately if needed)
			has_escape = true
			escape_tile = escape_check
			score += 20.0  # Bonus for having escape
			break
	
	# Penalty for distance from current position (prefer closer positions)
	var distance = _manhattan_distance(tile, current_pos)
	score -= distance * 2.0
	
	# Bonus for being next to hard walls (safer corner positions)
	var wall_count = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check = tile + dir
		if not observer._is_tile_walkable(check):
			wall_count += 1
	score += wall_count * 5.0
	
	# Must have escape route
	if not has_escape:
		score = -500
	
	return {
		"position": tile,
		"score": score,
		"blocks_hit": blocks_hit,
		"escape_tile": escape_tile
	}

# ========================================
# HELPER FUNCTIONS FOR STATE MACHINE
# ========================================

## Find nearest player for hunting
func _find_nearest_player(current_tile: Vector2i) -> Dictionary:
	if not latest_game_state.has("players"):
		return {}
	
	var nearest_distance = INF
	var nearest_tile = Vector2i(-1, -1)
	var nearest_player = null
	
	# latest_game_state.players is a Dictionary (peer_id -> ServerPlayer object)
	for peer_id in latest_game_state.players:
		var player_data = latest_game_state.players[peer_id]
		if not is_instance_valid(player_data):
			continue
		if player_data.has_method("is_dead") and player_data.is_dead:
			continue
		var player_tile = player_data.get_tile_position()
		var distance = _manhattan_distance(current_tile, player_tile)
		
		if distance < nearest_distance:
			nearest_distance = distance
			nearest_tile = player_tile
			nearest_player = player_data
	
	if nearest_tile == Vector2i(-1, -1):
		return {}
	
	return {
		"tile": nearest_tile,
		"distance": nearest_distance,
		"player_data": nearest_player
	}

## Find nearest power-up for collection
func _find_nearest_powerup(current_tile: Vector2i, current_time: float) -> Dictionary:
	var powerup_weights = personality_weights.get("powerup_utility_weights", {
		"max_bombs": 600.0,
		"explosion_range": 600.0,
		"speed": 600.0,
		"bomb_kicker": 400.0,
		"power_glove": 400.0
	})
	
	var best_powerup = observer.find_valuable_powerup(current_tile, powerup_weights)
	
	if best_powerup.tile == Vector2i(-1, -1):
		return {}
	
	# Check if path is dangerous
	var path_danger = danger_mapper.get_danger_at_tile(best_powerup.tile, current_time, 1.0)
	if path_danger > 0.6:
		return {}  # Too dangerous
	
	return {
		"tile": best_powerup.tile,
		"distance": best_powerup.distance,
		"value": best_powerup.value,
		"type": best_powerup.type
	}

## Calculate tiles affected by a bomb blast
func _get_bomb_blast_tiles(bomb_tile: Vector2i, blast_range: int) -> Array:
	var blast_tiles = [bomb_tile]
	
	# Add tiles in 4 directions
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for dist in range(1, blast_range + 1):
			var test_tile = bomb_tile + dir * dist
			if not observer._is_tile_valid(test_tile):
				break
			blast_tiles.append(test_tile)
			if not observer._is_tile_walkable(test_tile):
				break  # Wall blocks blast
	
	return blast_tiles

## Calculate Manhattan distance between two tiles
func _manhattan_distance(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)

## Mark a target as failed/unreachable
func _mark_target_failed(target_tile: Vector2i, current_time: float):
	var key = "%d,%d" % [target_tile.x, target_tile.y]
	if not failed_targets.has(key):
		failed_targets[key] = {"fail_count": 0, "last_fail_time": current_time}
	failed_targets[key].fail_count += 1
	failed_targets[key].last_fail_time = current_time
	if Engine.get_physics_frames() % 30 == 0:
		print("[AI-TARGET] Marked ", target_tile, " as failed (", failed_targets[key].fail_count, "/", max_target_failures, ")")

## Check if target should be abandoned
func _is_target_failed(target_tile: Vector2i, current_time: float) -> bool:
	var key = "%d,%d" % [target_tile.x, target_tile.y]
	if not failed_targets.has(key):
		return false
	var data = failed_targets[key]
	# Forget old failures
	if current_time - data.last_fail_time > failed_target_timeout:
		failed_targets.erase(key)
		return false
	return data.fail_count >= max_target_failures

## Get simple fallback direction toward target (ignores obstacles)
func _get_fallback_direction(from_tile: Vector2i, to_tile: Vector2i) -> Vector2:
	var dx = to_tile.x - from_tile.x
	var dy = to_tile.y - from_tile.y
	if abs(dx) > abs(dy):
		return Vector2(sign(dx), 0) if dx != 0 else Vector2(0, sign(dy)) if dy != 0 else Vector2.DOWN
	else:
		return Vector2(0, sign(dy)) if dy != 0 else Vector2(sign(dx), 0) if dx != 0 else Vector2.DOWN

# ========================================
# LEGACY METHODS (Keep for compatibility but unused in new state machine)
# ========================================

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
		print("[ImprovedAI] _execute_current_action called with EMPTY action! Forcing replan.")
		force_replan = true
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "EMPTY_ACTION"}
	
	# Phase 1: Check if we should replan (log it if so)
	if debug_enabled and (current_time - last_decision_time) >= decision_interval:
		debug_replanning_count += 1
	
	# Follow current path
	var target_tile = current_action.get("target_tile", null)
	var direction = Vector2.ZERO
	
	if target_tile != null and target_tile != Vector2i(-1, -1):
		direction = _get_direction_to_tile(current_tile, target_tile, ai_player.position, current_time)
		if direction.length() < 0.01:
			print("[ImprovedAI] _get_direction_to_tile returned ZERO! From: ", current_tile, " To: ", target_tile)
			force_replan = true
	
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
		if Engine.get_physics_frames() % 60 == 0:
			print("[ImprovedAI] A* path from ", from_tile, " to ", to_tile, ": ", current_path.size(), " waypoints")
	
	# Follow path
	if current_path.is_empty():
		# No path found - this is a pathfinding failure
		# Return ZERO to trigger failed target tracking in state handlers
		if Engine.get_physics_frames() % 60 == 0:
			print("[ImprovedAI] No A* path from ", from_tile, " to ", to_tile, " - returning ZERO")
		return Vector2.ZERO
	
	# Get next waypoint
	var next_waypoint = current_path[0]
	
	# Calculate direction to next waypoint, prioritizing cardinal movement
	var delta = next_waypoint - from_position
	var direction = Vector2.ZERO
	
	if abs(delta.x) > abs(delta.y):
		# Dominant movement is horizontal
		direction.x = sign(delta.x)
	else:
		# Dominant movement is vertical
		direction.y = sign(delta.y)
	
	# If both are zero (e.g., already at waypoint), try to move towards it anyway
	if direction == Vector2.ZERO and delta.length() > 0.1:
		if abs(delta.x) > 0:
			direction.x = sign(delta.x)
		elif abs(delta.y) > 0:
			direction.y = sign(delta.y)
	
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

## Calculate STRATEGIC A* path that includes soft blocks as expensive but traversable
## Returns: Array of Vector2 waypoints, may include soft block positions that need to be bombed
func _calculate_strategic_path(from_tile: Vector2i, to_tile: Vector2i, _current_time: float) -> Array:
	var from_key = "%d,%d" % [from_tile.x, from_tile.y]
	var to_key = "%d,%d" % [to_tile.x, to_tile.y]
	
	if not tile_to_id_strategic.has(from_key) or not tile_to_id_strategic.has(to_key):
		return []
	
	var from_id = tile_to_id_strategic[from_key]
	var to_id = tile_to_id_strategic[to_key]
	
	# Get strategic path (may go through soft blocks)
	var path_points = astar_strategic.get_point_path(from_id, to_id)
	
	# Convert to waypoints
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
	astar_strategic.clear()
	tile_to_id_strategic.clear()
	
	var map = game_state.get("map", [])
	if map.is_empty():
		return
	
	var point_id = 0
	var strategic_point_id = 0
	
	# Build both graphs simultaneously
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]
			var tile_center = Vector2(
				x * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
				y * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
			)
			
			# Regular graph: only truly walkable tiles
			if observer._is_tile_walkable(tile):
				tile_to_id[tile_key] = point_id
				astar.add_point(point_id, tile_center)
				point_id += 1
			
			# Strategic graph: include soft blocks as expensive paths
			var tile_type = map[y][x]
			if tile_type != 1:  # Not a hard wall
				# Check for bombs (still block strategic paths)
				var has_bomb = false
				for bomb_id in game_instance.bombs:
					var bomb = game_instance.bombs[bomb_id]
					if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
						has_bomb = true
						break
				
				if not has_bomb:
					tile_to_id_strategic[tile_key] = strategic_point_id
					astar_strategic.add_point(strategic_point_id, tile_center)
					strategic_point_id += 1
	
	# Connect adjacent tiles with danger-aware weights
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]
			
			# Connect regular graph
			if tile_to_id.has(tile_key):
				var from_id = tile_to_id[tile_key]
				
				for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
					var neighbor = tile + dir
					var neighbor_key = "%d,%d" % [neighbor.x, neighbor.y]
					
					if not tile_to_id.has(neighbor_key):
						continue
					
					var to_id = tile_to_id[neighbor_key]
					var danger = danger_mapper.get_danger_at_tile(neighbor, current_time, 1.0)
					var weight = 1.0
					
					if danger > 0.7:
						weight = 100.0
					elif danger > 0.3:
						weight = 10.0
					
					astar.connect_points(from_id, to_id, true)
					astar.set_point_weight_scale(to_id, weight)
			
			# Connect strategic graph with soft block penalties
			if tile_to_id_strategic.has(tile_key):
				var from_id_s = tile_to_id_strategic[tile_key]
				var tile_type = map[y][x]
				
				for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
					var neighbor = tile + dir
					var neighbor_key = "%d,%d" % [neighbor.x, neighbor.y]
					
					if not tile_to_id_strategic.has(neighbor_key):
						continue
					
					var to_id_s = tile_to_id_strategic[neighbor_key]
					var neighbor_type = map[neighbor.y][neighbor.x]
					
					# Base weight: soft blocks are expensive but traversable
					var weight = 1.0
					if tile_type == 2:  # Current tile is soft block
						weight = 50.0  # Very expensive to "path through" soft blocks
					if neighbor_type == 2:  # Neighbor is soft block
						weight = max(weight, 50.0)
					
					# Danger still matters
					var danger = danger_mapper.get_danger_at_tile(neighbor, current_time, 1.0)
					if danger > 0.7:
						weight = 1000.0  # Never path through high danger
					elif danger > 0.3:
						weight = max(weight, 100.0)
					
					astar_strategic.connect_points(from_id_s, to_id_s, true)
					astar_strategic.set_point_weight_scale(to_id_s, weight)
	
	astar_strategic_initialized = true

## Emergency fallback when no good actions
func _emergency_fallback(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# Try to find any safe tile
	var safe_tiles = danger_mapper.find_nearest_safe_tiles(current_tile, current_time, 8)
	
	if not safe_tiles.is_empty():
		var safe_tile = safe_tiles[0].tile
		var direction = _get_direction_to_tile(current_tile, safe_tile, ai_player.position, current_time)
		
		print("[ImprovedAI] FALLBACK_SAFETY: From ", current_tile, " to ", safe_tile, " dir: ", direction)
		
		return {
			"direction": direction,
			"place_bomb": false,
			"reasoning": "FALLBACK_SAFETY"
		}
	
	# Last resort: try each cardinal direction and pick first walkable one
	var directions = [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT]
	directions.shuffle()
	
	for dir in directions:
		var test_tile = current_tile + Vector2i(int(dir.x), int(dir.y))
		if observer._is_tile_valid(test_tile) and observer._is_tile_walkable(test_tile):
			print("[ImprovedAI] RANDOM_WALKABLE: Chose ", dir, " to ", test_tile)
			return {
				"direction": dir,
				"place_bomb": false,
				"reasoning": "RANDOM_WALKABLE"
			}
	
	print("[ImprovedAI] EMERGENCY: NO WALKABLE DIRECTIONS! Stuck at ", current_tile)
	return {
		"direction": Vector2.ZERO,
		"place_bomb": false,
		"reasoning": "STUCK"
	}

## Check if AI is stuck (oscillating in small area)
func _check_stuck_condition(current_position: Vector2) -> void:
	# Add current position to history
	position_history.append(current_position)
	
	# Keep only recent history
	if position_history.size() > position_history_size:
		position_history.pop_front()
	
	# Need enough history to determine if stuck
	if position_history.size() < position_history_size:
		return
	
	# Calculate if all positions are within stuck_threshold radius
	var center = Vector2.ZERO
	for pos in position_history:
		center += pos
	center /= position_history.size()
	
	var max_dist = 0.0
	for pos in position_history:
		var dist = center.distance_to(pos)
		if dist > max_dist:
			max_dist = dist
	
	# If all positions are close together, we're stuck
	if max_dist < stuck_threshold:
		stuck_counter += 1
		if stuck_counter >= stuck_replan_threshold:
			print("[ImprovedAI] STUCK DETECTED! Oscillating in %.1fpx radius for %d frames - FORCING RANDOM WALK" % [max_dist, stuck_counter])
			# Force a completely random direction to break out of stuck state
			var random_directions = [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
			random_directions.shuffle()
			current_action = {
				"direction": Vector2(random_directions[0]),
				"place_bomb": false,
				"reasoning": "STUCK_RANDOM_WALK"
			}
			current_path = []
			force_replan = true
			stuck_counter = 0
			position_history.clear()
	else:
		# Moving freely, reset counter
		stuck_counter = 0

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
	var _my_power = _calculate_power_score(ai_player)
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

## Validate that the AI's chosen action won't immediately collide
## If it will, try to find an alternative safe direction
func _validate_and_fix_action(action: Dictionary, ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	# STARTUP SAFETY ENFORCEMENT: Block ALL bombs during initial safety period
	var time_since_startup = current_time - startup_time
	if time_since_startup < STARTUP_SAFETY_DELAY and action.get("place_bomb", false):
		action = action.duplicate()  # Don't modify original dict
		action.place_bomb = false
		if Engine.get_physics_frames() % 60 == 0:
			print("[ImprovedAI] STARTUP SAFETY: Blocking bomb (", time_since_startup, "/", STARTUP_SAFETY_DELAY, "s)")
	
	# If not moving, no need to validate
	var direction = action.get("direction", Vector2.ZERO)
	if direction.length() < 0.01:
		return action
	
	# Determine next tile in CARDINAL direction (no diagonals)
	var next_tile = current_tile
	if abs(direction.x) > abs(direction.y):
		next_tile = current_tile + Vector2i(int(sign(direction.x)), 0)
	else:
		next_tile = current_tile + Vector2i(0, int(sign(direction.y)))
	
	# Check if next tile is walkable
	if observer._is_tile_valid(next_tile) and observer._is_tile_walkable(next_tile):
		# Good to go!
		return action
	
	# Next tile is blocked! Try to find alternative
	if Engine.get_physics_frames() % 60 == 0:
		print("[ImprovedAI-VALIDATE] Next tile ", next_tile, " blocked, finding alternative...")
	
	# Try perpendicular directions (corner sliding)
	var perpendicular_dirs = []
	if abs(direction.x) > abs(direction.y):
		# Was trying to move horizontally, try vertical
		perpendicular_dirs = [Vector2(0, -1), Vector2(0, 1)]
	else:
		# Was trying to move vertically, try horizontal
		perpendicular_dirs = [Vector2(-1, 0), Vector2(1, 0)]
	
	for perp_dir in perpendicular_dirs:
		var perp_tile = current_tile + Vector2i(int(perp_dir.x), int(perp_dir.y))
		if observer._is_tile_valid(perp_tile) and observer._is_tile_walkable(perp_tile):
			# Found walkable perpendicular direction!
			if Engine.get_physics_frames() % 60 == 0:
				print("[ImprovedAI-VALIDATE] Using perpendicular direction to ", perp_tile)
			action.direction = perp_dir
			return action
	
	# Can't move in any direction - stand still
	if Engine.get_physics_frames() % 60 == 0:
		print("[ImprovedAI-VALIDATE] All directions blocked, standing still")
	action.direction = Vector2.ZERO
	return action
