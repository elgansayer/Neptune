extends Resource
class_name AIManager

## Centralized AI brain for all bots
## Maintains global ThreatMatrix and provides pathfinding services
## All bots query this singleton for danger awareness and navigation

const Constants = preload("res://shared/constants.gd")
const BombForecast = preload("res://shared/ai/perception/bomb_threat_forecast.gd")
const DangerAwareAStarScript = preload("res://shared/ai/pathfinding/danger_aware_astar.gd")
const OpponentProfileScript = preload("res://shared/ai/intel/opponent_profile.gd")

# Global threat data: Vector2i -> time in milliseconds when tile becomes lethal
# If tile not in dictionary, it's safe (threat time = INF)
var threat_matrix: Dictionary = {}
var hazard_intervals: Dictionary = {}
var forecast_uncertainty: Array = []
const MAX_FORECAST_CACHE_ENTRIES := 128
var _forecast_query_cache: Dictionary = {}
var _forecast_query_revision := -1
var _forecast_query_time := -INF

# Time-aware pathfinder (configured once at setup)
var pathfinder: DangerAwareAStarScript = null

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
	_forecast_query_cache.clear()
	_forecast_query_revision = -1
	_forecast_query_time = -INF
	_game_instance = game_instance
	_grid_sampler = grid_sampler
	_map_width = map_width
	_map_height = map_height
	
	# Initialize pathfinder
	pathfinder = DangerAwareAStarScript.new()
	pathfinder.region = Rect2i(0, 0, map_width, map_height)
	pathfinder.cell_size = Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)
	pathfinder.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER # 4-directional only
	pathfinder.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	pathfinder.default_estimate_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	
	# Build initial connectivity (must be called before set_point_solid)
	pathfinder.update()
	
	# Mark solid tiles
	_initialize_pathfinder_walls()
	
	# print("[AIManager] Configured with ", map_width, "x", map_height, " grid")

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
	var timeline := BombForecast.build_timeline(_game_instance, _grid_sampler, current_time_msec)
	threat_matrix = timeline.deadlines
	hazard_intervals = timeline.intervals
	forecast_uncertainty = timeline.uncertain

## Get all tiles affected by bomb blast
func _get_blast_tiles(center: Vector2i, range_val: int, debug_log: bool = false) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	tiles.append(center)
	
	# Check four cardinal directions
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	var dir_names := ["RIGHT", "LEFT", "UP", "DOWN"]
	
	for i in range(directions.size()):
		var dir: Vector2i = directions[i]
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			# Check bounds
			if tile.x < 0 or tile.x >= _map_width or tile.y < 0 or tile.y >= _map_height:
				if debug_log:
					print("[_get_blast_tiles] ", dir_names[i], " dist=", dist, " tile=", tile, " OUT OF BOUNDS")
				break
			
			# Check for hard walls (blast stops)
			if not _grid_sampler.is_tile_walkable(tile):
				var tile_type = _grid_sampler.get_tile_type(tile)
				if tile_type == 1 or tile_type == 3: # Hard wall or hurry block
					if debug_log:
						print("[_get_blast_tiles] ", dir_names[i], " dist=", dist, " tile=", tile, " HARD_WALL/HURRY (stop)")
					break
				elif tile_type == 2: # Soft wall (destroys but stops)
					if debug_log:
						print("[_get_blast_tiles] ", dir_names[i], " dist=", dist, " tile=", tile, " SOFT_BLOCK (add+stop)")
					tiles.append(tile)
					break
			
			if debug_log:
				print("[_get_blast_tiles] ", dir_names[i], " dist=", dist, " tile=", tile, " WALKABLE (add)")
			tiles.append(tile)
	
	if debug_log:
		print("[_get_blast_tiles] center=", center, " range=", range_val, " result=", tiles)
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
func simulate_threat_matrix(hypothetical_bomb_pos: Vector2i, bomb_range: int, current_time_msec: float, fuse_lower_bound: float = Constants.BOMB_TIMER) -> Dictionary:
	var cached: bool = _prepare_forecast_query_cache(current_time_msec)
	var key := ["hypothetical", hypothetical_bomb_pos, bomb_range, fuse_lower_bound]
	if cached and _forecast_query_cache.has(key):
		return _forecast_query_cache[key].duplicate(true)
	var result := _build_hypothetical_forecast(hypothetical_bomb_pos, bomb_range, current_time_msec, fuse_lower_bound)
	if cached and _forecast_query_cache.size() < MAX_FORECAST_CACHE_ENTRIES:
		_forecast_query_cache[key] = result
		return result.duplicate(true)
	return result

