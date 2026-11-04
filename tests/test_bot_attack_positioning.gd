extends "res://tests/bot_test_suite.gd"

const Planner = preload("res://shared/ai/decision/tactical_position_planner.gd")
const ExecuteTactic = preload("res://ai/tasks/actions/bt_execute_tactic.gd")
const Assessment = preload("res://ai/tasks/actions/bt_tactical_assessment.gd")

var observed_actor

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(3, 3))
	bot_controller.active = false
	bot_player.set_physics_process(false)
	bot_player.bomb_range = 3
	bot_manager.bomb_safety_checker.debug_logging = false
	var joined: Dictionary = game_instance.add_player(811, "AttackTarget", BotTestHelpers.tile_to_world_center(Vector2i(8, 3)))
	if not joined.accepted:
		push_error("Attack positioning fixture failed admission: " + str(joined))
	game_instance.players[811].set_physics_process(false)
	_refresh()
	observed_actor = bot_controller.get_blackboard().get_var("player")

func _refresh() -> void:
	bot_manager.refresh_perception()
	bot_manager.opponent_tracker.update_from_players(bot_manager.perception_world.players.values())

func _choose(max_steps: int = 24, max_expansions: int = 512, max_safety_checks: int = 8) -> Dictionary:
	_refresh()
	return Planner.choose(observed_actor, game_instance.players[811].get_tile_position(),
		bot_manager.grid_sampler, bot_manager.observed_ai_manager, bot_manager.bomb_safety_checker,
		game_instance.get_simulation_time_msec(), max_steps, max_expansions, max_safety_checks)

func _task():
	var task = ExecuteTactic.new()
	task.initialize(observed_actor, bot_controller.get_blackboard(), get_tree().current_scene)
	return task

func test_already_aligned_current_tile_is_a_valid_firing_position() -> Variant:
	game_instance.players[811].position = BotTestHelpers.tile_to_world_center(Vector2i(5, 3))
	var result := _choose()
	return assert_true(result.found and result.tile == Vector2i(3, 3) and result.steps == 0,
		"An already useful safe firing tile must not be discarded because its approach path is empty")

func test_native_chase_accepts_a_valid_custom_map_firing_tile_at_zero() -> Variant:
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i.ZERO)
	game_instance.players[811].position = BotTestHelpers.tile_to_world_center(Vector2i(2, 0))
	game_instance.invalidate_public_observation()
	_refresh()
	var board = bot_controller.get_blackboard()
	board.set_var("tactical_plan", "AGGRESSIVE_CHASE")
	var task = _task()
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and board.get_var("tactic_target_cell") == Vector2i.ZERO,
		"The planner's explicit invalid result must not reject a playable custom-map tile at the origin")

func test_native_attack_targets_a_reachable_firing_tile_beyond_a_long_detour() -> Variant:
	for y in range(10):
		set_tile(5, y, 1)
	_refresh()
	var board = bot_controller.get_blackboard()
	board.set_var("tactical_plan", "AGGRESSIVE_CHASE")
	var task = _task()
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Native chase could not find the open route around the wall"
	var target: Vector2i = board.get_var("tactic_target_cell")
	var route: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), target, 24, observed_actor, true)
	var detoured := false
	for cell in route:
		if cell.y >= 10: detoured = true
	return assert_true(target.x > 5 and detoured and route.size() > bot_manager.grid_sampler.get_manhattan_distance(Vector2i(3, 3), target),
		"Attack must commit to a real firing destination rather than oscillating between greedy adjacent flank tiles")

func test_unreachable_opponent_releases_attack_for_collection_or_farming() -> Variant:
	for y in range(default_map_height):
		set_tile(5, y, 1)
	_refresh()
	var board = bot_controller.get_blackboard()
	board.set_var("tactical_plan", "AGGRESSIVE_CHASE")
	board.set_var("tactic_target_cell", Vector2i(4, 3))
	var task = _task()
	var status: int = task.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "FAILURE") and board.get_var("tactic_target_cell") == null,
		"No reachable attack must fail and clear stale targets so the selector can farm or collect")

