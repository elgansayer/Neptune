extends Node
class_name DangerMapper

## Advanced Danger Mapping System for AI
## Provides continuous danger zone tracking with intensity gradients and bomb timer prediction
## Works with free-movement physics while reasoning about grid-based explosion zones

const Constants = preload("res://shared/constants.gd")

# Danger data structures (Phase 2: Per-tick countdown-weighted heatmap)
var danger_heatmap: Dictionary = {}  # tile_key -> {base_danger: float, explosion_countdowns: Array[{time: float, intensity: float, bomb_id}]}
var explosion_echoes: Dictionary = {}  # tile_key -> {decay_intensity: float, decay_start: float}
var chain_prediction_cache: Dictionary = {}  # bomb_id -> {chain_targets: Array, total_coverage: int}
var safe_zones: Array[Vector2i] = []  # Cached list of known safe tiles
var last_full_update: float = 0.0
const UPDATE_INTERVAL: float = 0.05  # Update every 50ms for responsiveness
const EXPLOSION_ECHO_DURATION: float = 0.4  # Fading danger lingers 400ms after explosion

# Diagnostics & debug (Phase 1)
var debug_enabled: bool = false
var update_count: int = 0
var avg_update_time: float = 0.0
var bomb_lifetime_tracker: Dictionary = {}  # bomb_id -> {spawn_time, predicted_explosion}
var danger_change_log: Array = []  # Recent danger spikes for analysis

# References
var game_instance: Node2D
var observer  # AIObserver reference

func _init(game_ref: Node2D, obs_ref):
	game_instance = game_ref
	observer = obs_ref

## Main update function - call this frequently (Phase 2: Per-tick heatmap)
func update(current_time: float) -> void:
	if current_time - last_full_update < UPDATE_INTERVAL:
		return
	
	var update_start = Time.get_ticks_usec() if debug_enabled else 0
	last_full_update = current_time
	update_count += 1
	
	# Clear old data but preserve echo decay
	danger_heatmap.clear()
	chain_prediction_cache.clear()
	safe_zones.clear()
	
	# Phase 2: Update explosion echoes (fading danger from recent explosions)
	for tile_key in explosion_echoes.keys().duplicate():
		var echo = explosion_echoes[tile_key]
		var elapsed = current_time - echo.decay_start
		if elapsed >= EXPLOSION_ECHO_DURATION:
			explosion_echoes.erase(tile_key)
		else:
			# Linear decay
			echo.decay_intensity = echo.decay_intensity * (1.0 - elapsed / EXPLOSION_ECHO_DURATION)
	
	# Analyze all active bombs and build countdown-weighted danger
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		
		# Track bomb lifecycle
		if not bomb_lifetime_tracker.has(bomb_id):
			bomb_lifetime_tracker[bomb_id] = {
				"spawn_time": current_time,
				"predicted_explosion": current_time + bomb.explosion_timer
			}
		
		var bomb_tile = bomb.get_tile_position()
		var time_remaining = bomb.explosion_timer
		var explosion_time = current_time + time_remaining
		var bomb_range = bomb.explosion_range
		
		# Phase 2: Calculate per-tick intensity (urgency-weighted)
		var urgency_weight = _calculate_urgency_weight(time_remaining)
		var affected_tiles = []
		
		# Mark bomb center
		_add_countdown_danger(bomb_tile, urgency_weight, explosion_time, bomb_id)
		affected_tiles.append(bomb_tile)
		
		# Mark cross-shaped explosion pattern
		for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
			for i in range(1, bomb_range + 1):
				var cell = bomb_tile + dir * i
				
				if not _is_tile_valid(cell):
					break
				
				# Check for walls
				if game_instance.game_map[cell.y][cell.x] == 1:
					break
				
				# Distance falloff: closer tiles = higher danger
				var distance_factor = 1.0 - (float(i) / float(bomb_range + 2))
				var cell_intensity = urgency_weight * distance_factor
				
				_add_countdown_danger(cell, cell_intensity, explosion_time, bomb_id)
				affected_tiles.append(cell)
				
				# Soft blocks stop explosion
				if game_instance.game_map[cell.y][cell.x] == 2:
					break
		
		# Phase 2: Predict chain reactions
		var chain_data = _predict_bomb_chains(bomb_id, bomb_tile, affected_tiles, current_time)
		chain_prediction_cache[bomb_id] = chain_data
	
	# Build safe zone cache
	_cache_safe_zones(current_time)
	
	# Cleanup stale bomb tracking
	for bomb_id in bomb_lifetime_tracker.keys():
		if not game_instance.bombs.has(bomb_id):
			# Bomb exploded - add echo
			_register_explosion_echo(bomb_id, current_time)
			bomb_lifetime_tracker.erase(bomb_id)
	
	# Update performance metrics
	if debug_enabled:
		var update_end = Time.get_ticks_usec()
		var delta_us = update_end - update_start
		avg_update_time = lerp(avg_update_time, delta_us / 1000.0, 0.1)
		if update_count % 60 == 0:
			print("[DangerMapper] Avg update: %.2fms, Active bombs: %d, Heatmap entries: %d, Echoes: %d" % [avg_update_time, game_instance.bombs.size(), danger_heatmap.size(), explosion_echoes.size()])

