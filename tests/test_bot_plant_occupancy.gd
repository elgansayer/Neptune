extends "res://tests/bot_test_suite.gd"

const MovementTiming = preload("res://shared/ai/movement_timing.gd")
const PlaceBomb = preload("res://ai/tasks/actions/bt_place_bomb.gd")
const SafeToAttack = preload("res://ai/tasks/conditions/bt_is_safe_to_attack.gd")
var actor
var checker

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	game_instance.add_to_group("bot_test_game")
	await spawn_bot_at(Vector2i(7, 6))
	bot_player.set_physics_process(false)
	bot_controller.active = false
	actor = bot_controller.get_blackboard().get_var("player")
	checker = bot_manager.bomb_safety_checker
	checker.safety_buffer_msec = 500.0
	checker.movement_delay_msec = 200.0
	var open := [Vector2i(7, 6), Vector2i(6, 6), Vector2i(8, 6),
		Vector2i(6, 5), Vector2i(8, 5), Vector2i(6, 4), Vector2i(8, 4)]
	for y in range(default_map_height):
		for x in range(default_map_width):
			set_tile(x, y, 0 if Vector2i(x, y) in open else 1)
	set_tile(7, 7, 2) # Real farming purpose, with two physical retreat lanes.
	_refresh()

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()

func _blocker(id: int, tile: Vector2i) -> bool:
	var receipt: Dictionary = game_instance.add_player(id, "PublicBlocker%d" % id, BotTestHelpers.tile_to_world_center(tile))
	if not receipt.accepted: return false
	game_instance.players[id].set_physics_process(false)
	_refresh()
	return true

func _check() -> Dictionary:
	return checker.check_plant_safety_detailed(Vector2i(7, 6), Vector2i(7, 6), 1,
		MovementTiming.tiles_per_second(actor), game_instance.current_time_msec, false, 3.0, actor)

func _place():
	var board = bot_controller.get_blackboard()
	board.set_var("target_cell", Vector2i(7, 6))
	board.set_var("tactical_plan", "NONE")
	board.set_var("personality", "COMPETITIVE")
	var task = PlaceBomb.new()
	task.initialize(actor, board, get_tree().current_scene)
	return task

func test_two_occupied_retreat_lanes_refuse_a_marginal_plant_and_one_free_lane_allows_it() -> Variant:
	if not _blocker(801, Vector2i(6, 6)) or not _blocker(802, Vector2i(8, 6)):
		return "Actual public blocker actors could not enter the corridor"
	var blocked := _check()
	if blocked.safe or blocked.margin_ms < 1500.0:
		return "Control must expose the old tempting marginal deadline while proving no refuge"
	if checker.can_safely_plant_bomb(Vector2i(7, 6), Vector2i(7, 6), 1,
			MovementTiming.tiles_per_second(actor), game_instance.current_time_msec, 3.0, actor):
		return "Boolean planting safety ignored both occupied exits"
	var task = _place()
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE") or not game_instance.bombs.is_empty():
		return "A still-in-blast marginal tile became an actual competitive bomb placement"
	game_instance.remove_player(802)
	_refresh()
	if not _check().safe: return "The same terrain with one free retreat lane must remain usable"
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and game_instance.bombs.size() == 1,
		"Removing one observed blocker must permit a real validated placement without ignoring the remaining opponent")

func test_valid_first_bomb_breakout_from_a_single_exit_still_succeeds() -> Variant:
	set_tile(8, 6, 1)
	_refresh()
	if not _check().safe: return "The unoccupied single-exit route has a real refuge beyond the blast"
	var task = _place()
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and game_instance.bombs.size() == 1,
		"A first breakout bomb remains legal when its actual retreat reaches a verified refuge")

func test_an_occupied_further_exit_is_not_a_free_refuge() -> Variant:
	set_tile(8, 6, 1)
	if not _blocker(803, Vector2i(6, 4)): return "Actual refuge blocker could not enter"
	return assert_true(not _check().safe,
		"Refuge viability must include observed bodies at its only continuing exit")

func test_finite_escape_margin_changes_with_public_speed_and_attack_threshold() -> Variant:
	var board = bot_controller.get_blackboard()
	board.set_var("in_danger", false)
	board.set_var("personality", "DEFENSIVE")
	board.set_var("was_safe_to_attack", false)
	var slow := _check()
	if not slow.safe or not is_finite(slow.margin_ms):
		return "A verified short retreat must expose a finite transit safety margin"
	var task = SafeToAttack.new()
	task.initialize(actor, board, get_tree().current_scene)
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "The strict attack threshold ignored the actual lower escape margin"
	bot_player.skate_count = 8
	_refresh()
	var fast := _check()
	board.set_var("was_safe_to_attack", false)
	return assert_true(fast.safe and fast.margin_ms > slow.margin_ms
		and task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS"),
		"Faster public movement should increase measured escape slack enough to meet the same strict threshold")

func test_stale_tactic_cannot_justify_farming_but_an_actual_covered_opponent_can() -> Variant:
	set_tile(7, 7, 1) # No blocks remain to farm.
	_refresh()
	var board = bot_controller.get_blackboard()
	var task = _place()
	board.set_var("tactical_plan", "SPACE_DENIAL")
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE") or not game_instance.bombs.is_empty():
		return "A stale attack label authorized a purposeless farming bomb"
	if not _blocker(804, Vector2i(8, 6)): return "Actual covered opponent could not enter"
	board.set_var("tactic_target_cell", Vector2i(7, 6))
	task.target_cell_var = &"tactic_target_cell"
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and game_instance.bombs.size() == 1,
		"A real covered opponent and a free retreat must still permit a tactical placement")

func test_hurry_block_hides_soft_blocks_from_placement_purpose() -> Variant:
	set_tile(7, 7, 3)
	set_tile(7, 8, 2)
	bot_player.bomb_range = 3
	_refresh()
	var task = _place()
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and game_instance.bombs.is_empty(),
		"A soft block behind an indestructible hurry block cannot justify a farming bomb")
