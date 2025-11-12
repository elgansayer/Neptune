extends Node
class_name AIObserver

# AI Observer System
# Provides world state analysis for AI decision-making

const Constants = preload("res://shared/constants.gd")

var game_instance: Node2D  # Reference to GameInstance
var danger_map: Dictionary = {}  # tile_key -> explosion_time
var last_danger_update: float = 0.0
const DANGER_UPDATE_INTERVAL = 0.1  # Update danger map every 100ms
var player_position_history: Dictionary = {}  # player_id -> Array of {position, time}

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
		"powerups": _get_visible_powerups()  # Phase 4: Track visible powerups
	}

func _get_visible_powerups() -> Array:
	"""Get list of visible powerups with their locations and types - Phase 4 Enhancement"""
	var powerups = []
	
	# Check if game instance has powerups dictionary
	if not game_instance.has("powerups"):
		return powerups
	
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		
		# Skip collected or destroyed powerups
		if powerup.has("collected") and powerup.collected:
			continue
		if powerup.has("destroyed") and powerup.destroyed:
			continue
		
		var powerup_tile = powerup.get_tile_position()
		powerups.append({
			"id": powerup_id,
			"tile": powerup_tile,
			"type": powerup.powerup_type if powerup.has("powerup_type") else 0,
			"position": powerup.position
		})
	
	return powerups

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

func get_recent_velocity(player_id: String) -> Vector2:
	"""Get recent velocity for a player from position history"""
	if not player_position_history.has(player_id):
		return Vector2.ZERO
	
	var history = player_position_history[player_id]
	if history.size() < 2:
		return Vector2.ZERO
	
	# Calculate velocity from last two positions
	var recent = history[-1]
	var prev = history[-2]
	var time_delta = recent.time - prev.time
	if time_delta < 0.001:
		return Vector2.ZERO
	
	return (recent.position - prev.position) / time_delta

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
	var nearest = Vector2i(-1, -1)
	var min_distance = INF
	
	# Iterate known powerups dictionary on the game instance
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		
		# Skip collected or destroyed powerups
		if powerup.collected or powerup.destroyed:
			continue
		
		var powerup_tile = powerup.get_tile_position()
		var distance = abs(powerup_tile.x - from_tile.x) + abs(powerup_tile.y - from_tile.y)
		
		if distance < min_distance:
			min_distance = distance
			nearest = powerup_tile
	
	return nearest

func find_valuable_powerup(from_tile: Vector2i, utility_weights: Dictionary) -> Dictionary:
	"""Find most valuable powerup based on personality weights and distance"""
	var best_powerup = {"tile": Vector2i(-1, -1), "value": 0.0, "type": -1}
	
	# Iterate known powerups dictionary on the game instance
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		
		# Skip collected or destroyed powerups
		if powerup.collected or powerup.destroyed:
			continue
		
		var powerup_tile = powerup.get_tile_position()
		var distance = abs(powerup_tile.x - from_tile.x) + abs(powerup_tile.y - from_tile.y)
		
		# Calculate utility value based on type and personality weights
		var type_weight = 1.0
		match powerup.powerup_type:
			0:  # BOMB_INCREASE
				type_weight = utility_weights.get("max_bombs", 600.0)
			1:  # RANGE_INCREASE
				type_weight = utility_weights.get("explosion_range", 600.0)
			2:  # SPEED_INCREASE
				type_weight = utility_weights.get("speed", 600.0)
			3:  # BOMB_KICKER
				type_weight = utility_weights.get("bomb_kicker", 400.0)
			4:  # POWER_GLOVE
				type_weight = utility_weights.get("power_glove", 400.0)
			5:  # VIRUS (negative)
				type_weight = -500.0  # Avoid
		
		# Value = type_weight / (distance + 1) to prefer closer powerups
		var value = type_weight / (distance + 1.0)
		
		if value > best_powerup.value:
			best_powerup = {
				"tile": powerup_tile,
				"value": value,
				"type": powerup.powerup_type,
				"distance": distance
			}
	
	return best_powerup

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
		if not is_instance_valid(bomb):
			continue
		if bomb.get_tile_position() == tile:
			return false
	
	return true

