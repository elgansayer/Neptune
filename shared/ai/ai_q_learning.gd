extends RefCounted
class_name AIQLearning

# Q-Learning Implementation for Bomberman AI
# Learns optimal action values through reinforcement learning
# State: (my_position, nearest_opponent_position, bomb_positions, danger_level)
# Actions: UP, DOWN, LEFT, RIGHT, PLACE_BOMB, WAIT

const LEARNING_RATE = 0.1
const DISCOUNT_FACTOR = 0.95
const EPSILON = 0.1  # Exploration rate
const Q_TABLE_FILE = "user://q_table.json"

enum Action {
	MOVE_UP,
	MOVE_DOWN,
	MOVE_LEFT,
	MOVE_RIGHT,
	PLACE_BOMB,
	WAIT
}

# Q-Table: Dictionary mapping state_hash -> [action_values]
var q_table: Dictionary = {}
var episode_history: Array = []  # For batch learning
var training_mode: bool = false
var total_rewards: float = 0.0
var episodes_completed: int = 0

func _init():
	load_q_table()

# ============================================================================
# STATE REPRESENTATION
# ============================================================================

func get_state_hash(ai_player: Node2D, game_state: Dictionary, observer) -> String:
	"""
	Create a discrete state representation for Q-learning
	Simplifies continuous state space into buckets
	"""
	var my_tile = ai_player.get_tile_position()
	
	# Quantize position to 3x3 grid regions
	var map_width = game_state.map[0].size()
	var map_height = game_state.map.size()
	var region_x = int(my_tile.x / (map_width / 3.0))
	var region_y = int(my_tile.y / (map_height / 3.0))
	
	# Find nearest opponent (quantized)
	var nearest_opponent_region = Vector2i(-1, -1)
	var min_dist = INF
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		var opponent_tile = player.get_tile_position()
		var dist = abs(opponent_tile.x - my_tile.x) + abs(opponent_tile.y - my_tile.y)
		if dist < min_dist:
			min_dist = dist
			var opp_region_x = int(opponent_tile.x / (map_width / 3.0))
			var opp_region_y = int(opponent_tile.y / (map_height / 3.0))
			nearest_opponent_region = Vector2i(opp_region_x, opp_region_y)
	
	# Danger level (0-3: safe, low, medium, high)
	var danger = observer.get_time_until_explosion(my_tile)
	var danger_level = 0
	if danger < 0.5:
		danger_level = 3  # Critical
	elif danger < 1.5:
		danger_level = 2  # High
	elif danger < 3.0:
		danger_level = 1  # Medium
	else:
		danger_level = 0  # Safe
	
	# Number of nearby bombs (0-2+)
	var nearby_bombs = 0
	for bomb_pos in game_state.get("bombs", []):
		var dist = abs(bomb_pos.x - my_tile.x) + abs(bomb_pos.y - my_tile.y)
		if dist <= 3:
			nearby_bombs += 1
	nearby_bombs = min(nearby_bombs, 2)
	
	# Has bomb available
	var has_bomb = 1 if ai_player.can_place_bomb() else 0
	
	# Create state hash
	return "%d,%d|%d,%d|%d|%d|%d" % [
		region_x, region_y,
		nearest_opponent_region.x, nearest_opponent_region.y,
		danger_level,
		nearby_bombs,
		has_bomb
	]

# ============================================================================
# Q-LEARNING CORE
# ============================================================================

func get_q_value(state_hash: String, action: Action) -> float:
	"""Get Q-value for state-action pair"""
	if not q_table.has(state_hash):
		q_table[state_hash] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # 6 actions
	return q_table[state_hash][action]

func set_q_value(state_hash: String, action: Action, value: float):
	"""Set Q-value for state-action pair"""
	if not q_table.has(state_hash):
		q_table[state_hash] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
	q_table[state_hash][action] = value

func get_best_action(state_hash: String) -> Action:
	"""Get action with highest Q-value (exploitation)"""
	if not q_table.has(state_hash):
		return Action.values()[randi() % Action.size()]
	
	var q_values = q_table[state_hash]
	var best_action = 0
	var best_value = q_values[0]
	
	for i in range(1, q_values.size()):
		if q_values[i] > best_value:
			best_value = q_values[i]
			best_action = i
	
	return best_action