## Get danger level at a specific tile position (Phase 2: Countdown-weighted)
func get_danger_at_tile(tile: Vector2i, current_time: float, look_ahead: float = 0.5) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	var total_danger = 0.0
	
	# Phase 2: Sum all countdown-weighted dangers at this tile
	if danger_heatmap.has(tile_key):
		var heatmap_entry = danger_heatmap[tile_key]
		for countdown in heatmap_entry.explosion_countdowns:
			var time_until = countdown.time - current_time
			
			# If explosion is imminent (within look_ahead), use full intensity
			if time_until <= look_ahead:
				total_danger += countdown.intensity
			elif time_until <= look_ahead + 1.5:
				# Scale by proximity to danger window
				var proximity = 1.0 - ((time_until - look_ahead) / 1.5)
				total_danger += countdown.intensity * proximity
	
	# Phase 2: Add fading explosion echo danger
	if explosion_echoes.has(tile_key):
		total_danger += explosion_echoes[tile_key].decay_intensity * 0.5
	
	return min(total_danger, 1.0)  # Cap at 1.0

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

## Get time until explosion at tile (Phase 2: Earliest countdown)
func get_time_until_explosion(tile: Vector2i, current_time: float) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_heatmap.has(tile_key):
		return INF
	
	var heatmap_entry = danger_heatmap[tile_key]
	var earliest = INF
	for countdown in heatmap_entry.explosion_countdowns:
		var time_until = countdown.time - current_time
		earliest = min(earliest, time_until)
	
	return max(0.0, earliest)

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

## Predict danger at future time (for planning) (Phase 2: Use heatmap)
func predict_danger_at_time(tile: Vector2i, future_time: float) -> float:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_heatmap.has(tile_key):
		return 0.0
	
	var entry = danger_heatmap[tile_key]
	var max_danger = 0.0
	
	# Check all countdowns for this tile
	for countdown in entry.explosion_countdowns:
		# If explosion happens before future_time, it's deadly
		if countdown.time <= future_time:
			max_danger = max(max_danger, countdown.intensity)
		else:
			# Scale by time proximity
			var time_until = countdown.time - future_time
			if time_until <= 2.0:
				max_danger = max(max_danger, countdown.intensity * (1.0 - time_until / 2.0))
	
	return min(max_danger, 1.0)

## Simulate placing a bomb and return danger projection
func simulate_bomb_placement(bomb_tile: Vector2i, bomb_range: int, _current_time: float) -> Dictionary:
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

## Get all danger zones for visualization (Phase 2: Heatmap)
func get_all_danger_zones() -> Dictionary:
	return danger_heatmap

## Get chain prediction data for a bomb
func get_chain_prediction(bomb_id) -> Dictionary:
	return chain_prediction_cache.get(bomb_id, {})

## Phase 2: Get peak danger along a path (for pathfinding cost)
func get_peak_danger_path(tiles: Array, current_time: float, look_ahead: float = 0.5) -> float:
	var peak = 0.0
	for tile in tiles:
		var danger = get_danger_at_tile(tile, current_time, look_ahead)
		peak = max(peak, danger)
	return peak

