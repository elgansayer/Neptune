extends Resource
class_name BombPlanner

## Helps bots decide if a bomb placement has a safe escape route.

var grid_sampler: GridSampler
var hazard_predictor: HazardPredictor
var escape_search_radius := 8

func configure(sampler: GridSampler, predictor: HazardPredictor) -> void:
	grid_sampler = sampler
	hazard_predictor = predictor

func can_place_bomb_safely(tile: Vector2i, player, current_time: float) -> bool:
	if player == null or grid_sampler == null or hazard_predictor == null:
		return false
	if not grid_sampler.is_tile_walkable(tile, true):
		return false
	var escape_tiles = hazard_predictor.find_escape_tiles(tile, current_time, escape_search_radius)
	return escape_tiles.size() > 0

func should_attack_target(current_tile: Vector2i, opponent_tile: Vector2i, range: int) -> bool:
	if grid_sampler == null:
		return false
	return grid_sampler.get_manhattan_distance(current_tile, opponent_tile) <= range + 1
