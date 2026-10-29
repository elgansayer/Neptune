extends "res://tests/bot_test_suite.gd"

var projectile: ServerBomb
var occupant: ServerPlayer
var other: ServerBomb
const CELL := Vector2i(3, 3)

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	game_instance = GameInstance.new()
	game_instance.game_map = []
	for y in range(8):
		game_instance.game_map.append([0, 0, 0, 0, 0, 0, 0, 0])
	projectile = ServerBomb.new()
	projectile.bomb_id = "self"
	projectile.game_instance = game_instance
	projectile.position = Vector2(CELL) * GameConfig.TILE_SIZE
	game_instance.bombs["self"] = projectile
	occupant = ServerPlayer.new()
	other = ServerBomb.new()
	other.bomb_id = "other"

func teardown_test() -> void:
	projectile.free()
	occupant.free()
	other.free()
	game_instance.free()

func test_player_occupancy_matches_tile_boundaries() -> Variant:
	game_instance.players[1] = occupant
	return check_boundaries(occupant)

func test_bomb_occupancy_matches_tile_boundaries() -> Variant:
	game_instance.bombs["other"] = other
	return check_boundaries(other)

func check_boundaries(entity: Node2D) -> Variant:
	var size := float(GameConfig.TILE_SIZE)
	# Exact lower and upper edges, their neighbours, and fractional interiors.
	for x in [-0.01, 0.0, 0.01, size / 2.0, size - 0.01, size, size + 0.01]:
		for y in [-0.01, 0.0, 0.01, size / 2.0, size - 0.01, size, size + 0.01]:
			entity.position = Vector2(CELL) * size + Vector2(x, y)
			var occupied: bool = entity.get_tile_position() == CELL
			if projectile._check_tile_has_collision(CELL) != occupied:
				return "Collision disagrees with the entity tile at %s" % entity.position
			if projectile._is_tile_free_for_landing(CELL) == occupied:
				return "Landing disagrees with the entity tile at %s" % entity.position
	return true

func test_dead_players_exploded_bombs_and_self_do_not_block() -> Variant:
	occupant.position = projectile.position
	occupant.is_dead = true
	other.position = projectile.position
	other.has_exploded = true
	game_instance.players[1] = occupant
	game_instance.bombs["other"] = other
	return assert_true(not projectile._check_tile_has_collision(CELL) and projectile._is_tile_free_for_landing(CELL))

func test_static_walls_and_out_of_bounds_reject_landing() -> Variant:
	game_instance.game_map[CELL.y][CELL.x] = 1
	return assert_true(projectile._check_tile_has_collision(CELL)
		and not projectile._is_tile_free_for_landing(CELL)
		and not projectile._is_tile_free_for_landing(Vector2i(-1, 3)))
