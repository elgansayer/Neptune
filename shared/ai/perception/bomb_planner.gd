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
	if player == null or _grid_sampler == null or _hazard_predictor == null:
		return false
	if not _grid_sampler.is_tile_walkable(tile, true):
		return false
	var escape_tiles = _hazard_predictor.find_escape_tiles(tile, current_time, 8)
	return escape_tiles.size() > 0

func should_attack_target(current_tile: Vector2i, opponent_tile: Vector2i, range: int) -> bool:
	if _grid_sampler == null:
		return false
	return _grid_sampler.get_manhattan_distance(current_tile, opponent_tile) <= range + 1
