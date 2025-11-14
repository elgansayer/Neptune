extends Resource
class_name HazardPredictor

const Constants = preload("res://shared/constants.gd")

## Tracks bomb danger windows by sampling bombs from the authoritative GameInstance.

var _game_instance: Node
var _grid_sampler: GridSampler
var _default_buffer := 0.5
var _danger_cache := {}

func configure(instance: Node, sampler: GridSampler, default_buffer: float = 0.5) -> void:
	_game_instance = instance
	_grid_sampler = sampler
	_default_buffer = default_buffer

func refresh(current_time: float) -> void:
	_danger_cache.clear()
	if _game_instance == null:
		return
	for bomb_id in _game_instance.bombs:
		var bomb = _game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb) or bomb.has_exploded:
			continue
		var fuse_remaining = max(Constants.BOMB_TIMER - bomb.explosion_timer, 0.0)
		var impact_time = current_time + fuse_remaining
		for tile in _project_bomb_tiles(bomb):
			var key = _tile_key(tile)
			if not _danger_cache.has(key) or impact_time < _danger_cache[key]:
				_danger_cache[key] = impact_time

func get_time_to_safety(tile: Vector2i, current_time: float) -> float:
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time <= 0.0:
		return 0.0
	return max(danger_time - current_time, 0.0)

func is_tile_safe(tile: Vector2i, current_time: float, buffer: float = -1.0) -> bool:
	if buffer < 0.0:
		buffer = _default_buffer
	var danger_time = _danger_cache.get(_tile_key(tile), -INF)
	if danger_time <= 0.0:
		return true
	return current_time + buffer < danger_time

func find_escape_tiles(from_tile: Vector2i, current_time: float, max_distance: int = 6) -> Array[Vector2i]:
	if _grid_sampler == null:
		return []
	var queue: Array[Vector2i] = [from_tile]
	var head := 0
	var visited := {}
	visited[_tile_key(from_tile)] = 0
	var safe_tiles: Array[Vector2i] = []
	while head < queue.size():
		var current: Vector2i = queue[head]
		head += 1
		var depth: int = visited.get(_tile_key(current), 0)
		if is_tile_safe(current, current_time):
			safe_tiles.append(current)
			if safe_tiles.size() >= 3:
				break
		if depth >= max_distance:
			continue
		for neighbor in _grid_sampler.get_cardinal_neighbors(current):
			if not _grid_sampler.is_tile_walkable(neighbor):
				continue
			var key = _tile_key(neighbor)
			if visited.has(key):
				continue
			visited[key] = depth + 1
			queue.append(neighbor)
	return safe_tiles

func _project_bomb_tiles(bomb) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	if _grid_sampler == null:
		return tiles
	var origin = bomb.get_tile_position()
	if not _grid_sampler.is_in_bounds(origin):
		return tiles
	tiles.append(origin)
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]
	for dir in directions:
		for step in range(1, bomb.explosion_range + 1):
			var tile = origin + dir * step
			if not _grid_sampler.is_in_bounds(tile):
				break
			var tile_type = _game_instance.get_tile_type(tile)
			if tile_type == 1:
				break
			tiles.append(tile)
			if tile_type == 2:
				break
	return tiles

func _tile_key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]
