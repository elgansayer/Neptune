extends Resource
class_name AIManager

## Centralized AI brain for all bots
## Maintains global ThreatMatrix and provides pathfinding services
## All bots query this singleton for danger awareness and navigation

const Constants = preload("res://shared/constants.gd")
const DangerAwareAStar = preload("res://shared/ai/pathfinding/danger_aware_astar.gd")
const OpponentProfile = preload("res://shared/ai/intel/opponent_profile.gd")

# Global threat data: Vector2i -> time in milliseconds when tile becomes lethal
# If tile not in dictionary, it's safe (threat time = INF)
var threat_matrix: Dictionary = {}

# Time-aware pathfinder (configured once at setup)
var pathfinder: DangerAwareAStar = null

# Opponent intelligence profiles: player_id -> OpponentProfile
var opponent_profiles: Dictionary = {}

# Reference to game instance
var _game_instance: Node = null

# Grid sampler for map queries
var _grid_sampler = null

# Map dimensions
var _map_width: int = 0
var _map_height: int = 0

func configure(game_instance: Node, grid_sampler, map_width: int, map_height: int) -> void:
	_game_instance = game_instance
	_grid_sampler = grid_sampler
	_map_width = map_width
	_map_height = map_height
	
	# Initialize pathfinder
	pathfinder = DangerAwareAStar.new()
	pathfinder.region = Rect2i(0, 0, map_width, map_height)
	pathfinder.cell_size = Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)
	pathfinder.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER  # 4-directional only
	pathfinder.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	pathfinder.default_estimate_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	
	# Build initial connectivity (must be called before set_point_solid)
	pathfinder.update()
	
	# Mark solid tiles
	_initialize_pathfinder_walls()
	
	print("[AIManager] Configured with ", map_width, "x", map_height, " grid")

func _initialize_pathfinder_walls() -> void:
	if _grid_sampler == null:
		return
	
	for x in range(_map_width):
		for y in range(_map_height):
			var tile := Vector2i(x, y)
			var is_solid: bool = not _grid_sampler.is_tile_walkable(tile)
			pathfinder.set_point_solid(tile, is_solid)

## Update ThreatMatrix based on current bomb state
## Called every physics frame
func refresh_threat_matrix(current_time_msec: float) -> void:
	threat_matrix.clear()
	
	if _game_instance == null:
		return
	
	# Build threat data from all active bombs
	_build_threat_matrix_with_chains(current_time_msec)

## Core Algorithm: Build ThreatMatrix with chain reaction simulation
func _build_threat_matrix_with_chains(current_time_msec: float) -> void:
	if _game_instance == null or _grid_sampler == null:
		return
	
	# Priority queue: [bomb_id, detonation_time_msec]
	var bomb_queue: Array = []
	
	# Collect all active bombs
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		
		var fuse_remaining: float = max(Constants.BOMB_TIMER - bomb.explosion_timer, 0.0)
		var detonation_time: float = current_time_msec + (fuse_remaining * 1000.0)
		bomb_queue.append([bomb_id, detonation_time])
	
	# Sort by detonation time (earliest first)
	bomb_queue.sort_custom(func(a, b): return a[1] < b[1])
	
	# Process bombs in chronological order
	var processed_bombs := {}
	
	while bomb_queue.size() > 0:
		var entry = bomb_queue.pop_front()
		var bomb_id = entry[0]
		var det_time_msec = entry[1]
		
		if processed_bombs.has(bomb_id):
			continue
		
		processed_bombs[bomb_id] = true
		
		var bomb = _game_instance.bombs.get(bomb_id)
		if not is_instance_valid(bomb):
			continue
		
		var bomb_pos: Vector2i = bomb.get_tile_position()
		var bomb_range: int = bomb.explosion_range
		
		# Mark blast tiles with lethal time
		var blast_tiles := _get_blast_tiles(bomb_pos, bomb_range)
		
		for tile: Vector2i in blast_tiles:
			var key := _tile_key(tile)
			
			# Only update if this is earlier than existing threat
			if not threat_matrix.has(key) or det_time_msec < threat_matrix[key]:
				threat_matrix[key] = det_time_msec
		
		# Check for chain reactions
		for tile: Vector2i in blast_tiles:
			var triggered_bomb_id = _find_bomb_at_tile(tile)
			if triggered_bomb_id != null and not processed_bombs.has(triggered_bomb_id):
				# This bomb will be triggered by current explosion
				# It detonates at current bomb's time (instant chain)
				bomb_queue.append([triggered_bomb_id, det_time_msec])
				# Re-sort queue
				bomb_queue.sort_custom(func(a, b): return a[1] < b[1])

