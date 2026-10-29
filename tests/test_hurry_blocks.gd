extends "res://tests/bot_test_suite.gd"

var owned_players: Array = []
var owned_bombs: Array = []

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	game_instance = GameInstance.new()
	game_instance.match_active = false
	game_instance.game_map = []
	for y in range(8):
		game_instance.game_map.append([0, 0, 0, 0, 0, 0, 0, 0])

func teardown_test() -> void:
	for entity in owned_players + owned_bombs:
		if is_instance_valid(entity):
			entity.free()
	owned_players.clear()
	owned_bombs.clear()
	game_instance.free()

func player_at(cell: Vector2i) -> ServerPlayer:
	var player := ServerPlayer.new()
	player.position = BotTestHelpers.tile_to_world_center(cell)
	owned_players.append(player)
	game_instance.players[owned_players.size()] = player
	return player

func bomb_at(id: String, cell: Vector2i) -> ServerBomb:
	var bomb := ServerBomb.new()
	bomb.bomb_id = id
	bomb.position = BotTestHelpers.tile_to_world_center(cell)
	bomb.game_instance = game_instance
	owned_bombs.append(bomb)
	game_instance.bombs[id] = bomb
	return bomb

func test_batch_crushes_all_occupants_only_on_spawned_cells() -> Variant:
	var first := player_at(Vector2i(2, 2))
	var same_tile := player_at(Vector2i(2, 2))
	var second := player_at(Vector2i(3, 2))
	var outside := player_at(Vector2i(4, 2))
	game_instance.hurry_spawn_pattern.assign([Vector2i(2, 2), Vector2i(3, 2)])
	game_instance._process_hurry_mode(game_instance.hurry_spawn_interval * 2.0)
	return assert_true(first.is_dead and same_tile.is_dead and second.is_dead
		and not outside.is_dead and game_instance.hurry_blocks.size() == 2)

func test_direct_spawn_keeps_player_and_bomb_checks() -> Variant:
	var player := player_at(Vector2i(2, 2))
	var bomb := bomb_at("one", Vector2i(2, 2))
	game_instance._spawn_hurry_block(Vector2i(2, 2))
	return assert_true(player.is_dead and bomb.has_exploded and game_instance.game_map[2][2] == 3)

func test_explosion_callback_can_remove_later_cached_bomb() -> Variant:
	var first := bomb_at("first", Vector2i(2, 2))
	var second := bomb_at("second", Vector2i(3, 2))
	first.exploded.connect(func(_bomb, _pattern):
		game_instance.bombs.erase("second")
		second.free()
	)
	game_instance.hurry_spawn_pattern.assign([Vector2i(2, 2), Vector2i(3, 2)])
	game_instance._process_hurry_mode(game_instance.hurry_spawn_interval * 2.0)
	return assert_true(first.has_exploded and game_instance.hurry_blocks.size() == 2
		and game_instance.game_map[2][3] == 3)

func test_idle_tick_does_not_spawn_or_crush() -> Variant:
	var player := player_at(Vector2i(2, 2))
	game_instance.hurry_spawn_pattern.assign([Vector2i(2, 2)])
	game_instance._process_hurry_mode(game_instance.hurry_spawn_interval * 0.5)
	return assert_true(not player.is_dead and game_instance.hurry_blocks.is_empty())
