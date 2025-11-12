extends Node
class_name UnifiedAIController

## Unified AI Controller - Best of Both Worlds
## Combines ImprovedAI's safety systems with OriginalAI's strategic depth
## Architecture: Emergency Override → ML Systems → State Machine → Behavior Trees → Utility Layer

const Constants = preload("res://shared/constants.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")

# Safety Layer (from ImprovedAI)
const DangerMapperClass = preload("res://shared/ai/danger_mapper.gd")
const BombPlannerClass = preload("res://shared/ai/bomb_planner.gd")
const AIObserverClass = preload("res://shared/ai/ai_observer.gd")

# Strategic Layer (from OriginalAI)
const BehaviorTree = preload("res://shared/ai/behavior_tree.gd")

# ML Layer (from OriginalAI)
const AIQLearningClass = preload("res://shared/ai/ai_q_learning.gd")
const AIMCTSClass = preload("res://shared/ai/ai_mcts.gd")

# Debug Layer (from ImprovedAI)
const DebugVisualizerClass = preload("res://shared/ai/ai_debug_visualizer.gd")

# ============================================================================
# STATE MACHINE (from OriginalAI)
# ============================================================================
enum State {
	EXPLORING,      # Default: looking for blocks/power-ups
	HUNTING,        # Chasing a specific opponent
	CORNERING,      # Opponent trapped, setting up kill
	ESCAPING,       # In danger, running to safety
	AMBUSHING,      # Waiting at strategic choke point
	POWER_UP_RUSH   # Racing to grab power-up
}

var current_state: State = State.EXPLORING
var state_timer: float = 0.0
var state_entry_time: float = 0.0

# State-specific data
var hunt_target: Node2D = null
var hunt_target_tile: Vector2i = Vector2i(-1, -1)
var ambush_position: Vector2i = Vector2i(-1, -1)

# ============================================================================
# CORE SYSTEMS
# ============================================================================
var game_instance: Node2D
var observer
var danger_mapper
var bomb_planner
var debug_visualizer

# Configuration
var personality_type: int
var personality_weights: Dictionary

# Phase 4: Team coordination
var team_id: int = -1  # -1 = free-for-all, 0+ = team number
var teammates: Array = []  # List of teammate player IDs

# Behavior Trees per state
var explore_tree: BehaviorTree.BTNode
var hunt_tree: BehaviorTree.BTNode
var corner_tree: BehaviorTree.BTNode
var escape_tree: BehaviorTree.BTNode
var ambush_tree: BehaviorTree.BTNode
var powerup_rush_tree: BehaviorTree.BTNode

# ML Systems (optional, based on personality)
var q_learning = null
var mcts = null

# Decision state
var last_decision_time: float = 0.0
var decision_interval: float = 0.1
var last_reaction_time: float = 0.0

# Pathfinding
var astar: AStar2D
var tile_to_id: Dictionary = {}
var astar_initialized: bool = false
var current_path: Array = []
var last_path_update: float = 0.0
var path_update_interval: float = 0.3

# Position tracking for stuck detection
var stuck_counter: int = 0
var last_position: Vector2i = Vector2i(-1, -1)

# Spawn clearing phase
var spawn_clearing_phase: bool = true
var spawn_position: Vector2i = Vector2i(-1, -1)
var spawn_blocks_cleared: int = 0
var spawn_clearing_complete: bool = false

# ============================================================================
# INITIALIZATION
# ============================================================================

