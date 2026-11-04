extends "res://tests/bot_test_suite.gd"

var actor: ServerPlayer
var board

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	await game_instance.add_player(-301, "TemporalFixture", BotTestHelpers.tile_to_world_center(Vector2i(3, 3)), true, "fixture")
	actor = game_instance.players[-301]
	actor.set_physics_process(false)
	game_instance.match_active = true
	board = ClassDB.instantiate("Blackboard")
	var values := {"player": actor, "game_instance": game_instance,
		"ai_manager": game_instance.ai_manager, "grid_sampler": bot_manager.grid_sampler,
		"hazard_predictor": bot_manager.hazard_predictor, "escape_cell": Vector2i(5, 3),
		"escape_route_found": true, "target_cell": null, "in_danger": true, "stuck_targets": {}, "personality_config": {}}
	for key in values:
		board.set_var(key, values[key])

func teardown_test() -> void:
	board = null
	await super()

func _block(tile: Vector2i) -> void:
	set_tile(tile.x, tile.y, 1)

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_public_observations(true)
	bot_manager.observed_ai_manager.refresh_threat_matrix(game_instance.get_simulation_time_msec())
	game_instance.ai_manager.refresh_threat_matrix(game_instance.get_simulation_time_msec())
	bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())

func _move_task():
	var move = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move.cell_var = &"escape_cell"
	move.debug_logging = false
	move.initialize(actor, board, get_tree().current_scene)
	return move

func test_native_move_selects_safe_detour_around_active_fire() -> Variant:
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 1000.0
	_refresh()
	var move = _move_task()
	var status: int = move.execute(1.0 / 60.0)
	if status != ClassDB.class_get_integer_constant("BT", "RUNNING"):
		return "Native escape task stopped despite an available safe detour"
	return assert_true(not move._cached_path.has(Vector2i(4, 3)) and move._cached_path.back() == Vector2i(5, 3) and actor.input_direction.x == 0.0 and actor.input_direction.y != 0.0, "Movement must start along the safe corridor instead of entering fire")

func _only_corridor() -> void:
	for y in range(default_map_height):
		for x in range(default_map_width):
			if Vector2i(x, y) not in [Vector2i(3, 3), Vector2i(4, 3), Vector2i(5, 3)]:
				set_tile(x, y, 1)

func test_grid_timed_route_rejects_fire_beyond_the_planning_horizon() -> Variant:
	_only_corridor()
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 1000000.0
	_refresh()
	var move = _move_task()
	return assert_eq(move.execute(1.0 / 60.0), ClassDB.class_get_integer_constant("BT", "FAILURE"), "No legal route exists within the finite planning horizon")

func test_only_burning_corridor_waits_and_then_crosses_with_real_physics() -> Variant:
	_only_corridor()
	await get_tree().physics_frame
	var start := actor.position
	var initial_time := game_instance.get_simulation_time_msec()
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 1000.0
	_refresh()
	var move = _move_task()
	actor.set_physics_process(true)
	var stayed_safe := true
	var crossed := false
	for frame in range(180):
		game_instance.current_time_msec = initial_time + frame * (1000.0 / 60.0)
		game_instance._check_explosion_damage()
		_refresh()
		move.execute(1.0 / 60.0)
		if frame <= 60 and (actor.position != start or actor.input_direction != Vector2.ZERO):
			stayed_safe = false
		if actor.is_dead:
			stayed_safe = false
		if actor.get_tile_position() == Vector2i(5, 3) and actor.position.distance_to(BotTestHelpers.tile_to_world_center(Vector2i(5, 3))) < 1.0:
			crossed = true
			break
		await get_tree().physics_frame
		await get_tree().process_frame
	actor.set_physics_process(false)
	return assert_true(stayed_safe and crossed, "Native input must wait without false stuck recovery, then cross the expired flame through actual collision physics")

func test_source_bomb_refuses_a_wait_that_would_kill_the_actor() -> Variant:
	_only_corridor()
	game_instance.place_bomb(actor)
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	bomb.set_physics_process(false)
	bomb.fuse_lower_bound = 0.3
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 1000.0
	_refresh()
	var move = _move_task()
	return assert_eq(move.execute(1.0 / 60.0), ClassDB.class_get_integer_constant("BT", "FAILURE"), "An active source deadline must block a wait whose corridor clears too late")

func test_timed_route_preserves_legal_own_bomb_departure() -> Variant:
	game_instance.place_bomb(actor)
	if game_instance.bombs.size() != 1:
		return "Actual authority did not place the fixture bomb"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	bomb.set_physics_process(false)
	_refresh()
	var duration := 1000.0 * GameConfig.TILE_SIZE / GameConfig.BASE_SPEED
	var path: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), Vector2i(4, 2), 8, actor, false, game_instance.get_simulation_time_msec(), duration)
	return assert_true(path.size() == 2 and path.back() == Vector2i(4, 2), "Temporal routing must permit leaving an own bomb while respecting actual blast deadlines")

func test_new_flame_invalidates_cached_route_before_next_move() -> Variant:
	_refresh()
	var move = _move_task()
	if move.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "RUNNING") or not move._cached_path.has(Vector2i(4, 3)):
		return "Control case did not commit to the direct route"
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 1000.0
	_refresh()
	if move.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "RUNNING"):
		return "Changed hazard lost the reachable objective instead of rerouting"
	return assert_true(not move._cached_path.has(Vector2i(4, 3)) and actor.input_direction.x == 0.0, "Cached commitment must replan before walking into a newly observed flame")

func test_escape_finder_can_wait_for_fire_without_outliving_source_bomb() -> Variant:
	_only_corridor()
	game_instance.place_bomb(actor)
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	bomb.set_physics_process(false)
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 500.0
	_refresh()
	board.set_var("escape_cell", null)
	board.set_var("escape_route_found", false)
	var find = preload("res://ai/tasks/actions/bt_find_escape_route.gd").new()
	find.target_cell_var = &"escape_cell"
	find.debug_logging = false
	find.initialize(actor, board, get_tree().current_scene)
	var status: int = find.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and board.get_var("escape_cell") == Vector2i(5, 3)
		and board.get_var("escape_route_found", false), "Waiting for a short flame then reaching permanent refuge must beat giving up on an otherwise escapable own bomb")

func test_new_player_obstacle_invalidates_the_cached_route_without_push_stalling() -> Variant:
	_refresh()
	var move = _move_task()
	if move.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "RUNNING"):
		return "Control route failed"
	var admitted: Dictionary = await game_instance.add_player(302, "BlockingHuman", BotTestHelpers.tile_to_world_center(Vector2i(4, 3)))
	if not admitted.accepted: return "Obstacle control admission failed"
	game_instance.players[302].set_physics_process(false)
	_refresh()
	var status: int = move.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "RUNNING")
		and not move._cached_path.has(Vector2i(4, 3)) and actor.input_direction.y != 0.0,
		"A visible player blocking an intermediate waypoint must trigger a safe alternate route immediately")
