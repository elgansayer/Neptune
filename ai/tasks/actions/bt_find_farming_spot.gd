@tool
extends BTAction
class_name BTFindFarmingSpot

const SimulationTime = preload("res://shared/ai/simulation_time.gd")
const MovementTiming = preload("res://shared/ai/movement_timing.gd")

## Finds a nearby soft block position that has an escape route
## Sets target_cell in blackboard for safe bomb placement

@export var search_radius: int = 5 ## How far to search for soft blocks
@export var target_cell_var: StringName = &"target_cell" ## Where to store the target
@export var debug_logging: bool = false ## Opt-in diagnostic logging.
@export var broadcast_safety: bool = false ## Opt-in detached local safety snapshot.
@export var always_broadcast: bool = false ## Re-publish cached diagnostic data, never rescore it.
@export var max_search_expansions: int = 256
@export var max_safety_checks: int = 12
@export var rescan_interval_msec: float = 250.0

var _last_search_signature := 0
var _next_search_msec := -INF
var _last_safety_eval := {}
var _next_debug_msec := -INF

const INVALID_TILE := Vector2i(-1, -1)

func _generate_name() -> String:
	return "FindFarmingSpot(radius=%d)" % search_radius

func _tick(_delta: float) -> int:
	# print("[BTFindFarmingSpot] ===== _tick() CALLED ===== delta=", _delta)
	var player = blackboard.get_var("player")

	# Early exit if player is dead
	if player and player.is_dead:
		return FAILURE

	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")

	# print("[BTFindFarmingSpot] Retrieved from blackboard: player=", player != null, " game_instance=", game_instance != null, " grid_sampler=", grid_sampler != null, " bomb_safety_checker=", bomb_safety_checker != null)

	if not player or not game_instance or not grid_sampler or not bomb_safety_checker:
		# print("[BTFindFarmingSpot] _tick() FAILURE - missing dependencies")
		return FAILURE

	var current_tile = player.get_tile_position()
	var bomb_range = player.get_effective_bomb_range()
	var current_time_msec = SimulationTime.milliseconds(blackboard)

	# If we already have a valid farming target, reuse it to avoid expensive rescans every tick
	var existing_target = _coerce_to_tile(blackboard.get_var(target_cell_var, null))
	if _is_valid_target(existing_target, grid_sampler, bomb_range):
		# print("[BTFindFarmingSpot] *** REUSING CACHED TARGET at ", existing_target, " always_broadcast=", always_broadcast)
		# Still broadcast for continuous visualization even when reusing target
		if broadcast_safety and always_broadcast and current_time_msec >= _next_debug_msec:
			_broadcast_safety_data(_last_safety_eval)
			_next_debug_msec = current_time_msec + maxf(rescan_interval_msec, 100.0)
		return SUCCESS
	elif existing_target != INVALID_TILE:
		# Cache exists but is no longer valid - clear it and search for a new spot
		# print("[BTFindFarmingSpot] ⚠ Cached target ", existing_target, " is now INVALID - clearing cache and searching for new spot")
		blackboard.set_var(target_cell_var, null)
	var manager = blackboard.get_var("ai_manager", null)
	var threats: Dictionary = manager.get_current_threat_matrix() if manager else {}
	var signature := _search_signature(current_tile, bomb_range, game_instance, threats)
	if signature == _last_search_signature and current_time_msec < _next_search_msec:
		return FAILURE
	_last_search_signature = signature
	_next_search_msec = current_time_msec + maxf(rescan_interval_msec, 0.0)
	blackboard.set_var("farming_searches", int(blackboard.get_var("farming_searches", 0, false)) + 1)
	var reachable := _reachable_tiles(current_tile, grid_sampler, player, threats)
	blackboard.set_var("farming_search_expanded", reachable.size())
	var safety_checks := 0

	# Search nearby tiles for soft blocks
	var best_spot: Vector2i = INVALID_TILE
	var best_score: float = 0.0
	var candidates_checked := 0
	var rejected_unwalkable := 0
	var rejected_no_blocks := 0
	var rejected_no_nearby_safe := 0
	var rejected_no_escape := 0

	# Safety visualization data for client
	var safety_eval := {}

	# print("[BTFindFarmingSpot] STARTING SEARCH - broadcast_safety=", broadcast_safety)

	if debug_logging:
		pass # print("[BTFindFarmingSpot] Starting search from ", current_tile, " radius=", search_radius, " bomb_range=", bomb_range)
		pass
	for check_tile: Vector2i in reachable:
		candidates_checked += 1

		# Must be walkable AND not have a bomb on it
		if not grid_sampler.is_tile_safe_for_target(check_tile):
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
					pass # print("  [REJECT] ", check_tile, " - threatened")
				continue

		var tile_key := "%d,%d" % [check_tile.x, check_tile.y]

		# Check if target is penalized (stuck)
		var stuck_targets = {}
		if blackboard.has_var("stuck_targets"):
			stuck_targets = blackboard.get_var("stuck_targets")

		if stuck_targets.has(tile_key):
			if SimulationTime.milliseconds(blackboard) < stuck_targets[tile_key]:
				if debug_logging:
					pass # print("  [REJECT] ", check_tile, " - penalized (stuck)")
				continue
			else:
				stuck_targets.erase(tile_key) # Expired

		# Reachability and real route depth came from one shared bounded BFS.
		# CRITICAL: Check if there's ALREADY a safe tile nearby (without planting bomb)
		# This ensures we're not in a dead-end surrounded by soft blocks
		var has_nearby_safety = _has_safe_tile_nearby(check_tile, grid_sampler, current_time_msec)
		if not has_nearby_safety:
			rejected_no_nearby_safe += 1
			if broadcast_safety:
				safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": 0, "reason": "no_nearby_safe"}
			if debug_logging:
				pass # print("  [REJECT] ", check_tile, " - no nearby safe tile (blocks=", soft_blocks_hit, ")")

		# Check if we can safely plant a bomb HERE (at check_tile) and escape
		# IMPORTANT: bot_pos is check_tile because that's where we'll be when planting
		if safety_checks >= clampi(max_safety_checks, 0, 64):
			break
		safety_checks += 1
		var safety_result = bomb_safety_checker.check_plant_safety_detailed(
			check_tile, # Where the bot will be standing when planting
			check_tile, # Where the bomb will be planted
			bomb_range,
			MovementTiming.tiles_per_second(player),
			current_time_msec,
			false, player.get_bomb_fuse_lower_bound(), player
		)

		if not safety_result.get("safe", false):
			rejected_no_escape += 1
			if broadcast_safety:
				safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": safety_result.get("explored_tiles", 0), "reason": "no_escape"}
			if debug_logging:
				pass # print("  [REJECT] ", check_tile, " - no escape route (blocks=", soft_blocks_hit, ")")
			continue

		# CRITICAL: Check if the escape tile is a dead end!
		# If we escape to a dead end, we'll be stuck there until bomb explodes.
		# This causes DEAD-END ABORT spam when the tree loops.
		var escape_tile_raw = safety_result.get("escape_tile", Vector2i(-1, -1))
		var escape_tile_v2i: Vector2i
		if escape_tile_raw is Vector2i:
			escape_tile_v2i = escape_tile_raw
		elif escape_tile_raw is Dictionary:
			escape_tile_v2i = Vector2i(int(escape_tile_raw.x), int(escape_tile_raw.y))
		else:
			escape_tile_v2i = Vector2i(-1, -1)

		if escape_tile_v2i != Vector2i(-1, -1):
			var escape_exits = _count_walkable_neighbors(escape_tile_v2i, grid_sampler)
			if escape_exits <= 1:
				# Escape tile is a dead end - reject this farming spot!
				rejected_no_escape += 1
				if broadcast_safety:
					safety_eval[tile_key] = {"status": 0, "soft_blocks": soft_blocks_hit, "explored_tiles": safety_result.get("explored_tiles", 0), "reason": "escape_is_dead_end"}
				if debug_logging:
					print("  [REJECT] ", check_tile, " - escape tile ", escape_tile_v2i, " is a dead end (exits=", escape_exits, ")")
				continue

		# CORRECTED SCORING: Safety-First Algorithm
		# Score = Damage_Potential * Safety_Multiplier (NOT additive!)

		# Base damage score
		var damage_score = soft_blocks_hit * 10.0

		# Safety multiplier based on escape quality
		var margin = safety_result.get("margin_ms", 1000.0)
		# Margin factor (>1000ms = 1.2x, 800-1000ms = 1.0x, <800ms = 0.8x)
		# Calculate escape distance (1-step escapes are ideal)
		var escape_tile = safety_result.get("escape_tile", Vector2i(-1, -1))
		var escape_distance = 999
		if escape_tile and escape_tile != Vector2i(-1, -1):
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

		if margin > 1000.0:
			safety_multiplier *= 1.2
		elif margin < 800.0:
			safety_multiplier *= 0.8

		# Final score: multiplicative formula
		var score = damage_score * safety_multiplier

		# Proximity bonus (slightly favor closer tiles to avoid long walks)
		var distance: int = reachable[check_tile]
		score -= distance * 0.3

		if score > best_score:
			best_score = score
			best_spot = check_tile

		# Mark as safe or marginal for visualization based on safety margin
		if broadcast_safety:
			tile_key = "%d,%d" % [check_tile.x, check_tile.y]
			var safety_status = 2 if margin > 800.0 else 1 # Safe (cyan) if >800ms margin, marginal (orange) otherwise
			var eval_data = {
				"status": safety_status,
				"soft_blocks": soft_blocks_hit,
				"explored_tiles": safety_result.get("explored_tiles", 0),
				"margin_ms": margin,
				"escape_distance": escape_distance,
				"final_score": score # Include score for debugging
			}
			if escape_tile:
				eval_data["escape_tile"] = {"x": escape_tile.x, "y": escape_tile.y}
			safety_eval[tile_key] = eval_data

	blackboard.set_var("farming_safety_checks", safety_checks)
	blackboard.set_var("farming_search_diagnostics", {"candidates": candidates_checked,
		"blocked": rejected_unwalkable, "no_blocks": rejected_no_blocks,
		"unsafe": rejected_no_nearby_safe, "no_escape": rejected_no_escape})
	_last_safety_eval = safety_eval.duplicate(true) if broadcast_safety else {}

	# Broadcast safety data to all clients
	# print("[BTFindFarmingSpot] *** BROADCAST CHECK: broadcast_safety=", broadcast_safety, " safety_eval.size()=", safety_eval.size())
	if broadcast_safety and not safety_eval.is_empty():
		pass # print("[BTFindFarmingSpot] *** BROADCASTING %d safety evaluations to clients" % safety_eval.size())
		_broadcast_safety_data(safety_eval)
	elif broadcast_safety:
		pass # print("[BTFindFarmingSpot] *** WARNING: No safety data to broadcast (empty)")
	else:
		pass # print("[BTFindFarmingSpot] *** WARNING: broadcast_safety is FALSE")
	# If we found a good spot, store it
	if best_spot != INVALID_TILE:
		blackboard.set_var(target_cell_var, best_spot)
		# print("[BTFindFarmingSpot] ✓ Found farming spot at ", best_spot, " (score: ", best_score, ")")
		return SUCCESS

	# No good farming spot found - report why
	# print("[BTFindFarmingSpot] ✗ No safe farming spots found (checked=", candidates_checked,
	#	" unwalkable=", rejected_unwalkable,
	#	" no_blocks=", rejected_no_blocks,
	#	" no_path=", rejected_no_path,
	#	" no_nearby_safe=", rejected_no_nearby_safe,
	#	" no_escape=", rejected_no_escape, ")")

	# FINAL FALLBACK: If completely stuck with no farming or breakout options,
	# try to move toward map center or opponents to find more options
	var fallback_tile = _find_movement_fallback(current_tile, grid_sampler, player, reachable)
	if fallback_tile != INVALID_TILE:
		print("[BTFindFarmingSpot] FALLBACK MOVE: %s → %s (toward center/opponent)" % [current_tile, fallback_tile])
		blackboard.set_var(target_cell_var, fallback_tile)
		if broadcast_safety:
			_broadcast_safety_data({})
		return SUCCESS

	# Clear visualization if nothing found
	if broadcast_safety:
		_broadcast_safety_data({})

	return FAILURE

