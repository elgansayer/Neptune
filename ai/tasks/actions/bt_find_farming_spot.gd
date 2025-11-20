@tool
extends BTAction
class_name BTFindFarmingSpot

## Finds a nearby soft block position that has an escape route
## Sets target_cell in blackboard for safe bomb placement

@export var search_radius: int = 5 ## How far to search for soft blocks
@export var target_cell_var: StringName = &"target_cell" ## Where to store the target
@export var debug_logging: bool = true ## Enable detailed rejection logging (FORCED ON)
@export var broadcast_safety: bool = true ## Send safety eval to clients for visualization
@export var always_broadcast: bool = true ## Broadcast continuously even when reusing cached target

const INVALID_TILE := Vector2i(-1, -1)

func _generate_name() -> String:
	return "FindFarmingSpot(radius=%d)" % search_radius

func _tick(_delta: float) -> int:
	print("[BTFindFarmingSpot] ===== _tick() CALLED ===== delta=", _delta)
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	
	print("[BTFindFarmingSpot] Retrieved from blackboard: player=", player != null, " game_instance=", game_instance != null, " grid_sampler=", grid_sampler != null, " bomb_safety_checker=", bomb_safety_checker != null)
	
	if not player or not game_instance or not grid_sampler or not bomb_safety_checker:
		print("[BTFindFarmingSpot] _tick() FAILURE - missing dependencies")
		return FAILURE
	
	var current_tile = player.get_tile_position()
	var bomb_range = player.bomb_range
	var current_time_msec = Time.get_ticks_msec()

	# If we already have a valid farming target, reuse it to avoid expensive rescans every tick
	var existing_target = _coerce_to_tile(blackboard.get_var(target_cell_var))
	if _is_valid_target(existing_target, grid_sampler, bomb_range):
		print("[BTFindFarmingSpot] *** REUSING CACHED TARGET at ", existing_target, " always_broadcast=", always_broadcast)
		# Still broadcast for continuous visualization even when reusing target
		if always_broadcast:
			print("[BTFindFarmingSpot] *** BROADCASTING FOR CACHED TARGET")
			var ai_manager = blackboard.get_var("ai_manager")
			_do_full_search_and_broadcast(current_tile, bomb_range, current_time_msec, player, game_instance, grid_sampler, bomb_safety_checker, ai_manager)
		return SUCCESS
	
	# Search nearby tiles for soft blocks
	var best_spot: Vector2i = INVALID_TILE
	var best_score: float = 0.0
	var candidates_checked := 0
	var rejected_unwalkable := 0
	var rejected_no_blocks := 0
	var rejected_no_path := 0
	var rejected_no_nearby_safe := 0
	var rejected_no_escape := 0
	
	# Safety visualization data for client
	var safety_eval := {}
	
	print("[BTFindFarmingSpot] STARTING SEARCH - broadcast_safety=", broadcast_safety)
	
	if debug_logging:
		print("[BTFindFarmingSpot] Starting search from ", current_tile, " radius=", search_radius, " bomb_range=", bomb_range)
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			# Include current tile (dx=0, dy=0) in evaluation
			var check_tile = current_tile + Vector2i(dx, dy)
			candidates_checked += 1
			
			# Must be walkable
			if not grid_sampler.is_tile_walkable(check_tile):
				rejected_unwalkable += 1
				continue
			
			# Count soft blocks in bomb range - skip if none
			var soft_blocks_hit = _count_soft_blocks_in_range(check_tile, bomb_range, grid_sampler)
			if soft_blocks_hit == 0:
				rejected_no_blocks += 1
				continue
			
			# Check if tile is threatened
			var ai_manager = blackboard.get_var("ai_manager")
			if ai_manager:
				var threat_matrix = ai_manager.get_current_threat_matrix()
				var t_key := "%d,%d" % [check_tile.x, check_tile.y]
				if threat_matrix.has(t_key):
					rejected_no_nearby_safe += 1
					if debug_logging:
						print("  [REJECT] ", check_tile, " - threatened")
					continue
			
			var tile_key := "%d,%d" % [check_tile.x, check_tile.y]
			
			# Check if we can reach this tile - adjacent tiles are always reachable if walkable
			var manhattan_dist = abs(dx) + abs(dy)
			if manhattan_dist > 1:
				var path = grid_sampler.find_path(current_tile, check_tile, 15, player)
				if path.is_empty():
					rejected_no_path += 1
					if broadcast_safety:
						safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_path"}
					if debug_logging:
						print("  [REJECT] ", check_tile, " - no path (blocks=", soft_blocks_hit, ")")
					continue
			# Adjacent tile (distance == 1 or 0) - skip pathfinding, assume reachable
			
			# CRITICAL: Check if there's ALREADY a safe tile nearby (without planting bomb)
			# This ensures we're not in a dead-end surrounded by soft blocks
			var has_nearby_safety = _has_safe_tile_nearby(check_tile, grid_sampler, current_time_msec)
			if not has_nearby_safety:
				rejected_no_nearby_safe += 1
				if broadcast_safety:
					safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_nearby_safe"}
				if debug_logging:
					print("  [REJECT] ", check_tile, " - no nearby safe tile (blocks=", soft_blocks_hit, ")")
				continue
			
			# Check if we can safely plant a bomb HERE (at check_tile) and escape
			# IMPORTANT: bot_pos is check_tile because that's where we'll be when planting
			var safety_result = bomb_safety_checker.check_plant_safety_detailed(
				check_tile, # Where the bot will be standing when planting
				check_tile, # Where the bomb will be planted
				bomb_range,
				5.0, # bot speed
				current_time_msec
			)
			
			if not safety_result.safe:
				rejected_no_escape += 1
				if broadcast_safety:
					safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": safety_result.get("explored_tiles", 0), "reason": "no_escape"}
				if debug_logging:
					print("  [REJECT] ", check_tile, " - no escape route (blocks=", soft_blocks_hit, ")")
				continue
			
			# CORRECTED SCORING: Safety-First Algorithm
			# Score = Damage_Potential * Safety_Multiplier (NOT additive!)
			
			# Base damage score
			var damage_score = soft_blocks_hit * 10.0
			
			# Safety multiplier based on escape quality
			var margin = safety_result.get("margin_ms", 1000.0)
			var escape_tile = safety_result.get("escape_tile", null)
			
			# Calculate escape distance (1-step escapes are ideal)
			var escape_distance = 999
			if escape_tile:
				if escape_tile is Vector2i:
					escape_distance = abs(escape_tile.x - check_tile.x) + abs(escape_tile.y - check_tile.y)
				elif escape_tile is Dictionary:
					escape_distance = abs(int(escape_tile.x) - check_tile.x) + abs(int(escape_tile.y) - check_tile.y)
			
			# Safety multiplier: heavily favor short escapes and high margins
			var safety_multiplier = 1.0
			
			# Escape distance factor (1-step = 1.5x, 2-step = 1.2x, 3+ step = 1.0x)
			if escape_distance == 1:
				safety_multiplier *= 1.5 # HUGE bonus for "plant-and-hide-in-corner" strategy
			elif escape_distance == 2:
				safety_multiplier *= 1.2
			elif escape_distance >= 5:
				safety_multiplier *= 0.7 # Penalty for long escape runs
			
			# Margin factor (>1000ms = 1.2x, 800-1000ms = 1.0x, <800ms = 0.8x)
			if margin > 1000.0:
				safety_multiplier *= 1.2
			elif margin < 800.0:
				safety_multiplier *= 0.8
			
			# Final score: multiplicative formula
			var score = damage_score * safety_multiplier
			
			# Proximity bonus (slightly favor closer tiles to avoid long walks)
			var distance = abs(dx) + abs(dy)
			score -= distance * 0.3
			
			if score > best_score:
				best_score = score
				best_spot = check_tile
			
			# Mark as safe or marginal for visualization based on safety margin
			if broadcast_safety:
				tile_key = "%d,%d" % [check_tile.x, check_tile.y]
				var status = 2 if margin > 800.0 else 1 # Safe (cyan) if >800ms margin, marginal (orange) otherwise
				var eval_data = {
					"status": status,
					"soft_blocks": soft_blocks_hit,
					"explored_tiles": safety_result.get("explored_tiles", 0),
					"margin_ms": margin,
					"escape_distance": escape_distance,
					"final_score": score # Include score for debugging
				}
				if escape_tile:
					eval_data["escape_tile"] = {"x": escape_tile.x, "y": escape_tile.y}
				safety_eval[tile_key] = eval_data
	
	# Broadcast safety data to all clients
	print("[BTFindFarmingSpot] *** BROADCAST CHECK: broadcast_safety=", broadcast_safety, " safety_eval.size()=", safety_eval.size())
	if broadcast_safety and not safety_eval.is_empty():
		print("[BTFindFarmingSpot] *** BROADCASTING %d safety evaluations to clients" % safety_eval.size())
		_broadcast_safety_data(safety_eval)
	elif broadcast_safety:
		print("[BTFindFarmingSpot] *** WARNING: No safety data to broadcast (empty)")
	else:
		print("[BTFindFarmingSpot] *** WARNING: broadcast_safety is FALSE")
	
	# If we found a good spot, store it
	if best_spot != INVALID_TILE:
		blackboard.set_var(target_cell_var, best_spot)
		print("[BTFindFarmingSpot] ✓ Found farming spot at ", best_spot, " (score: ", best_score, ")")
		return SUCCESS
	
	# No good farming spot found - report why
	print("[BTFindFarmingSpot] ✗ No safe farming spots found (checked=", candidates_checked,
		" unwalkable=", rejected_unwalkable,
		" no_blocks=", rejected_no_blocks,
		" no_path=", rejected_no_path,
		" no_nearby_safe=", rejected_no_nearby_safe,
		" no_escape=", rejected_no_escape, ")")
	return FAILURE

