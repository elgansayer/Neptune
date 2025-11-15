extends Resource
class_name BombPlanner

## Helps bots decide if a bomb placement has a safe escape route.

var _grid_sampler
var _hazard_predictor

func configure(sampler, predictor) -> void:
	_grid_sampler = sampler
	_hazard_predictor = predictor

## Evaluates if placing a bomb at a given tile is a "good" idea.
func can_place_bomb_safely(tile: Vector2i, player, current_time: float) -> bool:
	return plan_escape_after_bomb(tile, player, current_time) != null

func plan_escape_after_bomb(tile: Vector2i, player, current_time: float):
	if player == null or _grid_sampler == null or _hazard_predictor == null:
		return null
	if not _grid_sampler.is_tile_walkable(tile, true):
		return null

	var escape_tiles = _hazard_predictor.find_escape_tiles(tile, current_time, 8)
	if escape_tiles.is_empty():
		return null

	var best_tile = null
	var best_cost := INF
	for escape_tile in escape_tiles:
		if escape_tile == tile:
			continue
		if not _grid_sampler.is_tile_walkable(escape_tile, true):
			continue
		var path: Array = _grid_sampler.find_path(tile, escape_tile, 32, player)
		if path.is_empty():
			continue
		var cost = path.size()
		if cost < best_cost:
			best_cost = cost
			best_tile = escape_tile

	return best_tile

func should_attack_target(current_tile: Vector2i, opponent_tile: Vector2i, range: int) -> bool:
	if _grid_sampler == null:
		return false
	return _grid_sampler.get_manhattan_distance(current_tile, opponent_tile) <= range + 1