func _init(game_inst: Node2D, personality: int = 0, difficulty: int = AIPersonality.Difficulty.NORMAL):
	game_instance = game_inst
	personality_type = personality
	
	# Phase 4: Apply difficulty scaling
	var base_weights = AIPersonality.get_weights(personality)
	personality_weights = AIPersonality.apply_difficulty_modifier(base_weights, difficulty)
	
	# Initialize safety systems
	observer = AIObserverClass.new(game_instance)
	danger_mapper = DangerMapperClass.new()
	bomb_planner = BombPlannerClass.new()
	
	# Initialize pathfinding
	astar = AStar2D.new()
	
	# Initialize behavior trees
	build_behavior_trees()
	
	# Initialize ML systems if personality requires them
	if personality_weights.get("use_q_learning", false):
		q_learning = AIQLearningClass.new()
		q_learning.load_q_table()
		print("[UnifiedAI] Q-Learning enabled for LEARNED personality")
	
	if personality_weights.get("use_mcts", false):
		mcts = AIMCTSClass.new(self, observer)
		print("[UnifiedAI] MCTS enabled for PERFECT personality")
	
	var difficulty_name = AIPersonality.get_difficulty_name(difficulty)
	print("[UnifiedAI] Initialized: ", AIPersonality.get_name(personality), " (", difficulty_name, " difficulty)")

# ============================================================================
# MAIN DECISION SYSTEM
# ============================================================================

func decide_action(ai_player: Node2D) -> Dictionary:
	"""
	Main decision entry point - Hierarchical AI system
	
	Priority Order:
	1. Emergency Override (imminent danger)
	2. ML Override (Q-Learning or MCTS personalities)
	3. State Machine Evaluation
	4. Behavior Tree Execution
	5. Utility Layer (pathfinding, bomb planning)
	"""
	var current_time = Time.get_ticks_msec() / 1000.0
	
	# Basic validation
	if ai_player == null or ai_player.is_dead:
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "DEAD"}
	
	# Reaction delay throttling (human-like response time)
	if current_time - last_reaction_time < personality_weights.reaction_delay * 0.5:
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "THROTTLED"}
	
	last_reaction_time = current_time
	var current_tile = ai_player.get_tile_position()
	
	# Track stuck detection
	if current_tile == last_position:
		stuck_counter += 1
	else:
		stuck_counter = 0
	last_position = current_tile
	
	# Clear path if stuck for too long
	if stuck_counter > 10:
		current_path.clear()
		stuck_counter = 0
		if OS.is_debug_build():
			print("[UnifiedAI] Stuck detected, clearing path")
	
	# Update world state
	observer.update_world_state(current_time)
	danger_mapper.update(game_instance, current_time)
	
	# PRIORITY 1: EMERGENCY OVERRIDE
	# If in immediate danger, override everything else
	var danger_level = danger_mapper.get_danger_at_tile(current_tile)
	if danger_level > 0.7:  # Critical danger threshold
		if OS.is_debug_build():
			print("[UnifiedAI] EMERGENCY ESCAPE - danger level: ", danger_level)
		return emergency_escape(ai_player, current_tile, current_time)
	
	# PRIORITY 2: ML OVERRIDE
	# If using Q-Learning or MCTS personality, bypass state machine
	if q_learning != null:
		return decide_action_q_learning(ai_player, current_tile, current_time)
	
	if mcts != null:
		return decide_action_mcts(ai_player, current_tile, current_time)
	
	# PRIORITY 3: STATE MACHINE EVALUATION
	# Evaluate state transitions based on game context
	evaluate_state_transitions(current_tile, ai_player, current_time)
	
	# PRIORITY 4: BEHAVIOR TREE EXECUTION
	# Execute current state's behavior tree
	var context = build_bt_context(ai_player, current_tile, current_time)
	var tree = get_current_state_tree()
	if tree:
		tree.execute(context)
		return context.action_result
	
	# Fallback
	return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "FALLBACK"}

# ============================================================================
# PRIORITY 1: EMERGENCY OVERRIDE
# ============================================================================

