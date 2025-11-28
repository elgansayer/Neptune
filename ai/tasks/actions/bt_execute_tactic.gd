@tool
extends BTAction
class_name BTExecuteTactic

## Executes the chosen tactic from tactical assessment
## Implements specific attack patterns for each strategy

@export var tactic_var: StringName = &"tactical_plan"  ## Blackboard var with chosen tactic
@export var target_var: StringName = &"tactic_target_cell"  ## Output: where to move/place bomb

func _generate_name() -> String:
	return "ExecuteTactic (%s)" % tactic_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var tactic = blackboard.get_var(tactic_var, "NONE")
	if tactic == "NONE":
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var target_tile: Vector2i = player_tile
	var game_instance = blackboard.get_var("game_instance")
	
	# Execute the chosen tactic
	match tactic:
		"KICK_SNIPE":
			# Special tactic: kick a bomb toward opponent!
			var kick_result = _execute_kick_snipe(player_tile, opponent_tile, grid_sampler, game_instance, player)
			if kick_result.has("kick_direction"):
				# Store kick info for BTKickBomb to use
				blackboard.set_var("kick_target", opponent_tile)
				blackboard.set_var("kick_direction", kick_result.kick_direction)
				print("[ExecuteTactic] ⚽ KICK_SNIPE: Kicking toward %s" % opponent_tile)
				return SUCCESS  # BTKickBomb will handle the actual kick
			return FAILURE
		
		"POWER_THROW":
			# Special tactic: throw a bomb at opponent!
			var throw_result = _execute_power_throw(player_tile, opponent_tile, grid_sampler, game_instance, player)
			if throw_result.has("throw_direction"):
				# Store throw info for BTThrowBomb to use
				blackboard.set_var("throw_target", opponent_tile)
				blackboard.set_var("throw_direction", throw_result.throw_direction)
				# Set target to current position - no movement needed for throw
				blackboard.set_var(target_var, player_tile)
				print("[ExecuteTactic] 💣 POWER_THROW: Throwing toward %s from %s" % [opponent_tile, player_tile])
				return SUCCESS  # BTThrowBomb will handle the actual throw
			return FAILURE
		
		"CORNER_TRAP":
			target_tile = _execute_corner_trap(player_tile, opponent_tile, grid_sampler, ai_manager, player)
		
		"BODY_BLOCK":
			target_tile = _execute_body_block(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"ONE_TILE_TRAP":
			target_tile = _execute_one_tile_trap(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"DOUBLE_BOMB":
			target_tile = _execute_double_bomb(player_tile, opponent_tile, grid_sampler, ai_manager, player)
		
		"CHOKE_POINT":
			target_tile = _execute_choke_point(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"TUNNEL_PRESSURE":
			target_tile = _execute_tunnel_pressure(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"SPACE_DENIAL":
			target_tile = _execute_space_denial(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"STUTTER_TRAP":
			target_tile = _execute_stutter_trap(player_tile, opponent_tile, nearest, grid_sampler, ai_manager)
		
		"ITEM_HUNTER_TRAP":
			target_tile = _execute_item_hunter_trap(player_tile, opponent_tile, nearest, grid_sampler, ai_manager)
		
		"AGGRESSIVE_CHASE":
			target_tile = _execute_aggressive_chase(player_tile, opponent_tile, grid_sampler)
		
		"DEFENSIVE_RETREAT":
			# Handled by escape sequence
			return FAILURE
		
		"WAIT_FOR_DEATH":
			target_tile = _execute_wait_safe(player_tile, opponent_tile, grid_sampler, ai_manager)
		
		"PREDICTIVE_INTERCEPT":
			target_tile = _execute_predictive_intercept(player_tile, opponent_tile, nearest, grid_sampler)
		
		"FARM_TOWARD_OPPONENT":
			target_tile = _execute_farm_toward_opponent(player_tile, opponent_tile, grid_sampler, ai_manager)
	
	# If the specific tactic failed to find a valid position, fall back to AGGRESSIVE_CHASE
	# This prevents the tree from cycling through alternatives and causing oscillation
	if target_tile == Vector2i.ZERO or target_tile == Vector2i(-1, -1):
		print("[ExecuteTactic] ⚠ Tactic %s failed to find position, falling back to AGGRESSIVE_CHASE" % tactic)
		target_tile = _execute_aggressive_chase(player_tile, opponent_tile, grid_sampler)
	
	# If even AGGRESSIVE_CHASE failed, we truly have no valid target
	if target_tile == Vector2i.ZERO or target_tile == Vector2i(-1, -1):
		return FAILURE
	
	blackboard.set_var(target_var, target_tile)
	blackboard.set_var("tactic_executed", tactic)
	print("[ExecuteTactic] ✓ Executing ", tactic, " → ", target_tile)
	return SUCCESS

## CORNER TRAP - L-shaped trap forcing opponent into wall corner
func _execute_corner_trap(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager, player) -> Vector2i:
	# Find the opponent's only escape and the corner walls
	var escape_routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
	if escape_routes.is_empty():
		# Already trapped! Just bomb them
		return _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
	
	var escape_tile = escape_routes[0]
	var bomb_range = player.bomb_range if player else 2
	
	# For corner trap: place bomb to cover BOTH the opponent AND their escape route
	# Find tile that hits both
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var bomb_pos = opponent_tile + dir
		if not grid_sampler.is_tile_safe_for_target(bomb_pos):
			continue
		
		# Check if this bomb would hit the escape route too
		var blast = _get_blast_tiles(bomb_pos, bomb_range, grid_sampler)
		if escape_tile in blast and opponent_tile in blast:
			print("[CornerTrap] 🎯 L-trap at %s covers opponent AND escape!" % bomb_pos)
			return bomb_pos
	
	# Fallback: just block the escape
	print("[CornerTrap] 📐 Blocking corner escape at ", escape_tile)
	return _get_bomb_placement_for_target(escape_tile, player_tile, grid_sampler)

## BODY BLOCK - Block opponent's escape with your body, then place bomb behind them
## This is a LETHAL pro-level tactic: requires precise positioning
func _execute_body_block(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find opponent's only escape route
	var escape_routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
	if escape_routes.is_empty():
		# No escapes - just bomb them
		return _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
	
	var escape_tile = escape_routes[0]
	
	# Check if we're already on/adjacent to the escape
	var dist_to_escape = grid_sampler.get_manhattan_distance(player_tile, escape_tile)
	
	if player_tile == escape_tile:
		# PERFECT: We're standing on their escape! 
		# Now place bomb on the opposite side of opponent to trap them
		var bomb_tile = Vector2i.ZERO
		for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var check = opponent_tile + dir
			if check != player_tile and grid_sampler.is_tile_safe_for_target(check):
				bomb_tile = check
				break
		
		if bomb_tile == Vector2i.ZERO:
			# Place bomb on opponent directly if no other option
			bomb_tile = opponent_tile
		
		# Flag that we're body blocking - bot should place bomb then stay put!
		blackboard.set_var("body_blocking", true)
		blackboard.set_var("body_block_position", player_tile)
		print("[BodyBlock] 🚧 BLOCKING escape at %s! Bombing at %s" % [player_tile, bomb_tile])
		return bomb_tile
	
	elif dist_to_escape == 1:
		# We're adjacent to escape - move onto it first
		print("[BodyBlock] 🏃 Moving to block escape at %s" % escape_tile)
		return escape_tile
	
	# Not close enough - move toward escape
	return escape_tile

## DOUBLE BOMB - Drop two bombs rapidly to shorten escape window
## This is a LETHAL tactic: place first bomb, immediately move and place second to cut off escape
func _execute_double_bomb(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager, player) -> Vector2i:
	var direction = opponent_tile - player_tile
	var bomb_range = player.bomb_range if player else 2
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	# Check if we're continuing a double bomb sequence
	var followup = blackboard.get_var("double_bomb_followup", Vector2i.ZERO)
	var followup_active = blackboard.get_var("double_bomb_active", false)
	
	if followup_active and followup != Vector2i.ZERO:
		# We already placed first bomb, now place second!
		if grid_sampler.is_tile_safe_for_target(followup) and player.can_place_bomb():
			blackboard.set_var("double_bomb_active", false)
			blackboard.set_var("double_bomb_followup", Vector2i.ZERO)
			print("[DoubleBomb] 💣💣 SECOND BOMB at %s - TRAP COMPLETE!" % followup)
			return followup
		else:
			# Can't place second bomb, reset
			blackboard.set_var("double_bomb_active", false)
	
	# Find opponent's escape routes to plan double bomb positions
	var escape_routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
	
	# === STRATEGY: Place bombs to cover MULTIPLE escape routes ===
	# First bomb cuts off one escape, second bomb cuts off another
	
	var first_bomb_pos = Vector2i.ZERO
	var second_bomb_pos = Vector2i.ZERO
	
	if escape_routes.size() >= 2:
		# Ideal case: block two different escape routes
		# Sort escapes by distance from us
		var sorted_escapes = escape_routes.duplicate()
		sorted_escapes.sort_custom(func(a, b): 
			return grid_sampler.get_manhattan_distance(player_tile, a) < grid_sampler.get_manhattan_distance(player_tile, b)
		)
		
		# First bomb: closest escape route
		first_bomb_pos = _get_bomb_placement_for_target(sorted_escapes[0], player_tile, grid_sampler)
		# Second bomb: next closest escape route
		second_bomb_pos = _get_bomb_placement_for_target(sorted_escapes[1], player_tile, grid_sampler)
		
	elif escape_routes.size() == 1:
		# One escape route: place first bomb to block it, second bomb on opponent
		first_bomb_pos = _get_bomb_placement_for_target(escape_routes[0], player_tile, grid_sampler)
		second_bomb_pos = _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
	else:
		# No escape routes - opponent already trapped! Bomb them directly
		first_bomb_pos = _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
		second_bomb_pos = Vector2i.ZERO
	
	# Validate first bomb position
	if first_bomb_pos == Vector2i.ZERO or not grid_sampler.is_tile_safe_for_target(first_bomb_pos):
		# Fallback to simple approach
		first_bomb_pos = player_tile
		if abs(direction.x) > abs(direction.y):
			first_bomb_pos += Vector2i(sign(direction.x), 0)
		else:
			first_bomb_pos += Vector2i(0, sign(direction.y))
		
		if not grid_sampler.is_tile_safe_for_target(first_bomb_pos):
			first_bomb_pos = player_tile
	
	# Store second bomb target for follow-up and mark chain active
	if second_bomb_pos != Vector2i.ZERO and grid_sampler.is_tile_walkable(second_bomb_pos):
		blackboard.set_var("double_bomb_followup", second_bomb_pos)
		blackboard.set_var("double_bomb_active", true)
		print("[DoubleBomb] 💣💣 First bomb at %s, followup at %s (blocking %d escapes)" % [first_bomb_pos, second_bomb_pos, escape_routes.size()])
	else:
		blackboard.set_var("double_bomb_active", false)
		print("[DoubleBomb] 💣 Single bomb at %s (opponent has %d escapes)" % [first_bomb_pos, escape_routes.size()])
	
	return first_bomb_pos

## TUNNEL PRESSURE - Force opponent into narrow path then cut off exit
func _execute_tunnel_pressure(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find which direction the corridor runs
	var horizontal_open = (grid_sampler.is_tile_walkable(opponent_tile + Vector2i.LEFT) or 
						   grid_sampler.is_tile_walkable(opponent_tile + Vector2i.RIGHT))
	var vertical_open = (grid_sampler.is_tile_walkable(opponent_tile + Vector2i.UP) or 
						 grid_sampler.is_tile_walkable(opponent_tile + Vector2i.DOWN))
	
	# Position at one end of the corridor
	var target = opponent_tile
	if horizontal_open and not vertical_open:
		# Corridor runs horizontally - block one end
		if player_tile.x < opponent_tile.x:
			target = opponent_tile + Vector2i.LEFT
		else:
			target = opponent_tile + Vector2i.RIGHT
	elif vertical_open and not horizontal_open:
		# Corridor runs vertically - block one end
		if player_tile.y < opponent_tile.y:
			target = opponent_tile + Vector2i.UP
		else:
			target = opponent_tile + Vector2i.DOWN
	
	if grid_sampler.is_tile_safe_for_target(target):
		print("[TunnelPressure] 🚇 Blocking tunnel at ", target)
		return target
	
	return _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)

## ITEM HUNTER TRAP - Predict where opponent will go for powerups
func _execute_item_hunter_trap(player_tile: Vector2i, opponent_tile: Vector2i, opponent_data: Dictionary, grid_sampler, ai_manager) -> Vector2i:
	var velocity: Vector2 = opponent_data.get("velocity", Vector2.ZERO)
	if velocity.length() < 10.0:
		# Not moving fast, fall back to regular intercept
		return _find_best_blocking_position(player_tile, opponent_tile, grid_sampler)
	
	# Predict 3-4 tiles ahead (item hunters move fast)
	var direction = velocity.normalized()
	var predicted = opponent_tile
	
	for i in range(4):
		var next: Vector2i
		if abs(direction.x) > abs(direction.y):
			next = predicted + Vector2i(sign(direction.x), 0)
		else:
			next = predicted + Vector2i(0, sign(direction.y))
		
		if not grid_sampler.is_tile_walkable(next):
			break
		predicted = next
	
	# Place bomb where they're heading
	print("[ItemHunterTrap] 🎁 Predicted item hunter path to %s" % predicted)
	return _get_bomb_placement_for_target(predicted, player_tile, grid_sampler)

## The "Kiss" - trap opponent on one tile, then bomb that tile
func _execute_one_tile_trap(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find the opponent's only escape route
	var escape_tile = _find_only_escape(opponent_tile, grid_sampler, ai_manager)
	if escape_tile == Vector2i.ZERO:
		# No single escape found - try to block ANY escape route
		var routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
		if routes.size() > 0:
			escape_tile = routes[0]
		else:
			# Opponent has no escapes - they're trapped! Place bomb near them
			return _get_bomb_placement_for_target(opponent_tile, player_tile, grid_sampler)
	
	# CRITICAL FIX: Position ourselves to bomb the escape route, not the opponent!
	var intercept_tile = _get_bomb_placement_for_target(escape_tile, player_tile, grid_sampler)
	print("[OneTileTrap] 💋 Blocking escape route: %s (bomb pos: %s)" % [escape_tile, intercept_tile])
	return intercept_tile

## Block one of two escape routes, forcing opponent into trap
func _execute_choke_point(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	var escape_routes = _find_escape_routes(opponent_tile, grid_sampler, ai_manager)
	if escape_routes.size() < 2:
		return opponent_tile
	
	# Choose the escape route closest to us to block
	var best_route = escape_routes[0]
	var best_dist = grid_sampler.get_manhattan_distance(player_tile, best_route)
	
	for route in escape_routes:
		var dist = grid_sampler.get_manhattan_distance(player_tile, route)
		if dist < best_dist:
			best_dist = dist
			best_route = route
	
	print("[ChokePoint] 🕷️ Blocking escape: ", best_route)
	return _get_bomb_placement_for_target(best_route, player_tile, grid_sampler)

## Cut off opponent's movement path
func _execute_space_denial(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find midpoint between us and opponent
	var direction = opponent_tile - player_tile
	var midpoint = player_tile + Vector2i(direction.x / 2, direction.y / 2)
	
	# Adjust to walkable tile
	if not grid_sampler.is_tile_walkable(midpoint):
		# Try adjacent tiles
		for offset in [Vector2i.ZERO, Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var check = midpoint + offset
			if grid_sampler.is_tile_walkable(check):
				midpoint = check
				break
	
	print("[SpaceDenial] 🚫 Cutting off path at: ", midpoint)
	return midpoint

## STUTTER TRAP - Fake approach then cut off retreat
## This exploits human reaction: players will retreat when they see you approach
## We predict their retreat path and bomb it ahead of time
func _execute_stutter_trap(player_tile: Vector2i, opponent_tile: Vector2i, opponent_data: Dictionary, grid_sampler, ai_manager) -> Vector2i:
	var velocity: Vector2 = opponent_data.get("velocity", Vector2.ZERO)
	
	# Predict where opponent will retreat TO (opposite of their movement)
	# When they see us approach, they'll likely retreat backward
	var retreat_direction: Vector2i
	
	if velocity.length() > 10.0:
		# They're already moving - predict they'll continue
		var dir = velocity.normalized()
		if abs(dir.x) > abs(dir.y):
			retreat_direction = Vector2i(sign(dir.x), 0)
		else:
			retreat_direction = Vector2i(0, sign(dir.y))
	else:
		# They're stationary - predict they'll retreat away from us
		var away = opponent_tile - player_tile
		if abs(away.x) > abs(away.y):
			retreat_direction = Vector2i(sign(away.x), 0)
		else:
			retreat_direction = Vector2i(0, sign(away.y))
	
	# Find the tile they'll retreat to (2-3 tiles in retreat direction)
	var retreat_target = opponent_tile
	for i in range(3):
		var next = retreat_target + retreat_direction
		if not grid_sampler.is_tile_walkable(next):
			break
		retreat_target = next
	
	# Check if retreat target is near a corner (ideal trap)
	var is_corner = false
	var wall_count = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		if not grid_sampler.is_tile_walkable(retreat_target + dir):
			wall_count += 1
	is_corner = wall_count >= 2
	
	if is_corner:
		# PERFECT: They'll retreat into a corner! Bomb the path
		print("[StutterTrap] 🎭 Opponent will retreat to CORNER at %s! Cutting off path." % retreat_target)
		# Place bomb to cut off their retreat before they reach the corner
		var intercept = opponent_tile + retreat_direction
		if grid_sampler.is_tile_safe_for_target(intercept):
			return intercept
	
	# Standard stutter: bomb their predicted position
	print("[StutterTrap] 🎭 Predicting retreat to %s" % retreat_target)
	return _get_bomb_placement_for_target(retreat_target, player_tile, grid_sampler)

## Chase aggressively with multiple bombs
## This is an ATTACK tactic - we want to find a position where we can BOMB the opponent!
func _execute_aggressive_chase(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler) -> Vector2i:
	var direction = opponent_tile - player_tile
	var manhattan_dist = abs(direction.x) + abs(direction.y)
	
	# Get player's bomb range from blackboard
	var player = blackboard.get_var("player")
	var bomb_range = player.bomb_range if player else 2
	
	# If we're ALREADY in bombing range, find the best attack position!
	# We need a tile where our bomb explosion would hit the opponent
	if manhattan_dist <= bomb_range + 2:
		# We're close! Find a tile where:
		# 1. We can place a bomb that threatens the opponent
		# 2. We have an escape route
		var best_attack_pos = _find_attack_position(player_tile, opponent_tile, bomb_range, grid_sampler)
		if best_attack_pos != Vector2i.ZERO and best_attack_pos != Vector2i(-1, -1):
			print("[AggressiveChase] 🎯 Attack position found: %s (range to target: %d)" % [best_attack_pos, manhattan_dist])
			return best_attack_pos
	
	# Not in bombing range yet - chase toward opponent
	# Find the best path tile toward the opponent
	var next_tile = player_tile
	
	# Primary direction: the axis with the larger gap
	var primary_dir: Vector2i
	var secondary_dir: Vector2i
	
	if abs(direction.x) > abs(direction.y):
		primary_dir = Vector2i(sign(direction.x), 0)
		secondary_dir = Vector2i(0, sign(direction.y)) if direction.y != 0 else Vector2i(0, 1)
	else:
		primary_dir = Vector2i(0, sign(direction.y))
		secondary_dir = Vector2i(sign(direction.x), 0) if direction.x != 0 else Vector2i(1, 0)
	
	# Try primary direction
	next_tile = player_tile + primary_dir
	if grid_sampler.is_tile_safe_for_target(next_tile):
		return next_tile
	
	# Try secondary direction (flanking approach)
	next_tile = player_tile + secondary_dir
	if grid_sampler.is_tile_safe_for_target(next_tile):
		return next_tile
	
	# Try opposite of secondary (other flank)
	next_tile = player_tile - secondary_dir
	if grid_sampler.is_tile_safe_for_target(next_tile):
		return next_tile
	
	# All directions blocked - stay in place
	return player_tile

## Find the best position to attack opponent from
## Returns a tile where a bomb would threaten the opponent AND we can escape
func _find_attack_position(player_tile: Vector2i, opponent_tile: Vector2i, bomb_range: int, grid_sampler) -> Vector2i:
	var ai_manager = blackboard.get_var("ai_manager")
	var threat_matrix = ai_manager.get_current_threat_matrix() if ai_manager else {}
	
	# Check tiles along each cardinal direction from opponent
	# These are positions where our bomb would hit them
	var attack_positions: Array[Dictionary] = []
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for dist in range(1, bomb_range + 1):
			var attack_tile = opponent_tile + (dir * dist)
			
			# Must be walkable and safe (no current threats)
			if not grid_sampler.is_tile_safe_for_target(attack_tile):
				break  # Can't pass through walls/blocks
			
			var key = "%d,%d" % [attack_tile.x, attack_tile.y]
			if threat_matrix.has(key):
				continue  # Don't stand in danger
			
			# Check if we can reach this position
			var path = grid_sampler.find_path(player_tile, attack_tile, 20, null, false)
			if path.is_empty():
				continue  # Can't reach
			
			# Count escape routes from this position (excluding the direction toward opponent)
			var escapes = 0
			for escape_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				if escape_dir == -dir:
					continue  # Don't count going back toward explosion
				var escape_tile = attack_tile + escape_dir
				if grid_sampler.is_tile_safe_for_target(escape_tile):
					var escape_key = "%d,%d" % [escape_tile.x, escape_tile.y]
					if not threat_matrix.has(escape_key):
						escapes += 1
			
			if escapes >= 1:
				var path_len = path.size()
				attack_positions.append({
					"tile": attack_tile,
					"dist_from_opp": dist,
					"path_len": path_len,
					"escapes": escapes
				})
	
	if attack_positions.is_empty():
		return Vector2i.ZERO
	
	# Sort by: closest to us (shortest path), then by escape options
	attack_positions.sort_custom(func(a, b):
		# First, shorter path is better
		if a.path_len != b.path_len:
			return a.path_len < b.path_len
		# Then, more escapes is better
		return a.escapes > b.escapes
	)
	
	return attack_positions[0].tile

## Stay safe while opponent dies
func _execute_wait_safe(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find safe position away from opponent's danger zone
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for radius in range(1, 5):
		for offset_x in range(-radius, radius + 1):
			for offset_y in range(-radius, radius + 1):
				var check_tile = player_tile + Vector2i(offset_x, offset_y)
				var key = "%d,%d" % [check_tile.x, check_tile.y]
				
				# CRITICAL FIX: Use is_tile_safe_for_target which checks for bombs!
				if grid_sampler.is_tile_safe_for_target(check_tile) and not threat_matrix.has(key):
					var dist_to_opponent = grid_sampler.get_manhattan_distance(check_tile, opponent_tile)
					if dist_to_opponent >= 4:  # Stay away from danger
						return check_tile
	
	return player_tile

## Standard predictive chase - intercept where opponent is GOING, not where they ARE
func _execute_predictive_intercept(player_tile: Vector2i, opponent_tile: Vector2i, opponent_data: Dictionary, grid_sampler) -> Vector2i:
	# Use velocity to predict 2-3 tiles ahead
	var velocity: Vector2 = opponent_data.get("velocity", Vector2.ZERO)
	if velocity.length() < 10.0:
		# Opponent stationary - find best blocking position around them
		return _find_best_blocking_position(player_tile, opponent_tile, grid_sampler)
	
	var prediction_distance = 2
	var direction = velocity.normalized()
	var predicted = opponent_tile
	
	for i in range(prediction_distance):
		var next: Vector2i
		if abs(direction.x) > abs(direction.y):
			next = predicted + Vector2i(sign(direction.x), 0)
		else:
			next = predicted + Vector2i(0, sign(direction.y))
		
		if not grid_sampler.is_tile_walkable(next):
			break
		predicted = next
	
	# Instead of moving to predicted position, find a blocking position AHEAD of it
	var blocking_pos = _find_best_blocking_position(player_tile, predicted, grid_sampler)
	print("[PredictiveIntercept] Opponent heading to %s, blocking at %s" % [predicted, blocking_pos])
	return blocking_pos

## Find the best position to place a bomb that blocks opponent's movement
func _find_best_blocking_position(player_tile: Vector2i, target_tile: Vector2i, grid_sampler) -> Vector2i:
	# Check tiles adjacent to target that we can reach
	var best_pos = target_tile  # Fallback
	var best_score = -1000
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = target_tile + dir
		# CRITICAL: Use is_tile_safe_for_target to avoid bombs!
		if not grid_sampler.is_tile_safe_for_target(check_tile):
			continue
		
		# Score based on distance from us (closer = better) and blocking potential
		var dist_from_us = grid_sampler.get_manhattan_distance(player_tile, check_tile)
		var dist_from_target = 1  # Adjacent
		
		# Prefer positions that are closer to us
		var score = 10 - dist_from_us
		
		# Bonus for positions that create corridor (more adjacent walls)
		var walls_nearby = 0
		for wall_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var wall_check = check_tile + wall_dir
			if not grid_sampler.is_tile_walkable(wall_check):
				walls_nearby += 1
		score += walls_nearby  # More walls = better trap position
		
		if score > best_score:
			best_score = score
			best_pos = check_tile
	
	return best_pos

## Helper: Find opponent's only escape route
func _find_only_escape(tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	var routes = _find_escape_routes(tile, grid_sampler, ai_manager)
	return routes[0] if routes.size() == 1 else Vector2i.ZERO

## Helper: Find all escape routes
func _find_escape_routes(tile: Vector2i, grid_sampler, ai_manager) -> Array[Vector2i]:
	var routes: Array[Vector2i] = []
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check = tile + dir
		if grid_sampler.is_tile_walkable(check):
			var key = "%d,%d" % [check.x, check.y]
			if not threat_matrix.has(key):
				routes.append(check)
	
	return routes

## Helper: Find best position to bomb a target tile
func _get_bomb_placement_for_target(target: Vector2i, our_pos: Vector2i, grid_sampler) -> Vector2i:
	# Check if we can bomb from adjacent tile
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var placement = target + dir
		if grid_sampler.is_tile_safe_for_target(placement):
			var dist = grid_sampler.get_manhattan_distance(our_pos, placement)
			if dist <= 4:  # Close enough to reach (increased range)
				return placement
	
	# Fallback: move toward target
	return target

## Helper: Get blast tiles for a bomb at position
func _get_blast_tiles(center: Vector2i, range_val: int, grid_sampler) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = [center]
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for dist in range(1, range_val + 1):
			var tile = center + (dir * dist)
			if not grid_sampler.is_tile_walkable(tile):
				break
			tiles.append(tile)
	return tiles

## FARM TOWARD OPPONENT - Destroy soft blocks in the direction of the enemy
## This is used when we're blocked and need to create a path to attack
func _execute_farm_toward_opponent(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, ai_manager) -> Vector2i:
	# Find direction toward opponent
	var direction = opponent_tile - player_tile
	
	# Check each adjacent tile in priority order (toward opponent first)
	var check_order: Array[Vector2i] = []
	
	# Primary direction (toward opponent)
	if abs(direction.x) > abs(direction.y):
		check_order.append(player_tile + Vector2i(sign(direction.x), 0))
		check_order.append(player_tile + Vector2i(0, sign(direction.y) if direction.y != 0 else 1))
		check_order.append(player_tile + Vector2i(0, -sign(direction.y) if direction.y != 0 else -1))
		check_order.append(player_tile + Vector2i(-sign(direction.x), 0))
	else:
		check_order.append(player_tile + Vector2i(0, sign(direction.y)))
		check_order.append(player_tile + Vector2i(sign(direction.x) if direction.x != 0 else 1, 0))
		check_order.append(player_tile + Vector2i(-sign(direction.x) if direction.x != 0 else -1, 0))
		check_order.append(player_tile + Vector2i(0, -sign(direction.y)))
	
	# Find the best tile adjacent to a soft block toward opponent
	for check_tile in check_order:
		# Check if this tile has a soft block that's blocking our path to opponent
		if not grid_sampler.is_tile_walkable(check_tile):
			# This direction is blocked - check if it's a soft block
			var tile_type = grid_sampler.get_tile_type(check_tile)
			if tile_type == 2:  # Soft block!
				# We found a soft block in the direction of opponent
				# Plant bomb at current position to destroy it
				print("[FarmTowardOpponent] 🎯 Destroying soft block at %s toward opponent" % check_tile)
				return player_tile
	
	# No direct soft block toward opponent - find any adjacent tile with soft block nearby
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var adj = player_tile + dir
		if grid_sampler.is_tile_walkable(adj):
			# Check if planting here would hit a soft block toward opponent
			for check_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
				var beyond = adj + check_dir
				if not grid_sampler.is_tile_walkable(beyond):
					var tile_type = grid_sampler.get_tile_type(beyond)
					if tile_type == 2:
						# Found a farming spot
						print("[FarmTowardOpponent] 📍 Moving to %s to farm soft block at %s" % [adj, beyond])
						return adj
	
	# Fallback - just move toward opponent as much as possible
	return player_tile

## KICK SNIPE - Kick a bomb toward the opponent
## Returns dictionary with kick_direction if valid kick found, empty dict otherwise
func _execute_kick_snipe(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, game_instance, player) -> Dictionary:
	if game_instance == null or not "bombs" in game_instance:
		return {}
	
	if not player.has_bomb_kicker:
		return {}
	
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	var best_kick: Dictionary = {}
	var best_score = 0.0
	
	for dir in directions:
		var bomb_tile = player_tile + dir
		
		# Check for bomb at this tile
		var found_bomb = null
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			# Check bomb_state instead of is_kicked (BombState.PLANTED = 0)
			if is_instance_valid(bomb) and not bomb.has_exploded and bomb.bomb_state == 0:
				if bomb.get_tile_position() == bomb_tile:
					found_bomb = bomb
					break
		
		if found_bomb == null:
			continue
		
		# Check if kicking in this direction moves toward opponent
		var to_target = Vector2(opponent_tile - bomb_tile)
		if to_target.length() < 0.1:
			continue  # Already at target
		
		var kick_dir = Vector2(dir)
		var alignment = kick_dir.normalized().dot(to_target.normalized())
		
		if alignment < 0.5:
			continue  # Kicking away from target
		
		# Check how far bomb would travel
		var travel_distance = 0
		var final_tile = bomb_tile
		var bomb_range = found_bomb.bomb_range if found_bomb.has_method("get") else 2
		
		for i in range(1, 10):
			var check_tile = bomb_tile + Vector2i(kick_dir * float(i))
			var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
			
			if tile_type != 0:  # Not empty floor
				break
			
			# Check for other bombs that would stop it
			var blocked = false
			for bomb_id in game_instance.bombs:
				var other_bomb = game_instance.bombs[bomb_id]
				if is_instance_valid(other_bomb) and other_bomb != found_bomb:
					if other_bomb.get_tile_position() == check_tile:
						blocked = true
						break
			
			if blocked:
				break
			
			travel_distance = i
			final_tile = check_tile
		
		if travel_distance == 0:
			continue  # Bomb can't move
		
		# Score: would the kicked bomb hit the opponent?
		var dist_to_opponent = abs(final_tile.x - opponent_tile.x) + abs(final_tile.y - opponent_tile.y)
		var score = alignment * 0.5
		
		if dist_to_opponent <= bomb_range:
			score += 1.0  # Direct hit potential!
		elif dist_to_opponent <= bomb_range + 2:
			score += 0.5  # Close hit
		
		if score > best_score:
			best_score = score
			best_kick = {
				"kick_direction": kick_dir,
				"bomb_tile": bomb_tile,
				"final_tile": final_tile,
				"score": score
			}
	
	if best_score > 0.5:
		print("[KickSnipe] ⚽ Found kick: %s → %s (score=%.2f)" % [
			best_kick.bomb_tile, best_kick.final_tile, best_kick.score
		])
		return best_kick
	
	return {}

func _execute_power_throw(player_tile: Vector2i, opponent_tile: Vector2i, grid_sampler, game_instance, player) -> Dictionary:
	"""Find the best direction to throw a bomb toward opponent"""
	if not player.has_power_glove:
		return {}
	
	var directions = [
		Vector2(1, 0),   # Right
		Vector2(-1, 0),  # Left
		Vector2(0, 1),   # Down
		Vector2(0, -1)   # Up
	]
	
	var best_throw: Dictionary = {}
	var best_score = -1.0
	var bomb_range = player.bomb_range if player else 2
	
	for dir in directions:
		var dir_i = Vector2i(int(dir.x), int(dir.y))
		
		# Check if throw direction aligns with opponent
		var to_opponent = Vector2(opponent_tile - player_tile)
		if to_opponent.length() < 0.1:
			continue
		
		var alignment = dir.normalized().dot(to_opponent.normalized())
		if alignment < 0.5:
			continue  # Throwing away from opponent
		
		# Calculate throw trajectory
		var travel_distance = 0
		var landing_tile = player_tile
		
		for i in range(1, 10):
			var check_tile = player_tile + dir_i * i
			var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
			
			if tile_type != 0:  # Not empty floor - bomb lands at previous tile
				break
			
			travel_distance = i
			landing_tile = check_tile
		
		if travel_distance < 3:
			continue  # Need decent throw distance
		
		# Score based on how close bomb lands to opponent
		var dist_to_opponent = abs(landing_tile.x - opponent_tile.x) + abs(landing_tile.y - opponent_tile.y)
		var score = alignment * 0.3
		
		if dist_to_opponent == 0:
			score += 1.5  # Direct hit!
		elif dist_to_opponent <= bomb_range:
			score += 1.0  # In blast radius
		elif dist_to_opponent <= bomb_range + 2:
			score += 0.5  # Near miss
		
		# Bonus for longer throws (harder to dodge)
		if travel_distance >= 5:
			score += 0.2
		
		if score > best_score:
			best_score = score
			best_throw = {
				"throw_direction": dir,
				"landing_tile": landing_tile,
				"distance": travel_distance,
				"score": score
			}
	
	if best_score > 0.5:
		print("[PowerThrow] 💣 Found throw: toward %s landing at %s (score=%.2f)" % [
			opponent_tile, best_throw.landing_tile, best_throw.score
		])
		return best_throw
	
	return {}
