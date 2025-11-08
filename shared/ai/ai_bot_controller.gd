extends Node
class_name AIBotController

# ADVANCED HYBRID AI: State Machine + Behavior Trees + Utility System
# State Machine: High-level strategic planning (HUNTING, CORNERING, etc.)
# Behavior Trees: Multi-step tactical sequences per state
# Utility System: Moment-to-moment decisions (pathfinding, bomb value)
# Q-Learning: Reinforcement learning for LEARNED personality
# MCTS: Monte Carlo Tree Search for PERFECT personality

const Constants = preload("res://shared/constants.gd")
const BehaviorTree = preload("res://shared/ai/behavior_tree.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")
const AIQLearningClass = preload("res://shared/ai/ai_q_learning.gd")
const AIMCTSClass = preload("res://shared/ai/ai_mcts.gd")

# ============================================================================
# AI STATE MACHINE
# ============================================================================
enum State {
	EXPLORING,      # Default: looking for blocks/power-ups
	HUNTING,        # Chasing a specific opponent
	CORNERING,      # Opponent trapped, setting up kill
	ESCAPING,       # In danger, running to safety
	AMBUSHING,      # Waiting at strategic choke point
	POWER_UP_RUSH   # Racing to grab power-up (future)
}

var current_state: State = State.EXPLORING
var state_timer: float = 0.0
var state_entry_time: float = 0.0

# Core components
var observer
var personality_weights: Dictionary
var personality_type: int

# Behavior Trees per state
var explore_tree: BehaviorTree.BTNode
var hunt_tree: BehaviorTree.BTNode
var corner_tree: BehaviorTree.BTNode
var escape_tree: BehaviorTree.BTNode
var ambush_tree: BehaviorTree.BTNode
var powerup_rush_tree: BehaviorTree.BTNode

# Utility system data (kept for tactical decisions)
var last_pathfinding_time: float = 0.0
var last_bomb_decision_time: float = 0.0
var current_path: Array = []  # Array of waypoint positions (Vector2)
var current_target_tile: Vector2i = Vector2i(-1, -1)
var last_reaction_time: float = 0.0
var stuck_counter: int = 0
var last_position: Vector2i = Vector2i(-1, -1)
var astar: AStar2D
var tile_to_id: Dictionary = {}  # Maps "x,y" -> AStar2D point ID
var astar_initialized: bool = false
var last_replan_time: float = 0.0
var astar_last_build_time: float = -1.0
var last_obstacle_signature: String = ""
var last_danger_signature: String = ""
const REPLAN_INTERVAL: float = 0.2  # Replan every 200ms
const WAYPOINT_REACH_DISTANCE: float = 4.0  # Pixels to consider waypoint reached

# State-specific data
var hunt_target: Node2D = null
var hunt_target_tile: Vector2i = Vector2i(-1, -1)
var ambush_position: Vector2i = Vector2i(-1, -1)
var last_opponent_seen_time: float = 0.0

# Advanced AI systems
var q_learning: AIQLearningClass = null
var mcts: AIMCTSClass = null
var last_state_hash: String = ""
var last_action: int = -1

func _init(game_instance: Node2D, personality: int = 0):
	var AIObserver_class = load("res://shared/ai/ai_observer.gd")
	observer = AIObserver_class.new(game_instance)
	personality_type = personality
	personality_weights = AIPersonality.get_weights(personality)
	astar = AStar2D.new()
	
	# Build behavior trees for each state
	build_behavior_trees()
	
	# Initialize advanced AI systems if using those personalities
	if personality_weights.get("use_q_learning", false):
		q_learning = AIQLearningClass.new()
		q_learning.load_q_table()  # Load previous learning
	
	if personality_weights.get("use_mcts", false):
		mcts = AIMCTSClass.new(self, observer)

# ============================================================================
# MAIN DECISION SYSTEM: State Machine → Behavior Tree → Utility
# ============================================================================

func decide_action(ai_player: Node2D) -> Dictionary:
	var current_time = Time.get_ticks_msec() / 1000.0
	var current_tile = ai_player.get_tile_position()
	
	# Update position history for all players (for prediction)
	for peer_id in observer.game_instance.players:
		var player = observer.game_instance.players[peer_id]
		if player != ai_player:  # Track opponents only
			observer.update_player_position_history(str(peer_id), player.position, current_time)
	
	# Track stuck detection
	if current_tile == last_position:
		stuck_counter += 1
	else:
		stuck_counter = 0
	last_position = current_tile
	
	if stuck_counter > 10:
		current_path.clear()
		stuck_counter = 0
	
	# Reaction delay throttling
	if current_time - last_reaction_time < personality_weights.reaction_delay * 0.5:
		return {"direction": Vector2.ZERO, "place_bomb": false}
	
	last_reaction_time = current_time
	state_timer = current_time - state_entry_time
	
	# Get game state for context
	var game_state = observer.get_world_state()
	
	# ========================================================================
	# ADVANCED AI: Q-Learning or MCTS (bypasses State Machine + BT)
	# ========================================================================
	if q_learning != null:
		return decide_action_q_learning(ai_player, current_tile, game_state, current_time)
	
	if mcts != null:
		return decide_action_mcts(ai_player, current_tile, game_state, current_time)
	
	# ========================================================================
	# STANDARD AI: State Machine + Behavior Trees
	# ========================================================================
	
	# STATE TRANSITIONS (high-level strategic decisions)
	evaluate_state_transitions(current_tile, game_state, ai_player, current_time)
	
	# Execute current state's behavior tree
	var context = {
		"ai_player": ai_player,
		"my_tile": current_tile,
		"observer": observer,
		"controller": self,
		"game_state": game_state,
		"action_result": {"direction": Vector2.ZERO, "place_bomb": false},
		"delta_time": 0.016,  # Approximate
		"current_time": current_time
	}
	
	# Run the appropriate behavior tree for current state
	var tree = get_current_state_tree()
	if tree:
		tree.execute(context)
	
	return context.action_result

