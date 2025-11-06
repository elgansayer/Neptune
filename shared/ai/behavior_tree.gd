extends RefCounted
class_name BehaviorTree

# Needed for tile-size calculations in prediction checks
const Constants = preload("res://shared/constants.gd")

# Lightweight Behavior Tree implementation for strategic AI planning
# Used by AIBotController for multi-step tactical sequences

enum Status {
	SUCCESS,   # Node completed successfully
	FAILURE,   # Node failed to complete
	RUNNING    # Node is still executing (multi-frame)
}

# Base class for all BT nodes
class BTNode extends RefCounted:
	var name: String = "BTNode"
	
	func execute(context: Dictionary) -> int:
		return Status.SUCCESS
	
	func reset():
		pass

# ============================================================================
# COMPOSITE NODES - Control flow for child nodes
# ============================================================================

# Sequence: Execute children in order, fail if any fails
class Sequence extends BTNode:
	var children: Array = []
	var current_child: int = 0
	
	func _init():
		name = "Sequence"
	
	func execute(context: Dictionary) -> int:
		while current_child < children.size():
			var result = children[current_child].execute(context)
			
			if result == Status.FAILURE:
				current_child = 0
				return Status.FAILURE
			
			if result == Status.RUNNING:
				return Status.RUNNING
			
			current_child += 1
		
		current_child = 0
		return Status.SUCCESS
	
	func reset():
		current_child = 0
		for child in children:
			child.reset()

# Selector: Try children in order, succeed if any succeeds (fallback)
class Selector extends BTNode:
	var children: Array = []
	var current_child: int = 0
	
	func _init():
		name = "Selector"
	
	func execute(context: Dictionary) -> int:
		while current_child < children.size():
			var result = children[current_child].execute(context)
			
			if result == Status.SUCCESS:
				current_child = 0
				return Status.SUCCESS
			
			if result == Status.RUNNING:
				return Status.RUNNING
			
			current_child += 1
		
		current_child = 0
		return Status.FAILURE
	
	func reset():
		current_child = 0
		for child in children:
			child.reset()

# Parallel: Execute all children, succeed if all succeed
class Parallel extends BTNode:
	var children: Array = []
	
	func _init():
		name = "Parallel"
	
	func execute(context: Dictionary) -> int:
		var all_success = true
		var any_running = false
		
		for child in children:
			var result = child.execute(context)
			if result == Status.FAILURE:
				return Status.FAILURE
			if result == Status.RUNNING:
				any_running = true
			if result != Status.SUCCESS:
				all_success = false
		
		if any_running:
			return Status.RUNNING
		return Status.SUCCESS if all_success else Status.FAILURE

# ============================================================================
# DECORATOR NODES - Modify child behavior
# ============================================================================

# Inverter: Flip child's success/failure
class Inverter extends BTNode:
	var child: BTNode
	
	func _init():
		name = "Inverter"
	
	func execute(context: Dictionary) -> int:
		var result = child.execute(context)
		if result == Status.SUCCESS:
			return Status.FAILURE
		if result == Status.FAILURE:
			return Status.SUCCESS
		return Status.RUNNING

# Repeater: Repeat child N times
class Repeater extends BTNode:
	var child: BTNode
	var repeat_count: int = 3
	var current_count: int = 0
	
	func _init(count: int = 3):
		name = "Repeater"
		repeat_count = count
	
	func execute(context: Dictionary) -> int:
		while current_count < repeat_count:
			var result = child.execute(context)
			if result == Status.RUNNING:
				return Status.RUNNING
			if result == Status.FAILURE:
				current_count = 0
				return Status.FAILURE
			current_count += 1
		
		current_count = 0
		return Status.SUCCESS

# Cooldown: Only allow child to execute after cooldown expires
class Cooldown extends BTNode:
	var child: BTNode
	var cooldown_time: float = 1.0
	var last_execution: float = -999.0
	
	func _init(cooldown: float = 1.0):
		name = "Cooldown"
		cooldown_time = cooldown
	
	func execute(context: Dictionary) -> int:
		var current_time = Time.get_ticks_msec() / 1000.0
		if current_time - last_execution < cooldown_time:
			return Status.FAILURE
		
		last_execution = current_time
		return child.execute(context)

# ============================================================================
# CONDITION NODES - Check game state
# ============================================================================