func _reachable_tiles(start: Vector2i, sampler, player, threats: Dictionary) -> Dictionary:
	var depths := {start: 0}
	var queue: Array[Vector2i] = [start]
	var head := 0
	var limit := clampi(max_search_expansions, 1, 2048)
	while head < queue.size() and head < limit:
		var cell: Vector2i = queue[head]
		head += 1
		if int(depths[cell]) >= maxi(0, search_radius): continue
		for direction: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			var next := cell + direction
			if depths.has(next) or depths.size() >= limit: continue
			if not sampler.is_tile_safe_for_target(next) or sampler.is_tile_occupied(next, player) or threats.has(_tile_key(next)): continue
			depths[next] = int(depths[cell]) + 1
			queue.append(next)
	return depths

func _search_signature(tile: Vector2i, radius: int, game, threats: Dictionary) -> int:
	var occupancy := []
	for actor in game.players.values():
		if is_instance_valid(actor) and not actor.is_dead: occupancy.append([actor.peer_id, actor.get_tile_position()])
	for bomb in game.bombs.values():
		if is_instance_valid(bomb): occupancy.append([bomb.bomb_id, bomb.get_tile_position(), bomb.bomb_state])
	var cells: Array = threats.keys()
	cells.sort()
	return hash([tile, radius, game.game_map, occupancy, cells, blackboard.get_var("stuck_targets", {}, false)])

