@tool
extends BTAction
class_name BTFindEscapeRoute

## Finds a safe escape route from danger using the AI pathfinder
## Sets target_cell in blackboard if a safe path is found

@export var escape_radius: int = 8  ## How far to search for safety
@export var target_cell_var: StringName = &"target_cell"  ## Where to store the escape destination

func _generate_name() -> String:
	return "FindEscapeRoute"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var ai_manager = blackboard.get_var("ai_manager")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	print("[BTFindEscapeRoute] STARTING escape route search for bot at ", player.get_tile_position() if player else "unknown")
	
	if not player or not game_instance or not ai_manager or not grid_sampler:
		push_warning("[BTFindEscapeRoute] Missing required blackboard variables")
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var current_time_msec = Time.get_ticks_msec()
	var bot_speed_tiles_per_sec = 5.0
	var msec_per_tile = (1.0 / bot_speed_tiles_per_sec) * 1000.0
	
	# BFS to find safe tiles considering TIMING and WALLS
	# A tile is safe if either:
	# 1. It's not in threat matrix at all (never explodes)
	# 2. We can reach it and stay there safely before it explodes
	
	var queue: Array[Vector2i] = [player_tile]
	var visited: Dictionary = {_tile_key(player_tile): current_time_msec}  # tile_key -> arrival_time_msec
	var head := 0
	
	var best_safe_tile: Vector2i = Vector2i(-1, -1)
	var best_safety_margin: float = -1.0  # How long until this tile explodes (higher is better)
	
	while head < queue.size():
		var current_pos := queue[head]
		head += 1
		
		var current_key := _tile_key(current_pos)
		var arrival_time: float = visited[current_key]
		
		# CRITICAL: Never consider current tile as escape destination - bot MUST move
		if current_pos == player_tile:
			# Skip evaluation, just explore neighbors
			pass
		else:
			# Check if this tile is safe (using threat matrix)
			var is_permanently_safe = not threat_matrix.has(current_key)
			var safety_margin: float = 0.0
			
			if is_permanently_safe:
				# This tile never explodes - best possible safety
				blackboard.set_var(target_cell_var, current_pos)
				blackboard.set_var("escape_route_found", true)
				print("[BTFindEscapeRoute] Found permanently safe tile at ", current_pos)
				return SUCCESS
			else:
				# Tile will explode at some point - check if we have time
				var explosion_time: float = threat_matrix[current_key]
				safety_margin = explosion_time - arrival_time
				
				# Need at least 1000ms safety margin (increased from 500ms) to consider it "safe enough"
				# This discourages stopping on tiles that will explode, even if fuse is long
				if safety_margin > 1000.0:
					if safety_margin > best_safety_margin:
						best_safety_margin = safety_margin
						best_safe_tile = current_pos
		
		# Continue searching - explore neighbors if we can pass through safely
		var can_pass_through = false
		if threat_matrix.has(current_key):
			var explosion_time = threat_matrix[current_key]
			can_pass_through = arrival_time < explosion_time  # Can we pass before explosion?
		else:
			can_pass_through = true  # Safe tile, definitely can pass
		
		if can_pass_through and head < escape_radius * 4:  # Limit search depth
			for dir: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
				var next_pos := current_pos + dir
				var next_key := _tile_key(next_pos)
				var next_arrival_time: float = arrival_time + msec_per_tile
				
				# Must be walkable (walls block movement AND explosions)
				if not grid_sampler.is_tile_walkable(next_pos):
					continue
				
				# Skip if already visited with better time
				if visited.has(next_key) and visited[next_key] <= next_arrival_time:
					continue
				
				visited[next_key] = next_arrival_time
				queue.append(next_pos)
	
	# Use best tile found (even if temporary safety)
	if best_safe_tile != Vector2i(-1, -1):
		# CRITICAL: Verify escape tile is not the current tile or a bomb location
		if best_safe_tile == player_tile:
			print("[BTFindEscapeRoute] ERROR: Escape tile is current tile! This should never happen.")
			return FAILURE
		
		# Check if escape tile has a bomb
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == best_safe_tile:
					print("[BTFindEscapeRoute] ERROR: Escape tile ", best_safe_tile, " has a bomb! Rejecting.")
					return FAILURE
		
		blackboard.set_var(target_cell_var, best_safe_tile)
		blackboard.set_var("escape_route_found", true)
		print("[BTFindEscapeRoute] ✓ Found escape tile at ", best_safe_tile, " (safety margin: ", best_safety_margin, "ms) from current ", player_tile)
		return SUCCESS
	
	# No escape route found
	blackboard.set_var("escape_route_found", false)
	print("[BTFindEscapeRoute] No escape route found!")
	return FAILURE

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

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
				if tile_type == 1:  # Hard wall - stop blast
					break
				elif tile_type == 2:  # Soft block - blast hits it but stops
					tiles.append(tile)
					break
			else:
				# Empty tile - blast continues
				tiles.append(tile)
	
	return tiles
