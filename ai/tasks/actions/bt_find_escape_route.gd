@tool
extends BTAction
class_name BTFindEscapeRoute

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## Finds a safe escape route from danger using the AI pathfinder
## Sets target_cell in blackboard if a safe path is found

@export var escape_radius: int = 8 ## How far to search for safety
@export var target_cell_var: StringName = &"target_cell" ## Where to store the escape destination
@export var debug_logging: bool = true

static var _tick_count: int = 0

func _generate_name() -> String:
	return "FindEscapeRoute"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	
	# Early exit if player is dead
	if player and player.is_dead:
		return FAILURE
	
	var game_instance = blackboard.get_var("game_instance")
	var ai_manager = blackboard.get_var("ai_manager")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var threat_matrix = ai_manager.threat_matrix if ai_manager else {}
	var current_time_msec = SimulationTime.milliseconds(blackboard)
	# Calculate msec_per_tile based on bot speed (tiles per second = speed / tile_size)
	# Default: BASE_SPEED=45 px/s, TILE_SIZE=16px → 45/16 = 2.8125 tiles/s → 355ms/tile
	var bot_speed_tiles_per_sec = GameConfig.BASE_SPEED / GameConfig.TILE_SIZE
	var msec_per_tile = (1.0 / bot_speed_tiles_per_sec) * 1000.0
	var hazard_predictor = blackboard.get_var("hazard_predictor")
	
	# DEBUG: Log threat matrix state at start
	if threat_matrix.size() > 0 and debug_logging:
		print("[BTFindEscapeRoute] THREAT_MATRIX_SIZE=", threat_matrix.size(), " KEYS=", threat_matrix.keys())
	
	# print("[BTFindEscapeRoute] STARTING escape route search for bot at ", player.get_tile_position() if player else "unknown")
	
	if not player or not game_instance or not ai_manager or not grid_sampler or not hazard_predictor:
		push_warning("[BTFindEscapeRoute] Missing required blackboard variables")
		return FAILURE
		
	var player_tile = player.get_tile_position()
	
	# --- COMMITMENT LOGIC ---
	# Check if we already have a valid escape route that is still safe
	# This prevents the bot from jittering between multiple safe spots
	var current_escape_target = blackboard.get_var(target_cell_var, null)
	var escape_route_found = blackboard.get_var("escape_route_found", false)
	
	if escape_route_found and current_escape_target != null:
		# We have a route. Is it still valid?
		if current_escape_target is Vector2:
			current_escape_target = Vector2i(int(current_escape_target.x), int(current_escape_target.y))
			
		if current_escape_target is Vector2i:
			# Check if the target is still safe
			var current_time = SimulationTime.seconds(blackboard)
			var is_target_safe = hazard_predictor.is_tile_safe(current_escape_target, current_time, 0.5)
			
			# CRITICAL: Also verify the PATH to the target is still valid!
			# This prevents the bot from being trapped when another bomb blocks the path.
			var path_valid = true
			var path_to_target = grid_sampler.find_path(player_tile, current_escape_target, escape_radius, player)
			if path_to_target.is_empty() and player_tile != current_escape_target:
				path_valid = false
				if debug_logging:
					print("[BTFindEscapeRoute] ⚠ Path to escape target blocked! Recalculating...")
			
			# CRITICAL: Check if any tile along the path is in an active explosion!
			# The threat_matrix now includes active_explosion_tiles (tiles currently on fire)
			if path_valid and path_to_target.size() > 0:
				for index in range(path_to_target.size()):
					var tile_pos: Vector2i = path_to_target[index]
					var tile_key = _tile_key(tile_pos)
					if threat_matrix.has(tile_key):
						# Check if this tile is IMMEDIATELY dangerous (current time or earlier = active explosion)
						var threat_time = threat_matrix[tile_key]
						if threat_time <= current_time_msec + (index + 1) * msec_per_tile + 100.0:
							path_valid = false
							if debug_logging:
								print("[BTFindEscapeRoute] ⚠ Path passes through ACTIVE EXPLOSION at ", tile_pos, "! Recalculating...")
							break
			
			# Check if the target has a bomb on it (which would be bad)
			var has_bomb = false
			if not grid_sampler.is_tile_safe_for_target(current_escape_target):
				has_bomb = true
				
			if is_target_safe and not has_bomb and path_valid:
				current_escape_target = _improve_refuge(current_escape_target, player_tile, threat_matrix, grid_sampler, player, current_time_msec, msec_per_tile)
				blackboard.set_var(target_cell_var, current_escape_target)
				if debug_logging:
					print("[BTFindEscapeRoute] Keeping existing valid escape target: ", current_escape_target)
				return SUCCESS
			elif not path_valid:
				# Path is blocked or dangerous - need to find new escape route
				blackboard.set_var("escape_route_found", false)
	
	# BFS to find safe tiles considering TIMING and WALLS
	# A tile is safe if either:
	# 1. It's not in threat matrix at all (never explodes)
	# 2. We can reach it and stay there safely before it explodes
	
	# Get personality config for escape aggression
	var personality_config = blackboard.get_var("personality_config", {})
	# COMPETITIVE bots cut closer margins (750ms) vs cautious bots (1500ms)
	var min_safety_margin_ms = 750.0 if personality_config.get("trap_aggression", 0.5) >= 0.8 else 1500.0
	
	var queue: Array[Vector2i] = [player_tile]
	var visited: Dictionary = {_tile_key(player_tile): current_time_msec} # tile_key -> arrival_time_msec
	var head := 0
	
	var best_safe_tile: Vector2i = Vector2i(-1, -1)
	var best_distance: int = 999999
	var best_safety_margin: float = -1.0
	var found_permanent_safe: bool = false
	var found_safe_dead_end := false
	var best_panic_tile: Vector2i = Vector2i(-1, -1)
	var best_panic_margin: float = -1.0
	
	while head < queue.size():
		var current_pos := queue[head]
		head += 1
		
		var current_key := _tile_key(current_pos)
		var arrival_time: float = visited[current_key]
		var distance_from_start: int = abs(current_pos.x - player_tile.x) + abs(current_pos.y - player_tile.y)
		
		# CRITICAL: Never consider current tile as escape destination - bot MUST move
		if current_pos == player_tile:
			pass
		else:
			# Check if this tile is safe (using threat matrix)
			var is_permanently_safe = not threat_matrix.has(current_key)
			var safety_margin: float = 0.0
			
			# DEBUG: Log check for first few tiles
			if distance_from_start <= 2 and debug_logging:
				print("[BTFindEscapeRoute] CHECK tile=", current_pos, " key=", current_key, " in_threat=", threat_matrix.has(current_key), " perm_safe=", is_permanently_safe)
			
			if is_permanently_safe:
				# CRITICAL FIX: For ESCAPE routes, a permanently safe dead end is ACCEPTABLE!
				# The bot can survive there even if trapped - they just wait for bombs to explode.
				# Dead ends are only dangerous when we're PLANNING to place a bomb after arriving.
				var has_further_exit = _tile_has_further_exit(current_pos, threat_matrix, player_tile, grid_sampler)
				
				if not has_further_exit:
					# This is a DEAD END but permanently safe - still use it for escape!
					if debug_logging:
						print("[BTFindEscapeRoute] ✓ Tile ", current_pos, " is DEAD END but PERMANENTLY SAFE - acceptable for escape!")
					# Accept this as a valid escape destination (lower priority than tiles with exits)
					if not found_permanent_safe:
						# A true refuge outranks a closer tile that will explode.
						if not found_safe_dead_end or distance_from_start < best_distance:
							best_safe_tile = current_pos
							best_distance = distance_from_start
							best_safety_margin = 999999.0
							found_safe_dead_end = true
							print("[BTFindEscapeRoute] Using SAFE DEAD END at ", current_pos, " (distance: ", distance_from_start, ")")
				elif not found_permanent_safe:
					# This tile never explodes AND has further exits - PRIORITIZE IT
					found_permanent_safe = true
					best_safe_tile = current_pos
					best_distance = distance_from_start
					best_safety_margin = 999999.0
					print("[BTFindEscapeRoute] Found permanently safe tile at ", current_pos, " (distance: ", distance_from_start, ")")
				elif distance_from_start < best_distance:
					best_safe_tile = current_pos
					best_distance = distance_from_start
					best_safety_margin = 999999.0
					print("[BTFindEscapeRoute] Found CLOSER permanently safe tile at ", current_pos, " (distance: ", distance_from_start, ")")
			else:
				# Tile will explode at some point
				if not found_permanent_safe and not found_safe_dead_end:
					var explosion_time: float = threat_matrix[current_key]
					safety_margin = explosion_time - arrival_time
					
					# CRITICAL: Check for dead ends even on tiles that will explode!
					# A dead end is dangerous because there's nowhere to go after
					var has_further_exit = _tile_has_further_exit(current_pos, threat_matrix, player_tile, grid_sampler)
					
					if not has_further_exit:
						# This is a DEAD END - only use as panic option, never as safe tile
						if safety_margin > best_panic_margin:
							best_panic_margin = safety_margin
							best_panic_tile = current_pos
						if debug_logging:
							print("[BTFindEscapeRoute] ⚠ Tile ", current_pos, " has margin ", safety_margin, "ms but is DEAD END - only for panic")
					else:
						# Track best panic option (any tile we can reach before explosion)
						# Prefer larger margins
						if safety_margin > best_panic_margin:
							best_panic_margin = safety_margin
							best_panic_tile = current_pos
						
						# Need at least min_safety_margin_ms safety margin to consider it "safe enough"
						# COMPETITIVE bots use 750ms, cautious bots use 1500ms
						if safety_margin > min_safety_margin_ms:
							if distance_from_start < best_distance or (distance_from_start == best_distance and safety_margin > best_safety_margin):
								best_safe_tile = current_pos
								best_distance = distance_from_start
								best_safety_margin = safety_margin
		
		# Continue searching...
		# CRITICAL FIX: Always explore neighbors from the STARTING tile, even if it's threatened!
		# The bot is already there, so it doesn't matter if it's threatened.
		# Only check can_pass_through for INTERMEDIATE tiles.
		var can_pass_through = false
		if current_pos == player_tile:
			can_pass_through = true # Always explore from starting position
		elif threat_matrix.has(current_key):
			var explosion_time = threat_matrix[current_key]
			can_pass_through = arrival_time < explosion_time # Can we pass before explosion?
		else:
			can_pass_through = true
		
		if best_safe_tile != Vector2i(-1, -1) and distance_from_start >= best_distance:
			if found_permanent_safe:
				continue
		
		if can_pass_through and distance_from_start < escape_radius:
			var neighbors_checked = 0
			var neighbors_added = 0
			for dir: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
				var next_pos := current_pos + dir
				neighbors_checked += 1
				
				if not grid_sampler.is_tile_walkable(next_pos):
					if debug_logging and current_pos == player_tile:
						print("[BTFindEscapeRoute] DEBUG: Neighbor ", next_pos, " not walkable (wall/block)")
					continue
				
				var next_key := _tile_key(next_pos)
				var next_arrival_time: float = arrival_time + msec_per_tile
				
				if visited.has(next_key) and visited[next_key] <= next_arrival_time:
					if debug_logging and current_pos == player_tile:
						print("[BTFindEscapeRoute] DEBUG: Neighbor ", next_pos, " already visited")
					continue
				
				# CRITICAL: DO NOT check stuck penalties during escape!
				# Survival trumps movement history. If a tile was stuck due to
				# collision/pathfinding issues, that's still better than dying.
				# The bot MUST try every possible escape route.
				# Skip if penalized (stuck) - DISABLED FOR ESCAPE
				# var stuck_targets = {}
				# if blackboard.has_var("stuck_targets"):
				# 	stuck_targets = blackboard.get_var("stuck_targets")
				# if stuck_targets.has(next_key):
				# 	if SimulationTime.milliseconds(blackboard) < stuck_targets[next_key]:
				# 		if debug_logging and current_pos == player_tile:
				# 			print("[BTFindEscapeRoute] DEBUG: Neighbor ", next_pos, " penalized (stuck)")
				# 		continue
				# 	else:
				# 		stuck_targets.erase(next_key)
				
				# Skip if tile has a bomb
				var has_bomb = false
				for bomb_id in game_instance.bombs:
					var bomb = game_instance.bombs[bomb_id]
					if is_instance_valid(bomb) and not bomb.has_exploded:
						if bomb.get_tile_position() == next_pos:
							has_bomb = true
							break
				if has_bomb:
					if debug_logging and current_pos == player_tile:
						print("[BTFindEscapeRoute] DEBUG: Neighbor ", next_pos, " has bomb")
					continue

				visited[next_key] = next_arrival_time
				queue.append(next_pos)
				neighbors_added += 1
			
			if debug_logging and current_pos == player_tile:
				print("[BTFindEscapeRoute] DEBUG: From starting tile: checked ", neighbors_checked, " neighbors, added ", neighbors_added, " to queue")
	
	# Use best tile found
	var final_target = Vector2i(-1, -1)
	var is_panic = false
	
	if best_safe_tile != Vector2i(-1, -1):
		final_target = best_safe_tile
		if found_permanent_safe:
			final_target = _improve_refuge(final_target, player_tile, threat_matrix, grid_sampler, player, current_time_msec, msec_per_tile)
	elif best_panic_tile != Vector2i(-1, -1):
		final_target = best_panic_tile
		is_panic = true
		
	if final_target != Vector2i(-1, -1):
		# CRITICAL: Verify escape tile is not the current tile or a bomb location
		if final_target == player_tile:
			print("[BTFindEscapeRoute] ERROR: Escape tile is current tile! This should never happen.")
			return FAILURE
		
		# Check if escape tile has a bomb (double check)
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == final_target:
					if debug_logging:
						print("[BTFindEscapeRoute] ⚠ Escape tile ", final_target, " has a bomb! Rejecting.")
					return FAILURE
		
		blackboard.set_var(target_cell_var, final_target)
		blackboard.set_var("escape_route_found", true)
		if is_panic:
			print("[BTFindEscapeRoute] ⚠ PANIC: No safe route found. Moving to best available option: ", final_target, " (margin: ", best_panic_margin, "ms)")
		else:
			print("[BTFindEscapeRoute] ✓ Found escape tile at ", final_target, " (safety margin: ", best_safety_margin, "ms)")
		return SUCCESS
	
	# LAST RESORT: No safe escape found - try to move to ANY walkable adjacent tile
	# This gives the bot a chance to survive if the situation changes (bomb moves, explodes early, etc.)
	# Better to try something than stand still and die for sure
	var last_resort_tile = Vector2i(-1, -1)
	var last_resort_margin: float = -1.0
	
	for dir: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var adjacent = player_tile + dir
		if not grid_sampler.is_tile_walkable(adjacent):
			continue
		
		# Check if has bomb
		var has_bomb = false
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == adjacent:
					has_bomb = true
					break
		if has_bomb:
			continue
		
		# Calculate how much time we have on this tile
		var adj_key = _tile_key(adjacent)
		var margin: float = 0.0
		if threat_matrix.has(adj_key):
			var explosion_time = threat_matrix[adj_key]
			margin = explosion_time - (current_time_msec + msec_per_tile)
		else:
			margin = 999999.0 # Not in threat at all
		
		if margin > last_resort_margin:
			last_resort_margin = margin
			last_resort_tile = adjacent
	
	if last_resort_tile != Vector2i(-1, -1):
		blackboard.set_var(target_cell_var, last_resort_tile)
		blackboard.set_var("escape_route_found", true)
		print("[BTFindEscapeRoute] 🆘 LAST RESORT: Moving to ", last_resort_tile, " (margin: ", last_resort_margin, "ms)")
		return SUCCESS
	
	# Truly no escape - print debug and fail
	blackboard.set_var("escape_route_found", false)
	blackboard.set_var(target_cell_var, null)
	print("[BTFindEscapeRoute] ❌ No escape route found!")
	print("[BTFindEscapeRoute] DEBUG: Explored ", queue.size(), " tiles, visited ", visited.size(), " unique tiles")
	print("[BTFindEscapeRoute] DEBUG: best_safe_tile=", best_safe_tile, " best_panic_tile=", best_panic_tile)
	print("[BTFindEscapeRoute] DEBUG: best_panic_margin=", best_panic_margin, "ms")
	print("[BTFindEscapeRoute] DEBUG: Current position=", player_tile, " escape_radius=", escape_radius)
	print("[BTFindEscapeRoute] DEBUG: Threat matrix size=", threat_matrix.size())
	return FAILURE

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

