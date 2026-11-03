extends "res://tests/bot_test_suite.gd"

## Production timed routing and validated bot commands with a controlled authority
## clock. The motor is frozen until a legal departure is commanded; no teleport
## or timeout relaxation is used to turn an intentional wait into progress.
const MoveToCell = preload("res://ai/tasks/actions/bt_move_to_cell.gd")
var actor: Node
var board
var running_status: int = ClassDB.class_get_integer_constant("BT", "RUNNING")
var failure_status: int = ClassDB.class_get_integer_constant("BT", "FAILURE")


func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(3, 3))
	bot_controller.active = false
	bot_player.set_physics_process(false)
	board = bot_controller.get_blackboard()
	bot_manager.refresh_perception()
	actor = board.get_var("player")
	board.set_var("target_cell", Vector2i(5, 3))
	board.set_var("in_danger", false)
	board.set_var("stuck_targets", {})


func _clock(value: float) -> void:
	game_instance.current_time_msec = value
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()


func _move():
	var task = MoveToCell.new()
	task.initialize(actor, board, get_tree().current_scene)
	return task


func _only_corridor() -> void:
	for y in range(default_map_height):
		for x in range(default_map_width):
			if Vector2i(x, y) not in [Vector2i(3, 3), Vector2i(4, 3), Vector2i(5, 3)]:
				set_tile(x, y, 1)


func _wait_after_brief_idle(task) -> Variant:
	_clock(1000.0)
	if task.execute(1.0 / 60.0) != running_status or actor.input_direction != Vector2.RIGHT:
		return "The production task did not start its direct route"
	# One motor interval without displacement starts genuine stuck tracking.
	_clock(1100.0)
	if task.execute(1.0 / 60.0) != running_status:
		return "A brief idle interval was treated as an actual stall"
	# A new public flame forces the same route to wait for its safe interval.
	game_instance.active_explosion_tiles["4,3"] = 1500.0
	_clock(1200.0)
	if task.execute(1.0 / 60.0) != running_status or actor.input_direction != Vector2.ZERO:
		return "The production replan failed to wait for the observed flame"
	var deadline: float = board.get_var("route_wait_until_msec", 0.0)
	if deadline <= game_instance.get_simulation_time_msec():
		return "The timed planner did not expose a future legal departure"
	return deadline


func test_replanned_wait_resumes_without_a_false_stuck_penalty() -> Variant:
	_only_corridor()
	await get_tree().physics_frame
	var task = _move()
	var deadline = _wait_after_brief_idle(task)
	if not deadline is float: return deadline
	_clock(deadline)
	var status: int = task.execute(1.0 / 60.0)
	if status != running_status or actor.input_direction != Vector2.RIGHT or not board.get_var("stuck_targets").is_empty():
		return "A legal departure inherited the pre-wait idle interval as a stall"
	var start: Vector2 = bot_player.position
	bot_player.set_physics_process(true)
	await get_tree().physics_frame
	await get_tree().process_frame
	bot_player.set_physics_process(false)
	return assert_true(bot_player.position.x > start.x and bot_player.position.y == start.y,
		"The resumed validated command must move the actual authority motor")


func test_repeated_intentional_waits_do_not_count_as_stuck_time() -> Variant:
	_only_corridor()
	await get_tree().physics_frame
	var task = _move()
	var deadline = _wait_after_brief_idle(task)
	if not deadline is float: return deadline
	for value in [1250.0, 1400.0, deadline - 1.0]:
		_clock(value)
		if task.execute(10.0) != running_status or actor.input_direction != Vector2.ZERO:
			return "A scheduled wait moved or abandoned the safe route before departure"
	_clock(deadline)
	if task.execute(1.0 / 60.0) != running_status or actor.input_direction != Vector2.RIGHT or not board.get_var("stuck_targets").is_empty():
		return "Repeated intentional waits must end with a fresh movement stall window"
	# The frozen motor now represents an actual stall, which must still fail
	# at the original threshold measured from this new departure.
	_clock(deadline + 499.0)
	if task.execute(1.0 / 60.0) != running_status: return "The post-wait stall window was shortened"
	_clock(deadline + 500.0)
	return assert_true(task.execute(1.0 / 60.0) == failure_status and board.get_var("stuck_targets").has("5,3"),
		"A real post-wait stall must retain the unchanged 500 ms deadline")


func test_real_stall_still_fails_at_the_existing_half_second_deadline() -> Variant:
	_clock(1000.0)
	var task = _move()
	if task.execute(1.0 / 60.0) != running_status: return "The control route did not start"
	_clock(1100.0)
	if task.execute(1.0 / 60.0) != running_status: return "A genuine stall failed before tracking began"
	_clock(1599.0)
	if task.execute(1.0 / 60.0) != running_status: return "The existing 500 ms deadline was shortened"
	_clock(1600.0)
	return assert_true(task.execute(1.0 / 60.0) == failure_status
		and board.get_var("target_cell") == null and board.get_var("stuck_targets").has("5,3")
		and actor.input_direction == Vector2.ZERO,
		"Actual nonmovement must still fail and penalise its target at the unchanged 500 ms limit")