func _count_soft_blocks_in_range(center: Vector2i, bomb_range: int, grid_sampler) -> int:
	var count = 0
	
	# Check horizontal (right)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check horizontal (left)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(-dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (down)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (up)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, -dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type == 1: # Hard block - stops blast
			break
	
	return count

func _has_safe_tile_nearby(position: Vector2i, grid_sampler, current_time_msec: float) -> bool:
	"""Check if there's at least one safe tile within reasonable distance (no threats, walkable)"""
	var ai_manager = blackboard.get_var("ai_manager")
	if not ai_manager:
		return false
	return _has_safe_tile_nearby_static(position, grid_sampler, current_time_msec, ai_manager)

func _has_safe_tile_nearby_static(position: Vector2i, grid_sampler, current_time_msec: float, ai_manager) -> bool:
	"""Static version that accepts ai_manager as parameter"""
	if not ai_manager:
		return false
	
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var max_distance = 4 # tiles
	
	# Check if ANY nearby tile is safe (not in threat matrix and walkable)
	for dx in range(-max_distance, max_distance + 1):
		for dy in range(-max_distance, max_distance + 1):
			var check_pos = position + Vector2i(dx, dy)
			
			if not grid_sampler.is_tile_walkable(check_pos):
				continue

			var tile_key := "%d,%d" % [check_pos.x, check_pos.y]
			# If this tile is not in the threat matrix, it's safe
			if not threat_matrix.has(tile_key):
				return true
			
			# Also consider it safe if the threat is far in the future (> 2.5 seconds)
			# This prevents rejecting valid spots just because a distant bomb exists
			# if threat_matrix[tile_key] > current_time_msec + 2500.0:
			#	return true

	# No safe tiles found nearby - we're in a danger zone
	return false

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