func emergency_escape(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	"""Immediate escape from danger - highest priority"""
	var escape_plan = bomb_planner.plan_emergency_escape(ai_player, current_time)
	
	if not escape_plan.emergency:
		return {"direction": Vector2.ZERO, "place_bomb": false, "reasoning": "FALSE_ALARM"}
	
	var escape_tile = escape_plan.escape_tile
	var direction = get_direction_to_tile(current_tile, escape_tile, ai_player.position, current_time)
	
	return {
		"direction": direction,
		"place_bomb": false,
		"reasoning": "EMERGENCY_ESCAPE",
		"target_tile": escape_tile
	}

# ============================================================================
# PRIORITY 2: ML OVERRIDES
# ============================================================================

func decide_action_q_learning(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	"""Q-Learning decision (LEARNED personality)"""
	var game_state = observer.get_world_state()
	var state_hash = q_learning.build_state_hash(current_tile, game_state, ai_player)
	var action_index = q_learning.choose_action(state_hash)
	
	# Convert action index to game action
	var direction = Vector2.ZERO
	var place_bomb = false
	
	match action_index:
		0: direction = Vector2(0, -1)  # UP
		1: direction = Vector2(0, 1)   # DOWN
		2: direction = Vector2(-1, 0)  # LEFT
		3: direction = Vector2(1, 0)   # RIGHT
		4: place_bomb = true           # PLACE_BOMB
		5: pass                        # WAIT
	
	return {
		"direction": direction,
		"place_bomb": place_bomb,
		"reasoning": "Q_LEARNING"
	}

func decide_action_mcts(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	"""MCTS decision (PERFECT personality)"""
	var game_state = observer.get_world_state()
	var mcts_state = {
		"position": current_tile,
		"danger_map": danger_mapper.danger_map.duplicate(),
		"bombs": game_state.bombs.duplicate(),
		"opponents": game_state.players.duplicate(),
		"map": game_state.map,
		"has_bomb": ai_player.can_place_bomb()
	}
	
	var action_index = mcts.search(mcts_state, 100)  # 100 simulations
	
	# Convert action index to game action
	var direction = Vector2.ZERO
	var place_bomb = false
	
	match action_index:
		0: direction = Vector2(0, -1)  # UP
		1: direction = Vector2(0, 1)   # DOWN
		2: direction = Vector2(-1, 0)  # LEFT
		3: direction = Vector2(1, 0)   # RIGHT
		4: place_bomb = true           # PLACE_BOMB
		5: pass                        # WAIT
	
	return {
		"direction": direction,
		"place_bomb": place_bomb,
		"reasoning": "MCTS"
	}

# ============================================================================
# PRIORITY 3: STATE MACHINE
# ============================================================================

func evaluate_state_transitions(current_tile: Vector2i, ai_player: Node2D, current_time: float):
	"""Evaluate and execute state transitions"""
	var danger = danger_mapper.get_danger_at_tile(current_tile)
	
	# CRITICAL: Always escape danger
	var escape_threshold = 1.5
	if personality_type == AIPersonality.Type.DEFENSIVE:
		escape_threshold = 2.5  # Escape earlier
	elif personality_type == AIPersonality.Type.KAMIKAZE:
		escape_threshold = 0.5  # Only escape at last second
	
	if danger > (1.0 - escape_threshold / 3.0) and current_state != State.ESCAPING:
		enter_state(State.ESCAPING)
		return
	
	# Exit ESCAPING when safe
	if current_state == State.ESCAPING and danger < 0.2:
		enter_state(State.EXPLORING)
		return
	
	# Don't transition if escaping
	if current_state == State.ESCAPING:
		return
	
	# State-specific transitions
	match current_state:
		State.EXPLORING:
			transition_from_exploring(current_tile, ai_player, current_time)
		State.HUNTING:
			transition_from_hunting(current_tile, ai_player, current_time)
		State.CORNERING:
			transition_from_cornering(current_tile, ai_player, current_time)
		State.AMBUSHING:
			transition_from_ambushing(current_tile, ai_player, current_time)

func transition_from_exploring(current_tile: Vector2i, ai_player: Node2D, current_time: float):
	"""Transitions from EXPLORING state"""
	# Check for nearby opponents
	var nearest_opponent = find_nearest_opponent(current_tile)
	if nearest_opponent.has("distance"):
		var hunt_distance = 7
		if personality_weights.aggression > 400:
			hunt_distance = 10
		
		if nearest_opponent.distance <= hunt_distance:
			hunt_target_tile = nearest_opponent.tile
			enter_state(State.HUNTING)
			return
	
	# Check for valuable powerups
	# TODO: Implement powerup tracking in observer
	
	# Check for ambush positions (TRAPPER personality)
	if personality_type == AIPersonality.Type.TRAPPER:
		if randf() < 0.15 and state_timer > 3.0:
			enter_state(State.AMBUSHING)
			return

func transition_from_hunting(current_tile: Vector2i, ai_player: Node2D, current_time: float):
	"""Transitions from HUNTING state"""
	# Check if target is close and cornered
	var distance_to_target = abs(current_tile.x - hunt_target_tile.x) + abs(current_tile.y - hunt_target_tile.y)
	if distance_to_target <= 3:
		# Check if target has limited escape routes
		var escape_routes = count_escape_routes(hunt_target_tile)
		if escape_routes <= 1:
			enter_state(State.CORNERING)
			return
	
	# Give up if target too far
	if distance_to_target > 12:
		enter_state(State.EXPLORING)
		return

func transition_from_cornering(current_tile: Vector2i, ai_player: Node2D, current_time: float):
	"""Transitions from CORNERING state"""
	# Exit after placing bomb and waiting briefly
	if state_timer > 0.5:
		enter_state(State.ESCAPING)

func transition_from_ambushing(current_tile: Vector2i, ai_player: Node2D, current_time: float):
	"""Transitions from AMBUSHING state"""
	# Timeout after 5 seconds
	if state_timer > 5.0:
		enter_state(State.EXPLORING)

func enter_state(new_state: State):
	"""Enter new state with cleanup"""
	var old_state = current_state
	
	# Cleanup old state
	match old_state:
		State.HUNTING:
			hunt_target = null
			hunt_target_tile = Vector2i(-1, -1)
		State.AMBUSHING:
			ambush_position = Vector2i(-1, -1)
	
	# Enter new state
	current_state = new_state
	state_entry_time = Time.get_ticks_msec() / 1000.0
	state_timer = 0.0
	
	if OS.is_debug_build():
		print("[UnifiedAI] State transition: ", State.keys()[old_state], " → ", State.keys()[new_state])

# ============================================================================
# PRIORITY 4: BEHAVIOR TREES
# ============================================================================

func build_behavior_trees():
	"""Build behavior trees for each state"""
	# EXPLORING: Find blocks, move strategically
	explore_tree = BehaviorTree.Selector.new()
	explore_tree.children = [
		build_explore_sequence(),
		BehaviorTree.ExploreRandomly.new()
	]
	
	# HUNTING: Chase opponent, place traps
	hunt_tree = build_hunt_sequence()
	
	# CORNERING: Place bomb and escape
	corner_tree = build_corner_sequence()
	
	# ESCAPING: Just run to safety
	escape_tree = BehaviorTree.MoveToSafety.new()
	
	# AMBUSHING: Wait or strike
	ambush_tree = BehaviorTree.Selector.new()
	ambush_tree.children = [
		build_ambush_strike_sequence(),
		BehaviorTree.Wait.new(1.0)
	]

func build_explore_sequence() -> BehaviorTree.BTNode:
	"""Build exploration behavior sequence"""
	var find_and_move = BehaviorTree.Sequence.new()
	find_and_move.children = [
		BehaviorTree.FindBlockCluster.new(),
		BehaviorTree.MoveToTarget.new()
	]
	
	var bomb_check = BehaviorTree.Sequence.new()
	bomb_check.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(250.0),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new()
	]
	
	var bomb_optional = BehaviorTree.Selector.new()
	bomb_optional.children = [bomb_check, BehaviorTree.BTNode.new()]
	
	var main_seq = BehaviorTree.Sequence.new()
	main_seq.children = [find_and_move, bomb_optional]
	
	return main_seq

func build_hunt_sequence() -> BehaviorTree.BTNode:
	"""Build hunting behavior sequence"""
	var find_and_chase = BehaviorTree.Sequence.new()
	find_and_chase.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new()
	]
	
	var bomb_attack = BehaviorTree.Sequence.new()
	bomb_attack.children = [
		BehaviorTree.IsOpponentNear.new(4),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(150.0),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new()
	]
	
	var bomb_optional = BehaviorTree.Selector.new()
	bomb_optional.children = [bomb_attack, BehaviorTree.BTNode.new()]
	
	var main_seq = BehaviorTree.Sequence.new()
	main_seq.children = [find_and_chase, bomb_optional]
	
	return main_seq

func build_corner_sequence() -> BehaviorTree.BTNode:
	"""Build cornering behavior sequence"""
	var seq = BehaviorTree.Sequence.new()
	seq.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.Wait.new(0.2),
		BehaviorTree.MoveToSafety.new()
	]
	return seq

