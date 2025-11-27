@tool
extends BTAction
class_name BTTacticalAssessment

## Evaluates the tactical situation and chooses the best attack strategy
## Implements advanced Bomberman tactics: trapping, space control, defensive positioning
## Includes HYSTERESIS to prevent rapid switching between tactics

@export var assessment_var: StringName = &"tactical_plan" ## Stores chosen tactic in blackboard
@export var min_safety_margin: float = 1.0 ## Minimum time (seconds) to maintain safety (reduced for aggression)
@export var lock_duration_ms: int = 600 ## Minimum time to stick to a tactic (reduced for faster reactions)

# Hysteresis state
var _current_tactic: String = "NONE"
var _tactic_start_time: int = 0
var _last_opponent_pos: Vector2i = Vector2i(-999, -999)

func _generate_name() -> String:
	return "TacticalAssessment → %s" % assessment_var

func _enter() -> void:
	# Don't reset state here! We want persistence across ticks
	pass

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	var personality_config = blackboard.get_var("personality_config")
	var game_instance = blackboard.get_var("game_instance")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		_set_tactic("NONE", 0)
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
	
	# Assess our current state
	var we_have_bombs = player.can_place_bomb()
	var our_range = player.bomb_range if player else 2
	var bomb_count = player.bombs_placed if player else 0
	var max_bombs = player.max_bombs if player else 10
	var trap_aggression = personality_config.get("trap_aggression", 0.5)
	var has_path_to_opponent = blackboard.get_var("path_to_opponent", true)
	
	# Assess threat matrix
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var we_are_safe = not _is_in_danger(player_tile, threat_matrix)
	var opponent_is_safe = not _is_in_danger(opponent_tile, threat_matrix)
	
	# Count available escape routes for opponent
	var opponent_escape_routes = _count_escape_routes(opponent_tile, grid_sampler, ai_manager)
	
	# === TACTICAL DECISION TREE ===
	
	var new_tactic = "NONE"
	var new_priority = 0
	
	# Check if opponent is near a corner (prime trap opportunity)
	var opponent_near_corner = _is_near_corner(opponent_tile, grid_sampler)
	var opponent_in_corridor = _is_in_corridor(opponent_tile, grid_sampler)
	var opponent_velocity: Vector2 = nearest.get("velocity", Vector2.ZERO)
	var opponent_moving = opponent_velocity.length() > 10.0
	
	# Check for kickable bombs (for KICK_SNIPE tactic)
	var has_kickable_bomb = player.has_bomb_kicker and _has_kickable_bomb_toward(player_tile, opponent_tile, game_instance, grid_sampler)
	
	# Check for throw opportunity (for POWER_THROW tactic)
	var can_throw = player.has_power_glove and _has_throw_opportunity(player_tile, opponent_tile, game_instance, grid_sampler, player)
	
	# Debug POWER_THROW detection
	if distance >= 3 and we_are_safe and not has_kickable_bomb:
		print("[TacticalDebug] POWER_THROW check: can_throw=%s distance=%d safe=%s glove=%s" % [can_throw, distance, we_are_safe, player.has_power_glove])
	
	# PRIORITY 0: KICK SNIPE - kick a bomb toward opponent (instant attack!)
	if has_kickable_bomb and distance <= 8 and we_are_safe:
		new_tactic = "KICK_SNIPE"
		new_priority = 13  # Highest priority - immediate kill opportunity!
	
	# PRIORITY 0.3: POWER THROW - lob a bomb at opponent in clear corridor!
	elif can_throw and distance >= 3 and we_are_safe:
		new_tactic = "POWER_THROW"
		new_priority = 12  # Very high - ranged attack!
		print("[TacticalAssessment] 🎯 POWER_THROW selected! can_throw=%s dist=%d safe=%s" % [can_throw, distance, we_are_safe])
	
	# PRIORITY 0.5: CORNER TRAP - opponent backed into corner (LETHAL)
	# Changed from 'if' to 'elif' to not override POWER_THROW
	elif opponent_escape_routes == 1 and opponent_near_corner and we_have_bombs and distance <= 5:
		new_tactic = "CORNER_TRAP"
		new_priority = 12
	
	# PRIORITY 1: BODY BLOCK - we're adjacent to opponent's only escape, block with body then bomb!
	elif opponent_escape_routes == 1 and distance <= 2 and we_are_safe:
		var escape_tile = _get_opponent_escape(opponent_tile, grid_sampler, threat_matrix)
		if escape_tile != Vector2i.ZERO:
			var dist_to_escape = grid_sampler.get_manhattan_distance(player_tile, escape_tile)
			if dist_to_escape <= 1: # We're on or adjacent to their escape
				new_tactic = "BODY_BLOCK"
				new_priority = 11
	
	# PRIORITY 1.5: One-Tile Trap (The Kiss) - opponent has 1 escape route
	elif opponent_escape_routes == 1 and we_have_bombs and distance <= 5:
		new_tactic = "ONE_TILE_TRAP"
		new_priority = 11
	
	# PRIORITY 2: DOUBLE BOMB PRESSURE - we have 2+ bombs, opponent in corridor
	elif opponent_in_corridor and (max_bombs - bomb_count) >= 2 and distance <= 4 and we_are_safe:
		new_tactic = "DOUBLE_BOMB"
		new_priority = 10
	
	# PRIORITY 3: Choke Point Trap - opponent has 2 escape routes, we can block one
	elif opponent_escape_routes == 2 and we_have_bombs and distance <= 6:
		new_tactic = "CHOKE_POINT"
		new_priority = 9
	
	# PRIORITY 4: TUNNEL PRESSURE - opponent in corridor, cut them off
	elif opponent_in_corridor and we_have_bombs and distance <= 5 and we_are_safe:
		new_tactic = "TUNNEL_PRESSURE"
		new_priority = 8
	
	# PRIORITY 5: Setup Trap - opponent has 3 escape routes, proactively block one
	elif opponent_escape_routes == 3 and we_have_bombs and distance <= 7:
		new_tactic = "CHOKE_POINT"
		new_priority = 7
	
	# PRIORITY 6: Space Denial - opponent moving toward us or we're close
	elif distance <= our_range + 2 and we_have_bombs and we_are_safe:
		new_tactic = "SPACE_DENIAL"
		new_priority = 6
	
	# PRIORITY 6.5: STUTTER TRAP - fake approach to bait opponent, then cut off retreat
	elif distance >= 3 and distance <= 6 and we_have_bombs and we_are_safe and opponent_moving:
		# Check if we can predict their path
		var predicted_pos = _predict_position(opponent_tile, opponent_velocity, 3)
		if predicted_pos != opponent_tile and _is_near_corner(predicted_pos, grid_sampler):
			new_tactic = "STUTTER_TRAP"
			new_priority = 6
	
	# PRIORITY 7: ITEM HUNTER TRAP - predict where opponent will go for powerups
	elif opponent_moving and distance <= 8 and we_have_bombs:
		new_tactic = "ITEM_HUNTER_TRAP"
		new_priority = 5
	
	# PRIORITY 8: Defensive Positioning - we're in danger
	elif not we_are_safe:
		new_tactic = "DEFENSIVE_RETREAT"
		new_priority = 100
	
	# PRIORITY 9: Patient Ambush - opponent is in danger, let them die
	elif not opponent_is_safe and distance > 2:
		new_tactic = "WAIT_FOR_DEATH"
		new_priority = 4
	
	# PRIORITY 10: Aggressive Chase - we have bomb advantage
	elif (max_bombs - bomb_count) >= 1 and distance <= 10 and we_are_safe:
		new_tactic = "AGGRESSIVE_CHASE"
		new_priority = 3
	
	# PRIORITY 11: Predictive Intercept - standard chase
	elif distance <= 15 and we_have_bombs:
		new_tactic = "PREDICTIVE_INTERCEPT"
		new_priority = 2
	
	# PRIORITY 12: FARM TOWARD OPPONENT - blocked by soft blocks, destroy them to reach enemy
	elif not has_path_to_opponent and distance <= 20 and we_have_bombs and we_are_safe:
		new_tactic = "FARM_TOWARD_OPPONENT"
		new_priority = 2
	
	# DEFAULT: No good tactic available
	else:
		new_tactic = "NONE"
		new_priority = 0
	
	# === HYSTERESIS & LOCKING ===
	var current_time = Time.get_ticks_msec()
	var time_since_switch = current_time - _tactic_start_time
	
	# Determine if we should switch
	var should_switch = false
	
	# 1. Critical override (Danger)
	if new_priority >= 100:
		should_switch = true
		
	# 2. Current tactic became invalid (NONE)
	elif _current_tactic == "NONE" or new_tactic == "NONE":
		should_switch = true # Always allow switching to/from NONE to avoid getting stuck doing nothing
		
	# 3. Lock expired AND new tactic is better or different
	elif time_since_switch > lock_duration_ms:
		if new_tactic != _current_tactic:
			# Only switch if priority is higher or equal (prevent downgrading unless necessary)
			# Or if the old tactic is no longer applicable (logic above handles that implicitly via if/else chain)
			should_switch = true
			
	# 4. New tactic is SIGNIFICANTLY better (Priority Jump)
	# e.g. We were chasing (5), but now we can Trap (10) -> Switch immediately
	elif new_priority > (_get_priority(_current_tactic) + 2):
		should_switch = true
		print("[TacticalAssessment] ⚡ PRIORITY JUMP: %s (%d) -> %s (%d)" % [_current_tactic, _get_priority(_current_tactic), new_tactic, new_priority])
	
	if should_switch:
		if new_tactic != _current_tactic:
			print("[TacticalAssessment] 🔄 SWITCH: %s -> %s (Priority: %d)" % [_current_tactic, new_tactic, new_priority])
			_set_tactic(new_tactic, current_time)
	else:
		# Stick to current tactic
		# Update priority in blackboard to match current (even if we didn't switch logic)
		blackboard.set_var("tactical_priority", _get_priority(_current_tactic))
		# print("[TacticalAssessment] 🔒 LOCKED: Keeping %s (Time: %dms)" % [_current_tactic, time_since_switch])
	
	# Store assessment in blackboard
	blackboard.set_var(assessment_var, _current_tactic)
	blackboard.set_var("opponent_escape_routes", opponent_escape_routes)
	blackboard.set_var("opponent_distance", distance)
	
	return SUCCESS if _current_tactic != "NONE" else FAILURE

