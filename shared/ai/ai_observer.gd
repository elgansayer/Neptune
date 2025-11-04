extends Node
class_name AIObserver

# AI Observer System
# Provides world state analysis for AI decision-making

const Constants = preload("res://shared/constants.gd")

var game_instance: Node2D  # Reference to GameInstance
var danger_map: Dictionary = {}  # tile_key -> explosion_time
var last_danger_update: float = 0.0
const DANGER_UPDATE_INTERVAL = 0.1  # Update danger map every 100ms

func _init(game_ref: Node2D):
	game_instance = game_ref

func get_world_state() -> Dictionary:
	"""Returns a comprehensive world state snapshot for AI decision-making"""
	update_danger_map()
	
	return {
		"map": game_instance.game_map,
		"bombs": game_instance.bombs,
		"players": game_instance.players,
		"danger_map": danger_map,
		"powerups": []  # TODO: Add when power-ups are implemented
	}

func update_danger_map():
	"""Calculate which tiles are dangerous and when they'll explode"""
	var current_time = Time.get_ticks_msec() / 1000.0
	
	# Only update periodically for performance
	if current_time - last_danger_update < DANGER_UPDATE_INTERVAL:
		return
	
	last_danger_update = current_time
	danger_map.clear()
	
	# Check all active bombs
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		var bomb_tile = bomb.get_tile_position()
		var explosion_time = current_time + bomb.explosion_timer
		var explosion_range = bomb.explosion_range
		
		# Mark bomb center as dangerous
		_mark_tile_dangerous(bomb_tile, explosion_time)
		
		# Mark explosion rays in 4 directions
		for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			for i in range(1, explosion_range + 1):
				var cell = bomb_tile + dir * i
				
				# Check bounds
				if not _is_tile_valid(cell):
					break
				
				# Check for solid wall
				if game_instance.game_map[cell.y][cell.x] == 1:
					break
				
				_mark_tile_dangerous(cell, explosion_time)
				
				# Destructible block stops explosion
				if game_instance.game_map[cell.y][cell.x] == 2:
					break

func _mark_tile_dangerous(tile: Vector2i, explosion_time: float):
	"""Mark a tile as dangerous with the explosion time"""
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	# Store earliest explosion time for this tile
	if not danger_map.has(tile_key) or explosion_time < danger_map[tile_key]:
		danger_map[tile_key] = explosion_time

func is_tile_in_danger(tile: Vector2i, time_buffer: float = 0.0) -> bool:
	"""Check if a tile is currently dangerous
	time_buffer: additional safety margin in seconds (e.g., 0.5 = need 500ms to escape)
	"""
	var tile_key = "%d,%d" % [tile.x, tile.y]
	if not danger_map.has(tile_key):
		return false
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var explosion_time = danger_map[tile_key]
	
	# Tile is dangerous if it will explode within the time buffer
	return explosion_time <= (current_time + time_buffer)

func get_time_until_explosion(tile: Vector2i) -> float:
	"""Returns seconds until tile explodes, or INF if safe"""
	var tile_key = "%d,%d" % [tile.x, tile.y]
	if not danger_map.has(tile_key):
		return INF
	
	var current_time = Time.get_ticks_msec() / 1000.0
	return danger_map[tile_key] - current_time

func find_nearest_safe_tiles(from_tile: Vector2i, max_distance: int = 10) -> Array:
	"""Find all safe tiles within max_distance, sorted by distance"""
	var safe_tiles = []
	
	for dy in range(-max_distance, max_distance + 1):
		for dx in range(-max_distance, max_distance + 1):
			var tile = from_tile + Vector2i(dx, dy)
			
			if not _is_tile_valid(tile):
				continue
			
			if _is_tile_walkable(tile) and not is_tile_in_danger(tile, 0.5):
				var distance = abs(dx) + abs(dy)  # Manhattan distance
				safe_tiles.append({"tile": tile, "distance": distance})
	
	# Sort by distance
	safe_tiles.sort_custom(func(a, b): return a.distance < b.distance)
	
	return safe_tiles

func find_nearest_powerup(from_tile: Vector2i) -> Vector2i:
	"""Find nearest power-up location"""
	# TODO: Implement when power-ups are added
	return Vector2i(-1, -1)

func get_adjacent_tiles(tile: Vector2i) -> Array:
	"""Get all valid adjacent tiles (up, down, left, right)"""
	var adjacent = []
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var neighbor = tile + dir
		if _is_tile_valid(neighbor) and _is_tile_walkable(neighbor):
			adjacent.append(neighbor)
	
	return adjacent

func count_escape_routes(tile: Vector2i) -> int:
	"""Count number of safe escape routes from a tile"""
	var escape_count = 0
	
	for adj_tile in get_adjacent_tiles(tile):
		if not is_tile_in_danger(adj_tile, 0.5):
			escape_count += 1
	
	return escape_count

func can_trap_opponent_from(tile: Vector2i, game_state: Dictionary) -> bool:
	"""Check if placing a bomb at 'tile' would trap an opponent"""
	# Simplified trap detection: check if any opponent is within bomb range
	# and has limited escape routes
	
	for peer_id in game_state.players:
		var player = game_state.players[peer_id]
		var player_tile = player.get_tile_position()
		
		# Check if player is in potential bomb range
		var distance = abs(player_tile.x - tile.x) + abs(player_tile.y - tile.y)
		if distance <= 3:  # Within typical bomb range
			# Check if player has few escape routes
			if count_escape_routes(player_tile) <= 1:
				return true
	
	return false

func get_nearest_destructible_block(from_tile: Vector2i, max_search: int = 20) -> Vector2i:
	"""Find nearest destructible block for exploration"""
	var nearest = Vector2i(-1, -1)
	var min_distance = INF
	
	for dy in range(-max_search, max_search + 1):
		for dx in range(-max_search, max_search + 1):
			var tile = from_tile + Vector2i(dx, dy)
			
			if not _is_tile_valid(tile):
				continue
			
			if game_instance.game_map[tile.y][tile.x] == 2:  # Destructible block
				var distance = abs(dx) + abs(dy)
				if distance < min_distance:
					min_distance = distance
					nearest = tile
	
	return nearest

func _is_tile_valid(tile: Vector2i) -> bool:
	"""Check if tile coordinates are within map bounds"""
	if tile.y < 0 or tile.y >= game_instance.game_map.size():
		return false
	if tile.x < 0 or tile.x >= game_instance.game_map[0].size():
		return false
	return true

func _is_tile_walkable(tile: Vector2i) -> bool:
	"""Check if tile can be walked on (not a wall or bomb)"""
	if not _is_tile_valid(tile):
		return false
	
	var tile_type = game_instance.game_map[tile.y][tile.x]
	
	# Can't walk through walls or blocks
	if tile_type == 1 or tile_type == 2:
		return false
	
	# Check if there's a bomb on this tile
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if bomb.get_tile_position() == tile:
			return false
	
	return true
