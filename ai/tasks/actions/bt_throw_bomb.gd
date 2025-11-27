@tool
extends BTAction
class_name BTThrowBomb

## Throws a bomb at an opponent using Power Glove
## State machine: PLACE -> PICKUP -> THROW
## Used with POWER_THROW tactic for aggressive ranged attacks

enum ThrowState { IDLE, PLACING, PICKING_UP, THROWING }

@export var min_throw_distance: int = 3 ## Minimum tiles for a worthwhile throw
@export var max_throw_distance: int = 8 ## Maximum tiles to consider for throw

var _state: ThrowState = ThrowState.IDLE
var _throw_dir: Vector2 = Vector2.ZERO
var _attempts: int = 0

func _generate_name() -> String:
	return "ThrowBomb (range=%d-%d)" % [min_throw_distance, max_throw_distance]

func _enter() -> void:
	_state = ThrowState.IDLE
	_throw_dir = Vector2.ZERO
	_attempts = 0

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	
	if not player or not game_instance:
		return FAILURE
	
	# Must have power glove
	if not player.has_power_glove:
		return FAILURE
	
	# Only execute if the tactic is POWER_THROW
	var tactic = blackboard.get_var("tactical_plan", "NONE")
	if tactic != "POWER_THROW":
		return FAILURE  # Let other actions handle non-throw tactics
	
	# Get throw direction from tactical execution
	var throw_direction = blackboard.get_var("throw_direction", Vector2.ZERO)
	if throw_direction != Vector2.ZERO:
		_throw_dir = throw_direction
	
	var player_tile = player.get_tile_position()
	
	# STATE MACHINE
	match _state:
		ThrowState.IDLE:
			# Check if already carrying - go straight to throw
			if player.is_carrying_bomb():
				_state = ThrowState.THROWING
				return RUNNING
			
			# Check if there's a bomb at our position to pick up
			var bomb_at_feet = _find_bomb_at_tile(player_tile, game_instance)
			if bomb_at_feet:
				_state = ThrowState.PICKING_UP
				return RUNNING
			
			# Need to place a bomb first
			if player.can_place_bomb():
				_state = ThrowState.PLACING
				return RUNNING
			else:
				return FAILURE  # Can't place bomb
		
		ThrowState.PLACING:
			# Place the bomb - AI bots call game_instance directly
			if player.can_place_bomb() and not _bomb_at_position(player_tile, game_instance):
				game_instance.place_bomb(player)
				print("[BTThrowBomb] 💣 Placed bomb for throwing")
				_state = ThrowState.PICKING_UP
				_attempts = 0
				return RUNNING
			else:
				_attempts += 1
				if _attempts > 5:
					return FAILURE
				return RUNNING
		
		ThrowState.PICKING_UP:
			# Find bomb at our position and pick it up
			var bomb = _find_bomb_at_tile(player_tile, game_instance)
			if bomb == null:
				_attempts += 1
				if _attempts > 10:
					return FAILURE  # Bomb disappeared or moved
				return RUNNING
			
			if player.try_pickup_bomb(bomb):
				print("[BTThrowBomb] 🎯 Picked up bomb")
				_state = ThrowState.THROWING
				return RUNNING
			else:
				_attempts += 1
				if _attempts > 10:
					return FAILURE
				return RUNNING
		
		ThrowState.THROWING:
			if not player.is_carrying_bomb():
				return FAILURE  # Lost the bomb somehow
			
			# Determine throw direction
			if _throw_dir == Vector2.ZERO:
				# Get from tactical execution or find best
				_throw_dir = blackboard.get_var("throw_direction", Vector2.ZERO)
				if _throw_dir == Vector2.ZERO:
					var opponent_tracker = blackboard.get_var("opponent_tracker")
					var best_throw = _find_best_throw_target(player, player_tile, game_instance, opponent_tracker)
					if best_throw.is_empty():
						# No good throw - just throw in last move direction
						_throw_dir = player.last_move_direction if player.last_move_direction != Vector2.ZERO else Vector2.RIGHT
					else:
						_throw_dir = best_throw.direction
			
			# Face the throw direction
			player.last_move_direction = _throw_dir
			
			# THROW!
			if player.throw_carried_bomb():
				print("[BTThrowBomb] 💣 THROW! Direction %s" % _throw_dir)
				blackboard.set_var("last_throw_time", Time.get_ticks_msec())
				# Clear the tactic so we don't repeat
				blackboard.set_var("tactical_plan", "NONE")
				return SUCCESS
			
			_attempts += 1
			if _attempts > 5:
				return FAILURE
			return RUNNING
	
	return FAILURE

