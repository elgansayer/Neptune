extends Node
class_name DangerMapper

## Advanced Danger Mapping System for AI
## Provides continuous danger zone tracking with intensity gradients and bomb timer prediction
## Works with free-movement physics while reasoning about grid-based explosion zones

const Constants = preload("res://shared/constants.gd")

# Danger data structures
var danger_zones: Dictionary = {}  # tile_key -> {intensity: float, explosion_time: float, source_bombs: Array}
var continuous_danger_map: Dictionary = {}  # position_hash -> danger_level (for fine-grained checks)
var safe_zones: Array[Vector2i] = []  # Cached list of known safe tiles
var last_full_update: float = 0.0
const UPDATE_INTERVAL: float = 0.05  # Update every 50ms for responsiveness

# References
var game_instance: Node2D
var observer  # AIObserver reference

func _init(game_ref: Node2D, obs_ref):
	game_instance = game_ref
	observer = obs_ref

## Main update function - call this frequently
func update(current_time: float) -> void:
	if current_time - last_full_update < UPDATE_INTERVAL:
		return
	
	last_full_update = current_time
	
	danger_zones.clear()
	safe_zones.clear()
	
	# Analyze all active bombs
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		
		var bomb_tile = bomb.get_tile_position()
		var time_remaining = bomb.explosion_timer
		var explosion_time = current_time + time_remaining
		var bomb_range = bomb.explosion_range
		
		# Calculate danger intensity based on timer (closer to explosion = higher danger)
		var base_intensity = _calculate_intensity_from_timer(time_remaining)
		
		# Mark bomb center
		_add_danger_to_tile(bomb_tile, base_intensity, explosion_time, bomb_id)
		
		# Mark cross-shaped explosion pattern
		for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			for i in range(1, bomb_range + 1):
				var cell = bomb_tile + dir * i
				
				if not _is_tile_valid(cell):
					break
				
				# Check for walls
				if game_instance.game_map[cell.y][cell.x] == 1:
					break
				
				# Intensity decreases with distance from bomb center
				var distance_factor = 1.0 - (float(i) / float(bomb_range + 1))
				var cell_intensity = base_intensity * distance_factor
				
				_add_danger_to_tile(cell, cell_intensity, explosion_time, bomb_id)
				
				# Soft blocks stop explosion
				if game_instance.game_map[cell.y][cell.x] == 2:
					break
	
	# Build safe zone cache
	_cache_safe_zones(current_time)

## Get danger level at a specific tile position
func get_danger_at_tile(tile: Vector2i, current_time: float, look_ahead: float = 0.5) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_zones.has(tile_key):
		return 0.0
	
	var zone = danger_zones[tile_key]
	var time_until_explosion = zone.explosion_time - current_time
	
	# If explosion time is within look_ahead window, consider it dangerous
	if time_until_explosion <= look_ahead:
		return zone.intensity
	
	# Scale danger based on how soon the explosion will occur
	var danger_factor = 1.0 - (time_until_explosion / (look_ahead + 2.0))
	return zone.intensity * max(0.0, danger_factor)

## Get danger level at continuous position (for smooth movement)
func get_danger_at_position(position: Vector2, current_time: float, look_ahead: float = 0.5) -> float:
	var tile = _position_to_tile(position)
	return get_danger_at_tile(tile, current_time, look_ahead)

## Check if a tile is safe to move to
func is_tile_safe(tile: Vector2i, current_time: float, safety_margin: float = 1.0) -> bool:
	var danger = get_danger_at_tile(tile, current_time, safety_margin)
	return danger < 0.3  # Threshold for "safe"

## Check if a position is safe (continuous)
func is_position_safe(position: Vector2, current_time: float, safety_margin: float = 1.0) -> bool:
	var tile = _position_to_tile(position)
	return is_tile_safe(tile, current_time, safety_margin)

## Get time until explosion at tile
func get_time_until_explosion(tile: Vector2i, current_time: float) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_zones.has(tile_key):
		return INF
	
	var zone = danger_zones[tile_key]
	return max(0.0, zone.explosion_time - current_time)

## Find nearest safe tiles sorted by distance
func find_nearest_safe_tiles(from_tile: Vector2i, current_time: float, max_distance: int = 10) -> Array:
	var safe_candidates: Array = []
	
	# Search in expanding radius
	for distance in range(1, max_distance + 1):
		for dy in range(-distance, distance + 1):
			for dx in range(-distance, distance + 1):
				var manhattan = abs(dx) + abs(dy)
				if manhattan != distance:  # Only check tiles at current distance ring
					continue
				
				var tile = from_tile + Vector2i(dx, dy)
				
				if not _is_tile_valid(tile):
					continue
				
				if not observer._is_tile_walkable(tile):
					continue
				
				# Check if tile is safe with generous margin
				if is_tile_safe(tile, current_time, 1.5):
					safe_candidates.append({
						"tile": tile,
						"distance": manhattan,
						"danger": get_danger_at_tile(tile, current_time, 2.0)  # Check future danger too
					})
		
		# Early exit if we found safe tiles at this distance
		if not safe_candidates.is_empty():
			break
	
	# Sort by danger level (prefer safest), then distance
	safe_candidates.sort_custom(func(a, b):
		if abs(a.danger - b.danger) < 0.1:
			return a.distance < b.distance
		return a.danger < b.danger
	)
	
	return safe_candidates