func choose_action(state_hash: String) -> Action:
	"""Choose action using epsilon-greedy policy"""
	if training_mode and randf() < EPSILON:
		# Exploration: random action
		return Action.values()[randi() % Action.size()]
	else:
		# Exploitation: best known action
		return get_best_action(state_hash)

func update_q_value(state_hash: String, action: Action, reward: float, next_state_hash: String):
	"""Q-Learning update rule: Q(s,a) = Q(s,a) + α[r + γ max Q(s',a') - Q(s,a)]"""
	var current_q = get_q_value(state_hash, action)
	
	# Find max Q-value for next state
	var max_next_q = -INF
	if q_table.has(next_state_hash):
		for q_val in q_table[next_state_hash]:
			max_next_q = max(max_next_q, q_val)
	else:
		max_next_q = 0.0
	
	# Q-learning update
	var new_q = current_q + LEARNING_RATE * (reward + DISCOUNT_FACTOR * max_next_q - current_q)
	set_q_value(state_hash, action, new_q)
	
	total_rewards += reward

# ============================================================================
# REWARD FUNCTION
# ============================================================================

func calculate_reward(ai_player: Node2D, game_state: Dictionary, observer, action: Action, result: Dictionary) -> float:
	"""
	Calculate reward for taking an action
	Positive rewards: kills, survival, blocks destroyed
	Negative rewards: death, damage taken, wasted moves
	"""
	var reward = 0.0
	
	# Survival reward (per frame alive)
	reward += 0.1
	
	# Death penalty
	if not ai_player.is_alive:
		reward -= 1000.0
		return reward
	
	# Kill reward
	var kills_this_frame = result.get("kills", 0)
	reward += kills_this_frame * 500.0
	
	# Block destruction reward
	var blocks_destroyed = result.get("blocks_destroyed", 0)
	reward += blocks_destroyed * 50.0
	
	# Danger penalty (being in danger is bad)
	var my_tile = ai_player.get_tile_position()
	var danger = observer.get_time_until_explosion(my_tile)
	if danger < 0.5:
		reward -= 100.0  # Critical danger
	elif danger < 1.5:
		reward -= 20.0   # High danger
	
	# Escape reward (moving away from danger)
	if action in [Action.MOVE_UP, Action.MOVE_DOWN, Action.MOVE_LEFT, Action.MOVE_RIGHT]:
		if danger < 2.0:
			# Check if movement was toward safety
			var safe_tiles = observer.find_nearest_safe_tiles(my_tile, 5)
			if not safe_tiles.is_empty():
				# Reward moving toward safety
				reward += 30.0
	
	# Strategic bomb placement reward
	if action == Action.PLACE_BOMB:
		if result.get("bomb_placed", false):
			var bomb_value = result.get("bomb_value", 0.0)
			reward += bomb_value * 0.5  # Scale down bomb value
			
			# Penalty if no escape route
			var escape_routes = observer.count_escape_routes(my_tile)
			if escape_routes == 0:
				reward -= 200.0  # Trapped yourself
		else:
			reward -= 5.0  # Wasted action (couldn't place bomb)
	
	# Idle penalty
	if action == Action.WAIT:
		reward -= 2.0
	
	# Proximity to opponent reward (for aggressive behavior)
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		if player == ai_player:
			continue
		var opponent_tile = player.get_tile_position()
		var dist = abs(opponent_tile.x - my_tile.x) + abs(opponent_tile.y - my_tile.y)
		if dist <= 3:
			reward += 10.0  # Close to opponent (good for trapping)
	
	return reward

# ============================================================================
# ACTION EXECUTION
# ============================================================================

func action_to_direction(action: Action) -> Vector2:
	"""Convert action enum to movement direction"""
	match action:
		Action.MOVE_UP:
			return Vector2.UP
		Action.MOVE_DOWN:
			return Vector2.DOWN
		Action.MOVE_LEFT:
			return Vector2.LEFT
		Action.MOVE_RIGHT:
			return Vector2.RIGHT
		_:
			return Vector2.ZERO