## Phase 2: Sample danger in a cone/direction (for kiting/flanking)
func sample_cone_danger(origin: Vector2i, direction: Vector2i, range: int, current_time: float, look_ahead: float = 0.5) -> float:
	var total_danger = 0.0
	var samples = 0
	
	# Sample tiles in the direction cone
	for dist in range(1, range + 1):
		var center_tile = origin + direction * dist
		
		# Sample center and adjacent tiles
		for offset in [Vector2i.ZERO, Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var sample_tile = center_tile + offset
			if _is_tile_valid(sample_tile):
				total_danger += get_danger_at_tile(sample_tile, current_time, look_ahead)
				samples += 1
	
	return total_danger / max(1, samples)

## Phase 2: Get average danger in radius (for positioning)
func get_area_danger(center: Vector2i, radius: int, current_time: float, look_ahead: float = 0.5) -> float:
	var total_danger = 0.0
	var samples = 0
	
	for dy in range(-radius, radius + 1):
		for dx in range(-radius, radius + 1):
			if abs(dx) + abs(dy) > radius:
				continue
			
			var tile = center + Vector2i(dx, dy)
			if _is_tile_valid(tile):
				total_danger += get_danger_at_tile(tile, current_time, look_ahead)
				samples += 1
	
	return total_danger / max(1, samples)

## Phase 2: Get directional danger gradient (which way to escape)
func get_danger_gradient(tile: Vector2i, current_time: float) -> Vector2:
	var gradient = Vector2.ZERO
	var center_danger = get_danger_at_tile(tile, current_time, 0.5)
	
	# Sample 4 directions
	var directions = [
		{"vec": Vector2i.UP, "weight": Vector2(0, -1)},
		{"vec": Vector2i.DOWN, "weight": Vector2(0, 1)},
		{"vec": Vector2i.LEFT, "weight": Vector2(-1, 0)},
		{"vec": Vector2i.RIGHT, "weight": Vector2(1, 0)}
	]
	
	for dir in directions:
		var neighbor = tile + dir.vec
		if _is_tile_valid(neighbor):
			var neighbor_danger = get_danger_at_tile(neighbor, current_time, 0.5)
			var diff = neighbor_danger - center_danger
			gradient += dir.weight * diff
	
	return gradient.normalized() if gradient.length() > 0.01 else Vector2.ZERO

## Phase 2: Check if direction moves toward or away from danger
func is_direction_safe(from_tile: Vector2i, direction: Vector2i, current_time: float) -> bool:
	var target_tile = from_tile + direction
	if not _is_tile_valid(target_tile):
		return false
	
	var current_danger = get_danger_at_tile(from_tile, current_time, 0.3)
	var target_danger = get_danger_at_tile(target_tile, current_time, 0.5)
	
	# Safe if target has less danger or both are safe
	return target_danger < current_danger or (current_danger < 0.2 and target_danger < 0.3)

## Private helper functions (Phase 2)

func _add_countdown_danger(tile: Vector2i, intensity: float, explosion_time: float, bomb_id) -> void:
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	if not danger_heatmap.has(tile_key):
		danger_heatmap[tile_key] = {
			"base_danger": 0.0,
			"explosion_countdowns": []
		}
	
	var entry = danger_heatmap[tile_key]
	entry.explosion_countdowns.append({
		"time": explosion_time,
		"intensity": intensity,
		"bomb_id": bomb_id
	})
	
	# Update base danger to highest intensity
	entry.base_danger = max(entry.base_danger, intensity)

func _calculate_urgency_weight(time_remaining: float) -> float:
	# Phase 2: Smooth urgency curve based on time remaining
	if time_remaining <= 0.5:
		return 1.0  # Critical urgency
	elif time_remaining <= 1.0:
		return 0.85  # High urgency
	elif time_remaining <= 1.5:
		return 0.65  # Medium urgency
	elif time_remaining <= 2.5:
		return 0.4  # Low urgency
	else:
		return 0.2  # Minimal urgency

func _predict_bomb_chains(bomb_id, _bomb_tile: Vector2i, affected_tiles: Array, _current_time: float) -> Dictionary:
	# Phase 2: Predict which bombs will be triggered by this explosion
	var chain_targets = []
	var total_coverage = affected_tiles.size()
	
	for other_bomb_id in game_instance.bombs:
		if other_bomb_id == bomb_id:
			continue
		
		var other_bomb = game_instance.bombs[other_bomb_id]
		if not is_instance_valid(other_bomb):
			continue
		
		var other_tile = other_bomb.get_tile_position()
		if other_tile in affected_tiles:
			chain_targets.append(other_bomb_id)
			# Estimate additional coverage from chain
			total_coverage += other_bomb.explosion_range * 4
	
	return {
		"chain_targets": chain_targets,
		"total_coverage": total_coverage,
		"creates_chain": chain_targets.size() > 0
	}

func _register_explosion_echo(bomb_id, current_time: float) -> void:
	# Phase 2: Register fading danger from recent explosion
	if not bomb_lifetime_tracker.has(bomb_id):
		return
	
	# Find all tiles that were affected by this bomb
	for tile_key in danger_heatmap.keys():
		var entry = danger_heatmap[tile_key]
		for countdown in entry.explosion_countdowns:
			if countdown.bomb_id == bomb_id:
				explosion_echoes[tile_key] = {
					"decay_intensity": countdown.intensity * 0.6,
					"decay_start": current_time
				}
				break

func _calculate_intensity_from_timer(time_remaining: float) -> float:
	# Legacy function - now using _calculate_urgency_weight
	return _calculate_urgency_weight(time_remaining)

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
