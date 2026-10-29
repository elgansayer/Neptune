extends "res://tests/support/player_command_fixture.gd"

func test_native_kick_uses_a_valid_accepted_movement_command() -> Variant:
	var bomb := own_bomb(Vector2i(8, 6))
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(7, 6))
	actor.has_bomb_kicker = true
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("game_instance", game_instance)
	board.set_var("grid_sampler", bot_manager.grid_sampler)
	board.set_var("kick_target", Vector2i(12, 6))
	var task = preload("res://ai/tasks/actions/bt_kick_bomb.gd").new()
	task.initialize(actor, board, get_tree().current_scene)
	var status: int = task.execute(0.02)
	if status != ClassDB.class_get_integer_constant("BT", "SUCCESS") or actor.input_direction != Vector2.RIGHT:
		return "Real native kick branch failed to issue the ordinary rightward move"
	return assert_true(bomb.bomb_state == ServerBomb.BombState.PLANTED and board.get_var("kick_direction") == Vector2.RIGHT, "Task must request movement rather than mutate bomb state directly")

func test_actual_contact_kick_requires_the_same_ability_as_human_movement() -> Variant:
	var bomb := own_bomb(Vector2i(8, 6))
	# Clear the real owner-overlap exception before approaching the bomb again.
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(6, 6))
	actor.has_bomb_kicker = false
	actor.set_input(-1, 0)
	actor.set_physics_process(true)
	for step in range(2):
		await get_tree().physics_frame
	await get_tree().process_frame
	if actor.collision_exceptions.has(bomb):
		return "Fixture did not clear its production owner-overlap exception"
	actor.set_input(1, 0)
	for step in range(24):
		await get_tree().physics_frame
	await get_tree().process_frame
	actor.set_physics_process(false)
	if bomb.bomb_state != ServerBomb.BombState.PLANTED:
		return "Actor without kicker changed the real bomb to KICKED"
	actor.has_bomb_kicker = true
	actor.set_physics_process(true)
	for step in range(12):
		await get_tree().physics_frame
	await get_tree().process_frame
	actor.set_physics_process(false)
	return assert_true(bomb.bomb_state == ServerBomb.BombState.KICKED and bomb.kick_direction == Vector2.RIGHT, "Ordinary validated movement and actual physics contact must kick after acquiring the same ability")

func test_native_kick_rejection_does_not_fabricate_an_attempt() -> Variant:
	own_bomb(Vector2i(8, 6))
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(7, 6))
	actor.has_bomb_kicker = true
	game_instance.match_active = false
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("game_instance", game_instance)
	board.set_var("grid_sampler", bot_manager.grid_sampler)
	board.set_var("kick_target", Vector2i(12, 6))
	var task = preload("res://ai/tasks/actions/bt_kick_bomb.gd").new()
	task.initialize(actor, board, get_tree().current_scene)
	return assert_true(task.execute(0.02) == ClassDB.class_get_integer_constant("BT", "FAILURE") and actor.input_direction == Vector2.ZERO and not board.has_var("last_kick_attempt"), "Rejected native movement must not report a successful kick attempt")