func _broadcast_safety_data(data: Dictionary) -> void:
	"""Send safety evaluation to all clients for visualization"""
	print("[BTFindFarmingSpot] >>> _broadcast_safety_data called with %d tiles" % data.size())
	
	# Get the bot player node from blackboard
	var player_node = blackboard.get_var("player")
	if not player_node:
		print("[BTFindFarmingSpot] !!! Cannot broadcast: no player in blackboard")
		return
	print("[BTFindFarmingSpot] >>> Got player_node: ", player_node.name)
	
	# Navigate to the game instance (player's parent)
	var game_instance = player_node.get_parent()
	if not game_instance:
		print("[BTFindFarmingSpot] !!! Cannot broadcast: no game_instance")
		return
	print("[BTFindFarmingSpot] >>> Got game_instance")
	
	# Get ClientMain autoload
	var client_main = game_instance.get_node_or_null("/root/ClientMain")
	if not client_main:
		print("[BTFindFarmingSpot] !!! Cannot broadcast: ClientMain not found")
		return
	print("[BTFindFarmingSpot] >>> Got ClientMain, players count: ", game_instance.players.size())
	
	# Send RPC to all connected clients (iterate through players, not multiplayer.get_peers())
	var sent_count = 0
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		print("[BTFindFarmingSpot] >>> Checking peer_id ", peer_id, " is_ai_bot=", player.is_ai_bot())
		if not player.is_ai_bot():
			print("[BTFindFarmingSpot] >>> Sending RPC to peer %d with %d tiles" % [peer_id, data.size()])
			client_main.rpc_id(peer_id, "bomb_safety_update", data)
			sent_count += 1
	
	print("[BTFindFarmingSpot] >>> BROADCAST COMPLETE: %d tiles to %d clients" % [data.size(), sent_count])

func _coerce_to_tile(value) -> Vector2i:
	if value == null:
		return INVALID_TILE
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	if typeof(value) == TYPE_DICTIONARY and value.has("x") and value.has("y"):
		return Vector2i(int(value.x), int(value.y))
	return INVALID_TILE

func _is_valid_target(tile: Vector2i, grid_sampler, bomb_range: int) -> bool:
	if tile == INVALID_TILE:
		return false
	if not grid_sampler.is_tile_walkable(tile):
		return false
	if _count_soft_blocks_in_range(tile, bomb_range, grid_sampler) == 0:
		return false
	return true