func _count_soft_blocks_in_range(center: Vector2i, bomb_range: int, grid_sampler) -> int:
	var count = 0

	# Check horizontal (right)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type in [1, 3]: # Hard and hurry blocks stop blast.
			break

	# Check horizontal (left)
	for dx in range(1, bomb_range + 1):
		var tile = center + Vector2i(-dx, 0)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type in [1, 3]: # Hard and hurry blocks stop blast.
			break

	# Check vertical (down)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type in [1, 3]: # Hard and hurry blocks stop blast.
			break

	# Check vertical (up)
	for dy in range(1, bomb_range + 1):
		var tile = center + Vector2i(0, -dy)
		var tile_type = grid_sampler.get_tile_type(tile)
		if tile_type == 2: # Soft block
			count += 1
			break # Soft block stops the blast
		if tile_type in [1, 3]: # Hard and hurry blocks stop blast.
			break

	return count

func _has_safe_tile_nearby(position: Vector2i, grid_sampler, current_time_msec: float) -> bool:
	"""Check if there's at least one safe tile within reasonable distance (no threats, walkable)"""
	var ai_manager = blackboard.get_var("ai_manager")
	if not ai_manager:
		return false
	return _has_safe_tile_nearby_static(position, grid_sampler, current_time_msec, ai_manager)

