extends "res://tests/bot_test_suite.gd"

## Own a real game for legacy scenarios. Genuine bot outcomes may still fail.
const SCENARIO_SEED := 424242

func run_tests() -> void:
	default_map_width = 21
	default_map_height = 15
	await setup_suite()
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.bot_manager.set_physics_process(false)
	game_instance.add_to_group("bot_test_game")
	game_instance.set_meta("fixture_owner", self)
	clear_map()
	for y in range(default_map_height):
		for x in range(default_map_width):
			if x == 0 or y == 0 or x == default_map_width - 1 or y == default_map_height - 1:
				set_tile(x, y, 1)
	await get_tree().physics_frame
	await get_tree().physics_frame
	game_instance.ai_manager.configure(game_instance, game_instance.bot_manager.grid_sampler, default_map_width, default_map_height)
	seed(SCENARIO_SEED)
	print("SCENARIO_SEED=", SCENARIO_SEED, " scenario=", get_script().resource_path)
	await setup()
	if get("test_result").is_empty():
		if game_instance.players.is_empty():
			set("test_result", "FAIL: No real bots spawned")
		for player in game_instance.players.values():
			var expected = player.get_meta("fixture_spawn", Vector2i(-1, -1))
			if player.get_tile_position() != expected or game_instance.bot_manager.get_bot_controller(player.peer_id) == null:
				set("test_result", "FAIL: Incorrect bot position or absent controller")
	if get("test_result").is_empty():
		game_instance.match_active = true
		for player in game_instance.players.values():
			var controller = game_instance.bot_manager.get_bot_controller(player.peer_id)
			controller.process_mode = Node.PROCESS_MODE_INHERIT
			controller.active = true
		game_instance.bot_manager.set_physics_process(true)
		await execute()
	game_instance.bot_manager.set_physics_process(false)
	if get("test_result").begins_with("PASS:") and game_instance.next_bomb_id == 0:
		set("test_result", "FAIL: No bomb exercised; survival result is inconclusive")
	var result: String = get("test_result")
	passed = 1 if result.begins_with("PASS:") else 0
	failed = 1 - passed
	results[get_script().resource_path] = "PASS" if passed else "FAIL: " + result
	await teardown()
	await teardown_suite()

func setup() -> void:
	pass

func execute() -> void:
	pass

func teardown() -> void:
	pass
