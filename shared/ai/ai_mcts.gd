extends RefCounted
class_name AIMCTS

# Monte Carlo Tree Search Implementation for Bomberman AI
# Simulates future game states to find optimal moves
# Uses UCB1 (Upper Confidence Bound) for tree policy

const EXPLORATION_CONSTANT = 1.41  # sqrt(2) for UCB1
const MAX_SIMULATION_DEPTH = 10    # How many moves to simulate
const MAX_SIMULATIONS = 50         # Reduced from 100 for performance
const SIMULATION_TIME_BUDGET = 0.04  # 40ms time budget (reduced from 50ms)
const EARLY_TERMINATION_THRESHOLD = 0.6  # Stop if best action has 60% of visits

enum Action {
	MOVE_UP,
	MOVE_DOWN,
	MOVE_LEFT,
	MOVE_RIGHT,
	PLACE_BOMB,
	WAIT
}

class MCTSNode:
	var state_hash: String
	var parent: MCTSNode = null
	var children: Array = []  # Array of MCTSNode
	var action: Action = Action.WAIT
	var visits: int = 0
	var total_reward: float = 0.0
	var untried_actions: Array = []
	
	func _init(state: String, parent_node: MCTSNode = null, taken_action: Action = Action.WAIT):
		state_hash = state
		parent = parent_node
		action = taken_action
		# Initialize with all possible actions
		untried_actions = Action.values().duplicate()
	
	func is_fully_expanded() -> bool:
		return untried_actions.is_empty()
	
	func get_max_children() -> int:
		"""Progressive widening: limit children based on visits"""
		return max(1, int(ceil(sqrt(visits))))
	
	func can_expand() -> bool:
		"""Check if we can expand (progressive widening)"""
		return children.size() < get_max_children() and not untried_actions.is_empty()
	
	func is_terminal() -> bool:
		# Terminal if no children and fully expanded (dead end)
		return children.is_empty() and is_fully_expanded()
	
	func get_ucb1_value(total_parent_visits: int) -> float:
		"""Calculate UCB1 value for this node"""
		if visits == 0:
			return INF  # Unvisited nodes have highest priority
		
		var exploitation = total_reward / float(visits)
		var exploration = EXPLORATION_CONSTANT * sqrt(log(total_parent_visits) / float(visits))
		return exploitation + exploration
	
	func best_child() -> MCTSNode:
		"""Select child with highest UCB1 value"""
		var best_node: MCTSNode = null
		var best_value = -INF
		
		for child in children:
			var value = child.get_ucb1_value(visits)
			if value > best_value:
				best_value = value
				best_node = child
		
		return best_node

# Root of the MCTS tree
var root: MCTSNode = null
var controller = null  # Reference to AIBotController
var observer = null    # Reference to AIObserver
var state_cache: Dictionary = {}  # Cache for state evaluations: hash -> {value, visits}

func _init(ai_controller, ai_observer):
	controller = ai_controller
	observer = ai_observer

# ============================================================================
# MCTS MAIN ALGORITHM
# ============================================================================

func search(ai_player: Node2D, game_state: Dictionary, time_budget: float = SIMULATION_TIME_BUDGET) -> Action:
	"""
	Main MCTS search algorithm with optimizations
	Returns: Best action to take
	"""
	var start_time = Time.get_ticks_msec() / 1000.0
	var current_state_hash = get_state_hash(ai_player, game_state)
	
	# Clear state cache for new decision (prevent stale data)
	state_cache.clear()
	
	# Create or reuse root node
	if root == null or root.state_hash != current_state_hash:
		root = MCTSNode.new(current_state_hash)
	
	var simulations = 0
	var time_check_interval = 10  # Check time every 10 simulations
	
	# Run simulations until time budget exhausted or max simulations reached
	while simulations < MAX_SIMULATIONS:
		# Periodic time budget check (every 10 simulations for performance)
		if simulations % time_check_interval == 0:
			var current_time = Time.get_ticks_msec() / 1000.0
			if current_time - start_time > time_budget:
				break
		
		# Early termination: Check if best action has >60% of visits
		if simulations > 10 and _check_early_termination():
			if OS.is_debug_build():
				print("[MCTS] Early termination at %d simulations" % simulations)
			break
		
		# 1. SELECTION: Traverse tree using UCB1
		var node = select(root)
		
		# 2. EXPANSION: Add new child node (with progressive widening)
		if node.can_expand() and node.visits > 0:
			node = expand(node, ai_player, game_state)
		
		# 3. SIMULATION: Run random playout from this node (check cache first)
		var reward = simulate_with_cache(node, ai_player, game_state)
		
		# 4. BACKPROPAGATION: Update node statistics
		backpropagate(node, reward)
		
		simulations += 1
	
	# Return best action from root
	var best_child = root.best_child()
	if best_child:
		if OS.is_debug_build():
			print("[MCTS] Ran %d simulations. Best action: %s (visits: %d, avg reward: %.2f)" % [
				simulations,
				Action.keys()[best_child.action],
				best_child.visits,
				best_child.total_reward / max(1, best_child.visits)
			])
		return best_child.action
	
	# Fallback to random if no children
	return Action.values()[randi() % Action.size()]