func evaluate_state_transitions(current_tile: Vector2i, game_state: Dictionary, ai_player: Node2D, current_time: float):
	var danger = observer.get_time_until_explosion(current_tile)
	
	# KAMIKAZE: Ignore danger if hunting (willing to trade kills)
	if personality_type == AIPersonality.Type.KAMIKAZE:
		if danger < 0.5 and current_state == State.CORNERING:
			# Stay to ensure kill, even if suicidal
			return
	
	# DEFENSIVE: Escape earlier than others
	var escape_threshold = 1.5
	if personality_type == AIPersonality.Type.DEFENSIVE:
		escape_threshold = 2.5  # Escape much earlier
	elif personality_type == AIPersonality.Type.KAMIKAZE:
		escape_threshold = 0.3  # Only escape at last second
	
	# CRITICAL: Always escape danger (highest priority, except Kamikaze in cornering)
	if danger < escape_threshold and current_state != State.ESCAPING:
		enter_state(State.ESCAPING)
		return
	
	# Exit ESCAPING when safe
	var safe_threshold = 2.5
	if personality_type == AIPersonality.Type.DEFENSIVE:
		safe_threshold = 4.0  # Stays in escape mode longer
	
	if current_state == State.ESCAPING and danger >= safe_threshold:
		# Check for valuable powerups before returning to exploration
		var powerup_weights = personality_weights.get("powerup_utility_weights", {})
		var valuable_powerup = observer.find_valuable_powerup(current_tile, powerup_weights)
		
		if valuable_powerup.value >= personality_weights.powerup:
			enter_state(State.POWER_UP_RUSH)
			return
		
		# DEFENSIVE and TRAPPER prefer AMBUSHING after escape
		if personality_type == AIPersonality.Type.DEFENSIVE or personality_type == AIPersonality.Type.TRAPPER:
			if randf() < 0.4:  # 40% chance to ambush
				enter_state(State.AMBUSHING)
				return
		enter_state(State.EXPLORING)
		return
	
	# Don't transition if escaping
	if current_state == State.ESCAPING:
		return
	
	# State-specific transitions
	match current_state:
		State.EXPLORING:
			# Check for valuable powerups (higher priority for Greedy)
			var powerup_threshold = personality_weights.powerup
			if personality_type == AIPersonality.Type.GREEDY:
				powerup_threshold *= 0.5  # Greedy rushes to powerups more eagerly
			
			var powerup_weights = personality_weights.get("powerup_utility_weights", {})
			var valuable_powerup = observer.find_valuable_powerup(current_tile, powerup_weights)
			
			if valuable_powerup.value >= powerup_threshold:
				enter_state(State.POWER_UP_RUSH)
				return
			
			# TRAPPER: Frequently enters ambush mode
			if personality_type == AIPersonality.Type.TRAPPER:
				if randf() < 0.15 and state_timer > 3.0:  # 15% chance every 3s
					enter_state(State.AMBUSHING)
					return
			
			# DEFENSIVE: Prefers ambushing over hunting
			if personality_type == AIPersonality.Type.DEFENSIVE:
				if randf() < 0.1 and state_timer > 5.0:  # 10% chance every 5s
					enter_state(State.AMBUSHING)
					return
			
			# Transition to HUNTING if aggressive and opponent nearby
			var hunt_aggression_threshold = 400.0
			var hunt_distance = 7
			
			# Personality-specific hunting behavior
			if personality_type == AIPersonality.Type.KAMIKAZE:
				hunt_aggression_threshold = 100.0  # Always hunts
				hunt_distance = 15  # Chases from far away
			elif personality_type == AIPersonality.Type.STRATEGIC:
				hunt_aggression_threshold = 300.0  # More selective
				hunt_distance = 8  # Moderate range
			elif personality_type == AIPersonality.Type.DEFENSIVE:
				hunt_aggression_threshold = 1500.0  # Almost never hunts
				hunt_distance = 3  # Only if very close
			elif personality_type == AIPersonality.Type.TRAPPER:
				hunt_aggression_threshold = 350.0  # Moderate
				hunt_distance = 6  # Prefers ambush over chase
			
			if personality_weights.aggression > hunt_aggression_threshold:
				var opponent_tile = find_nearest_opponent(current_tile, game_state, ai_player)
				if opponent_tile != Vector2i(-1, -1):
					var dist = abs(opponent_tile.x - current_tile.x) + abs(opponent_tile.y - current_tile.y)
					if dist <= hunt_distance:
						hunt_target_tile = opponent_tile
						enter_state(State.HUNTING)
						return
		
		State.HUNTING:
			# Lost target or target died
			if hunt_target_tile == Vector2i(-1, -1):
				enter_state(State.EXPLORING)
				return
			
			# Update hunt target with prediction (1-3 seconds based on personality)
			var prediction_time = personality_weights.reaction_delay * 20.0  # Scale by reaction
			hunt_target_tile = find_nearest_opponent_predicted(current_tile, game_state, ai_player, prediction_time)
			if hunt_target_tile == Vector2i(-1, -1):
				enter_state(State.EXPLORING)
				return
			
			var dist_to_target = abs(hunt_target_tile.x - current_tile.x) + abs(hunt_target_tile.y - current_tile.y)
			
			# Personality-specific chase persistence
			var max_chase_distance = 10
			if personality_type == AIPersonality.Type.KAMIKAZE:
				max_chase_distance = 20  # Never gives up
			elif personality_type == AIPersonality.Type.STRATEGIC:
				max_chase_distance = 12  # Persistent
			elif personality_type == AIPersonality.Type.DEFENSIVE:
				max_chase_distance = 5  # Gives up quickly
			
			# Too far, give up chase
			if dist_to_target > max_chase_distance:
				enter_state(State.EXPLORING)
				return
			
			# Close enough and target cornered → CORNERING
			var cornering_distance = 3
			var escape_routes_threshold = 1
			
			if personality_type == AIPersonality.Type.STRATEGIC:
				cornering_distance = 4  # Plans ahead
				escape_routes_threshold = 2  # More aggressive cornering
			elif personality_type == AIPersonality.Type.TRAPPER:
				cornering_distance = 5  # Sets up from distance
				escape_routes_threshold = 1  # Perfect trap
			
			if dist_to_target <= cornering_distance:
				var target_escapes = observer.count_escape_routes(hunt_target_tile)
				if target_escapes <= escape_routes_threshold:
					enter_state(State.CORNERING)
					return
		
		State.CORNERING:
			# Personality-specific cornering duration
			var corner_duration = 0.5
			if personality_type == AIPersonality.Type.KAMIKAZE:
				corner_duration = 1.5  # Stays longer to ensure kill
			elif personality_type == AIPersonality.Type.STRATEGIC:
				corner_duration = 0.3  # Quick, calculated
			
			# Bomb placed, time to escape
			if state_timer > corner_duration:
				enter_state(State.ESCAPING)
				return
		
		State.AMBUSHING:
			# Personality-specific ambush duration
			var ambush_timeout = 5.0
			if personality_type == AIPersonality.Type.TRAPPER:
				ambush_timeout = 10.0  # Very patient
			elif personality_type == AIPersonality.Type.DEFENSIVE:
				ambush_timeout = 8.0  # Patient
			elif personality_type == AIPersonality.Type.STRATEGIC:
				ambush_timeout = 6.0  # Calculated wait
			
			# Timeout ambush
			if state_timer > ambush_timeout:
				enter_state(State.EXPLORING)
				return
		
		State.POWER_UP_RUSH:
			# Check if powerup is still available
			var powerup_weights = personality_weights.get("powerup_utility_weights", {})
			var valuable_powerup = observer.find_valuable_powerup(current_tile, powerup_weights)
			
			# Powerup collected or no longer valuable
			if valuable_powerup.tile == Vector2i(-1, -1) or valuable_powerup.value < personality_weights.powerup:
				enter_state(State.EXPLORING)
				return
			
			# Reached powerup tile
			if current_tile == valuable_powerup.tile:
				enter_state(State.EXPLORING)
				return
			
			# Timeout if taking too long (prevents stuck on unreachable powerup)
			if state_timer > 5.0:
				enter_state(State.EXPLORING)
				return

