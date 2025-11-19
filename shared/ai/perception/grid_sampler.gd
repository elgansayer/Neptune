extends Resource
class_name GridSampler

## Provides tile/world conversions plus walkability + occupancy info from the live GameInstance.

var navigation_region: NavigationRegion2D
var tile_size := 64.0

var _game_instance: Node
var _map_size := Vector2i.ZERO
var _astar: AStarGrid2D

func configure(instance: Node, region: NavigationRegion2D = null, new_tile_size: float = GameConfig.TILE_SIZE) -> void:
	_game_instance = instance
	navigation_region = region
	tile_size = new_tile_size
	_update_map_size()

func _update_map_size() -> void:
	if _game_instance and _game_instance.game_map.size() > 0:
		_map_size = Vector2i(_game_instance.game_map[0].size(), _game_instance.game_map.size())
		_init_astar()

func _init_astar() -> void:
	_astar = AStarGrid2D.new()
	_astar.region = Rect2i(0, 0, _map_size.x, _map_size.y)
	_astar.cell_size = Vector2(tile_size, tile_size)
	_astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	_astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	_astar.default_estimate_heuristic = AStarGrid2D.HEURISTIC_MANHATTAN
	_astar.update()

func world_to_tile(world_position: Vector2) -> Vector2i:
	return Vector2i(int(floor(world_position.x / tile_size)), int(floor(world_position.y / tile_size)))

func tile_to_world_center(tile_position: Vector2i) -> Vector2:
	return Vector2(
		tile_position.x * tile_size + tile_size * 0.5,
		tile_position.y * tile_size + tile_size * 0.5
	)

func is_in_bounds(tile_position: Vector2i) -> bool:
	if _map_size == Vector2i.ZERO:
		_update_map_size()
	return tile_position.x >= 0 and tile_position.x < _map_size.x \
		and tile_position.y >= 0 and tile_position.y < _map_size.y

func is_tile_walkable(tile_position: Vector2i, allow_soft_block: bool = false) -> bool:
	if not is_in_bounds(tile_position):
		return false
	if _game_instance == null:
		return true
	var tile_type = _game_instance.get_tile_type(tile_position)
	if tile_type == 0:
		return true
	if tile_type == 2 and allow_soft_block:
		return true
	return false

func is_tile_occupied(tile_position: Vector2i, ignore_player: Node = null) -> bool:
	if _game_instance == null:
		return false
	for peer_id in _game_instance.players:
		var player = _game_instance.players[peer_id]
		if not is_instance_valid(player) or player == ignore_player:
			continue
		if player.is_dead:
			continue
		if player.get_tile_position() == tile_position:
			return true
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		if bomb.get_tile_position() == tile_position:
			return true
	return false

func get_cardinal_neighbors(tile_position: Vector2i) -> Array[Vector2i]:
	var neighbors: Array[Vector2i] = []
	var offsets = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]
	for offset in offsets:
		var candidate = tile_position + offset
		if is_in_bounds(candidate):
			neighbors.append(candidate)
	return neighbors


func find_path(start_tile: Vector2i, goal_tile: Vector2i, max_depth: int = 30, ignore_player: Node = null, avoid_threats: bool = false) -> Array[Vector2i]:
	if start_tile == goal_tile:
		return []
		
	if _astar == null or _map_size == Vector2i.ZERO:
		_update_map_size()
		if _astar == null: # Should be initialized by _update_map_size
			return []
			
	# 1. Reset grid solids based on static map (walls/soft blocks)
	# We iterate the map to ensure dynamic soft block changes are reflected
	# Optimization: We could track soft block changes, but for this map size, iteration is fast enough
	for x in range(_map_size.x):
		for y in range(_map_size.y):
			var pos = Vector2i(x, y)
			# 0 = Empty (Walkable), 1 = Hard Block (Solid), 2 = Soft Block (Solid)
			var tile_type = _game_instance.get_tile_type(pos)
			var is_solid = (tile_type != 0)
			_astar.set_point_solid(pos, is_solid)
	
	# 2. Mark other players as solid obstacles
	for peer_id in _game_instance.players:
		var p = _game_instance.players[peer_id]
		if is_instance_valid(p) and p != ignore_player and not p.is_dead:
			var p_pos = p.get_tile_position()
			if is_in_bounds(p_pos) and p_pos != goal_tile:
				_astar.set_point_solid(p_pos, true)
	
	# 3. Mark threats if requested
	if avoid_threats and _game_instance.ai_manager:
		var threat_matrix = _game_instance.ai_manager.get_current_threat_matrix()
		for tile_key in threat_matrix:
			var parts = tile_key.split(",")
			if parts.size() == 2:
				var tile = Vector2i(int(parts[0]), int(parts[1]))
				# Don't block start tile (we need to leave it)
				# Don't block goal tile (we decided to go there, presumably it's safe or we accept the risk)
				if tile != start_tile and tile != goal_tile:
					if is_in_bounds(tile):
						_astar.set_point_solid(tile, true)
	
	# Note: We do NOT mark bombs as solid because bots have collision exceptions
	# and can walk through their own bombs (and often others depending on rules)
	
	# 4. Get the path
	var path = _astar.get_id_path(start_tile, goal_tile)
	
	# AStarGrid2D returns path including start point.
	# If path is empty, no path found.
	return path

func get_manhattan_distance(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)

func get_map_bounds() -> Vector2i:
	if _map_size == Vector2i.ZERO:
		_update_map_size()
	return _map_size

func get_tile_type(tile_position: Vector2i) -> int:
	if _game_instance == null:
		return 0  # Default to empty
	return _game_instance.get_tile_type(tile_position)

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