func _do_full_search_and_broadcast(current_tile: Vector2i, bomb_range: int, current_time_msec: int, player, game_instance, grid_sampler, bomb_safety_checker, ai_manager) -> void:
	"""Perform full search and broadcast for continuous visualization"""
	var safety_eval := {}
	
	if not ai_manager:
		print("[BTFindFarmingSpot] BROADCAST SKIPPED - no ai_manager")
		return # Can't evaluate without ai_manager
	
	print("[BTFindFarmingSpot] Broadcasting from ", current_tile, " (search_radius=", search_radius, ")")
	
	var total_tiles = 0
	var rejected_path = 0
	var rejected_safety = 0
	var rejected_escape = 0
	var passed = 0
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			var check_tile = current_tile + Vector2i(dx, dy)
			total_tiles += 1
			
			if not grid_sampler.is_tile_walkable(check_tile):
				continue
			
			var soft_blocks_hit = _count_soft_blocks_in_range(check_tile, bomb_range, grid_sampler)
			if soft_blocks_hit == 0:
				continue
			
			# Check if tile is threatened
			if ai_manager:
				var threat_matrix = ai_manager.get_current_threat_matrix()
				var t_key := "%d,%d" % [check_tile.x, check_tile.y]
				if threat_matrix.has(t_key):
					safety_eval[t_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "threatened"}
					rejected_safety += 1
					continue
			
			var tile_key := "%d,%d" % [check_tile.x, check_tile.y]
			
			# Check path - adjacent tiles are always reachable if walkable
			var manhattan_dist = abs(dx) + abs(dy)
			if manhattan_dist > 1:
				var path = grid_sampler.find_path(current_tile, check_tile, 15, player)
				if path.is_empty():
					safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_path"}
					rejected_path += 1
					continue
			# Adjacent tile (distance == 1) - skip pathfinding, assume reachable
			
			# Check nearby safety
			var has_nearby_safety = _has_safe_tile_nearby_static(check_tile, grid_sampler, current_time_msec, ai_manager)
			if not has_nearby_safety:
				safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_nearby_safe"}
				rejected_safety += 1
				continue
			
			# Check escape
			var safety_result = bomb_safety_checker.check_plant_safety_detailed(
				check_tile,
				check_tile,
				bomb_range,
				5.0,
				current_time_msec
			)
			
			if not safety_result.safe:
				safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": safety_result.get("explored_tiles", 0), "reason": "no_escape"}
				rejected_escape += 1
				continue
			
			# Calculate score
			var damage_score = soft_blocks_hit * 10.0
			var margin = safety_result.get("margin_ms", 1000.0)
			var escape_tile = safety_result.get("escape_tile", null)
			
			var escape_distance = 999
			if escape_tile:
				if escape_tile is Vector2i:
					escape_distance = abs(escape_tile.x - check_tile.x) + abs(escape_tile.y - check_tile.y)
				elif escape_tile is Dictionary:
					escape_distance = abs(int(escape_tile.x) - check_tile.x) + abs(int(escape_tile.y) - check_tile.y)
			
			var safety_multiplier = 1.0
			if escape_distance == 1:
				safety_multiplier *= 1.5
			elif escape_distance == 2:
				safety_multiplier *= 1.2
			elif escape_distance >= 5:
				safety_multiplier *= 0.7
			
			if margin > 1000.0:
				safety_multiplier *= 1.2
			elif margin < 800.0:
				safety_multiplier *= 0.8
			
			var score = damage_score * safety_multiplier
			var distance = abs(dx) + abs(dy)
			score -= distance * 0.3
			
			var status = 2 if margin > 800.0 else 1
			var eval_data = {
				"status": status,
				"soft_blocks": soft_blocks_hit,
				"explored_tiles": safety_result.get("explored_tiles", 0),
				"margin_ms": margin,
				"escape_distance": escape_distance,
				"final_score": score
			}
			if escape_tile:
				eval_data["escape_tile"] = {"x": escape_tile.x, "y": escape_tile.y}
			safety_eval[tile_key] = eval_data
			passed += 1
	
	# Debug logging
	print("[BTFindFarmingSpot] _do_full_search_and_broadcast: passed=", passed, " path=", rejected_path, " safety=", rejected_safety, " escape=", rejected_escape, " dict_size=", safety_eval.size())
	
	# Broadcast
	if not safety_eval.is_empty():
		print("[BTFindFarmingSpot] *** Broadcasting ", safety_eval.size(), " tiles from _do_full_search_and_broadcast")
		_broadcast_safety_data(safety_eval)
	else:
		print("[BTFindFarmingSpot] *** WARNING: safety_eval is EMPTY in _do_full_search_and_broadcast")
