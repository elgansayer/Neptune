extends "res://tests/bot_test_suite.gd"

const FindPowerup = preload("res://ai/tasks/actions/bt_find_powerup.gd")
const MoveToCell = preload("res://ai/tasks/actions/bt_move_to_cell.gd")

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	game_instance.add_to_group("bot_test_game")

func teardown_test() -> void:
	for item in game_instance.powerups.values():
		if is_instance_valid(item): item.queue_free()
	game_instance.powerups.clear()
	await super()

func _actor(tile: Vector2i = Vector2i(3, 3)) -> Node:
	await spawn_bot_at(tile)
	bot_controller.active = false
	bot_player.set_physics_process(false)
	bot_manager.refresh_public_observations(true)
	return bot_controller.get_blackboard().get_var("player")

func _item(id: String, tile: Vector2i, type: int) -> ServerPowerUp:
	var item: ServerPowerUp = game_instance.ServerPowerUpScene.instantiate()
	item.powerup_id = id
	item.powerup_type = type
	item.position = BotTestHelpers.tile_to_world_center(tile)
	game_instance.powerups[id] = item
	game_instance.add_child(item)
	return item

func _selection(actor):
	bot_manager.refresh_perception()
	var task = FindPowerup.new()
	task.initialize(actor, bot_controller.get_blackboard(), get_tree().current_scene)
	return task

func test_native_collection_targets_the_actual_item_around_an_obstacle() -> Variant:
	var actor = await _actor()
	set_tile(4, 3, 1)
	_item("detour", Vector2i(5, 3), ServerPowerUp.PowerUpType.BOMB_INCREASE)
	var task = _selection(actor)
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and bot_controller.get_blackboard().get_var("target_cell") == Vector2i(5, 3), "Collection must route to the item instead of requesting a blocked adjacent tile")

func test_unreachable_high_value_item_does_not_starve_a_reachable_item() -> Variant:
	var actor = await _actor()
	for tile in [Vector2i(7, 6), Vector2i(9, 6), Vector2i(8, 5), Vector2i(8, 7)]:
		set_tile(tile.x, tile.y, 1)
	_item("sealed", Vector2i(8, 6), ServerPowerUp.PowerUpType.FULL_FIRE)
	_item("reachable", Vector2i(3, 5), ServerPowerUp.PowerUpType.SPEED_INCREASE)
	var task = _selection(actor)
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and bot_controller.get_blackboard().get_var("target_cell") == Vector2i(3, 5), "Unreachable loot must not lock the bot into repeated failed moves")

func test_item_utility_prices_the_detour_instead_of_straight_line_distance() -> Variant:
	var actor = await _actor()
	set_tile(4, 3, 1)
	_item("detour", Vector2i(5, 3), ServerPowerUp.PowerUpType.BOMB_INCREASE)
	_item("shorter_route", Vector2i(3, 6), ServerPowerUp.PowerUpType.BOMB_INCREASE)
	var task = _selection(actor)
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and bot_controller.get_blackboard().get_var("target_cell") == Vector2i(3, 6), "Equally valuable loot should use reachable route cost, not Manhattan displacement")

func test_collection_route_horizon_releases_an_objective_outside_its_budget() -> Variant:
	var actor = await _actor()
	set_tile(4, 3, 1)
	_item("detour", Vector2i(5, 3), ServerPowerUp.PowerUpType.BOMB_INCREASE)
	var task = _selection(actor)
	task.max_path_length = 3
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "FAILURE") and bot_controller.get_blackboard().get_var("target_cell") == null, "Collection must respect its bounded route horizon")

func test_only_negative_or_threatened_items_clear_the_stale_target() -> Variant:
	var actor = await _actor()
	_item("negative", Vector2i(3, 5), ServerPowerUp.PowerUpType.SKULL)
	_item("danger", Vector2i(8, 6), ServerPowerUp.PowerUpType.FULL_FIRE)
	var bomb = BotTestHelpers.place_bomb(Vector2i(9, 6), 3.0)
	bomb.set_physics_process(false)
	var board = bot_controller.get_blackboard()
	board.set_var("target_cell", Vector2i(8, 6))
	var task = _selection(actor)
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "FAILURE") and board.get_var("target_cell") == null, "Unsafe or harmful loot must fail and release an old collection target")

func test_native_item_selection_and_movement_collect_through_real_physics() -> Variant:
	var actor = await _actor()
	set_tile(4, 3, 1)
	var item := _item("physical", Vector2i(5, 3), ServerPowerUp.PowerUpType.BOMB_INCREASE)
	var capacity_before: int = bot_player.max_bombs
	var task = _selection(actor)
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "The native selection task could not select the real item"
	var move = MoveToCell.new()
	move.debug_logging = false
	move.initialize(actor, bot_controller.get_blackboard(), get_tree().current_scene)
	bot_player.set_physics_process(true)
	for frame in range(240):
		# This fixture freezes the authority process, so advance its public
		# simulation clock explicitly alongside actual player physics.
		game_instance.current_time_msec += 1000.0 / 60.0
		game_instance.simulation_tick += 1
		bot_manager.refresh_perception()
		move.execute(1.0 / 60.0)
		if item.collected:
			break
		await get_tree().physics_frame
		await get_tree().process_frame
	bot_player.set_input(0, 0)
	return assert_true(item.collected and bot_player.max_bombs == capacity_before + 1 and bot_player.position.distance_to(BotTestHelpers.tile_to_world_center(Vector2i(3, 3))) > GameConfig.TILE_SIZE, "Native bot commands must move the authority around the wall and collect the item through its real collision trigger")