func enter_state(new_state: State):
	# Exit old state cleanup
	match current_state:
		State.HUNTING:
			hunt_target = null
			hunt_target_tile = Vector2i(-1, -1)
		State.AMBUSHING:
			ambush_position = Vector2i(-1, -1)
	
	# Enter new state
	var old_state = current_state
	current_state = new_state
	state_entry_time = Time.get_ticks_msec() / 1000.0
	state_timer = 0.0
	
	# State entry setup
	match new_state:
		State.AMBUSHING:
			ambush_position = find_ambush_position()
	
	# Debug logging
	if OS.is_debug_build():
		print("[AI %s] State: %s → %s" % [get_personality_name(), State.keys()[old_state], State.keys()[new_state]])

func get_current_state_tree() -> BehaviorTree.BTNode:
	match current_state:
		State.EXPLORING:
			return explore_tree
		State.HUNTING:
			return hunt_tree
		State.CORNERING:
			return corner_tree
		State.ESCAPING:
			return escape_tree
		State.AMBUSHING:
			return ambush_tree
		State.POWER_UP_RUSH:
			return powerup_rush_tree
	return explore_tree

# ============================================================================
# BEHAVIOR TREE CONSTRUCTION
# ============================================================================

func build_behavior_trees():
	# Build personality-specific trees if applicable
	if personality_type == AIPersonality.Type.KAMIKAZE:
		build_kamikaze_trees()
	elif personality_type == AIPersonality.Type.TRAPPER:
		build_trapper_trees()
	elif personality_type == AIPersonality.Type.STRATEGIC:
		build_strategic_trees()
	else:
		# Standard behavior trees for all other personalities
		build_explore_tree()
		build_hunt_tree()
		build_corner_tree()
		build_escape_tree()
		build_ambush_tree()
		build_powerup_rush_tree()

func build_explore_tree():
	# Root: Try blocks → strategic position → random
	var root = BehaviorTree.Selector.new()
	
	# Sequence: Find and move to block clusters
	var block_sequence = BehaviorTree.Sequence.new()
	block_sequence.children = [
		BehaviorTree.FindBlockCluster.new(),
		BehaviorTree.MoveToTarget.new(),
		# Optional: Place bomb if valuable
		BehaviorTree.Selector.new()
	]
	var bomb_option = BehaviorTree.Sequence.new()
	bomb_option.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(250.0),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new()
	]
	block_sequence.children[2].children = [bomb_option, BehaviorTree.BTNode.new()]  # Always succeed after bomb check
	
	root.children.append(block_sequence)
	
	# Fallback: Strategic position
	var strategic_sequence = BehaviorTree.Sequence.new()
	strategic_sequence.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	root.children.append(strategic_sequence)
	
	# Last resort: Explore randomly
	root.children.append(BehaviorTree.ExploreRandomly.new())
	
	explore_tree = root

func build_hunt_tree():
	# Sequence: Track opponent → Move toward → Place bomb if close
	var root = BehaviorTree.Sequence.new()
	
	root.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new(),
		# Optional bomb placement
		BehaviorTree.Selector.new()
	]
	
	var aggressive_bomb = BehaviorTree.Sequence.new()
	aggressive_bomb.children = [
		BehaviorTree.IsOpponentNear.new(3),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(150.0),  # Lower threshold when hunting
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new()
	]
	root.children[2].children = [aggressive_bomb, BehaviorTree.BTNode.new()]
	
	hunt_tree = root