func _build_hypothetical_forecast(hypothetical_bomb_pos: Vector2i, bomb_range: int, current_time_msec: float, fuse_lower_bound: float) -> Dictionary:
	return BombForecast.build(_game_instance, _grid_sampler, current_time_msec, {
		"cell": hypothetical_bomb_pos, "range": bomb_range,
		"fuse_lower_bound": fuse_lower_bound, "elapsed": 0.0
	})

func get_placement_capability(cell: Vector2i, current_time_msec: float) -> Dictionary:
	var cached: bool = _prepare_forecast_query_cache(current_time_msec)
	var key := ["capability", cell]
	if cached and _forecast_query_cache.has(key):
		return _forecast_query_cache[key].duplicate(true)
	var result: Dictionary = BombForecast.placement_capability(_game_instance, _grid_sampler, cell)
	if cached and _forecast_query_cache.size() < MAX_FORECAST_CACHE_ENTRIES:
		_forecast_query_cache[key] = result
		return result.duplicate(true)
	return result

func _prepare_forecast_query_cache(current_time_msec: float) -> bool:
	# A raw authority or legacy fixture has no revision contract: calculate
	# afresh rather than infer validity from a frozen simulation timestamp.
	if _game_instance == null or not _game_instance.has_method("get_observation_revision") or not is_finite(current_time_msec):
		return false
	var revision: int = _game_instance.get_observation_revision()
	if revision != _forecast_query_revision or current_time_msec != _forecast_query_time:
		_forecast_query_cache.clear()
		_forecast_query_revision = revision
		_forecast_query_time = current_time_msec
	return true

## Get current ThreatMatrix (for external queries)
func get_current_threat_matrix() -> Dictionary:
	return threat_matrix

## Update pathfinder when soft wall is destroyed
func on_wall_destroyed(tile: Vector2i) -> void:
	if pathfinder != null:
		pathfinder.set_point_solid(tile, false)
		pathfinder.update()

## Get or create opponent profile for player
func get_opponent_profile(player_id: int, player_name: String = "") -> OpponentProfileScript:
	if not opponent_profiles.has(player_id):
		opponent_profiles[player_id] = OpponentProfileScript.new(player_id, player_name)
	return opponent_profiles[player_id]

## Update opponent profiles based on current game state
func update_opponent_intel(bot_positions: Dictionary, all_players: Dictionary, delta: float) -> void:
	# bot_positions: bot_id -> Vector2i position
	# all_players: player_id -> player_node
	# Profiles are shared, so observe each player once, independently of bot
	# count/order. Repeating the update per bot inflated spatial time and made
	# the first observer overwrite the previous position before others used it.
	var observer_ids: Array = bot_positions.keys()
	observer_ids.sort()
	for player_id in all_players:
		var player = all_players[player_id]
		if not is_instance_valid(player) or player.is_dead:
			continue
		var player_pos: Vector2i = player.get_tile_position()
		var observer_pos := Vector2i.ZERO
		var nearest_distance := INF
		for bot_id in observer_ids:
			if bot_id == player_id:
				continue
			var candidate: Vector2i = bot_positions[bot_id]
			var distance := float(abs(candidate.x - player_pos.x) + abs(candidate.y - player_pos.y))
			if distance < nearest_distance:
				nearest_distance = distance
				observer_pos = candidate
		if nearest_distance == INF:
			continue
		var profile := get_opponent_profile(player_id, player.player_name)
		if profile.has_observation:
			# Use the same observer position for both measurements: our own
			# motion cannot be mistaken for the opponent approaching/fleeing.
			var previous_distance := float(abs(observer_pos.x - profile.last_seen_pos.x) + abs(observer_pos.y - profile.last_seen_pos.y))
			profile.update_aggression(nearest_distance, previous_distance, 0.05)
		profile.last_seen_pos = player_pos
		profile.last_seen_time = _game_instance.get_simulation_time_sec()
		profile.has_observation = true
		profile.update_quadrant_time(_get_quadrant(player_pos), delta)

## Determine which map quadrant a position is in
func _get_quadrant(pos: Vector2i) -> int:
	var mid_x := _map_width / 2.0
	var mid_y := _map_height / 2.0
	
	if pos.x < mid_x and pos.y < mid_y:
		return OpponentProfileScript.Quadrant.Q1
	elif pos.x >= mid_x and pos.y < mid_y:
		return OpponentProfileScript.Quadrant.Q2
	elif pos.x < mid_x and pos.y >= mid_y:
		return OpponentProfileScript.Quadrant.Q3
	else:
		return OpponentProfileScript.Quadrant.Q4

## Tile key helper
func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