func build_ambush_strike_sequence() -> BehaviorTree.BTNode:
	"""Build ambush strike sequence"""
	var seq = BehaviorTree.Sequence.new()
	seq.children = [
		BehaviorTree.IsOpponentNear.new(4),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	return seq

func get_current_state_tree() -> BehaviorTree.BTNode:
	"""Get behavior tree for current state"""
	match current_state:
		State.EXPLORING: return explore_tree
		State.HUNTING: return hunt_tree
		State.CORNERING: return corner_tree
		State.ESCAPING: return escape_tree
		State.AMBUSHING: return ambush_tree
		State.POWER_UP_RUSH: return explore_tree  # TODO: implement powerup tree
	return null

func build_bt_context(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> Dictionary:
	"""Build context for behavior tree execution"""
	return {
		"ai_player": ai_player,
		"my_tile": current_tile,
		"observer": observer,
		"controller": self,
		"danger_mapper": danger_mapper,
		"bomb_planner": bomb_planner,
		"game_state": observer.get_world_state(),
		"action_result": {"direction": Vector2.ZERO, "place_bomb": false},
		"current_time": current_time,
		"target_tile": Vector2i(-1, -1)
	}

# ============================================================================
# UTILITY FUNCTIONS (Shared by all systems)
# ============================================================================

func get_direction_to_tile(from_tile: Vector2i, to_tile: Vector2i, from_position: Vector2, current_time: float) -> Vector2:
	"""Get movement direction to target tile using A* pathfinding"""
	if from_tile == to_tile:
		return Vector2.ZERO
	
	# Rebuild A* graph if needed
	_ensure_astar_ready(current_time)
	
	# Update path if needed
	if current_time - last_path_update > path_update_interval or current_path.is_empty():
		current_path = _calculate_astar_path(from_tile, to_tile)
		last_path_update = current_time
	
	# Follow path
	if current_path.is_empty():
		# No path found - return fallback direction
		var dx = to_tile.x - from_tile.x
		var dy = to_tile.y - from_tile.y
		if abs(dx) > abs(dy):
			return Vector2(sign(dx), 0) if dx != 0 else Vector2.ZERO
		else:
			return Vector2(0, sign(dy)) if dy != 0 else Vector2.ZERO
	
	# Get next waypoint
	var next_waypoint = current_path[0]
	
	# Calculate direction to next waypoint (cardinal only)
	var delta = next_waypoint - from_position
	var direction = Vector2.ZERO
	
	if abs(delta.x) > abs(delta.y):
		direction.x = sign(delta.x)
	else:
		direction.y = sign(delta.y)
	
	# Check if we reached waypoint
	if from_position.distance_to(next_waypoint) < Constants.TILE_SIZE * 0.3:
		current_path.remove_at(0)
	
	return direction

func find_nearest_opponent(from_tile: Vector2i) -> Dictionary:
	"""Find nearest opponent using Manhattan distance"""
	var result = {}
	var min_distance = INF
	
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		# Skip self and dead players
		if player.has_method("is_ai_bot"):
			continue
		if player.is_dead:
			continue
		
		var player_tile = player.get_tile_position()
		var distance = abs(player_tile.x - from_tile.x) + abs(player_tile.y - from_tile.y)
		
		if distance < min_distance:
			min_distance = distance
			result = {
				"tile": player_tile,
				"distance": distance,
				"player": player
			}
	
	return result

func calculate_bomb_value(tile: Vector2i, game_state: Dictionary, ai_player: Node2D) -> float:
	"""Calculate tactical value of placing bomb at tile - Phase 4 Enhanced"""
	var value = 0.0
	var bomb_range = ai_player.bomb_range if ai_player.has("bomb_range") else 2
	
	# Phase 4: Use advanced chain reaction if enabled
	if personality_weights.get("use_advanced_chains", false):
		var chain_result = observer.calculate_advanced_chain_reaction(tile, bomb_range, 3.0)
		
		# Value from blocks destroyed (with chain multiplier)
		value += chain_result.blocks_destroyed * 100.0
		
		# Exponential bonus for deep chains
		if chain_result.chain_depth > 0:
			var chain_bonus = 200.0 * chain_result.chain_depth
			if chain_result.chain_depth >= 3:
				chain_bonus += 500.0  # Major bonus for 3+ chain
			value += chain_bonus
		
		# Bonus for trapped players
		value += chain_result.players_trapped.size() * personality_weights.get("trap_bonus", 400)
		
		# Bonus for powerup reveals
		value += chain_result.powerups_revealed.size() * 50.0
		
		return value
	
	# Standard chain reaction (fallback)
	var explosion_cells = simulate_explosion(tile, bomb_range, game_state.get("map", []))
	
	# Value from blocks destroyed
	for cell in explosion_cells:
		if is_breakable_block(cell, game_state):
			value += 100.0
	
	# Value from trapping opponents (Phase 4: Team-aware)
	for peer_id in game_state.get("players", {}):
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		
		# Phase 4: Skip teammates
		if team_id >= 0 and is_teammate(peer_id):
			# Penalty for hitting teammates
			var player_tile = player.get_tile_position()
			if player_tile in explosion_cells:
				value -= 500.0  # Large penalty for friendly fire
			continue
		
		var player_tile = player.get_tile_position()
		if player_tile in explosion_cells:
			value += personality_weights.get("trap_bonus", 400) * 0.5
	
	return value

func simulate_explosion(center: Vector2i, bomb_range: int, map: Array) -> Array:
	"""Simulate bomb explosion pattern"""
	var cells = [center]
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for i in range(1, bomb_range + 1):
			var cell = center + dir * i
			
			if cell.y < 0 or cell.y >= map.size() or cell.x < 0 or cell.x >= map[0].size():
				break
			
			if map[cell.y][cell.x] == 1:  # Hard wall
				break
			
			cells.append(cell)
			
			if map[cell.y][cell.x] == 2:  # Soft block
				break
	
	return cells

func is_breakable_block(tile: Vector2i, game_state: Dictionary) -> bool:
	"""Check if tile contains a breakable block"""
	var map = game_state.get("map", [])
	if tile.y < 0 or tile.y >= map.size() or tile.x < 0 or tile.x >= map[0].size():
		return false
	return map[tile.y][tile.x] == 2

func find_valuable_block_clusters(from_tile: Vector2i, game_state: Dictionary, max_search: int) -> Array:
	"""Find clusters of breakable blocks"""
	var clusters = []
	var map = game_state.get("map", [])
	
	for y in range(max(0, from_tile.y - max_search), min(map.size(), from_tile.y + max_search)):
		for x in range(max(0, from_tile.x - max_search), min(map[0].size(), from_tile.x + max_search)):
			var tile = Vector2i(x, y)
			if is_breakable_block(tile, game_state):
				var cluster_count = 1
				# Count adjacent breakable blocks
				for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
					if is_breakable_block(tile + dir, game_state):
						cluster_count += 1
				
				var distance = abs(tile.x - from_tile.x) + abs(tile.y - from_tile.y)
				clusters.append({
					"tile": tile,
					"count": cluster_count,
					"distance": distance,
					"value": float(cluster_count) / max(1.0, float(distance))
				})
	
	# Sort by value
	clusters.sort_custom(func(a, b): return a.value > b.value)
	return clusters.slice(0, 5)  # Top 5 clusters

func find_strategic_position(from_tile: Vector2i, game_state: Dictionary) -> Vector2i:
	"""Find strategic position (map center control)"""
	var map = game_state.get("map", [])
	if map.is_empty():
		return from_tile
	
	var map_center = Vector2i(map[0].size() / 2, map.size() / 2)
	
	# Find walkable tile nearest to center
	var best_tile = from_tile
	var min_distance = INF
	
	for dy in range(-5, 6):
		for dx in range(-5, 6):
			var tile = map_center + Vector2i(dx, dy)
			if observer._is_tile_walkable(tile):
				var distance = abs(tile.x - from_tile.x) + abs(tile.y - from_tile.y)
				if distance < min_distance:
					min_distance = distance
					best_tile = tile
	
	return best_tile

func count_escape_routes(tile: Vector2i) -> int:
	"""Count number of safe tiles adjacent to position"""
	var count = 0
	for direction in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = tile + direction
		if observer._is_tile_walkable(check_tile):
			var danger = danger_mapper.get_danger_at_tile(check_tile)
			if danger < 0.3:  # Safe enough
				count += 1
	return count

func get_personality_name() -> String:
	"""Get name of current personality"""
	return AIPersonality.get_name(personality_type)

# ============================================================================
# PATHFINDING SYSTEM
# ============================================================================

func _ensure_astar_ready(current_time: float) -> void:
	"""Ensure A* graph is built and updated"""
	if not astar_initialized or current_time - last_path_update > 0.5:
		_build_astar_graph()
		astar_initialized = true

func _build_astar_graph() -> void:
	"""Build A* navigation graph with danger awareness"""
	astar.clear()
	tile_to_id.clear()
	
	var game_state = observer.get_world_state()
	var map = game_state.get("map", [])
	if map.is_empty():
		return
	
	var point_id = 0
	
	# Add all walkable tiles
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]
			var tile_center = Vector2(
				x * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
				y * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
			)
			
			if observer._is_tile_walkable(tile):
				tile_to_id[tile_key] = point_id
				astar.add_point(point_id, tile_center)
				point_id += 1
	
	# Connect adjacent tiles with danger-aware weights
	for y in range(map.size()):
		for x in range(map[y].size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]
			
			if tile_to_id.has(tile_key):
				var from_id = tile_to_id[tile_key]
				
				for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
					var neighbor = tile + dir
					var neighbor_key = "%d,%d" % [neighbor.x, neighbor.y]
					
					if not tile_to_id.has(neighbor_key):
						continue
					
					var to_id = tile_to_id[neighbor_key]
					var danger = danger_mapper.get_danger_at_tile(neighbor)
					var weight = 1.0
					
					# Penalize dangerous tiles
					if danger > 0.7:
						weight = 100.0
					elif danger > 0.3:
						weight = 10.0
					
					astar.connect_points(from_id, to_id, true)
					astar.set_point_weight_scale(to_id, weight)

func _calculate_astar_path(from_tile: Vector2i, to_tile: Vector2i) -> Array:
	"""Calculate A* path avoiding danger"""
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

# ============================================================================
# DEBUG VISUALIZATION
# ============================================================================

func setup_debug_visualizer(game_ref: Node2D, ai_player: Node2D):
	"""Setup debug visualization"""
	if OS.is_debug_build():
		debug_visualizer = DebugVisualizerClass.new()
		debug_visualizer.setup(game_ref, self, ai_player)
		game_ref.add_child(debug_visualizer)
		print("[UnifiedAI] Debug visualizer enabled")

# ============================================================================
# EVENT CALLBACKS (for ML systems)
# ============================================================================

func on_player_death():
	"""Called when AI dies - for ML training"""
	if q_learning:
		q_learning.update_q_value(last_state_hash, last_action, -1000.0, "", true)

func on_player_kill():
	"""Called when AI kills opponent - for ML training"""
	if q_learning:
		q_learning.update_q_value(last_state_hash, last_action, 500.0, "", false)

func on_block_destroyed():
	"""Called when AI destroys block - for ML training"""
	if q_learning:
		q_learning.update_q_value(last_state_hash, last_action, 50.0, "", false)

func on_match_end():
	"""Called when match ends - save ML data"""
	if q_learning:
		q_learning.save_q_table()
		print("[UnifiedAI] Q-table saved")

# ============================================================================
# PHASE 4: TEAM COORDINATION
# ============================================================================

func set_team(team_number: int, teammate_ids: Array = []):
	"""
	Set team for this bot (Phase 4 Enhancement)
	
	Args:
		team_number: Team ID (0+ for teams, -1 for free-for-all)
		teammate_ids: Array of peer IDs that are teammates
	"""
	team_id = team_number
	teammates = teammate_ids.duplicate()
	
	if team_id >= 0:
		print("[UnifiedAI] Joined team ", team_id, " with ", teammates.size(), " teammates")

func is_teammate(peer_id: int) -> bool:
	"""Check if a player is a teammate"""
	return peer_id in teammates

func find_nearest_opponent_team_aware(from_tile: Vector2i, game_state: Dictionary, ai_player: Node2D) -> Vector2i:
	"""
	Find nearest opponent, excluding teammates (Phase 4 Enhancement)
	"""
	var nearest = Vector2i(-1, -1)
	var min_dist = INF
	
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		
		# Skip teammates
		if team_id >= 0 and is_teammate(peer_id):
			continue
		
		var player_tile = player.get_tile_position()
		var dist = abs(player_tile.x - from_tile.x) + abs(player_tile.y - from_tile.y)
		
		if dist < min_dist:
			min_dist = dist
			nearest = player_tile
	
	return nearest

func should_coordinate_attack(target_tile: Vector2i) -> Dictionary:
	"""
	Check if teammates are also targeting this opponent (Phase 4 Enhancement)
	
	Returns: {
		"coordinated": bool,
		"teammate_count": int,
		"recommended_action": String  # "attack", "support", "retreat"
	}
	"""
	if team_id < 0 or teammates.is_empty():
		return {"coordinated": false, "teammate_count": 0, "recommended_action": "attack"}
	
	var teammates_nearby = 0
	var teammates_targeting = 0
	
	for teammate_id in teammates:
		if not game_instance.players.has(teammate_id):
			continue
		
		var teammate = game_instance.players[teammate_id]
		if teammate.has_method("is_dead") and teammate.is_dead:
			continue
		
		var teammate_tile = teammate.get_tile_position()
		var distance_to_target = abs(teammate_tile.x - target_tile.x) + abs(teammate_tile.y - target_tile.y)
		
		if distance_to_target <= 5:
			teammates_nearby += 1
		
		if distance_to_target <= 3:
			teammates_targeting += 1
	
	var coordinated = teammates_targeting > 0
	var action = "attack"
	
	if teammates_targeting >= 2:
		action = "support"  # Multiple teammates already attacking, provide support
	elif teammates_nearby >= 1:
		action = "attack"  # Coordinate pincer attack
	
	return {
		"coordinated": coordinated,
		"teammate_count": teammates_targeting,
		"recommended_action": action
	}