func _check_early_termination() -> bool:
	"""Check if best action has sufficient confidence to terminate early"""
	if root.children.is_empty():
		return false
	
	# Find child with most visits
	var max_visits = 0
	for child in root.children:
		if child.visits > max_visits:
			max_visits = child.visits
	
	# Check if best action has >60% of total visits
	var visit_ratio = float(max_visits) / float(root.visits) if root.visits > 0 else 0.0
	return visit_ratio > EARLY_TERMINATION_THRESHOLD

# ============================================================================
# MCTS PHASES
# ============================================================================

func select(node: MCTSNode) -> MCTSNode:
	"""Selection phase: Traverse tree using UCB1 until we find unexpanded node"""
	while not node.untried_actions.is_empty() == false and not node.children.is_empty():
		node = node.best_child()
		if node == null:
			break
	return node

func expand(node: MCTSNode, ai_player: Node2D, game_state: Dictionary) -> MCTSNode:
	"""Expansion phase: Add a new child node for an untried action"""
	if node.untried_actions.is_empty():
		return node
	
	# Pick random untried action
	var action_idx = randi() % node.untried_actions.size()
	var action = node.untried_actions[action_idx]
	node.untried_actions.remove_at(action_idx)
	
	# Simulate taking this action
	var next_state = simulate_action(ai_player, game_state, action)
	var next_state_hash = get_state_hash_from_simulated(next_state)
	
	# Create new child node
	var child = MCTSNode.new(next_state_hash, node, action)
	node.children.append(child)
	
	return child

func simulate(node: MCTSNode, ai_player: Node2D, game_state: Dictionary) -> float:
	"""
	Simulation phase: Random playout from this node until terminal state
	Returns: Accumulated reward
	"""
	var simulated_state = game_state.duplicate(true)
	var simulated_player = duplicate_player_state(ai_player)
	var depth = 0
	var total_reward = 0.0
	
	while depth < MAX_SIMULATION_DEPTH:
		# Random action
		var action = Action.values()[randi() % Action.size()]
		
		# Simulate action and get reward
		var result = simulate_action(simulated_player, simulated_state, action)
		var reward = calculate_immediate_reward(simulated_player, result)
		total_reward += reward * pow(0.95, depth)  # Discount future rewards
		
		# Check if terminal (dead)
		if not result.is_alive:
			break
		
		# Update state
		simulated_state = result.next_state
		simulated_player = result.next_player
		depth += 1
	
	return total_reward

func simulate_with_cache(node: MCTSNode, ai_player: Node2D, game_state: Dictionary) -> float:
	"""Simulation with state caching for repeated evaluations"""
	# Check cache first
	if state_cache.has(node.state_hash):
		var cached = state_cache[node.state_hash]
		cached.visits += 1
		return cached.value
	
	# Run simulation
	var reward = simulate(node, ai_player, game_state)
	
	# Cache result
	state_cache[node.state_hash] = {"value": reward, "visits": 1}
	
	return reward

func backpropagate(node: MCTSNode, reward: float):
	"""Backpropagation phase: Update node statistics up the tree"""
	while node != null:
		node.visits += 1
		node.total_reward += reward
		node = node.parent

# ============================================================================
# GAME STATE SIMULATION
# ============================================================================

func get_state_hash(ai_player: Node2D, game_state: Dictionary) -> String:
	"""Create hash representing current game state"""
	var my_tile = ai_player.get_tile_position()
	
	# Simplified state: position + danger + opponent positions
	var state_parts = ["%d,%d" % [my_tile.x, my_tile.y]]
	
	# Add danger level
	var danger = observer.get_time_until_explosion(my_tile)
	state_parts.append(str(int(danger * 10)))
	
	# Add nearest opponent
	var opponent_tile = controller.find_nearest_opponent(my_tile, game_state, ai_player)
	if opponent_tile != Vector2i(-1, -1):
		state_parts.append("%d,%d" % [opponent_tile.x, opponent_tile.y])
	
	return "|".join(state_parts)

