extends "res://tests/bot_test_suite.gd"

const Farming = preload("res://ai/tasks/actions/bt_find_farming_spot.gd")
var observed_actor
var counter

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(7, 6))
	bot_player.set_physics_process(false)
	bot_player.bomb_range = 3
	counter = preload("res://tests/support/counting_bomb_safety.gd").new()
	counter.delegate = bot_manager.bomb_safety_checker
	counter.delegate.debug_logging = false
	bot_controller.get_blackboard().set_var("bomb_safety_checker", counter)
	_refresh()
	observed_actor = bot_controller.get_blackboard().get_var("player")

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()

func _task():
	var task = Farming.new()
	task.search_radius = 20
	task.max_search_expansions = 64
	task.max_safety_checks = 3
	task.initialize(observed_actor, bot_controller.get_blackboard(), get_tree().current_scene)
	return task

func _blocks() -> void:
	for cell in [Vector2i(9, 6), Vector2i(7, 4), Vector2i(4, 6)]:
		set_tile(cell.x, cell.y, 2)
	_refresh()

func test_real_farming_search_enforces_expansion_and_safety_budgets() -> Variant:
	_blocks()
	var task = _task()
	var status: int = task.execute(1.0 / 60.0)
	var board = bot_controller.get_blackboard()
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and counter.calls > 0 and counter.calls <= 3 and board.get_var("farming_search_expanded") <= 64
		and board.get_var("farming_safety_checks") == counter.calls
		and not task.broadcast_safety and not task.always_broadcast and not task.debug_logging,
		"Production farming must find a real safe objective within explicit work limits and quiet defaults")

func test_hurry_blocks_stop_farming_damage_projection() -> Variant:
	set_tile(8, 6, 3)
	set_tile(9, 6, 2)
	_refresh()
	var task = _task()
	return assert_eq(task._count_soft_blocks_in_range(Vector2i(7, 6), 3, bot_manager.grid_sampler), 0,
		"An indestructible hurry block must stop a farming blast before the soft block behind it")

func test_reusing_a_valid_goal_does_not_repeat_safety_scoring() -> Variant:
	_blocks()
	var task = _task()
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Control farming objective was not selected"
	var calls: int = counter.calls
	var board = bot_controller.get_blackboard()
	var target = board.get_var("target_cell")
	for tick in range(30):
		if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
			return "A valid cached farming objective was dropped"
	return assert_true(counter.calls == calls and board.get_var("farming_searches") == 1
		and board.get_var("target_cell") == target,
		"Stable objectives must reuse their scoring instead of scanning the arena on every callback")

func test_opt_in_diagnostics_republish_detached_cached_scores_without_rescanning() -> Variant:
	_blocks()
	var task = _task()
	task.broadcast_safety = true
	task.always_broadcast = true
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Diagnostic control could not select farming target"
	var board = bot_controller.get_blackboard()
	var expected: Dictionary = board.get_var("safety_debug_snapshot").duplicate(true)
	if expected.is_empty(): return "Opt-in scoring snapshot was absent"
	var calls: int = counter.calls
	board.set_var("safety_debug_snapshot", {"mutated": true})
	game_instance.current_time_msec += 300.0
	_refresh()
	task.execute(1.0 / 60.0)
	return assert_true(counter.calls == calls and board.get_var("safety_debug_snapshot") == expected,
		"Local visualization must reuse detached cached evaluations and add no safety searches")

func test_failed_search_is_cached_but_new_terrain_invalidates_it_immediately() -> Variant:
	var task = _task()
	var board = bot_controller.get_blackboard()
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "Empty centered arena control unexpectedly supplied an objective"
	task.execute(1.0 / 60.0)
	if board.get_var("farming_searches") != 1:
		return "Identical failed searches were repeated in the same authority interval"
	_blocks()
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and board.get_var("farming_searches") == 2 and counter.calls > 0,
		"A newly reachable destructible objective must bypass the negative-result cooldown")

func test_expired_failed_search_can_retry_and_zero_safety_budget_cannot_authorize_bombing() -> Variant:
	var task = _task()
	task.execute(1.0 / 60.0)
	game_instance.current_time_msec += 251.0
	_refresh()
	task.execute(1.0 / 60.0)
	if bot_controller.get_blackboard().get_var("farming_searches") != 2:
		return "A failed search never became eligible for retry"
	_blocks()
	task.max_safety_checks = 0
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and counter.calls == 0, "No safety budget must never become an implicit safe planting decision")