func _set_tactic(tactic: String, time: int) -> void:
	_current_tactic = tactic
	_tactic_start_time = time
	blackboard.set_var("tactical_priority", _get_priority(tactic))

func _get_priority(tactic: String) -> int:
	match tactic:
		"DEFENSIVE_RETREAT": return 100
		"CORNER_TRAP": return 12
		"BODY_BLOCK": return 11
		"ONE_TILE_TRAP": return 11
		"DOUBLE_BOMB": return 10
		"CHOKE_POINT": return 9
		"TUNNEL_PRESSURE": return 8
		"STUTTER_TRAP": return 6
		"SPACE_DENIAL": return 6
		"ITEM_HUNTER_TRAP": return 5
		"WAIT_FOR_DEATH": return 4
		"AGGRESSIVE_CHASE": return 3
		"PREDICTIVE_INTERCEPT": return 2
		"FARM_TOWARD_OPPONENT": return 2
		_: return 0

func _is_in_danger(tile: Vector2i, threat_matrix: Dictionary) -> bool:
	var key = "%d,%d" % [tile.x, tile.y]
	return threat_matrix.has(key)

func _count_escape_routes(tile: Vector2i, grid_sampler, ai_manager) -> int:
	"""Count number of safe adjacent tiles opponent can move to"""
	var safe_routes = 0
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = tile + dir
		
		# Must be walkable
		if not grid_sampler.is_tile_walkable(check_tile):
			continue
		
		# Must not be in danger
		var key = "%d,%d" % [check_tile.x, check_tile.y]
		if threat_matrix.has(key):
			continue
		
		safe_routes += 1
	
	return safe_routes