func test_native_attack_approaches_around_a_wall_and_places_a_real_threatening_bomb() -> Variant:
	for y in range(6):
		set_tile(5, y, 1)
	_refresh()
	var board = bot_controller.get_blackboard()
	board.set_var("tactical_plan", "AGGRESSIVE_CHASE")
	var task = _task()
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Native chase failed to select the physical approach objective"
	var target: Vector2i = board.get_var("tactic_target_cell")
	var move = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move.cell_var = &"tactic_target_cell"
	move.clear_on_success = false
	move.debug_logging = false
	move.initialize(observed_actor, board, get_tree().current_scene)
	bot_player.set_physics_process(true)
	var arrived := false
	for frame in range(420):
		# The fixture freezes GameInstance updates, so advance its authority
		# clock explicitly alongside each real motor physics callback. Timed
		# route departures must not be tested against a frozen timestamp.
		game_instance.current_time_msec += 1000.0 / Engine.physics_ticks_per_second
		game_instance.simulation_tick += 1
		game_instance.invalidate_public_observation()
		_refresh()
		var status: int = move.execute(1.0 / 60.0)
		if status == ClassDB.class_get_integer_constant("BT", "SUCCESS"):
			arrived = true
			break
		if status == ClassDB.class_get_integer_constant("BT", "FAILURE"):
			return "Native movement abandoned the reachable attack approach"
		await get_tree().physics_frame
		await get_tree().process_frame
	bot_player.set_input(0, 0)
	bot_player.set_physics_process(false)
	if not arrived or bot_player.get_tile_position() != target:
		return "The actual authority actor did not reach its planned firing tile"
	_refresh()
	var plant = preload("res://ai/tasks/actions/bt_place_bomb.gd").new()
	plant.target_cell_var = &"tactic_target_cell"
	plant.initialize(observed_actor, board, get_tree().current_scene)
	var planted: int = plant.execute(1.0 / 60.0)
	var blast: Array[Vector2i] = preload("res://shared/ai/perception/bomb_threat_forecast.gd").project(target, observed_actor.get_effective_bomb_range(), bot_manager.grid_sampler)
	return assert_true(planted == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and game_instance.bombs.size() == 1 and blast.has(game_instance.players[811].get_tile_position()),
		"Native tactic, movement and validated placement must create an actual bomb threatening the observed opponent")

func test_existing_fire_is_not_used_as_an_attack_approach() -> Variant:
	for y in range(default_map_height):
		if y != 3: set_tile(5, y, 1)
	game_instance.active_explosion_tiles["5,3"] = game_instance.get_simulation_time_msec() + 1000.0
	var result := _choose()
	return assert_true(not result.found, "Attack positioning must not route through the only burning passage")

func test_attack_search_and_safety_work_have_explicit_limits() -> Variant:
	var result := _choose(24, 1, 1)
	if result.expanded > 1 or result.safety_checks > 1 or not result.budget_exhausted:
		return "Expansion/safety budgets were not recorded and enforced"
	var zero := _choose(24, 512, 0)
	return assert_true(not zero.found and zero.expanded == 0 and zero.safety_checks == 0,
		"An invalid planning budget must fail without doing unbounded fallback work")

func test_safe_attack_position_is_deterministic_without_consuming_policy_rng() -> Variant:
	var before: Dictionary = bot_manager.get_bot_policy_snapshot(bot_player.peer_id)
	var first := _choose()
	var second := _choose()
	return assert_true(first == second and first.found and before == bot_manager.get_bot_policy_snapshot(bot_player.peer_id),
		"Equal public states must select the same firing tile without consuming random gameplay or policy state")

func test_tactic_lock_priorities_match_the_selected_attack_priorities() -> Variant:
	var assessment = Assessment.new()
	return assert_true(assessment._get_priority("AGGRESSIVE_CHASE") == 5
		and assessment._get_priority("PREDICTIVE_INTERCEPT") == 3
		and assessment._get_priority("KICK_SNIPE") == 13
		and assessment._get_priority("POWER_THROW") == 12,
		"Hysteresis must compare the priorities actually used by tactical selection")