func calculate_chain_reaction(bomb_position: Vector2i, bomb_range: int, visited_bombs: Dictionary = {}) -> Dictionary:
	"""Recursively calculate chain reaction from placing a bomb
	Returns: {blocks_destroyed: int, players_trapped: int, chain_depth: int, affected_tiles: Array}
	"""
	var result = {
		"blocks_destroyed": 0,
		"players_trapped": 0,
		"chain_depth": 0,
		"affected_tiles": []
	}
	
	# Mark this bomb as visited to prevent re-detonation
	var bomb_key = "%d,%d" % [bomb_position.x, bomb_position.y]
	if visited_bombs.has(bomb_key):
		return result  # Already processed this bomb
	
	visited_bombs[bomb_key] = true
	
	# Simulate explosion in 4 directions
	var explosion_tiles = [bomb_position]
	result.affected_tiles.append(bomb_position)
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for i in range(1, bomb_range + 1):
			var cell = bomb_position + dir * i
			
			# Check bounds
			if not _is_tile_valid(cell):
				break
			
			var tile_type = game_instance.game_map[cell.y][cell.x]
			
			# Solid wall stops explosion
			if tile_type == 1:
				break
			
			explosion_tiles.append(cell)
			result.affected_tiles.append(cell)
			
			# Count destructible blocks
			if tile_type == 2:
				result.blocks_destroyed += 1
				break  # Block stops explosion
	
	# Check for secondary bombs in explosion range (chain reaction)
	var secondary_bombs = []
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		var bomb_tile = bomb.get_tile_position()
		
		# Skip if this bomb is the one we're simulating or already visited
		var secondary_key = "%d,%d" % [bomb_tile.x, bomb_tile.y]
		if bomb_tile == bomb_position or visited_bombs.has(secondary_key):
			continue
		
		# Check if bomb is in explosion range
		if bomb_tile in explosion_tiles:
			secondary_bombs.append({"tile": bomb_tile, "range": bomb.explosion_range})
	
	# Recursively calculate secondary explosions
	var max_chain_depth = 0
	for secondary in secondary_bombs:
		var chain_result = calculate_chain_reaction(secondary.tile, secondary.range, visited_bombs)
		
		# Accumulate results
		result.blocks_destroyed += chain_result.blocks_destroyed
		result.players_trapped += chain_result.players_trapped
		
		# Track chain depth
		max_chain_depth = max(max_chain_depth, chain_result.chain_depth + 1)
		
		# Merge affected tiles (avoid duplicates)
		for tile in chain_result.affected_tiles:
			if tile not in result.affected_tiles:
				result.affected_tiles.append(tile)
	
	result.chain_depth = max_chain_depth
	
	# Check for players trapped in final explosion pattern
	for peer_id in game_instance.players:
		var player = game_instance.players[peer_id]
		var player_tile = player.get_tile_position()
		
		if player_tile in result.affected_tiles:
			# Check if player has escape routes from explosion
			var escape_count = 0
			for adj_tile in get_adjacent_tiles(player_tile):
				if adj_tile not in result.affected_tiles:
					escape_count += 1
			
			if escape_count <= 1:  # Trapped or very limited escapes
				result.players_trapped += 1
	
	return result

func update_player_position_history(player_id: String, position: Vector2, current_time: float):
	"""Update position history for velocity prediction"""
	if not player_position_history.has(player_id):
		player_position_history[player_id] = []
	
	var history = player_position_history[player_id]
	history.append({"position": position, "time": current_time})
	
	# Keep only last 3 frames
	if history.size() > 3:
		history.remove_at(0)

func predict_opponent_position(player_id: String, time_ahead: float) -> Vector2:
	"""Predict opponent position based on velocity history
	time_ahead: seconds into the future to predict (typically 1-3)
	Returns: predicted position (Vector2)
	"""
	if not player_position_history.has(player_id):
		# No history, use random direction fallback
		return _predict_random_movement(player_id, time_ahead)
	
	var history = player_position_history[player_id]
	
	# Need at least 2 frames to calculate velocity
	if history.size() < 2:
		return _predict_random_movement(player_id, time_ahead)
	
	# Calculate average velocity from last 2-3 frames
	var velocities = []
	for i in range(1, history.size()):
		var prev = history[i - 1]
		var curr = history[i]
		var dt = curr.time - prev.time
		
		if dt > 0:
			var velocity = (curr.position - prev.position) / dt
			velocities.append(velocity)
	
	if velocities.is_empty():
		return _predict_random_movement(player_id, time_ahead)
	
	# Average velocity
	var avg_velocity = Vector2.ZERO
	for vel in velocities:
		avg_velocity += vel
	avg_velocity /= velocities.size()
	
	# Check if player is stationary (velocity near zero)
	if avg_velocity.length() < 5.0:  # Less than 5 pixels/sec
		return _predict_random_movement(player_id, time_ahead)
	
	# Extrapolate position
	var current_pos = history[history.size() - 1].position
	var predicted_pos = current_pos + avg_velocity * time_ahead
	
	return predicted_pos

func _predict_random_movement(player_id: String, time_ahead: float) -> Vector2:
	"""Fallback: predict random direction movement when velocity unavailable"""
	# Get current position if available
	var current_pos = Vector2.ZERO
	
	if player_position_history.has(player_id) and not player_position_history[player_id].is_empty():
		current_pos = player_position_history[player_id][-1].position
	elif game_instance.players.has(player_id):
		current_pos = game_instance.players[player_id].position
	else:
		return current_pos  # Can't predict
	
	# Generate random direction
	var random_direction = Vector2(
		randf_range(-1.0, 1.0),
		randf_range(-1.0, 1.0)
	).normalized()
	
	# Assume average movement speed (e.g., 100 pixels/sec)
	var avg_speed = 100.0
	var distance = avg_speed * time_ahead

	# Clamp distance to 2-4 tiles
	var tile_size = Constants.TILE_SIZE
	distance = clamp(distance, tile_size * 2, tile_size * 4)
	
	return current_pos + random_direction * distance


