extends Resource
class_name GridSampler

## Provides tile/world conversions plus walkability + occupancy info from the live GameInstance.

var navigation_region: NavigationRegion2D
var tile_size := 64.0

var _game_instance: Node
var _map_size := Vector2i.ZERO

func configure(instance: Node, region: NavigationRegion2D = null, new_tile_size: float = GameConfig.TILE_SIZE) -> void:
	_game_instance = instance
	navigation_region = region
	tile_size = new_tile_size
	_update_map_size()

func _update_map_size() -> void:
	if _game_instance and _game_instance.game_map.size() > 0:
		_map_size = Vector2i(_game_instance.game_map[0].size(), _game_instance.game_map.size())

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


func find_path(start_tile: Vector2i, goal_tile: Vector2i, max_depth: int = 30, ignore_player: Node = null) -> Array[Vector2i]:
	if start_tile == goal_tile:
		return []
	var frontier: Array[Vector2i] = [start_tile]
	var head := 0
	var came_from := {}
	var depth_map := {}
	depth_map[_tile_key(start_tile)] = 0
	while head < frontier.size():
		var current: Vector2i = frontier[head]
		head += 1
		if current == goal_tile:
			break
		var current_depth: int = depth_map.get(_tile_key(current), 0)
		if current_depth >= max_depth:
			continue
		for neighbor in get_cardinal_neighbors(current):
			if not is_tile_walkable(neighbor):
				continue
			# Allow movement through bomb tiles (bots have collision exceptions)
			# but still avoid other players
			if neighbor != goal_tile:
				var occupied_by_player = false
				for peer_id in _game_instance.players:
					var p = _game_instance.players[peer_id]
					if is_instance_valid(p) and p != ignore_player and not p.is_dead:
						if p.get_tile_position() == neighbor:
							occupied_by_player = true
							break
				if occupied_by_player:
					continue
			var key = _tile_key(neighbor)
			if depth_map.has(key):
				continue
			depth_map[key] = current_depth + 1
			came_from[key] = current
			frontier.append(neighbor)
	if not came_from.has(_tile_key(goal_tile)):
		return []
	var path: Array[Vector2i] = []
	var cursor: Vector2i = goal_tile
	while cursor != start_tile:
		path.push_front(cursor)
		cursor = came_from[_tile_key(cursor)]
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
