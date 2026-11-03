extends "res://tests/bot_test_suite.gd"

const DecisionWait = preload("res://ai/tasks/actions/bt_wait_for_decision.gd")
var running_status: int = ClassDB.class_get_integer_constant("BT", "RUNNING")
var success_status: int = ClassDB.class_get_integer_constant("BT", "SUCCESS")

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	game_instance.add_to_group("bot_test_game")

func _actor() -> Node:
	await spawn_bot_at(Vector2i(7, 6))
	bot_player.set_physics_process(false)
	bot_controller.active = true
	bot_manager.refresh_perception()
	return bot_controller.get_blackboard().get_var("player")

func _clock(value: float) -> void:
	game_instance.current_time_msec = value
	game_instance.invalidate_public_observation()
	bot_manager.refresh_public_observations(true)

func test_native_strategic_wait_uses_each_profile_reaction_and_simulation_clock() -> Variant:
	var actor = await _actor()
	var board = bot_controller.get_blackboard()
	for personality in bot_manager.PERSONALITY_CONFIGS:
		var delay: float = bot_manager.PERSONALITY_CONFIGS[personality].reaction_time_ms
		board.set_var("reaction_time_ms", delay)
		var task = DecisionWait.new()
		task.initialize(actor, board, get_tree().current_scene)
		_clock(1000.0)
		actor.set_input(1, 0)
		if task.execute(20.0) != running_status or actor.input_direction != Vector2.ZERO:
			return "%s acted before its configured strategic delay" % personality
		# Large callback deltas cannot advance a frozen authority clock.
		if task.execute(20.0) != running_status:
			return "Strategic delay used callback delta instead of simulation time"
		_clock(1000.0 + delay - 0.01)
		if task.execute(0.0001) != running_status:
			return "%s reacted before the exact simulation deadline" % personality
		_clock(1000.0 + delay)
		if task.execute(0.0001) != success_status:
			return "%s failed to become eligible at its simulation deadline" % personality
	return true

func test_next_goal_starts_a_new_wait_without_retiming_a_running_goal() -> Variant:
	var actor = await _actor()
	var board = bot_controller.get_blackboard()
	board.set_var("reaction_time_ms", 50.0)
	var task = DecisionWait.new()
	task.initialize(actor, board, get_tree().current_scene)
	_clock(2000.0)
	if task.execute(0.01) != running_status: return "Initial goal did not wait"
	_clock(2050.0)
	if task.execute(0.01) != success_status: return "Initial goal did not become eligible"
	if task.execute(0.01) != running_status or board.get_var("strategic_ready_at_msec") != 2100.0:
		return "A new intentional goal inherited an expired reaction deadline"
	_clock(2075.0)
	if task.execute(0.01) != running_status or board.get_var("strategic_ready_at_msec") != 2100.0:
		return "An ongoing wait moved its deadline on each motor callback"
	return true

func test_actual_policy_interrupts_a_running_strategic_wait_for_public_danger() -> Variant:
	var actor = await _actor()
	var board = bot_controller.get_blackboard()
	board.set_var("reaction_time_ms", 500.0)
	_clock(3000.0)
	bot_controller.restart()
	bot_controller.update(1.0 / 60.0)
	if actor.input_direction != Vector2.ZERO or board.get_var("strategic_ready_at_msec", 0.0) != 3500.0:
		return "The production tree did not enter its strategic wait"
	var bomb = BotTestHelpers.place_bomb(Vector2i(7, 6), 3.0)
	if not is_instance_valid(bomb): return "Public danger control did not create a real bomb"
	bomb.set_physics_process(false)
	_clock(3010.0)
	bot_manager.refresh_perception()
	bot_controller.update(1.0 / 60.0)
	return assert_true(board.get_var("in_danger", false)
		and board.get_var("escape_cell", null) != null and actor.input_direction != Vector2.ZERO,
		"The actual native policy must interrupt a lower-priority reaction wait in the same physics tick")

func test_running_execution_keeps_every_native_tick_after_the_initial_reaction() -> Variant:
	var actor = await _actor()
	var board = bot_controller.get_blackboard()
	board.set_var("reaction_time_ms", 100.0)
	actor.set_meta("fixture_bt_ticks", 0)
	var sequence = ClassDB.instantiate("BTSequence")
	sequence.add_child(DecisionWait.new())
	sequence.add_child(preload("res://tests/support/count_bot_ticks.gd").new())
	sequence.initialize(actor, board, get_tree().current_scene)
	_clock(4000.0)
	sequence.execute(1.0 / 60.0)
	if actor.get_meta("fixture_bt_ticks", 0) != 0: return "Execution started before reaction elapsed"
	_clock(4100.0)
	for tick in range(8):
		sequence.execute(1.0 / 60.0)
	return assert_true(actor.get_meta("fixture_bt_ticks", 0) == 8,
		"A running goal must keep all motor callbacks instead of waiting again every frame")