# ============================================================================
# PHASE 4 ENHANCEMENTS
# ============================================================================

func calculate_advanced_chain_reaction(bomb_tile: Vector2i, bomb_range: int, time_offset: float = 0.0) -> Dictionary:
"""
Phase 4 Enhancement: Advanced chain reaction prediction with timing

Predicts chain reactions with accurate timing for better strategic planning

Args:
bomb_tile: Position of the initial bomb
bomb_range: Explosion range of the bomb
time_offset: Time until initial bomb explodes (seconds)

Returns:
{
"blocks_destroyed": int,
"players_trapped": Array of player_ids,
"chain_depth": int,
"affected_tiles": Array of Vector2i,
"explosion_sequence": Array of {tile, time, range},
"total_damage_tiles": int,
"powerups_revealed": Array of tiles where powerups might spawn
}
"""
var result = {
"blocks_destroyed": 0,
"players_trapped": [],
"chain_depth": 0,
"affected_tiles": [],
"explosion_sequence": [],
"total_damage_tiles": 0,
"powerups_revealed": []
}

# Track which bombs have been processed
var processed_bombs = {}
var explosion_queue = []  # Priority queue of explosions by time

# Add initial bomb
explosion_queue.append({
"tile": bomb_tile,
"range": bomb_range,
"time": time_offset,
"depth": 0
})

# Process explosion queue
while not explosion_queue.is_empty():
# Get next explosion (earliest time)
explosion_queue.sort_custom(func(a, b): return a.time < b.time)
var explosion = explosion_queue.pop_front()

var tile_key = "%d,%d" % [explosion.tile.x, explosion.tile.y]
if processed_bombs.has(tile_key):
continue

processed_bombs[tile_key] = true
result.chain_depth = max(result.chain_depth, explosion.depth)

# Calculate explosion pattern
var explosion_tiles = _simulate_explosion_pattern(explosion.tile, explosion.range)

# Add to explosion sequence
result.explosion_sequence.append({
"tile": explosion.tile,
"time": explosion.time,
"range": explosion.range,
"tiles": explosion_tiles
})

result.total_damage_tiles += explosion_tiles.size()

# Check each tile in explosion
for exp_tile in explosion_tiles:
if exp_tile not in result.affected_tiles:
result.affected_tiles.append(exp_tile)

# Check for destructible blocks
if _is_tile_valid(exp_tile):
var tile_type = game_instance.game_map[exp_tile.y][exp_tile.x]
if tile_type == 2:  # Soft block
result.blocks_destroyed += 1
# Track potential powerup spawn
if exp_tile not in result.powerups_revealed:
result.powerups_revealed.append(exp_tile)

# Check for chain reaction bombs
for bomb_id in game_instance.bombs:
var bomb = game_instance.bombs[bomb_id]
var bomb_pos = bomb.get_tile_position()

if bomb_pos == exp_tile:
var bomb_key = "%d,%d" % [bomb_pos.x, bomb_pos.y]
if not processed_bombs.has(bomb_key):
# Add chained bomb to queue
explosion_queue.append({
"tile": bomb_pos,
"range": bomb.explosion_range if bomb.has("explosion_range") else 2,
"time": explosion.time + 0.1,  # Chain reaction delay
"depth": explosion.depth + 1
})

# Check for trapped players
for peer_id in game_instance.players:
var player = game_instance.players[peer_id]
if player.has_method("is_dead") and player.is_dead:
continue

var player_tile = player.get_tile_position()

# Check if player is in any explosion at any time
for explosion_data in result.explosion_sequence:
if player_tile in explosion_data.tiles:
# Check if player can escape before explosion
var time_to_escape = explosion_data.time
var escape_routes = _count_safe_escape_routes(player_tile, result.explosion_sequence, time_to_escape)

if escape_routes == 0:
if peer_id not in result.players_trapped:
result.players_trapped.append(peer_id)
break

return result

func _simulate_explosion_pattern(center: Vector2i, range: int) -> Array:
"""Simulate cross-shaped explosion pattern"""
var tiles = [center]

for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
for dist in range(1, range + 1):
var tile = center + dir * dist

if not _is_tile_valid(tile):
break

tiles.append(tile)

# Check if explosion stops
var tile_type = game_instance.game_map[tile.y][tile.x]
if tile_type == 1 or tile_type == 2:  # Wall or soft block
break

return tiles

func _count_safe_escape_routes(player_tile: Vector2i, explosion_sequence: Array, current_time: float) -> int:
"""Count safe escape routes for a player given explosion sequence"""
var safe_routes = 0

for adj_tile in get_adjacent_tiles(player_tile):
var is_safe = true

# Check if this route is hit by any explosion
for explosion_data in explosion_sequence:
if adj_tile in explosion_data.tiles and explosion_data.time <= current_time + 0.5:
is_safe = false
break

if is_safe:
safe_routes += 1

return safe_routes