func get_state_hash_from_simulated(simulated_state: Dictionary) -> String:
	"""Create hash from simulated state"""
	var pos = simulated_state.get("position", Vector2i(0, 0))
	var danger = simulated_state.get("danger", 10.0)
	var opponent_pos = simulated_state.get("opponent_position", Vector2i(-1, -1))
	
	var parts = ["%d,%d" % [pos.x, pos.y], str(int(danger * 10))]
	if opponent_pos != Vector2i(-1, -1):
		parts.append("%d,%d" % [opponent_pos.x, opponent_pos.y])
	
	return "|".join(parts)

func simulate_action(ai_player, game_state: Dictionary, action: Action) -> Dictionary:
	"""
	Simulate taking an action and return resulting state
	Returns: {"position": Vector2i, "danger": float, "is_alive": bool, "opponent_position": Vector2i, "next_state": Dictionary, "next_player": Dictionary}
	"""
	var result = {
		"position": ai_player.get_tile_position() if typeof(ai_player) == TYPE_OBJECT else ai_player.position,
		"danger": 10.0,
		"is_alive": true,
		"opponent_position": Vector2i(-1, -1),
		"next_state": game_state.duplicate(true),
		"next_player": duplicate_player_state(ai_player)
	}
	
	var current_pos = result.position
	
	# Simulate movement
	match action:
		Action.MOVE_UP:
			current_pos.y -= 1
		Action.MOVE_DOWN:
			current_pos.y += 1
		Action.MOVE_LEFT:
			current_pos.x -= 1
		Action.MOVE_RIGHT:
			current_pos.x += 1
		Action.PLACE_BOMB:
			# Simulate bomb placement (danger increases nearby)
			result.danger = 1.0  # Immediate danger from own bomb
		Action.WAIT:
			pass
	
	# Clamp to map bounds
	if typeof(game_state.get("map")) == TYPE_ARRAY and not game_state.map.is_empty():
		current_pos.x = clamp(current_pos.x, 0, game_state.map[0].size() - 1)
		current_pos.y = clamp(current_pos.y, 0, game_state.map.size() - 1)
	
	result.position = current_pos
	result.next_player.position = current_pos
	
	# Check if position is valid
	if typeof(game_state.get("map")) == TYPE_ARRAY and not game_state.map.is_empty():
		if game_state.map[current_pos.y][current_pos.x] == 1:  # Wall
			result.is_alive = false
			return result
	
	# Update danger level
	if typeof(observer) == TYPE_OBJECT:
		result.danger = observer.get_time_until_explosion(current_pos)
	
	# Check if in danger
	if result.danger < 0.5:
		result.is_alive = false  # Would die to explosion
	
	return result

func duplicate_player_state(ai_player) -> Dictionary:
	"""Create a simplified copy of player state for simulation"""
	if typeof(ai_player) == TYPE_DICTIONARY:
		return ai_player.duplicate(true)
	
	return {
		"position": ai_player.get_tile_position() if ai_player.has_method("get_tile_position") else Vector2i(0, 0),
		"bomb_count": ai_player.bomb_count if "bomb_count" in ai_player else 1,
		"bomb_range": ai_player.bomb_range if "bomb_range" in ai_player else 2
	}

# ============================================================================
# REWARD CALCULATION
# ============================================================================

func calculate_immediate_reward(simulated_player, result: Dictionary) -> float:
	"""Calculate reward for a simulated action"""
	var reward = 0.0
	
	# Survival reward
	if result.is_alive:
		reward += 1.0
	else:
		reward -= 100.0  # Death penalty
		return reward
	
	# Danger penalty
	var danger = result.get("danger", 10.0)
	if danger < 0.5:
		reward -= 50.0
	elif danger < 1.5:
		reward -= 10.0
	elif danger > 3.0:
		reward += 5.0  # Reward being safe
	
	# Movement reward (prefer action over inaction)
	reward += 0.5
	
	return reward

# ============================================================================
# TREE MANAGEMENT
# ============================================================================

func reset_tree():
	"""Clear the MCTS tree (call when game state changes dramatically)"""
	root = null

func get_stats() -> Dictionary:
	"""Get MCTS statistics"""
	if root == null:
		return {
			"root_visits": 0,
			"children_count": 0,
			"avg_child_visits": 0.0
		}
	
	var total_child_visits = 0
	for child in root.children:
		total_child_visits += child.visits
	
	return {
		"root_visits": root.visits,
		"children_count": root.children.size(),
		"avg_child_visits": total_child_visits / max(1, root.children.size()),
		"best_action": Action.keys()[root.best_child().action] if root.children.size() > 0 else "NONE"
	}