func _is_near_corner(tile: Vector2i, grid_sampler) -> bool:
	"""Check if tile is near a corner (2+ adjacent walls)"""
	var wall_count = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check = tile + dir
		if not grid_sampler.is_tile_walkable(check):
			wall_count += 1
	return wall_count >= 2

func _is_in_corridor(tile: Vector2i, grid_sampler) -> bool:
	"""Check if tile is in a corridor (walls on opposite sides)"""
	var horizontal_blocked = (not grid_sampler.is_tile_walkable(tile + Vector2i.LEFT) and 
							  not grid_sampler.is_tile_walkable(tile + Vector2i.RIGHT))
	var vertical_blocked = (not grid_sampler.is_tile_walkable(tile + Vector2i.UP) and 
							not grid_sampler.is_tile_walkable(tile + Vector2i.DOWN))
	return horizontal_blocked or vertical_blocked

func _get_opponent_escape(tile: Vector2i, grid_sampler, threat_matrix: Dictionary) -> Vector2i:
	"""Get the opponent's single escape route tile. Returns ZERO if multiple or none."""
	var escapes: Array[Vector2i] = []
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check = tile + dir
		if not grid_sampler.is_tile_walkable(check):
			continue
		var key = "%d,%d" % [check.x, check.y]
		if threat_matrix.has(key):
			continue
		escapes.append(check)
	
	return escapes[0] if escapes.size() == 1 else Vector2i.ZERO