# Check if AI is in danger from explosions
class IsInDanger extends BTNode:
	var danger_threshold: float = 1.5
	
	func _init(threshold: float = 1.5):
		name = "IsInDanger"
		danger_threshold = threshold
	
	func execute(context: Dictionary) -> int:
		var observer = context.observer
		var my_tile = context.my_tile
		var danger = observer.get_time_until_explosion(my_tile)
		return Status.SUCCESS if danger < danger_threshold else Status.FAILURE

# Check if an opponent is nearby
class IsOpponentNear extends BTNode:
	var max_distance: int = 5
	
	func _init(distance: int = 5):
		name = "IsOpponentNear"
		max_distance = distance
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var game_state = context.game_state
		var my_tile = context.my_tile
		
		for peer_id in game_state.players:
			var player = game_state.players[peer_id]
			if player == context.ai_player:
				continue
			
			var player_tile = player.get_tile_position()
			var dist = abs(player_tile.x - my_tile.x) + abs(player_tile.y - my_tile.y)
			
			if dist <= max_distance:
				context.target_opponent = player
				context.target_tile = player_tile
				return Status.SUCCESS
		
		return Status.FAILURE

# Check if an opponent is predicted to be nearby (velocity-based)
class IsOpponentPredictedNear extends BTNode:
	var max_distance: int = 5
	var prediction_time: float = 2.0
	
	func _init(distance: int = 5, time_ahead: float = 2.0):
		name = "IsOpponentPredictedNear"
		max_distance = distance
		prediction_time = time_ahead
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var observer = context.observer
		var game_state = context.game_state
		var my_tile = context.my_tile
		
		for peer_id in game_state.players:
			var player = game_state.players[peer_id]
			if player == context.ai_player:
				continue
			
			# Get predicted position
			var predicted_pos = observer.predict_opponent_position(str(peer_id), prediction_time)
			var predicted_tile = Vector2i(
				int(floor(predicted_pos.x / Constants.TILE_SIZE)),
				int(floor(predicted_pos.y / Constants.TILE_SIZE))
			)
			
			# Validate predicted tile
			if not observer._is_tile_valid(predicted_tile):
				predicted_tile = player.get_tile_position()
			
			var dist = abs(predicted_tile.x - my_tile.x) + abs(predicted_tile.y - my_tile.y)
			
			if dist <= max_distance:
				context.target_opponent = player
				context.target_tile = predicted_tile
				return Status.SUCCESS
		
		return Status.FAILURE

# Check if AI has escape routes from current position
class HasEscapeRoute extends BTNode:
	var min_routes: int = 1
	
	func _init(min_count: int = 1):
		name = "HasEscapeRoute"
		min_routes = min_count
	
	func execute(context: Dictionary) -> int:
		var observer = context.observer
		var my_tile = context.my_tile
		var routes = observer.count_escape_routes(my_tile)
		return Status.SUCCESS if routes >= min_routes else Status.FAILURE

# Check if AI is aggressive personality
class IsAggressive extends BTNode:
	func _init():
		name = "IsAggressive"
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		return Status.SUCCESS if controller.personality_weights.aggression > 400 else Status.FAILURE

# Check if target is cornered (few escape routes)
class IsTargetCornered extends BTNode:
	func _init():
		name = "IsTargetCornered"
	
	func execute(context: Dictionary) -> int:
		if not context.has("target_tile"):
			return Status.FAILURE
		
		var observer = context.observer
		var routes = observer.count_escape_routes(context.target_tile)
		return Status.SUCCESS if routes <= 1 else Status.FAILURE

# Check if bomb would be valuable at current position
class IsBombValuable extends BTNode:
	var min_value: float = 250.0
	
	func _init(threshold: float = 250.0):
		name = "IsBombValuable"
		min_value = threshold
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var value = controller.calculate_bomb_value(
			context.my_tile,
			context.game_state,
			context.ai_player
		)
		return Status.SUCCESS if value >= min_value else Status.FAILURE

# Check if AI can place a bomb
class CanPlaceBomb extends BTNode:
	func _init():
		name = "CanPlaceBomb"
	
	func execute(context: Dictionary) -> int:
		return Status.SUCCESS if context.ai_player.can_place_bomb() else Status.FAILURE