## Get all tiles affected by bomb blast
func _get_blast_tiles(center: Vector2i, range_val: int) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	tiles.append(center)
	
	# Check four cardinal directions
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	
	for dir: Vector2i in directions:
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			# Check bounds
			if tile.x < 0 or tile.x >= _map_width or tile.y < 0 or tile.y >= _map_height:
				break
			
			# Check for hard walls (blast stops)
			if not _grid_sampler.is_tile_walkable(tile):
				var tile_type = _grid_sampler.get_tile_type(tile)
				if tile_type == 1:  # Hard wall
					print("[ThreatMatrix] Blast from ", center, " stopped by HARD WALL at ", tile, " direction ", dir)
					break
				elif tile_type == 2:  # Soft wall (destroys but stops)
					print("[ThreatMatrix] Blast from ", center, " stopped by SOFT BLOCK at ", tile, " direction ", dir)
					tiles.append(tile)
					break
			
			tiles.append(tile)
	
	return tiles

## Find bomb at specific tile
func _find_bomb_at_tile(tile: Vector2i):
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and not bomb.has_exploded:
			if bomb.get_tile_position() == tile:
				return bomb_id
	return null

## Simulate ThreatMatrix with hypothetical bomb placement
## Used for "what-if" planning before committing to bomb placement
func simulate_threat_matrix(hypothetical_bomb_pos: Vector2i, bomb_range: int, current_time_msec: float) -> Dictionary:
	var simulated_matrix := threat_matrix.duplicate()
	
	# Add hypothetical bomb that detonates in 3 seconds
	var fuse_time_msec := 3000.0
	var det_time := current_time_msec + fuse_time_msec
	
	# Get blast tiles for hypothetical bomb
	var blast_tiles := _get_blast_tiles(hypothetical_bomb_pos, bomb_range)
	
	for tile: Vector2i in blast_tiles:
		var key := _tile_key(tile)
		if not simulated_matrix.has(key) or det_time < simulated_matrix[key]:
			simulated_matrix[key] = det_time
	
	return simulated_matrix

## Get current ThreatMatrix (for external queries)
func get_current_threat_matrix() -> Dictionary:
	return threat_matrix

## Update pathfinder when soft wall is destroyed
func on_wall_destroyed(tile: Vector2i) -> void:
	if pathfinder != null:
		pathfinder.set_point_solid(tile, false)
		pathfinder.update()

## Get or create opponent profile for player
func get_opponent_profile(player_id: int, player_name: String = "") -> OpponentProfile:
	if not opponent_profiles.has(player_id):
		opponent_profiles[player_id] = OpponentProfile.new(player_id, player_name)
	return opponent_profiles[player_id]

## Update opponent profiles based on current game state
func update_opponent_intel(bot_positions: Dictionary, all_players: Dictionary, delta: float) -> void:
	# bot_positions: bot_id -> Vector2i position
	# all_players: player_id -> player_node
	
	for bot_id in bot_positions:
		var bot_pos: Vector2i = bot_positions[bot_id]
		
		for player_id in all_players:
			if player_id == bot_id:
				continue  # Don't profile self
			
			var player = all_players[player_id]
			if not is_instance_valid(player) or player.is_dead:
				continue
			
			var profile := get_opponent_profile(player_id, player.player_name)
			var player_pos: Vector2i = player.get_tile_position()
			
			# Update last seen
			profile.last_seen_pos = player_pos
			profile.last_seen_time = Time.get_ticks_msec() / 1000.0
			
			# Calculate distance for aggression scoring
			var dist_now := float(abs(bot_pos.x - player_pos.x) + abs(bot_pos.y - player_pos.y))
			
			# Update aggression if we have previous distance
			if profile._previous_distances.size() > 0:
				var dist_prev: float = profile._previous_distances[-1]
				profile.update_aggression(dist_now, dist_prev, 0.05)
			
			# Store distance for next frame
			profile._previous_distances.append(dist_now)
			if profile._previous_distances.size() > 10:
				profile._previous_distances.pop_front()  # Keep last 10 samples
			
			# Update quadrant tracking
			var quadrant := _get_quadrant(player_pos)
			profile.update_quadrant_time(quadrant, delta)

## Determine which map quadrant a position is in
func _get_quadrant(pos: Vector2i) -> int:
	var mid_x := _map_width / 2
	var mid_y := _map_height / 2
	
	if pos.x < mid_x and pos.y < mid_y:
		return OpponentProfile.Quadrant.Q1
	elif pos.x >= mid_x and pos.y < mid_y:
		return OpponentProfile.Quadrant.Q2
	elif pos.x < mid_x and pos.y >= mid_y:
		return OpponentProfile.Quadrant.Q3
	else:
		return OpponentProfile.Quadrant.Q4

## Tile key helper
func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