func _adjacent_threat_count(tile: Vector2i, threats: Dictionary) -> int:
	var count := 0
	for direction: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		if threats.has(_tile_key(tile + direction)):
			count += 1
	return count

func _improve_refuge(refuge: Vector2i, start: Vector2i, threats: Dictionary, sampler, player, now_msec: float, msec_per_tile: float) -> Vector2i:
	# Leave a flame edge when an immediately adjoining, reachable refuge is better.
	# Strictly decreasing adjacency bounds retargeting; a tight refuge stays valid.
	if threats.has(_tile_key(refuge)):
		return refuge
	var best := refuge
	var best_count := _adjacent_threat_count(refuge, threats)
	for candidate: Vector2i in sampler.get_cardinal_neighbors(refuge):
		if not sampler.is_tile_safe_for_target(candidate) or threats.has(_tile_key(candidate)):
			continue
		var count := _adjacent_threat_count(candidate, threats)
		if count >= best_count:
			continue
		var path: Array[Vector2i] = sampler.find_path(start, candidate, escape_radius, player)
		if path.is_empty() or path.size() > escape_radius:
			continue
		var safe := true
		for index in range(path.size()):
			var key := _tile_key(path[index])
			if threats.has(key) and threats[key] <= now_msec + (index + 1) * msec_per_tile + 100.0:
				safe = false
				break
		if safe:
			best = candidate
			best_count = count
	return best

