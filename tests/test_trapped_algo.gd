extends "res://tests/bot_test_suite.gd"

## Exercise the production method; do not copy its algorithm into the test.
func setup_suite() -> void:
	game_instance = GameInstance.new()

func teardown_suite() -> void:
	game_instance.free()

func setup_test() -> void:
	game_instance.game_map = [[1, 1, 1], [1, 0, 0], [1, 1, 1]]

func teardown_test() -> void:
	for bomb in game_instance.bombs.values():
		bomb.free()
	game_instance.bombs.clear()

func test_open_exit_is_not_trapped() -> Variant:
	return assert_false(game_instance._is_player_physically_trapped(Vector2i(1, 1)), "Open exit classified as trapped")

func test_bomb_blocks_last_exit() -> Variant:
	var bomb := ServerBomb.new()
	bomb.position = BotTestHelpers.tile_to_world_center(Vector2i(2, 1))
	game_instance.bombs["fixture"] = bomb
	return assert_true(game_instance._is_player_physically_trapped(Vector2i(1, 1)), "Bomb did not block last exit")

func test_soft_block_blocks_last_exit() -> Variant:
	game_instance.game_map[1][2] = 2
	return assert_true(game_instance._is_player_physically_trapped(Vector2i(1, 1)), "Soft block did not block last exit")