func _predict_position(tile: Vector2i, velocity: Vector2, tiles_ahead: int) -> Vector2i:
	"""Predict where opponent will be based on velocity."""
	if velocity.length() < 10.0:
		return tile
	
	var direction = velocity.normalized()
	var predicted = tile
	
	for i in range(tiles_ahead):
		if abs(direction.x) > abs(direction.y):
			predicted += Vector2i(sign(direction.x), 0)
		else:
			predicted += Vector2i(0, sign(direction.y))
	
	return predicted

func _has_kickable_bomb_toward(player_tile: Vector2i, target_tile: Vector2i, game_instance, grid_sampler) -> bool:
	"""Check if there's a bomb adjacent to player that can be kicked toward target"""
	if game_instance == null or not "bombs" in game_instance:
		return false
	
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	
	for dir in directions:
		var bomb_tile = player_tile + dir
		
		# Check for bomb at this tile
		var found_bomb = false
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			# Check bomb_state instead of is_kicked (BombState.KICKED = 3)
			var is_kickable = bomb.bomb_state == 0  # PLANTED state
			if is_instance_valid(bomb) and not bomb.has_exploded and is_kickable:
				if bomb.get_tile_position() == bomb_tile:
					found_bomb = true
					break
		
		if not found_bomb:
			continue
		
		# Check if kicking this direction would move toward target
		var to_target = Vector2(target_tile - bomb_tile)
		if to_target.length() < 0.1:
			continue  # Already at target
		
		var kick_dir = Vector2(dir)
		var alignment = kick_dir.normalized().dot(to_target.normalized())
		
		if alignment > 0.5:
			# This bomb could be kicked toward the target
			# Verify path is clear
			var check_tile = bomb_tile + dir
			var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
			if tile_type == 0:  # Clear path
				return true
	
	return false

func _has_throw_opportunity(player_tile: Vector2i, target_tile: Vector2i, game_instance, grid_sampler, player) -> bool:
	"""Check if player can throw a bomb toward target (can place bomb or has bomb at feet or is carrying)"""
	if player == null or not player.has_power_glove:
		return false
	
	var can_throw = false
	var reason = "unknown"
	
	# Check if already carrying a bomb - best case!
	if player.is_carrying_bomb():
		can_throw = _check_throw_path_clear(player_tile, target_tile, game_instance, grid_sampler)
		reason = "carrying_bomb" if can_throw else "no_clear_path_while_carrying"
	else:
		# Check if there's a bomb at player's position to pick up
		var has_bomb_at_feet = false
		if game_instance != null and "bombs" in game_instance:
			for bomb_id in game_instance.bombs:
				var bomb = game_instance.bombs[bomb_id]
				if is_instance_valid(bomb) and not bomb.has_exploded:
					if bomb.get_tile_position() == player_tile and bomb.bomb_state == 0:  # PLANTED
						has_bomb_at_feet = true
						break
		
		if has_bomb_at_feet:
			can_throw = _check_throw_path_clear(player_tile, target_tile, game_instance, grid_sampler)
			reason = "bomb_at_feet" if can_throw else "no_clear_path_bomb_at_feet"
		# NEW: Can we place a bomb to throw?
		elif player.can_place_bomb():
			can_throw = _check_throw_path_clear(player_tile, target_tile, game_instance, grid_sampler)
			reason = "can_place_bomb" if can_throw else "no_clear_path_can_place"
		else:
			reason = "no_bombs_available"
	
	# Debug log occasionally
	if can_throw:
		print("[ThrowCheck] tile=%s target=%s result=%s reason=%s" % [player_tile, target_tile, can_throw, reason])
	
	return can_throw

func _check_throw_path_clear(player_tile: Vector2i, target_tile: Vector2i, game_instance, grid_sampler) -> bool:
	"""Check if there's a clear corridor for throwing toward target"""
	var delta = target_tile - player_tile
	
	# Determine primary throw direction
	var throw_dir: Vector2i
	if abs(delta.x) > abs(delta.y):
		throw_dir = Vector2i(1 if delta.x > 0 else -1, 0)
	else:
		throw_dir = Vector2i(0, 1 if delta.y > 0 else -1)
	
	# Check if path is clear for at least 3 tiles
	for i in range(1, 4):
		var check_tile = player_tile + throw_dir * i
		var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
		if tile_type != 0:  # Not empty floor
			if i < 2:  # Need at least 2 tiles of travel
				return false
			break
	
	return true