## Get escape route quality from a position
func calculate_escape_routes(tile: Vector2i, current_time: float) -> Dictionary:
	var routes: Array = []
	var total_escapes = 0
	
	# Check all 4 directions
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var next_tile = tile + dir
		
		if not _is_tile_valid(next_tile):
			continue
		
		if not observer._is_tile_walkable(next_tile):
			continue
		
		var danger_ahead = get_danger_at_tile(next_tile, current_time, 1.0)
		var is_safe = danger_ahead < 0.3
		
		routes.append({
			"direction": dir,
			"tile": next_tile,
			"danger": danger_ahead,
			"safe": is_safe
		})
		
		if is_safe:
			total_escapes += 1
	
	# Sort routes by safety (safest first)
	routes.sort_custom(func(a, b): return a.danger < b.danger)
	
	return {
		"routes": routes,
		"safe_count": total_escapes,
		"best_route": routes[0] if not routes.is_empty() else null
	}

## Predict danger at future time (for planning)
func predict_danger_at_time(tile: Vector2i, future_time: float) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_zones.has(tile_key):
		return 0.0
	
	var zone = danger_zones[tile_key]
	
	# If explosion happens before future_time, it's deadly
	if zone.explosion_time <= future_time:
		return 1.0  # Maximum danger
	
	# Otherwise, calculate based on how close the explosion is
	var time_until = zone.explosion_time - future_time
	if time_until > 2.0:
		return 0.0  # Safe
	
	return 1.0 - (time_until / 2.0)

## Simulate placing a bomb and return danger projection
func simulate_bomb_placement(bomb_tile: Vector2i, bomb_range: int, current_time: float) -> Dictionary:
	var affected_tiles: Array[Vector2i] = [bomb_tile]
	var blocks_destroyed = 0
	var creates_chain = false
	var traps_players = 0
	
	# Simulate explosion pattern
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for i in range(1, bomb_range + 1):
			var cell = bomb_tile + dir * i
			
			if not _is_tile_valid(cell):
				break
			
			if game_instance.game_map[cell.y][cell.x] == 1:
				break
			
			affected_tiles.append(cell)
			
			if game_instance.game_map[cell.y][cell.x] == 2:
				blocks_destroyed += 1
				break
	
	# Check if placement creates chain reaction
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if bomb.get_tile_position() in affected_tiles:
			creates_chain = true
			break
	
	# Check if traps players
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		var player_tile = player.get_tile_position()
		
		if player_tile in affected_tiles:
			# Count escape routes after bomb placement
			var escape_routes = 0
			for adj in observer.get_adjacent_tiles(player_tile):
				if adj not in affected_tiles and observer._is_tile_walkable(adj):
					escape_routes += 1
			
			if escape_routes <= 1:
				traps_players += 1
	
	return {
		"affected_tiles": affected_tiles,
		"blocks_destroyed": blocks_destroyed,
		"creates_chain": creates_chain,
		"traps_players": traps_players,
		"danger_area_size": affected_tiles.size()
	}

## Check if position has emergency danger (need to move NOW)
func is_emergency_danger(tile: Vector2i, current_time: float) -> bool:
	var time_until = get_time_until_explosion(tile, current_time)
	return time_until < 0.8  # Less than 800ms to escape

## Get all danger zones for visualization
func get_all_danger_zones() -> Dictionary:
	return danger_zones

## Private helper functions

func _add_danger_to_tile(tile: Vector2i, intensity: float, explosion_time: float, bomb_id) -> void:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if danger_zones.has(tile_key):
		var existing = danger_zones[tile_key]
		# Take the highest intensity and earliest explosion time
		existing.intensity = max(existing.intensity, intensity)
		existing.explosion_time = min(existing.explosion_time, explosion_time)
		existing.source_bombs.append(bomb_id)
	else:
		danger_zones[tile_key] = {
			"intensity": intensity,
			"explosion_time": explosion_time,
			"source_bombs": [bomb_id]
		}

func _calculate_intensity_from_timer(time_remaining: float) -> float:
	# Intensity increases as time decreases
	if time_remaining > 2.0:
		return 0.3  # Low danger (plenty of time)
	elif time_remaining > 1.0:
		return 0.7  # Medium danger
	else:
		return 1.0  # Critical danger

func _cache_safe_zones(current_time: float) -> void:
	for y in range(game_instance.game_map.size()):
		for x in range(game_instance.game_map[y].size()):
			var tile = Vector2i(x, y)
			
			if not observer._is_tile_walkable(tile):
				continue
			
			if is_tile_safe(tile, current_time, 1.5):
				safe_zones.append(tile)

func _is_tile_valid(tile: Vector2i) -> bool:
	if tile.y < 0 or tile.y >= game_instance.game_map.size():
		return false
	if tile.x < 0 or tile.x >= game_instance.game_map[0].size():
		return false
	return true

func _position_to_tile(position: Vector2) -> Vector2i:
	return Vector2i(
		int(floor(position.x / Constants.TILE_SIZE)),
		int(floor(position.y / Constants.TILE_SIZE))
	)
