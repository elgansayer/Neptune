extends "res://tests/bot_test_suite.gd"

const KickTask = preload("res://ai/tasks/actions/bt_kick_bomb.gd")
var observed_actor
var bomb: ServerBomb

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(7, 6))
	bot_player.set_physics_process(false)
	bot_player.has_bomb_kicker = true
	game_instance.add_player(844, "BombOwner", BotTestHelpers.tile_to_world_center(Vector2i(8, 6)))
	var owner: ServerPlayer = game_instance.players[844]
	owner.set_physics_process(false)
	owner.bomb_range = 2
	var placed: Dictionary = game_instance.place_bomb(owner)
	if not placed.accepted: push_error("Kick fixture placement failed: " + str(placed))
	bomb = game_instance.bombs[placed.bomb_ids[0]]
	bomb.set_physics_process(false)
	owner.position = BotTestHelpers.tile_to_world_center(Vector2i(1, 1))
	game_instance.add_player(855, "KickTarget", BotTestHelpers.tile_to_world_center(Vector2i(12, 6)))
	game_instance.players[855].set_physics_process(false)
	_refresh()
	observed_actor = bot_controller.get_blackboard().get_var("player")

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()
	bot_manager.opponent_tracker.update_from_players(bot_manager.perception_world.players.values())

func _action():
	var board = bot_controller.get_blackboard()
	board.set_var("kick_target", Vector2i(12, 6))
	var task = KickTask.new()
	task.confirm_contact = true
	task.require_direct_threat = true
	task.initialize(observed_actor, board, get_tree().current_scene)
	return task

func test_confirming_kick_keeps_running_until_real_physics_contact() -> Variant:
	var action = _action()
	var status: int = action.execute(1.0 / 60.0)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "RUNNING")
		and bot_player.input_direction == Vector2.RIGHT and bomb.bomb_state == ServerBomb.BombState.PLANTED
		and not bot_controller.get_blackboard().get_var("kick_contact_confirmed", true),
		"Kick intent must survive the native tick without claiming contact or directly mutating the bomb")

func test_production_tree_aims_and_physically_kicks_before_completing_the_action() -> Variant:
	var board = bot_controller.get_blackboard()
	bot_controller.active = true
	bot_controller.restart()
	bot_controller.update(1.0 / 60.0)
	if bot_player.input_direction != Vector2.RIGHT or bomb.bomb_state != ServerBomb.BombState.PLANTED:
		return "Production tree failed to retain the kick command until physics"
	bot_player.set_physics_process(true)
	bomb.set_physics_process(true)
	var initial_position := bomb.position
	for frame in range(30):
		await get_tree().physics_frame
		await get_tree().process_frame
		game_instance.current_time_msec += 1000.0 / Engine.physics_ticks_per_second
		game_instance.simulation_tick += 1
		_refresh()
		bot_controller.update(1.0 / 60.0)
		if board.get_var("kick_contact_confirmed", false) and bomb.position.x > initial_position.x:
			break
	bot_player.set_physics_process(false)
	bomb.set_physics_process(false)
	return assert_true(bomb.bomb_state == ServerBomb.BombState.KICKED
		and bomb.kick_direction == Vector2.RIGHT and bomb.position.x > initial_position.x
		and board.get_var("kick_contact_confirmed", false),
		"The actual production policy and normal actor contact must move the real bomb and confirm its public state")

func test_kick_attempt_times_out_without_inventing_contact() -> Variant:
	var action = _action()
	if action.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "RUNNING"):
		return "Control kick did not begin"
	game_instance.current_time_msec += 801.0
	_refresh()
	return assert_true(action.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and bot_player.input_direction == Vector2.ZERO and bomb.bomb_state == ServerBomb.BombState.PLANTED,
		"A blocked contact must stop within its simulation-time budget")

func test_imminent_fuse_and_missing_ability_refuse_kick_intent() -> Variant:
	bomb.explosion_timer = bomb.fuse_lower_bound - 0.05
	_refresh()
	var action = _action()
	if action.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "A bomb too close to expiry was approached"
	bomb.explosion_timer = 0.0
	bot_player.has_bomb_kicker = false
	_refresh()
	action = _action()
	return assert_true(action.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and bomb.bomb_state == ServerBomb.BombState.PLANTED and bot_player.input_direction == Vector2.ZERO,
		"The policy must require the same actual ability as human contact")

func test_active_fire_in_the_kick_lane_is_not_treated_as_clear() -> Variant:
	game_instance.active_explosion_tiles["10,6"] = game_instance.get_simulation_time_msec() + 1000.0
	_refresh()
	var action = _action()
	return assert_true(action.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and bot_player.input_direction == Vector2.ZERO, "An observed burning kick lane could trigger an unsafe early blast")

func test_earlier_chain_deadline_refuses_contact_despite_the_nominal_long_fuse() -> Variant:
	var owner: ServerPlayer = game_instance.players[844]
	owner.max_bombs = 2
	owner.position = BotTestHelpers.tile_to_world_center(Vector2i(8, 8))
	var placed: Dictionary = game_instance.place_bomb(owner)
	if not placed.accepted: return "Early-chain control failed to place the second real bomb"
	var early: ServerBomb = game_instance.bombs[placed.bomb_ids[0]]
	early.set_physics_process(false)
	early.explosion_timer = early.fuse_lower_bound - 0.05
	owner.position = BotTestHelpers.tile_to_world_center(Vector2i(1, 1))
	_refresh()
	var action = _action()
	return assert_true(action.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and bomb.explosion_timer == 0.0 and bot_player.input_direction == Vector2.ZERO,
		"A shortened public chain deadline must override the candidate bomb's unelapsed nominal fuse")