func _tile_has_further_exit(tile: Vector2i, threat_matrix: Dictionary, player_tile: Vector2i, grid_sampler) -> bool:
	"""Check if tile has at least one walkable neighbor that is NOT in the threat matrix.
	This prevents bots from escaping to dead-end tiles where they'll be trapped."""
	var directions := [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]
	for dir in directions:
		var neighbor = tile + dir
		# Skip the direction we came from (player's current tile)
		if neighbor == player_tile:
			continue
		if grid_sampler.is_tile_walkable(neighbor):
			var neighbor_key = _tile_key(neighbor)
			# A safe neighbor exists - this is not a dead end
			if not threat_matrix.has(neighbor_key):
				return true
	return false

func _get_blast_tiles(center: Vector2i, range_val: int, grid_sampler) -> Array[Vector2i]:
	"""Calculate which tiles will be hit by bomb explosion (respecting walls)"""
	var tiles: Array[Vector2i] = [center]
	
	# Check four cardinal directions
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	
	for dir: Vector2i in directions:
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			# Check if walkable (walls block explosions)
			if not grid_sampler.is_tile_walkable(tile):
				var tile_type = grid_sampler.get_tile_type(tile)
				if tile_type == 1: # Hard wall - stop blast
					break
				elif tile_type == 2: # Soft block - blast hits it but stops
					tiles.append(tile)
					break
			else:
				# Empty tile - blast continues
				tiles.append(tile)
	
	return tiles