func build_corner_tree():
	# Sequence: Move to intercept → Place bomb → Start retreat
	var root = BehaviorTree.Sequence.new()
	
	root.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.Wait.new(0.2),  # Brief pause
		BehaviorTree.MoveToSafety.new()
	]
	
	corner_tree = root

func build_escape_tree():
	# Simple: Just get to safety as fast as possible
	var root = BehaviorTree.MoveToSafety.new()
	escape_tree = root

func build_ambush_tree():
	# Sequence: Move to ambush point → Wait → Place bomb when opponent near
	var root = BehaviorTree.Selector.new()
	
	# Try to ambush
	var ambush_sequence = BehaviorTree.Sequence.new()
	ambush_sequence.children = [
		BehaviorTree.IsOpponentNear.new(4),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	root.children.append(ambush_sequence)
	
	# Otherwise move to strategic position (no idle waiting)
	var patrol_action = BehaviorTree.Sequence.new()
	patrol_action.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	root.children.append(patrol_action)
	
	ambush_tree = root

func build_powerup_rush_tree():
	# Sequence: Find valuable powerup → Move toward it
	var root = BehaviorTree.Sequence.new()
	
	root.children = [
		BehaviorTree.IsValuablePowerUpVisible.new(personality_weights.powerup),
		BehaviorTree.MoveToTarget.new()
	]
	
	powerup_rush_tree = root

# ============================================================================
# PERSONALITY-SPECIFIC BEHAVIOR TREES
# ============================================================================

func build_kamikaze_trees():
	"""Kamikaze: Aggressive pursuit, suicide bombing, continuous charging"""
	
	# EXPLORING: Aggressively seek opponents
	var explore_root = BehaviorTree.Selector.new()
	explore_root.children = [
		BehaviorTree.Sequence.new(),  # Try to find and charge opponent
		BehaviorTree.Sequence.new()   # Fallback: charge toward map center
	]
	
	var charge_sequence = explore_root.children[0]
	charge_sequence.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new()
	]
	
	var center_sequence = explore_root.children[1]
	center_sequence.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	explore_tree = explore_root
	
	# HUNTING: Charge directly, place bomb when adjacent
	var hunt_root = BehaviorTree.Sequence.new()
	hunt_root.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new(),
		BehaviorTree.Selector.new()  # Try to bomb if very close
	]
	
	var bomb_on_contact = BehaviorTree.Sequence.new()
	bomb_on_contact.children = [
		BehaviorTree.IsOpponentNear.new(1),  # Adjacent
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.PlaceBomb.new()
		# No escape check - Kamikaze doesn't care
	]
	hunt_root.children[2].children = [bomb_on_contact, BehaviorTree.BTNode.new()]
	hunt_tree = hunt_root
	
	# CORNERING: Place bomb and continue charging forward
	var corner_root = BehaviorTree.Sequence.new()
	corner_root.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.FindNearestOpponent.new(),  # Keep charging
		BehaviorTree.MoveToTarget.new()
	]
	corner_tree = corner_root
	
	# ESCAPING: Move to safety (even Kamikaze escapes sometimes)
	escape_tree = BehaviorTree.MoveToSafety.new()
	
	# AMBUSHING: Kamikaze doesn't ambush, patrol aggressively
	var ambush_root = BehaviorTree.Sequence.new()
	ambush_root.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	ambush_tree = ambush_root
	
	# POWER_UP_RUSH: Only grab bombs if nearby
	var powerup_root = BehaviorTree.Sequence.new()
	powerup_root.children = [
		BehaviorTree.IsValuablePowerUpVisible.new(personality_weights.powerup),
		BehaviorTree.MoveToTarget.new()
	]
	powerup_rush_tree = powerup_root

