@tool
extends BTAction
class_name BTFindFarmingSpot

## Finds a nearby soft block position that has an escape route
## Sets target_cell in blackboard for safe bomb placement

@export var search_radius: int = 5 ## How far to search for soft blocks
@export var target_cell_var: StringName = &"target_cell" ## Where to store the target
@export var debug_logging: bool = false ## Enable detailed rejection logging
@export var broadcast_safety: bool = true ## Send safety eval to clients for visualization

const INVALID_TILE := Vector2i(-1, -1)

func _generate_name() -> String:
	return "FindFarmingSpot(radius=%d)" % search_radius

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	
	if not player or not game_instance or not grid_sampler or not bomb_safety_checker:
		return FAILURE
	
	var current_tile = player.get_tile_position()
	var bomb_range = player.bomb_range
	var current_time_msec = Time.get_ticks_msec()

	# If we already have a valid farming target, reuse it to avoid expensive rescans every tick
	var existing_target = _coerce_to_tile(blackboard.get_var(target_cell_var))
	if _is_valid_target(existing_target, grid_sampler, bomb_range):
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
	
	if debug_logging:
		print("[BTFindFarmingSpot] Starting search from ", current_tile, " radius=", search_radius, " bomb_range=", bomb_range)
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			if dx == 0 and dy == 0:
				continue
			
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
			
			var tile_key := "%d,%d" % [check_tile.x, check_tile.y]
			
			# Check if we can reach this tile
			var path = grid_sampler.find_path(current_tile, check_tile, 15, player)
			if path.is_empty() and check_tile != current_tile:
				rejected_no_path += 1
				if broadcast_safety:
					safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_path"}
				if debug_logging:
					print("  [REJECT] ", check_tile, " - no path (blocks=", soft_blocks_hit, ")")
				continue
			
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
			
			# Score: prioritize closer tiles with more soft blocks
			var distance = abs(dx) + abs(dy)
			var score = (soft_blocks_hit * 10.0) - (distance * 0.5)
			
			if score > best_score:
				best_score = score
				best_spot = check_tile
			
			# Mark as safe or marginal for visualization based on safety margin
			if broadcast_safety:
				tile_key = "%d,%d" % [check_tile.x, check_tile.y]
				var margin = safety_result.get("margin_ms", 1000.0)
				var status = 2 if margin > 800.0 else 1  # Safe (cyan) if >800ms margin, marginal (orange) otherwise
				var escape_tile = safety_result.get("escape_tile", null)
				var eval_data = {
					"status": status,
					"soft_blocks": soft_blocks_hit,
					"explored_tiles": safety_result.get("explored_tiles", 0),
					"margin_ms": margin
				}
				if escape_tile:
					eval_data["escape_tile"] = {"x": escape_tile.x, "y": escape_tile.y}
				safety_eval[tile_key] = eval_data
	
	# Broadcast safety data to all clients
	if broadcast_safety and not safety_eval.is_empty():
		print("[BTFindFarmingSpot] Broadcasting %d safety evaluations" % safety_eval.size())
		_broadcast_safety_data(safety_eval)
	elif broadcast_safety:
		print("[BTFindFarmingSpot] No safety data to broadcast (empty)")
	
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
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check horizontal (left)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(-dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (down)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	# Check vertical (up)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, -dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
		if tile_type == 1: # Hard block - stops blast
			break
	
	return count

func _has_safe_tile_nearby(position: Vector2i, grid_sampler, current_time_msec: float) -> bool:
	"""Check if there's at least one safe tile within reasonable distance (no threats, walkable)"""
	var ai_manager = blackboard.get_var("ai_manager")
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

	# No safe tiles found nearby - we're in a danger zone
	return false

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

func _broadcast_safety_data(data: Dictionary) -> void:
	"""Send safety evaluation to all clients for visualization"""
	# Get the bot player node from blackboard
	var player_node = blackboard.get_var("player")
	if not player_node:
		return
	
	# Navigate to the game instance (player's parent)
	var game_instance = player_node.get_parent()
	if not game_instance:
		return
	
	# Broadcast via game instance's multiplayer peer
	if not game_instance.multiplayer:
		return
	
	var peers = game_instance.multiplayer.get_peers()
	if peers.is_empty():
		return
	
	# Send RPC to all connected clients
	for peer_id in peers:
		if peer_id > 0:  # Skip server (ID 1)
			ClientMain.rpc_id(peer_id, "bomb_safety_update", data)
	
	print("[BotAI] Broadcasted safety data: %d tiles to %d peers" % [data.size(), peers.size()])

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