func _has_safe_tile_nearby_static(position: Vector2i, grid_sampler, _current_time_msec: float, ai_manager) -> bool:
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
	# Local diagnostic data only. Policy views do not navigate to authority nodes
	# or send RPCs; an operator can inspect this detached blackboard payload.
	blackboard.set_var("safety_debug_snapshot", data.duplicate(true))

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
	if not grid_sampler.is_tile_safe_for_target(tile):
		return false
	if _count_soft_blocks_in_range(tile, bomb_range, grid_sampler) == 0:
		return false

	# CRITICAL: Check if the cached target is threatened by an active bomb
	# If there's a bomb on or near this tile, we need to invalidate the cache and find a new spot
	var ai_manager = blackboard.get_var("ai_manager")
	if ai_manager:
		var threat_matrix = ai_manager.get_current_threat_matrix()
		var t_key := "%d,%d" % [tile.x, tile.y]
		if threat_matrix.has(t_key):
			print("[BTFindFarmingSpot] ⚠ Cached target ", tile, " is now THREATENED - invalidating cache")
			return false

	# Check if target is penalized (stuck)
	var stuck_targets = {}
	if blackboard.has_var("stuck_targets"):
		stuck_targets = blackboard.get_var("stuck_targets")

	var s_key = "%d,%d" % [tile.x, tile.y]
	if stuck_targets.has(s_key):
		if SimulationTime.milliseconds(blackboard) < stuck_targets[s_key]:
			print("[BTFindFarmingSpot] ⚠ Cached target ", tile, " is PENALIZED (stuck) - invalidating cache")
			return false
		else:
			stuck_targets.erase(s_key) # Expired

	return true

## Count walkable neighbor tiles (used to detect dead ends)
func _count_walkable_neighbors(tile: Vector2i, grid_sampler) -> int:
	var count = 0
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var neighbor = tile + dir
		if grid_sampler.is_tile_walkable(neighbor):
			count += 1
	return count

## Movement-only fallback reuses the same bounded public reachability result.
## It does not authorize planting; BTPlaceBomb still requires a useful safe bomb.
func _find_movement_fallback(current_tile: Vector2i, grid_sampler, player, reachable: Dictionary) -> Vector2i:
	var bounds: Vector2i = grid_sampler.get_map_bounds()
	var target := Vector2i(bounds.x / 2, bounds.y / 2)
	var nearest = blackboard.get_var("opponent_tracker", null)
	for objective in range(2):
		var best := INVALID_TILE
		var best_distance: int = grid_sampler.get_manhattan_distance(current_tile, target)
		var best_depth := 2147483647
		for cell: Vector2i in reachable:
			if cell == current_tile: continue
			var distance: int = grid_sampler.get_manhattan_distance(cell, target)
			var depth: int = reachable[cell]
			if distance < best_distance or (distance == best_distance and best != INVALID_TILE and depth < best_depth):
				best = cell
				best_distance = distance
				best_depth = depth
		if best != INVALID_TILE: return best
		if objective == 0 and nearest:
			var opponent: Dictionary = nearest.get_nearest_opponent(player.position, player.peer_id)
			if opponent.is_empty(): return INVALID_TILE
			target = opponent.tile
		else:
			return INVALID_TILE
	return INVALID_TILE
