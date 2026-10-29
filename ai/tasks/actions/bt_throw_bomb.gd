@tool
extends BTAction
class_name BTThrowBomb

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## Throws a bomb at an opponent using Power Glove
## State machine: PLACE -> PICKUP -> THROW
## Used with POWER_THROW tactic for aggressive ranged attacks

enum ThrowState { IDLE, PLACING, PICKING_UP, THROWING }

## Throw mechanics:
## - Bombs travel exactly 2 tiles in the throw direction
## - If tile 1 or 2 is blocked, bomb bounces and lands on last free tile
## - Bomb explodes with player's bomb_range (1-3+ tiles)
## - Only throw if the landing position + explosion range can hit an opponent

const THROW_RANGE: int = 2 ## Server constant: bombs travel 2 tiles when thrown

@export var max_bounce_checks: int = 3 ## Max bounces to simulate

var _state: ThrowState = ThrowState.IDLE
var _throw_dir: Vector2 = Vector2.ZERO
var _attempts: int = 0

func _generate_name() -> String:
	return "ThrowBomb (range=%d, bounces=%d)" % [THROW_RANGE, max_bounce_checks]

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
				blackboard.set_var("last_throw_time", SimulationTime.milliseconds(blackboard))
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
	"""Find the best direction to throw a bomb toward an opponent.
	
	Simulates actual throw mechanics:
	- Bomb travels 2 tiles in throw direction
	- Bounces off obstacles (walls, blocks, bombs, players)
	- Lands on last free tile before obstacle OR at tile 2 if path is clear
	- Then explodes with player's bomb_range
	"""
	if not opponent_tracker:
		return {}
	
	var bomb_range = player.bomb_range if player else 2
	
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
		
		# Simulate where the bomb will actually land
		var landing_info = _simulate_throw_landing(player_tile, dir_i, game_instance)
		
		if landing_info.landing_tile == player_tile:
			continue  # Bomb would land on us - don't throw!
		
		# Check if any opponent is in blast range of the landing spot
		var hit_info = _check_opponents_in_blast_zone(landing_info.landing_tile, bomb_range, opponent_tracker, player, game_instance)
		
		if hit_info.is_empty():
			continue  # No opponent threatened by this throw
		
		# Score this throw
		var score = _score_throw_v2(landing_info, hit_info, bomb_range)
		
		if score > best_score:
			best_score = score
			best_throw = {
				"direction": dir,
				"landing_tile": landing_info.landing_tile,
				"target_tile": hit_info.opponent_tile,
				"distance": landing_info.tiles_traveled,
				"bounces": landing_info.bounces,
				"score": score
			}
			print("[BTThrowBomb] Evaluated %s: land=%s, target=%s, bounces=%d, score=%.2f" % [
				dir_data.name, landing_info.landing_tile, hit_info.opponent_tile, landing_info.bounces, score])
	
	return best_throw

func _simulate_throw_landing(start_tile: Vector2i, direction: Vector2i, game_instance) -> Dictionary:
	"""Simulate where a thrown bomb will land.
	
	Returns:
		landing_tile: The tile where bomb will land
		tiles_traveled: How many tiles it moved
		bounces: Number of bounces (0 = clear path)
	"""
	var current_tile = start_tile
	var tiles_traveled = 0
	var bounces = 0
	var last_free_tile = start_tile
	
	# Bomb travels up to THROW_RANGE tiles
	for i in range(1, THROW_RANGE + 1):
		var check_tile = current_tile + direction * i
		
		# Check if this tile is blocked
		var is_blocked = _is_tile_blocked(check_tile, game_instance)
		
		if is_blocked:
			# Bomb bounces - lands on last free tile
			bounces += 1
			break
		else:
			# Tile is free - bomb can land here
			tiles_traveled = i
			last_free_tile = check_tile
	
	# If no bounces, bomb lands at max range (tile 2)
	var landing_tile = last_free_tile if tiles_traveled > 0 else start_tile
	
	return {
		"landing_tile": landing_tile,
		"tiles_traveled": tiles_traveled,
		"bounces": bounces
	}