func execute_action(action: Action, ai_player: Node2D, controller) -> Dictionary:
	"""
	Execute chosen action and return result info
	Returns: {"direction": Vector2, "place_bomb": bool, "bomb_placed": bool, "bomb_value": float}
	"""
	var result = {
		"direction": Vector2.ZERO,
		"place_bomb": false,
		"bomb_placed": false,
		"bomb_value": 0.0
	}
	
	match action:
		Action.MOVE_UP, Action.MOVE_DOWN, Action.MOVE_LEFT, Action.MOVE_RIGHT:
			result.direction = action_to_direction(action)
		
		Action.PLACE_BOMB:
			if ai_player.can_place_bomb():
				result.place_bomb = true
				result.bomb_placed = true
				# Calculate bomb value for reward
				var game_state = controller.observer.get_world_state()
				var my_tile = ai_player.get_tile_position()
				result.bomb_value = controller.calculate_bomb_value(my_tile, game_state, ai_player)
		
		Action.WAIT:
			pass  # Do nothing
	
	return result

# ============================================================================
# TRAINING INTERFACE
# ============================================================================

func start_training():
	"""Enable training mode (epsilon-greedy exploration)"""
	training_mode = true
	episode_history.clear()
	print("[Q-Learning] Training mode enabled")

func stop_training():
	"""Disable training mode (pure exploitation)"""
	training_mode = false
	print("[Q-Learning] Training mode disabled. Episodes: %d, Total Reward: %.2f" % [episodes_completed, total_rewards])

func record_step(state_hash: String, action: Action, reward: float, next_state_hash: String):
	"""Record a step for batch learning"""
	episode_history.append({
		"state": state_hash,
		"action": action,
		"reward": reward,
		"next_state": next_state_hash
	})

func end_episode(final_reward: float = 0.0):
	"""Process episode history with final reward"""
	if episode_history.is_empty():
		return
	
	# Apply final reward to last step
	if episode_history.size() > 0:
		episode_history[-1].reward += final_reward
	
	# Update Q-values for entire episode
	for step in episode_history:
		update_q_value(step.state, step.action, step.reward, step.next_state)
	
	episode_history.clear()
	episodes_completed += 1
	
	# Save periodically
	if episodes_completed % 10 == 0:
		save_q_table()
		print("[Q-Learning] Episode %d completed. Q-table saved." % episodes_completed)

# ============================================================================
# PERSISTENCE
# ============================================================================

func save_q_table():
	"""Save Q-table to disk"""
	var file = FileAccess.open(Q_TABLE_FILE, FileAccess.WRITE)
	if file:
		var data = {
			"q_table": q_table,
			"episodes": episodes_completed,
			"total_rewards": total_rewards
		}
		file.store_string(JSON.stringify(data))
		file.close()
		print("[Q-Learning] Q-table saved: %d states" % q_table.size())

func load_q_table():
	"""Load Q-table from disk"""
	if not FileAccess.file_exists(Q_TABLE_FILE):
		print("[Q-Learning] No saved Q-table found. Starting fresh.")
		return
	
	var file = FileAccess.open(Q_TABLE_FILE, FileAccess.READ)
	if file:
		var json = JSON.new()
		var parse_result = json.parse(file.get_as_text())
		if parse_result == OK:
			var data = json.data
			q_table = data.get("q_table", {})
			episodes_completed = data.get("episodes", 0)
			total_rewards = data.get("total_rewards", 0.0)
			print("[Q-Learning] Q-table loaded: %d states, %d episodes" % [q_table.size(), episodes_completed])
		file.close()

func get_stats() -> Dictionary:
	"""Get training statistics"""
	return {
		"states_learned": q_table.size(),
		"episodes": episodes_completed,
		"total_rewards": total_rewards,
		"avg_reward": total_rewards / max(1, episodes_completed),
		"training_mode": training_mode
	}
