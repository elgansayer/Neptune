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

func _init(game_inst: Node2D, personality: int = 0):
	game_instance = game_inst
	personality_type = personality
	personality_weights = AIPersonality.get_weights(personality)
	
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
	
	print("[UnifiedAI] Initialized with personality: ", AIPersonality.get_name(personality))

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
	explore_tree = BehaviorTree.BTSelector.new([
		build_explore_sequence(),
		BehaviorTree.BTAction.new("ExploreRandomly")
	])
	
	# HUNTING: Chase opponent, place traps
	hunt_tree = build_hunt_sequence()
	
	# CORNERING: Place bomb and escape
	corner_tree = build_corner_sequence()
	
	# ESCAPING: Just run to safety
	escape_tree = BehaviorTree.BTAction.new("MoveToSafety")
	
	# AMBUSHING: Wait or strike
	ambush_tree = BehaviorTree.BTSelector.new([
		build_ambush_strike_sequence(),
		BehaviorTree.BTAction.new("Wait")
	])

func build_explore_sequence() -> BehaviorTree.BTNode:
	"""Build exploration behavior sequence"""
	return BehaviorTree.BTSequence.new([
		BehaviorTree.BTAction.new("FindBlockCluster"),
		BehaviorTree.BTAction.new("MoveToTarget"),
		BehaviorTree.BTSelector.new([
			BehaviorTree.BTSequence.new([
				BehaviorTree.BTCondition.new("CanPlaceBomb"),
				BehaviorTree.BTCondition.new("IsBombValuable"),
				BehaviorTree.BTCondition.new("HasEscapeRoute"),
				BehaviorTree.BTAction.new("PlaceBomb")
			]),
			BehaviorTree.BTNode.new()  # Always succeed
		])
	])

func build_hunt_sequence() -> BehaviorTree.BTNode:
	"""Build hunting behavior sequence"""
	return BehaviorTree.BTSequence.new([
		BehaviorTree.BTAction.new("FindNearestOpponent"),
		BehaviorTree.BTAction.new("MoveToTarget"),
		BehaviorTree.BTSelector.new([
			BehaviorTree.BTSequence.new([
				BehaviorTree.BTCondition.new("IsOpponentNear"),
				BehaviorTree.BTCondition.new("CanPlaceBomb"),
				BehaviorTree.BTCondition.new("IsBombValuable"),
				BehaviorTree.BTCondition.new("HasEscapeRoute"),
				BehaviorTree.BTAction.new("PlaceBomb")
			]),
			BehaviorTree.BTNode.new()  # Always succeed
		])
	])

func build_corner_sequence() -> BehaviorTree.BTNode:
	"""Build cornering behavior sequence"""
	return BehaviorTree.BTSequence.new([
		BehaviorTree.BTCondition.new("CanPlaceBomb"),
		BehaviorTree.BTCondition.new("HasEscapeRoute"),
		BehaviorTree.BTAction.new("PlaceBomb"),
		BehaviorTree.BTAction.new("Wait", {"duration": 0.2}),
		BehaviorTree.BTAction.new("MoveToSafety")
	])

func build_ambush_strike_sequence() -> BehaviorTree.BTNode:
	"""Build ambush strike sequence"""
	return BehaviorTree.BTSequence.new([
		BehaviorTree.BTCondition.new("IsOpponentNear"),
		BehaviorTree.BTCondition.new("CanPlaceBomb"),
		BehaviorTree.BTCondition.new("HasEscapeRoute"),
		BehaviorTree.BTAction.new("PlaceBomb"),
		BehaviorTree.BTAction.new("MoveToSafety")
	])

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
	# TODO: Implement pathfinding
	# For now, simple direct movement
	var dx = to_tile.x - from_tile.x
	var dy = to_tile.y - from_tile.y
	
	if abs(dx) > abs(dy):
		return Vector2(sign(dx), 0).normalized()
	elif dy != 0:
		return Vector2(0, sign(dy)).normalized()
	
	return Vector2.ZERO

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