func _find_bomb_at_tile(tile: Vector2i, game_instance) -> Node:
	"""Find a bomb at the specified tile that can be picked up"""
	if not "bombs" in game_instance:
		return null
	
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		
		if bomb.get_tile_position() != tile:
			continue
		
		# Only pick up planted bombs (not already kicked/thrown)
		if bomb.bomb_state != 0:  # 0 = PLANTED
			continue
		
		return bomb
	
	return null

func _find_best_throw_target(player, player_tile: Vector2i, game_instance, opponent_tracker) -> Dictionary:
	"""Find the best direction to throw a bomb toward an opponent"""
	if not opponent_tracker:
		return {}
	
	var directions = [
		{"dir": Vector2(1, 0), "name": "right"},
		{"dir": Vector2(-1, 0), "name": "left"},
		{"dir": Vector2(0, 1), "name": "down"},
		{"dir": Vector2(0, -1), "name": "up"}
	]
	
	var best_throw: Dictionary = {}
	var best_score = -1.0
	
	for dir_data in directions:
		var dir: Vector2 = dir_data.dir
		var dir_i = Vector2i(int(dir.x), int(dir.y))
		
		# Check how far the bomb would travel in this direction
		var travel_info = _calculate_throw_trajectory(player_tile, dir_i, game_instance)
		
		if travel_info.distance < min_throw_distance:
			continue  # Won't travel far enough
		
		if travel_info.distance > max_throw_distance:
			travel_info.distance = max_throw_distance  # Cap for scoring
		
		# Check if there's an opponent along this corridor or at landing spot
		var opponent_info = _check_opponent_in_throw_path(player_tile, dir_i, travel_info.distance, opponent_tracker, player)
		
		if opponent_info.is_empty():
			continue  # No opponent threatened by this throw
		
		# Score this throw
		var score = _score_throw(travel_info, opponent_info)
		
		if score > best_score:
			best_score = score
			best_throw = {
				"direction": dir,
				"target_tile": opponent_info.tile,
				"distance": travel_info.distance,
				"score": score
			}
	
	return best_throw

func _calculate_throw_trajectory(start_tile: Vector2i, direction: Vector2i, game_instance) -> Dictionary:
	"""Calculate how far a thrown bomb would travel"""
	var distance = 0
	var landing_tile = start_tile
	
	for i in range(1, max_throw_distance + 2):
		var check_tile = start_tile + direction * i
		
		# Check if tile is passable (empty floor)
		var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
		
		if tile_type != 0:  # Not empty floor - bomb stops at previous tile
			break
		
		distance = i
		landing_tile = check_tile
	
	return {
		"distance": distance,
		"landing_tile": landing_tile
	}

func _check_opponent_in_throw_path(start_tile: Vector2i, direction: Vector2i, max_dist: int, opponent_tracker, player) -> Dictionary:
	"""Check if there's an opponent in the throw path or near landing zone"""
	var player_peer_id = player.peer_id if player else 0
	
	# Get bomb explosion range
	var bomb_range = player.bomb_range if player else 2
	
	# Check each tile along the path
	for i in range(1, max_dist + 1):
		var check_tile = start_tile + direction * i
		
		var nearest = opponent_tracker.get_nearest_opponent(Vector2(check_tile * 16), player_peer_id)
		if nearest and not nearest.is_empty():
			var opp_tile: Vector2i = nearest.get("tile", Vector2i(-99, -99))
			
			# Is opponent directly on the path?
			if opp_tile == check_tile:
				return {"tile": opp_tile, "on_path": true, "distance": i}
			
			# Is opponent within explosion range of where bomb lands?
			var dist_from_path = abs(opp_tile.x - check_tile.x) + abs(opp_tile.y - check_tile.y)
			if dist_from_path <= bomb_range and i >= min_throw_distance:
				return {"tile": opp_tile, "on_path": false, "distance": i, "splash_dist": dist_from_path}
	
	return {}

func _score_throw(travel_info: Dictionary, opponent_info: Dictionary) -> float:
	"""Score how good this throw would be"""
	var score = 0.0
	
	# Base score for having a target
	score += 0.5
	
	# Bonus for opponent being directly on the path
	if opponent_info.get("on_path", false):
		score += 0.5
	
	# Bonus for closer distance (faster hit)
	var distance = travel_info.distance
	if distance <= 4:
		score += 0.3
	elif distance <= 6:
		score += 0.15
	
	# Bonus for splash damage potential
	var splash_dist = opponent_info.get("splash_dist", 99)
	if splash_dist <= 1:
		score += 0.2
	elif splash_dist <= 2:
		score += 0.1
	
	return score

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
	"""Check if there's a bomb at the given tile"""
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
			return true
	return false