func _is_tile_blocked(tile: Vector2i, game_instance) -> bool:
	"""Check if a tile would block a thrown bomb."""
	if not game_instance:
		return true
	
	# Check tile type (walls, blocks)
	if game_instance.has_method("get_tile_type"):
		var tile_type = game_instance.get_tile_type(tile)
		if tile_type != 0:  # Not empty floor
			return true
	
	# Check for bombs at this tile
	if "bombs" in game_instance:
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == tile:
					return true
	
	# Check for players at this tile (bombs bounce off players too)
	if "players" in game_instance:
		for player_id in game_instance.players:
			var p = game_instance.players[player_id]
			if is_instance_valid(p) and not p.is_dead:
				if p.get_tile_position() == tile:
					return true
	
	return false

func _check_opponents_in_blast_zone(landing_tile: Vector2i, bomb_range: int, opponent_tracker, player, game_instance) -> Dictionary:
	"""Check if any opponent is within explosion range of the landing tile."""
	var player_peer_id = player.peer_id if player else 0
	
	# Get all opponents
	var opponents = opponent_tracker.get_all_opponents(player_peer_id) if opponent_tracker.has_method("get_all_opponents") else []
	
	# Fallback: use nearest opponent
	if opponents.is_empty():
		var nearest = opponent_tracker.get_nearest_opponent(Vector2(landing_tile * 16), player_peer_id)
		if nearest and not nearest.is_empty():
			opponents = [nearest]
	
	var best_hit: Dictionary = {}
	var best_distance = 999
	
	for opp in opponents:
		var opp_tile: Vector2i = opp.get("tile", Vector2i(-99, -99))
		
		# Check if opponent is in blast zone (cross pattern)
		var hit_distance = _get_blast_hit_distance(landing_tile, opp_tile, bomb_range, game_instance)
		
		if hit_distance >= 0 and hit_distance < best_distance:
			best_distance = hit_distance
			best_hit = {
				"opponent_tile": opp_tile,
				"hit_distance": hit_distance,
				"direct_hit": hit_distance == 0
			}
	
	return best_hit

func _get_blast_hit_distance(bomb_tile: Vector2i, target_tile: Vector2i, bomb_range: int, game_instance) -> int:
	"""Check if target_tile is hit by explosion at bomb_tile. Returns distance (0=center) or -1 if no hit."""
	
	# Direct hit (same tile)
	if bomb_tile == target_tile:
		return 0
	
	# Check cross pattern
	var delta = target_tile - bomb_tile
	
	# Must be in a cardinal direction (not diagonal)
	if delta.x != 0 and delta.y != 0:
		return -1  # Diagonal - no hit
	
	var distance = abs(delta.x) + abs(delta.y)
	
	if distance > bomb_range:
		return -1  # Too far
	
	# Check if there's a wall blocking the explosion
	var dir = Vector2i(sign(delta.x), sign(delta.y))
	for i in range(1, distance + 1):
		var check_tile = bomb_tile + dir * i
		if game_instance and game_instance.has_method("get_tile_type"):
			var tile_type = game_instance.get_tile_type(check_tile)
			if tile_type == 1:  # Hard wall blocks explosion
				return -1
	
	return distance

func _score_throw_v2(landing_info: Dictionary, hit_info: Dictionary, bomb_range: int) -> float:
	"""Score how good this throw would be."""
	var score = 0.0
	
	# Base score for having a valid target
	score += 0.3
	
	# Bonus for direct hit (opponent on landing tile)
	if hit_info.get("direct_hit", false):
		score += 0.5
	
	# Bonus for close hit distance (within explosion range)
	var hit_dist = hit_info.get("hit_distance", 99)
	if hit_dist <= 1:
		score += 0.4
	elif hit_dist <= 2:
		score += 0.2
	elif hit_dist <= bomb_range:
		score += 0.1
	
	# Slight penalty for bounces (less predictable)
	var bounces = landing_info.get("bounces", 0)
	if bounces > 0:
		score -= 0.1 * bounces
	
	# Bonus for bomb traveling full distance (more predictable)
	var traveled = landing_info.get("tiles_traveled", 0)
	if traveled >= THROW_RANGE:
		score += 0.1
	
	return score

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
	"""Check if there's a bomb at the given tile"""
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
			return true
	return false
