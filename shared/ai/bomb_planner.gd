extends Node
class_name BombPlanner

## Intelligent Bomb Placement Planning
## Ensures AI never suicides and always has escape routes
## Predicts enemy movement and plans tactical bomb chains

const Constants = preload("res://shared/constants.gd")

# References
var game_instance: Node2D
var observer
var danger_mapper  # DangerMapper instance
var personality_weights: Dictionary

func _init(game_ref: Node2D, obs_ref, danger_ref, personality: Dictionary):
	game_instance = game_ref
	observer = obs_ref
	danger_mapper = danger_ref
	personality_weights = personality

## Main function: Can we safely place a bomb here?
func can_place_bomb_safely(bomb_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	# Basic checks
	if not ai_player.can_place_bomb():
		return _failure_result("No bombs available")
	
	if not observer._is_tile_walkable(bomb_tile):
		return _failure_result("Tile not walkable")
	
	# Check if already a bomb on this tile
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if bomb.get_tile_position() == bomb_tile:
			return _failure_result("Bomb already here")
	
	# Simulate bomb placement
	var simulation = danger_mapper.simulate_bomb_placement(bomb_tile, ai_player.bomb_range, current_time)
	
	# Calculate escape routes AFTER bomb is placed
	var escape_analysis = _analyze_escape_routes(bomb_tile, simulation.affected_tiles, current_time)
	
	# Must have at least one escape route
	if escape_analysis.safe_routes.is_empty():
		return _failure_result("No escape routes")
	
	# Check if escape route is reachable in time
	var bomb_timer = Constants.BOMB_TIMER  # Default 3.0 seconds
	var movement_speed = Constants.BASE_SPEED  # Pixels per second
	
	for route in escape_analysis.safe_routes:
		var distance_to_safety = route.distance * Constants.TILE_SIZE
		var time_needed = distance_to_safety / movement_speed
		
		# Add 0.5s buffer for reaction time
		if time_needed + 0.5 < bomb_timer:
			# This route is reachable!
			return {
				"safe": true,
				"escape_route": route,
				"time_to_escape": time_needed,
				"time_buffer": bomb_timer - time_needed - 0.5,
				"simulation": simulation,
				"escape_direction": route.direction
			}
	
	return _failure_result("Escape routes too far")

## Evaluate bomb placement value (for strategic decisions)
func evaluate_bomb_placement(bomb_tile: Vector2i, ai_player: Node2D, current_time: float) -> Dictionary:
	var safety_check = can_place_bomb_safely(bomb_tile, ai_player, current_time)
	
	if not safety_check.safe:
		return {
			"value": -1000.0,  # Negative value = dangerous
			"reason": safety_check.reason,
			"safe": false
		}
	
	var simulation = safety_check.simulation
	var value = 0.0
	
	# Value from blocks destroyed
	value += simulation.blocks_destroyed * 100.0
	
	# Value from trapping players
	value += simulation.traps_players * personality_weights.get("trap_bonus", 500.0)
	
	# Chain reaction bonus
	if simulation.creates_chain:
		value += personality_weights.get("chain_setup_bonus", 500.0)
	
	# Area control bonus
	value += simulation.danger_area_size * 10.0
	
	# Defensive personality prefers safer bombs (more time buffer)
	if personality_weights.has("defensive_bonus"):
		value += safety_check.time_buffer * 50.0
	
	return {
		"value": value,
		"safe": true,
		"simulation": simulation,
		"escape_route": safety_check.escape_route,
		"blocks_destroyed": simulation.blocks_destroyed,
		"traps_players": simulation.traps_players,
		"creates_chain": simulation.creates_chain
	}

## Should we place a bomb NOW? (tactical decision)
func should_place_bomb_now(ai_player: Node2D, current_tile: Vector2i, current_time: float) -> bool:
	var evaluation = evaluate_bomb_placement(current_tile, ai_player, current_time)
	
	if not evaluation.safe:
		return false
	
	# Personality-specific thresholds
	var min_value_threshold = 100.0  # Default
	
	if personality_weights.has("aggression"):
		var aggression = personality_weights.aggression
		if aggression > 800:
			min_value_threshold = 50.0  # Kamikaze: place bombs more freely
		elif aggression < 200:
			min_value_threshold = 200.0  # Defensive: only place high-value bombs
	
	# Place bomb if value exceeds threshold
	if evaluation.value >= min_value_threshold:
		return true
	
	# Strategic personalities wait for chain setups
	if personality_weights.get("chain_setup_bonus", 0.0) > 500.0:
		if evaluation.creates_chain:
			return true
	
	# Trapper personalities wait for perfect traps
	if personality_weights.get("trap_bonus", 0.0) > 500.0:
		if evaluation.traps_players > 0:
			return true
	
	return false

## Find best tile nearby to place bomb
func find_best_bomb_placement(ai_player: Node2D, search_radius: int = 3) -> Dictionary:
	var current_tile = ai_player.get_tile_position()
	var current_time = Time.get_ticks_msec() / 1000.0
	
	var best_placement = null
	var best_value = -INF
	
	# Search nearby tiles
	for dy in range(-search_radius, search_radius + 1):
		for dx in range(-search_radius, search_radius + 1):
			var tile = current_tile + Vector2i(dx, dy)
			
			if not observer._is_tile_valid(tile):
				continue
			
			var evaluation = evaluate_bomb_placement(tile, ai_player, current_time)
			
			if evaluation.value > best_value:
				best_value = evaluation.value
				best_placement = {
					"tile": tile,
					"evaluation": evaluation
				}
	
	if best_placement == null:
		return {"found": false}
	
	return {
		"found": true,
		"tile": best_placement.tile,
		"value": best_value,
		"evaluation": best_placement.evaluation
	}

## Predict opponent movement for trap setup
func predict_opponent_trap(opponent: Node2D, ai_player: Node2D, current_time: float) -> Dictionary:
	var opponent_tile = opponent.get_tile_position()
	var ai_tile = ai_player.get_tile_position()
	
	# Use observer's prediction system
	var predicted_pos = observer.predict_opponent_position(opponent.player_id, 1.5)  # 1.5 seconds ahead
	var predicted_tile = Vector2i(
		int(floor(predicted_pos.x / Constants.TILE_SIZE)),
		int(floor(predicted_pos.y / Constants.TILE_SIZE))
	)
	
	# Validate prediction
	if not observer._is_tile_valid(predicted_tile):
		predicted_tile = opponent_tile  # Fallback to current
	
	# Check if we can intercept with a bomb
	var distance_to_predicted = abs(predicted_tile.x - ai_tile.x) + abs(predicted_tile.y - ai_tile.y)
	
	if distance_to_predicted <= ai_player.bomb_range + 2:
		# Find intercept tile (between AI and predicted opponent position)
		var intercept_tile = _calculate_intercept_tile(ai_tile, predicted_tile)
		
		# Check if intercept is safe to place bomb
		var safety = can_place_bomb_safely(intercept_tile, ai_player, current_time)
		
		if safety.safe:
			return {
				"can_trap": true,
				"intercept_tile": intercept_tile,
				"predicted_tile": predicted_tile,
				"opponent": opponent,
				"safety": safety
			}
	
	return {"can_trap": false}

## Plan chain bomb sequence
func plan_chain_bomb(ai_player: Node2D, current_time: float) -> Dictionary:
	var current_tile = ai_player.get_tile_position()
	
	# Find existing bombs that could be chained
	var chainable_bombs = []
	
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		var bomb_tile = bomb.get_tile_position()
		
		# Check if this bomb is within range of a potential new bomb
		for dy in range(-ai_player.bomb_range, ai_player.bomb_range + 1):
			for dx in range(-ai_player.bomb_range, ai_player.bomb_range + 1):
				var potential_tile = bomb_tile + Vector2i(dx, dy)
				
				if not observer._is_tile_valid(potential_tile):
					continue
				
				if not observer._is_tile_walkable(potential_tile):
					continue
				
				# Check if this tile can reach the existing bomb
				var simulation = danger_mapper.simulate_bomb_placement(potential_tile, ai_player.bomb_range, current_time)
				
				if bomb_tile in simulation.affected_tiles:
					var distance_from_ai = abs(potential_tile.x - current_tile.x) + abs(potential_tile.y - current_tile.y)
					
					chainable_bombs.append({
						"existing_bomb": bomb,
						"new_bomb_tile": potential_tile,
						"distance": distance_from_ai,
						"simulation": simulation
					})
	
	if chainable_bombs.is_empty():
		return {"chain_available": false}
	
	# Sort by total value (blocks + distance)
	chainable_bombs.sort_custom(func(a, b):
		var value_a = a.simulation.blocks_destroyed * 100.0 - a.distance * 10.0
		var value_b = b.simulation.blocks_destroyed * 100.0 - b.distance * 10.0
		return value_a > value_b
	)
	
	# Check best chain for safety
	var best_chain = chainable_bombs[0]
	var safety = can_place_bomb_safely(best_chain.new_bomb_tile, ai_player, current_time)
	
	if not safety.safe:
		return {"chain_available": false}
	
	return {
		"chain_available": true,
		"target_tile": best_chain.new_bomb_tile,
		"chain_length": 2,  # Could be extended for deeper analysis
		"value": best_chain.simulation.blocks_destroyed * 100.0,
		"safety": safety
	}

## Emergency escape planning (when already in danger)
func plan_emergency_escape(ai_player: Node2D, current_time: float) -> Dictionary:
	var current_tile = ai_player.get_tile_position()
	
	# Check current danger level
	var danger_level = danger_mapper.get_danger_at_tile(current_tile, current_time, 0.5)
	
	if danger_level < 0.3:
		return {"emergency": false}  # Not in danger
	
	# Find ALL safe tiles urgently
	var safe_tiles = danger_mapper.find_nearest_safe_tiles(current_tile, current_time, 8)
	
	if safe_tiles.is_empty():
		# Desperate situation - find LEAST dangerous tile
		var least_dangerous = _find_least_dangerous_tile(current_tile, current_time)
		
		return {
			"emergency": true,
			"desperate": true,
			"escape_tile": least_dangerous.tile,
			"survival_chance": "LOW"
		}
	
	# Get closest safe tile
	var best_safe = safe_tiles[0]
	
	return {
		"emergency": true,
		"escape_tile": best_safe.tile,
		"distance": best_safe.distance,
		"survival_chance": "HIGH" if best_safe.distance <= 2 else "MEDIUM"
	}

## Private helper functions

func _failure_result(reason: String) -> Dictionary:
	return {
		"safe": false,
		"reason": reason
	}

func _analyze_escape_routes(bomb_tile: Vector2i, danger_tiles: Array, current_time: float) -> Dictionary:
	var safe_routes = []
	var all_routes = []
	
	# Check all 4 directions from bomb tile
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var route_tiles = []
		var is_safe = false
		var distance_to_safety = 0
		
		# Walk in direction until we find safety or hit obstacle
		for step in range(1, 10):  # Check up to 10 tiles away
			var tile = bomb_tile + (dir * step)
			
			if not observer._is_tile_valid(tile):
				break
			
			if not observer._is_tile_walkable(tile):
				break
			
			route_tiles.append(tile)
			
			# Check if this tile is safe from the bomb we're planning
			if tile not in danger_tiles:
				# Also check it's not in danger from other bombs
				if danger_mapper.is_tile_safe(tile, current_time, 1.0):
					is_safe = true
					distance_to_safety = step
					break
		
		var route = {
			"direction": dir,
			"tiles": route_tiles,
			"safe": is_safe,
			"distance": distance_to_safety
		}
		
		all_routes.append(route)
		
		if is_safe:
			safe_routes.append(route)
	
	return {
		"safe_routes": safe_routes,
		"all_routes": all_routes,
		"safe_count": safe_routes.size()
	}

func _calculate_intercept_tile(from_tile: Vector2i, to_tile: Vector2i) -> Vector2i:
	# Calculate midpoint tile (simplified intercept)
	var mid_x = (from_tile.x + to_tile.x) / 2
	var mid_y = (from_tile.y + to_tile.y) / 2
	
	var intercept = Vector2i(int(mid_x), int(mid_y))
	
	# Validate intercept is walkable
	if observer._is_tile_walkable(intercept):
		return intercept
	
	# Fallback: return tile closer to AI
	return from_tile + ((to_tile - from_tile) / 3)

func _find_least_dangerous_tile(from_tile: Vector2i, current_time: float) -> Dictionary:
	var least_danger = INF
	var best_tile = from_tile
	
	for dy in range(-3, 4):
		for dx in range(-3, 4):
			var tile = from_tile + Vector2i(dx, dy)
			
			if not observer._is_tile_valid(tile):
				continue
			
			if not observer._is_tile_walkable(tile):
				continue
			
			var danger = danger_mapper.get_danger_at_tile(tile, current_time, 0.5)
			
			if danger < least_danger:
				least_danger = danger
				best_tile = tile
	
	return {
		"tile": best_tile,
		"danger": least_danger
	}