func build_trapper_trees():
	"""Trapper: Ambush setup, patient trap placement, chokepoint control"""
	
	# EXPLORING: Look for chokepoints and strategic positions
	var explore_root = BehaviorTree.Selector.new()
	explore_root.children = [
		BehaviorTree.Sequence.new(),  # Check for trap opportunity
		BehaviorTree.Sequence.new()   # Move to strategic position
	]
	
	var trap_check = explore_root.children[0]
	trap_check.children = [
		BehaviorTree.IsOpponentNear.new(6),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.IsBombValuable.new(400.0),  # High threshold for trap quality
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	
	var strategic_move = explore_root.children[1]
	strategic_move.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	explore_tree = explore_root
	
	# HUNTING: Methodical approach, set up trap from distance
	var hunt_root = BehaviorTree.Sequence.new()
	hunt_root.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new(),
		BehaviorTree.Selector.new()
	]
	
	var trap_placement = BehaviorTree.Sequence.new()
	trap_placement.children = [
		BehaviorTree.IsOpponentNear.new(5),  # Setup from medium distance
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(2),  # Requires multiple escapes
		BehaviorTree.IsBombValuable.new(300.0),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	hunt_root.children[2].children = [trap_placement, BehaviorTree.BTNode.new()]
	hunt_tree = hunt_root
	
	# CORNERING: Perfect trap setup with timing
	var corner_root = BehaviorTree.Sequence.new()
	corner_root.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new(),
		BehaviorTree.FindStrategicPosition.new(),  # Move to secondary ambush
		BehaviorTree.MoveToTarget.new()
	]
	corner_tree = corner_root
	
	# ESCAPING: Escape to strategic ambush position
	var escape_root = BehaviorTree.MoveToSafety.new()
	escape_tree = escape_root
	
	# AMBUSHING: Hold position at chokepoint, patrol nearby
	var ambush_root = BehaviorTree.Selector.new()
	var trigger_trap = BehaviorTree.Sequence.new()
	trigger_trap.children = [
		BehaviorTree.IsOpponentNear.new(3),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	ambush_root.children = [trigger_trap]
	
	# Fallback: Patrol around ambush point
	var patrol = BehaviorTree.Sequence.new()
	patrol.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	ambush_root.children.append(patrol)
	ambush_tree = ambush_root
	
	# POWER_UP_RUSH: Grab range powerups especially
	var powerup_root = BehaviorTree.Sequence.new()
	powerup_root.children = [
		BehaviorTree.IsValuablePowerUpVisible.new(personality_weights.powerup),
		BehaviorTree.MoveToTarget.new()
	]
	powerup_rush_tree = powerup_root

func build_strategic_trees():
	"""Strategic: Chess-like play, chain setups, calculated moves, map control"""
	
	# EXPLORING: Systematic map control and resource denial
	var explore_root = BehaviorTree.Selector.new()
	explore_root.children = [
		BehaviorTree.Sequence.new(),  # Setup chain if possible
		BehaviorTree.Sequence.new(),  # Clear blocks efficiently
		BehaviorTree.Sequence.new()   # Control center
	]
	
	var chain_setup = explore_root.children[0]
	chain_setup.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(500.0),  # High value threshold for chains
		BehaviorTree.HasEscapeRoute.new(2),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	
	var block_clear = explore_root.children[1]
	block_clear.children = [
		BehaviorTree.FindBlockCluster.new(),
		BehaviorTree.MoveToTarget.new()
	]
	
	var map_control = explore_root.children[2]
	map_control.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	explore_tree = explore_root
	
	# HUNTING: Calculated pursuit with optimal bomb placement
	var hunt_root = BehaviorTree.Sequence.new()
	hunt_root.children = [
		BehaviorTree.FindNearestOpponent.new(),
		BehaviorTree.MoveToTarget.new(),
		BehaviorTree.Selector.new()
	]
	
	var calculated_bomb = BehaviorTree.Sequence.new()
	calculated_bomb.children = [
		BehaviorTree.IsOpponentNear.new(4),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(250.0),
		BehaviorTree.HasEscapeRoute.new(2),  # Always ensures safety
		BehaviorTree.PlaceBomb.new()
	]
	hunt_root.children[2].children = [calculated_bomb, BehaviorTree.BTNode.new()]
	hunt_tree = hunt_root
	
	# CORNERING: Optimal trap execution with chain potential
	var corner_root = BehaviorTree.Sequence.new()
	corner_root.children = [
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.HasEscapeRoute.new(1),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new(),
		BehaviorTree.FindStrategicPosition.new(),  # Reposition to advantage
		BehaviorTree.MoveToTarget.new()
	]
	corner_tree = corner_root
	
	# ESCAPING: Escape to optimal position
	var escape_root = BehaviorTree.MoveToSafety.new()
	escape_tree = escape_root
	
	# AMBUSHING: Strategic denial and resource control
	var ambush_root = BehaviorTree.Selector.new()
	var deny_opponent = BehaviorTree.Sequence.new()
	deny_opponent.children = [
		BehaviorTree.IsOpponentNear.new(5),
		BehaviorTree.CanPlaceBomb.new(),
		BehaviorTree.IsBombValuable.new(200.0),
		BehaviorTree.HasEscapeRoute.new(2),
		BehaviorTree.PlaceBomb.new(),
		BehaviorTree.MoveToSafety.new()
	]
	ambush_root.children = [deny_opponent]
	
	# Fallback: Control key areas
	var area_control = BehaviorTree.Sequence.new()
	area_control.children = [
		BehaviorTree.FindStrategicPosition.new(),
		BehaviorTree.MoveToTarget.new()
	]
	ambush_root.children.append(area_control)
	ambush_tree = ambush_root
	
	# POWER_UP_RUSH: Strategic powerup collection
	var powerup_root = BehaviorTree.Sequence.new()
	powerup_root.children = [
		BehaviorTree.IsValuablePowerUpVisible.new(personality_weights.powerup),
		BehaviorTree.MoveToTarget.new()
	]
	powerup_rush_tree = powerup_root

func find_ambush_position() -> Vector2i:
	# Find a choke point or strategic position
	# For now, use strategic position logic
	var game_state = observer.get_world_state()
	return find_strategic_position(last_position, game_state)

# ============================================================================
# UTILITY FUNCTIONS (Tactical decisions - kept from original)
# ============================================================================

func calculate_bomb_value(tile: Vector2i, game_state: Dictionary, ai_player: Node2D) -> float:
	var value = 0.0
	var bomb_range = ai_player.bomb_range
	
	# Use chain reaction detection for accurate value calculation
	var chain_data = observer.calculate_chain_reaction(tile, bomb_range)
	
	# Base value from blocks destroyed
	value += chain_data.blocks_destroyed * 100.0
	
	# Opponent trap value (personality-based)
	value += chain_data.players_trapped * personality_weights.trap_bonus * 0.5
	
	# Chain reaction bonus (exponential for long chains)
	if chain_data.chain_depth > 0:
		var chain_bonus = 200.0 * chain_data.chain_depth
		
		# Exponential bonus for deep chains (3+ bombs)
		if chain_data.chain_depth >= 3:
			chain_bonus += 500.0
		
		# Apply personality-specific chain setup bonus
		var chain_setup_bonus = personality_weights.get("chain_setup_bonus", 0.0)
		if chain_setup_bonus > 0.0:
			chain_bonus *= (chain_setup_bonus / 1000.0)  # Scale multiplier
		
		value += chain_bonus
	
	return value

func simulate_explosion(center: Vector2i, bomb_range: int, map: Array) -> Array:
	var cells = [center]
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for i in range(1, bomb_range + 1):
			var cell = center + dir * i
			
			if cell.y < 0 or cell.y >= map.size() or cell.x < 0 or cell.x >= map[0].size():
				break
			
			if map[cell.y][cell.x] == 1:
				break
			
			cells.append(cell)
			
			if map[cell.y][cell.x] == 2:
				break
	
	return cells

func find_nearest_opponent(from_tile: Vector2i, game_state: Dictionary, ai_player: Node2D) -> Vector2i:
	var nearest = Vector2i(-1, -1)
	var min_dist = INF
	
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		
		var player_tile = player.get_tile_position()
		var dist = abs(player_tile.x - from_tile.x) + abs(player_tile.y - from_tile.y)
		
		if dist < min_dist:
			min_dist = dist
			nearest = player_tile
	
	return nearest

func find_nearest_opponent_predicted(from_tile: Vector2i, game_state: Dictionary, ai_player: Node2D, time_ahead: float) -> Vector2i:
	"""Find nearest opponent using predicted positions"""
	var nearest = Vector2i(-1, -1)
	var min_dist = INF
	
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		
		# Get predicted position
		var predicted_pos = observer.predict_opponent_position(str(peer_id), time_ahead)
		var predicted_tile = Vector2i(
			int(floor(predicted_pos.x / Constants.TILE_SIZE)),
			int(floor(predicted_pos.y / Constants.TILE_SIZE))
		)
		
		# Validate predicted tile
		if not observer._is_tile_valid(predicted_tile):
			predicted_tile = player.get_tile_position()  # Fallback to current
		
		var dist = abs(predicted_tile.x - from_tile.x) + abs(predicted_tile.y - from_tile.y)
		
		if dist < min_dist:
			min_dist = dist
			nearest = predicted_tile
	
	return nearest

func find_valuable_block_clusters(from_tile: Vector2i, game_state: Dictionary, max_search: int) -> Array:
	var clusters = []
	var checked = {}
	
	for dy in range(-max_search, max_search + 1):
		for dx in range(-max_search, max_search + 1):
			var tile = from_tile + Vector2i(dx, dy)
			
			if not observer._is_tile_valid(tile):
				continue
			
			var tile_key = "%d,%d" % [tile.x, tile.y]
			if checked.has(tile_key):
				continue
			
			if game_state.map[tile.y][tile.x] == 2:
				var cluster_count = 1
				for adj in observer.get_adjacent_tiles(tile):
					if game_state.map[adj.y][adj.x] == 2:
						cluster_count += 1
				
				clusters.append({
					"tile": tile,
					"count": cluster_count,
					"distance": abs(dx) + abs(dy)
				})
				checked[tile_key] = true
	
	clusters.sort_custom(func(a, b): 
		return (a.count / max(1.0, a.distance)) > (b.count / max(1.0, b.distance))
	)
	
	return clusters.slice(0, 5)

func find_strategic_position(from_tile: Vector2i, game_state: Dictionary) -> Vector2i:
	var map_center = Vector2i(
		game_state.map[0].size() / 2,
		game_state.map.size() / 2
	)
	
	var best_tile = from_tile
	var min_distance = INF
	
	for dy in range(-5, 6):
		for dx in range(-5, 6):
			var tile = map_center + Vector2i(dx, dy)
			if not observer._is_tile_valid(tile) or not observer._is_tile_walkable(tile):
				continue
			
			var distance = abs(tile.x - from_tile.x) + abs(tile.y - from_tile.y)
			if distance < min_distance:
				min_distance = distance
				best_tile = tile
	
	return best_tile

func get_direction_to_tile(from_tile: Vector2i, to_tile: Vector2i, from_position: Vector2, current_time: float, game_state: Dictionary = {}) -> Vector2:
	"""Get direction using A* pathfinding with smooth waypoint-based movement"""
	if from_tile == to_tile:
		return Vector2.ZERO
	
	if game_state.is_empty():
		game_state = observer.get_world_state()

	_ensure_astar_ready(game_state, current_time)
	
	# Check if we need to replan (target changed or timer expired or path blocked)
	var should_replan = false
	if current_target_tile != to_tile:
		should_replan = true
		current_target_tile = to_tile
	elif current_time - last_replan_time > REPLAN_INTERVAL:
		should_replan = true
	elif current_path.is_empty():
		should_replan = true
	elif not _is_path_viable(from_tile):
		should_replan = true
	
	# Replan path using A*
	if should_replan:
		last_replan_time = current_time
		current_path = calculate_astar_path(from_tile, to_tile)
	
	# If no path found, fallback to direct movement
	if current_path.is_empty():
		var dx = to_tile.x - from_tile.x
		var dy = to_tile.y - from_tile.y
		return Vector2(sign(dx) if abs(dx) > 0 else 0, sign(dy) if abs(dy) > 0 else 0)
	
	# Follow waypoints smoothly
	var next_waypoint = current_path[0]
	var direction = (next_waypoint - from_position).normalized()
	
	# Check if we reached current waypoint
	if from_position.distance_to(next_waypoint) < WAYPOINT_REACH_DISTANCE:
		current_path.remove_at(0)  # Pop reached waypoint
		
		# Move to next waypoint if available
		if not current_path.is_empty():
			next_waypoint = current_path[0]
			direction = (next_waypoint - from_position).normalized()
		else:
			# Reached destination
			return Vector2.ZERO
	
	return direction

func _ensure_astar_ready(game_state: Dictionary, current_time: float) -> void:
	var obstacle_signature = _compute_obstacle_signature(game_state)
	var needs_rebuild = not astar_initialized or obstacle_signature != last_obstacle_signature
	if not needs_rebuild and astar_last_build_time >= 0.0 and current_time - astar_last_build_time > 0.5:
		needs_rebuild = true

	if needs_rebuild:
		build_astar_graph(game_state)
		astar_initialized = true
		astar_last_build_time = current_time
		last_obstacle_signature = obstacle_signature
		current_path.clear()
		current_target_tile = Vector2i(-1, -1)

	if not astar_initialized:
		return

	var danger_signature = _compute_danger_signature()
	if danger_signature != last_danger_signature:
		update_astar_for_danger(_collect_danger_tiles())
		last_danger_signature = danger_signature

func _compute_obstacle_signature(game_state: Dictionary) -> String:
	var parts := PackedStringArray()
	if game_state.has("map"):
		var map_data: Array = game_state.map
		for y in range(map_data.size()):
			var row: Array = map_data[y]
			for x in range(row.size()):
				if row[x] == 2:
					parts.append("d%d_%d" % [x, y])

	if game_state.has("bombs"):
		for bomb_id in game_state.bombs:
			var bomb = game_state.bombs[bomb_id]
			if is_instance_valid(bomb):
				var tile = bomb.get_tile_position()
				parts.append("b%d_%d" % [tile.x, tile.y])

	parts.sort()
	return ",".join(parts)

func _compute_danger_signature() -> String:
	var keys: Array = observer.danger_map.keys()
	keys.sort()
	var parts := PackedStringArray()
	for key in keys:
		parts.append(str(key))
	return ",".join(parts)

func _collect_danger_tiles() -> Array:
	var tiles: Array[Vector2i] = []
	for key in observer.danger_map.keys():
		var components = str(key).split(",")
		if components.size() != 2:
			continue
		tiles.append(Vector2i(components[0].to_int(), components[1].to_int()))
	return tiles

func _is_path_viable(from_tile: Vector2i) -> bool:
	if current_path.is_empty():
		return false
	var waypoint: Vector2 = current_path[0]
	var target_tile = Vector2i(int(floor(waypoint.x / Constants.TILE_SIZE)), int(floor(waypoint.y / Constants.TILE_SIZE)))
	return observer._is_tile_walkable(target_tile) or target_tile == from_tile

func build_astar_graph(game_state: Dictionary):
	"""Build AStar2D graph from current map state"""
	astar.clear()
	tile_to_id.clear()

	var map = game_state.get("map", [])
	if map.is_empty():
		return
	var point_id = 0

	# Add all walkable tiles as points
	for y in range(map.size()):
		var row: Array = map[y]
		for x in range(row.size()):
			var tile = Vector2i(x, y)
			if observer._is_tile_valid(tile) and observer._is_tile_walkable(tile):
				var tile_key = "%d,%d" % [x, y]
				tile_to_id[tile_key] = point_id

				# Position at tile center
				var tile_center = Vector2(
					float(x) * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
					float(y) * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
				)
				astar.add_point(point_id, tile_center)
				point_id += 1

	# Connect adjacent walkable tiles
	for y in range(map.size()):
		var row: Array = map[y]
		for x in range(row.size()):
			var tile = Vector2i(x, y)
			var tile_key = "%d,%d" % [x, y]

			if not tile_to_id.has(tile_key):
				continue

			var from_id = tile_to_id[tile_key]

			# Check 4 directions
			for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				var neighbor = tile + dir
				var neighbor_key = "%d,%d" % [neighbor.x, neighbor.y]

				if tile_to_id.has(neighbor_key):
					var to_id = tile_to_id[neighbor_key]
					# Bidirectional connection with cost = 1.0 per tile
					astar.connect_points(from_id, to_id, true)

func calculate_astar_path(from_tile: Vector2i, to_tile: Vector2i) -> Array:
	"""Calculate A* path and generate smooth waypoints at each tile center"""
	var from_key = "%d,%d" % [from_tile.x, from_tile.y]
	var to_key = "%d,%d" % [to_tile.x, to_tile.y]
	
	# Check if start/end tiles are valid
	if not tile_to_id.has(from_key) or not tile_to_id.has(to_key):
		return []
	
	var from_id = tile_to_id[from_key]
	var to_id = tile_to_id[to_key]
	
	# Get A* path (array of Vector2 positions)
	var path_points = astar.get_point_path(from_id, to_id)
	
	# Convert to array and remove first point (we're already there)
	var waypoints = []
	for i in range(1, path_points.size()):
		waypoints.append(path_points[i])
	
	return waypoints

func update_astar_for_danger(danger_tiles: Array):
	"""Update AStar2D weights to avoid dangerous tiles"""
	# Mark dangerous tiles with high cost
	for tile in danger_tiles:
		var tile_key = "%d,%d" % [tile.x, tile.y]
		if tile_to_id.has(tile_key):
			var point_id = tile_to_id[tile_key]
			# Increase cost by setting weight_scale high
			astar.set_point_weight_scale(point_id, 100.0)  # Very high cost
	
	# Reset non-dangerous tiles to normal weight
	for tile_key in tile_to_id.keys():
		var point_id = tile_to_id[tile_key]
		var coords = tile_key.split(",")
		var tile = Vector2i(int(coords[0]), int(coords[1]))
		
		if tile not in danger_tiles:
			astar.set_point_weight_scale(point_id, 1.0)  # Normal cost

func get_personality_name() -> String:
	return AIPersonality.get_personality_name(personality_type)

func get_current_state_name() -> String:
	return State.keys()[current_state]

# ============================================================================
# ADVANCED AI: Q-Learning Decision System
# ============================================================================

func decide_action_q_learning(ai_player: Node2D, current_tile: Vector2i, game_state: Dictionary, current_time: float) -> Dictionary:
	# Build state representation for Q-Learning
	var state_hash = q_learning.get_state_hash(ai_player, game_state, observer)
	
	# Choose action using epsilon-greedy
	var action_index = q_learning.choose_action(state_hash)
	
	# Update Q-values if we have a previous state-action pair
	if last_state_hash != "" and last_action != -1:
		var reward = calculate_reward(ai_player, current_tile, game_state)
		q_learning.update_q_value(last_state_hash, last_action, reward, state_hash)
	
	# Store for next update
	last_state_hash = state_hash
	last_action = action_index
	
	# Convert Q-Learning action to game action
	return convert_q_action_to_game_action(action_index, current_tile, ai_player)

func calculate_reward(ai_player: Node2D, current_tile: Vector2i, game_state: Dictionary) -> float:
	var reward = 0.0
	
	# Danger penalty
	var danger = observer.get_time_until_explosion(current_tile)
	if danger < 0.5:
		reward -= 50.0  # Critical danger
	elif danger < 1.5:
		reward -= 20.0  # High danger
	
	# Survival reward (small continuous reward)
	reward += 1.0
	
	# Power-up proximity bonus (from game state if available)
	# TODO: Add power-up tracking to game_state
	
	# Opponent proximity bonus (attacking)
	if game_state.opponents.size() > 0:
		var closest_dist = INF
		for opp in game_state.opponents:
			var dist = abs(opp.tile.x - current_tile.x) + abs(opp.tile.y - current_tile.y)
			closest_dist = min(closest_dist, dist)
		
		if closest_dist < 3:
			reward += 5.0  # Close to opponent
	
	# Block destruction bonus (detected via game state changes)
	# TODO: Track blocks destroyed between updates
	
	return reward

func convert_q_action_to_game_action(action_index: int, current_tile: Vector2i, ai_player: Node2D) -> Dictionary:
	var direction = Vector2.ZERO
	var place_bomb = false
	
	match action_index:
		0:  # MOVE_UP
			direction = Vector2(0, -1)
		1:  # MOVE_DOWN
			direction = Vector2(0, 1)
		2:  # MOVE_LEFT
			direction = Vector2(-1, 0)
		3:  # MOVE_RIGHT
			direction = Vector2(1, 0)
		4:  # PLACE_BOMB
			place_bomb = true
		5:  # WAIT
			direction = Vector2.ZERO
	
	# Validate move is safe
	var next_tile = current_tile + Vector2i(int(direction.x), int(direction.y))
	if not observer._is_tile_valid(next_tile) or not observer._is_tile_walkable(next_tile):
		direction = Vector2.ZERO  # Can't move there, stand still
	
	# Validate bomb placement
	if place_bomb:
		if not can_place_bomb_safely(current_tile, ai_player):
			place_bomb = false
	
	return {"direction": direction, "place_bomb": place_bomb}

# ============================================================================
# ADVANCED AI: MCTS Decision System
# ============================================================================

func decide_action_mcts(ai_player: Node2D, current_tile: Vector2i, game_state: Dictionary, current_time: float) -> Dictionary:
	# Create game state representation for MCTS
	var mcts_state = {
		"position": current_tile,
		"danger_map": observer.danger_map.duplicate(),
		"bombs": game_state.bombs.duplicate(),
		"opponents": game_state.opponents.duplicate(),
		"breakables": game_state.breakables.duplicate(),
		"map": game_state.map,
		"has_bomb": (ai_player.max_bombs - ai_player.bombs_placed) > 0
	}
	
	# Run MCTS search to find best action
	var action_index = mcts.search(mcts_state, observer)
	
	# Convert MCTS action to game action
	return convert_mcts_action_to_game_action(action_index, current_tile, ai_player)

func convert_mcts_action_to_game_action(action_index: int, current_tile: Vector2i, ai_player: Node2D) -> Dictionary:
	var direction = Vector2.ZERO
	var place_bomb = false
	
	match action_index:
		0:  # MOVE_UP
			direction = Vector2(0, -1)
		1:  # MOVE_DOWN
			direction = Vector2(0, 1)
		2:  # MOVE_LEFT
			direction = Vector2(-1, 0)
		3:  # MOVE_RIGHT
			direction = Vector2(1, 0)
		4:  # PLACE_BOMB
			place_bomb = true
		5:  # WAIT
			direction = Vector2.ZERO
	
	# Validate move
	var next_tile = current_tile + Vector2i(int(direction.x), int(direction.y))
	if not observer._is_tile_valid(next_tile) or not observer._is_tile_walkable(next_tile):
		direction = Vector2.ZERO
	
	# Validate bomb placement
	if place_bomb:
		if not can_place_bomb_safely(current_tile, ai_player):
			place_bomb = false
	
	return {"direction": direction, "place_bomb": place_bomb}

func can_place_bomb_safely(tile: Vector2i, ai_player: Node2D) -> bool:
	# Check if we have bombs available
	if (ai_player.max_bombs - ai_player.bombs_placed) <= 0:
		return false
	
	# Simulate bomb placement and check for escape routes
	var escape_routes = observer.count_escape_routes(tile)
	return escape_routes > 0

# ============================================================================
# TRAINING INTERFACE: Called by game_instance for Q-Learning
# ============================================================================

func on_player_death():
	"""Called when this AI player dies"""
	if q_learning and last_state_hash != "" and last_action != -1:
		q_learning.update_q_value(last_state_hash, last_action, -1000.0, "")  # Death penalty
		last_state_hash = ""
		last_action = -1

func on_player_kill():
	"""Called when this AI player kills an opponent"""
	if q_learning and last_state_hash != "" and last_action != -1:
		q_learning.update_q_value(last_state_hash, last_action, 500.0, last_state_hash)  # Kill reward

func on_block_destroyed():
	"""Called when this AI player destroys a block"""
	if q_learning and last_state_hash != "" and last_action != -1:
		q_learning.update_q_value(last_state_hash, last_action, 50.0, last_state_hash)  # Block reward

func on_match_end():
	"""Called when the match ends"""
	if q_learning:
		q_learning.end_episode()
		q_learning.save_q_table()  # Persist learning
		print("[AI Q-Learning] Episode complete. States learned: ", q_learning.get_stats()["states_learned"])

func get_learning_stats() -> Dictionary:
	"""Get Q-Learning statistics for debugging"""
	if q_learning:
		return q_learning.get_stats()
	return {}