# Check if valuable powerup is visible
class IsValuablePowerUpVisible extends BTNode:
	var min_value: float = 300.0
	
	func _init(threshold: float = 300.0):
		name = "IsValuablePowerUpVisible"
		min_value = threshold
	
	func execute(context: Dictionary) -> int:
		var observer = context.observer
		var controller = context.controller
		var powerup_weights = controller.personality_weights.get("powerup_utility_weights", {})
		
		var valuable_powerup = observer.find_valuable_powerup(context.my_tile, powerup_weights)
		
		if valuable_powerup.value >= min_value:
			context.target_tile = valuable_powerup.tile
			context.target_powerup = valuable_powerup
			return Status.SUCCESS
		
		return Status.FAILURE

# ============================================================================
# ACTION NODES - Perform actions
# ============================================================================

# Move toward a target tile
class MoveToTarget extends BTNode:
	func _init():
		name = "MoveToTarget"
	
	func execute(context: Dictionary) -> int:
		if not context.has("target_tile"):
			return Status.FAILURE
		
		var controller = context.controller
		var ai_player = context.ai_player
		var direction = controller.get_direction_to_tile(
			context.my_tile,
			context.target_tile,
			ai_player.position,
			context.current_time
		)
		
		context.action_result.direction = direction
		return Status.SUCCESS

# Move toward nearest safe tile (escape)
class MoveToSafety extends BTNode:
	func _init():
		name = "MoveToSafety"
	
	func execute(context: Dictionary) -> int:
		var observer = context.observer
		var safe_tiles = observer.find_nearest_safe_tiles(context.my_tile, 8)
		
		if safe_tiles.is_empty():
			# Random escape if no safe tiles found
			context.action_result.direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
			return Status.SUCCESS
		
		var controller = context.controller
		var ai_player = context.ai_player
		var nearest_safe = safe_tiles[0].tile
		context.action_result.direction = controller.get_direction_to_tile(
			context.my_tile,
			nearest_safe,
			ai_player.position,
			context.current_time
		)
		return Status.SUCCESS

# Place a bomb at current position
class PlaceBomb extends BTNode:
	func _init():
		name = "PlaceBomb"
	
	func execute(context: Dictionary) -> int:
		context.action_result.place_bomb = true
		return Status.SUCCESS

# Find nearest opponent and set as target
class FindNearestOpponent extends BTNode:
	func _init():
		name = "FindNearestOpponent"
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var target_tile = controller.find_nearest_opponent(
			context.my_tile,
			context.game_state,
			context.ai_player
		)
		
		if target_tile == Vector2i(-1, -1):
			return Status.FAILURE
		
		context.target_tile = target_tile
		return Status.SUCCESS

# Find valuable block clusters and set as target
class FindBlockCluster extends BTNode:
	func _init():
		name = "FindBlockCluster"
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var clusters = controller.find_valuable_block_clusters(
			context.my_tile,
			context.game_state,
			15
		)
		
		if clusters.is_empty():
			return Status.FAILURE
		
		context.target_tile = clusters[0].tile
		return Status.SUCCESS

# Find strategic position (e.g., map center) and set as target
class FindStrategicPosition extends BTNode:
	func _init():
		name = "FindStrategicPosition"
	
	func execute(context: Dictionary) -> int:
		var controller = context.controller
		var strategic_tile = controller.find_strategic_position(
			context.my_tile,
			context.game_state
		)
		
		context.target_tile = strategic_tile
		return Status.SUCCESS

# Wait/idle for a moment
class Wait extends BTNode:
	var wait_time: float = 0.5
	var elapsed: float = 0.0
	
	func _init(duration: float = 0.5):
		name = "Wait"
		wait_time = duration
	
	func execute(context: Dictionary) -> int:
		elapsed += context.get("delta_time", 0.016)
		
		if elapsed >= wait_time:
			elapsed = 0.0
			return Status.SUCCESS
		
		return Status.RUNNING
	
	func reset():
		elapsed = 0.0

# Set random exploration direction
class ExploreRandomly extends BTNode:
	var explore_timer: float = 0.0
	var current_direction: Vector2 = Vector2.ZERO
	
	func _init():
		name = "ExploreRandomly"
	
	func execute(context: Dictionary) -> int:
		explore_timer += context.get("delta_time", 0.016)
		
		# Change direction every 2 seconds
		if explore_timer > 2.0:
			current_direction = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
			explore_timer = 0.0
		
		context.action_result.direction = current_direction
		return Status.SUCCESS
