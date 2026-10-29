extends "res://tests/bot_test_suite.gd"

var actor: ServerPlayer
var board
var task

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	game_instance.add_to_group("bot_test_game")
	game_instance.set_meta("fixture_owner", self)
	await game_instance.add_player(-201, "RefugeFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	actor = game_instance.players[-201]
	actor.set_physics_process(false)
	board = ClassDB.instantiate("Blackboard")
	var values := {"player": actor, "game_instance": game_instance,
		"ai_manager": game_instance.ai_manager, "grid_sampler": game_instance.bot_manager.grid_sampler,
		"hazard_predictor": game_instance.bot_manager.hazard_predictor,
		"escape_cell": null, "escape_route_found": false, "personality_config": {},
		"target_cell": null, "in_danger": true, "stuck_targets": {}}
	for key in values:
		board.set_var(key, values[key])
	task = preload("res://ai/tasks/actions/bt_find_escape_route.gd").new()
	task.target_cell_var = &"escape_cell"
	task.debug_logging = false
	task.initialize(actor, board, get_tree().current_scene)

func teardown_test() -> void:
	task = null
	board = null
	await super()

func _observe_bomb() -> void:
	var bomb = BotTestHelpers.place_bomb(Vector2i(7, 6), 3.0)
	bomb.set_physics_process(false)
	game_instance.ai_manager.refresh_threat_matrix(game_instance.get_simulation_time_msec())
	game_instance.bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())

func _execute() -> int:
	task.abort()
	return task.execute(1.0 / 60.0)

func _success() -> int:
	return ClassDB.class_get_integer_constant("BT", "SUCCESS")

func test_open_refuge_moves_beyond_nearest_flame_corner() -> Variant:
	_observe_bomb()
	if _execute() != _success():
		return "Native escape task failed in open control"
	var target: Vector2i = board.get_var("escape_cell")
	var distance := absi(target.x - 7) + absi(target.y - 6)
	print("REFUGE_OPEN=" + JSON.stringify({"target": str(target), "distance": distance}))
	return assert_true(distance > 2, "Open refuge remained on the closest flame corner")

func test_tight_safe_refuge_is_retained_without_extension() -> Variant:
	_observe_bomb()
	# All other cells are walls; the only refuge is at the end of this L corridor.
	for y in range(default_map_height):
		for x in range(default_map_width):
			if Vector2i(x, y) not in [Vector2i(7, 6), Vector2i(6, 6), Vector2i(6, 5)]:
				set_tile(x, y, 1)
	game_instance.ai_manager.refresh_threat_matrix(game_instance.get_simulation_time_msec())
	game_instance.bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())
	if _execute() != _success():
		return "A tight safe escape was incorrectly rejected"
	return assert_eq(board.get_var("escape_cell"), Vector2i(6, 5), "Must keep the only safe refuge")

func test_existing_commitment_rechecks_real_tile_path() -> Variant:
	_observe_bomb()
	board.set_var("escape_cell", Vector2i(6, 5))
	board.set_var("escape_route_found", true)
	if _execute() != _success():
		return "Existing commitment failed to validate the actual GridSampler path"
	return true

func test_repeated_decisions_stabilise_and_do_not_oscillate() -> Variant:
	_observe_bomb()
	var choices: Array[Vector2i] = []
	for index in range(12):
		if _execute() != _success():
			return "Repeated native decision lost a valid refuge"
		choices.append(board.get_var("escape_cell"))
	for index in range(4, choices.size()):
		if choices[index] != choices[3]:
			return "Safe commitment kept changing after bounded clearance improvements"
	return true

func test_extension_never_targets_a_live_bomb() -> Variant:
	_observe_bomb()
	var blocker = BotTestHelpers.place_bomb(Vector2i(5, 5), 3.0)
	blocker.set_physics_process(false)
	# An omitted observation must not hide a directly observed physical obstacle.
	board.set_var("escape_cell", Vector2i(6, 5))
	board.set_var("escape_route_found", true)
	if _execute() != _success():
		return "Could not retain or improve the bomb-blocked refuge"
	return assert_true(board.get_var("escape_cell") != Vector2i(5, 5), "Refuge extension targets an occupied bomb cell")

func _move_task():
	var move = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move.cell_var = &"escape_cell"
	move.debug_logging = false
	move.initialize(actor, board, get_tree().current_scene)
	return move

func test_escape_movement_rejects_a_waypoint_already_on_fire() -> Variant:
	board.set_var("escape_cell", Vector2i(5, 6))
	board.set_var("escape_route_found", true)
	game_instance.active_explosion_tiles["6,6"] = game_instance.get_simulation_time_msec() + 1000.0
	game_instance.bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())
	var move = _move_task()
	var status: int = move.execute(1.0 / 60.0)
	print("ACTIVE_FLAME_MOVE=" + JSON.stringify({"status": status, "input": str(actor.input_direction)}))
	if status != ClassDB.class_get_integer_constant("BT", "FAILURE") or actor.input_direction != Vector2.ZERO:
		return "Escape movement must stop before an already-burning waypoint"
	return assert_false(board.get_var("escape_route_found"), "Unsafe commitment must be released for replanning")

func test_escape_movement_allows_a_future_blast_with_time_to_cross() -> Variant:
	_observe_bomb()
	board.set_var("escape_cell", Vector2i(6, 5))
	board.set_var("escape_route_found", true)
	var move = _move_task()
	var status: int = move.execute(1.0 / 60.0)
	if status != ClassDB.class_get_integer_constant("BT", "RUNNING") or actor.input_direction == Vector2.ZERO:
		return "Future blast control: enough time remains to leave through the threatened waypoint"
	return true

func test_escape_movement_rejects_a_blast_before_waypoint_arrival() -> Variant:
	_observe_bomb()
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	bomb.explosion_timer = 2.9
	game_instance.bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())
	board.set_var("escape_cell", Vector2i(6, 5))
	board.set_var("escape_route_found", true)
	var move = _move_task()
	return assert_eq(move.execute(1.0 / 60.0), ClassDB.class_get_integer_constant("BT", "FAILURE"), "Escape waypoint becomes lethal before estimated arrival")

func test_centering_cannot_bypass_active_target_check() -> Variant:
	var target := Vector2i(6, 5)
	actor.position = BotTestHelpers.tile_to_world_center(target) + Vector2(0, 3)
	board.set_var("escape_cell", target)
	board.set_var("escape_route_found", true)
	game_instance.active_explosion_tiles["6,5"] = game_instance.get_simulation_time_msec() + 1000.0
	game_instance.bot_manager.hazard_predictor.refresh(game_instance.get_simulation_time_sec())
	var move = _move_task()
	return assert_eq(move.execute(1.0 / 60.0), ClassDB.class_get_integer_constant("BT", "FAILURE"), "Already inside target: centering must not bypass the flame guard")
