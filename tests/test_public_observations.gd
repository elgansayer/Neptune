extends "res://tests/bot_test_suite.gd"

func setup_test() -> void:
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	game_instance.add_to_group("bot_test_game")

func teardown_test() -> void:
	for item in game_instance.powerups.values():
		if is_instance_valid(item): item.queue_free()
	game_instance.powerups.clear()
	await super()

func test_active_native_blackboard_and_agent_are_observed_views() -> Variant:
	await spawn_bot_at(Vector2i(7, 6))
	bot_manager.set_physics_process(false)
	bot_player.set_physics_process(false)
	var board = bot_controller.get_blackboard()
	var native_agent = bot_controller.get_node_or_null(bot_controller.agent_node)
	if board.get_var("game_instance") == game_instance or board.get_var("player") == bot_player or native_agent in [bot_player, bot_manager, game_instance]:
		return "Active native policy still receives raw authority game/actor references"
	return true

func test_registered_public_snapshot_api_has_data_only_results() -> Variant:
	await game_instance.add_player(-701, "PublicFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	if not game_instance.has_method("get_public_observation"):
		return "No registered-viewer public observation API"
	var snapshot: Dictionary = game_instance.call("get_public_observation", -701)
	return assert_true(snapshot.get("schema") == 1 and snapshot.get("valid") == true and snapshot.get("players") is Dictionary, "Public snapshot contract is missing")

func test_movement_task_does_not_snap_authority_position() -> Variant:
	await game_instance.add_player(-701, "SnapFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	var actor: ServerPlayer = game_instance.players[-701]
	actor.set_physics_process(false)
	actor.position += Vector2(0.5, 0)
	var before := actor.position
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("game_instance", game_instance)
	board.set_var("grid_sampler", bot_manager.grid_sampler)
	board.set_var("hazard_predictor", bot_manager.hazard_predictor)
	board.set_var("target_cell", Vector2i(7, 6))
	board.set_var("in_danger", false)
	board.set_var("stuck_targets", {})
	var task = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	task.initialize(actor, board, get_tree().current_scene)
	var status: int = task.execute(0.02)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and actor.position == before, "A decision cannot teleport even a subpixel offset without physics")

func test_native_player_accepts_the_supported_observation_agent_binding() -> Variant:
	var agent := Node2D.new()
	agent.name = "ObservationAgentProbe"
	add_child(agent)
	var tree = ClassDB.instantiate("BehaviorTree")
	tree.root_task = preload("res://tests/support/count_bot_ticks.gd").new()
	var controller = ClassDB.instantiate("BTPlayer")
	controller.behavior_tree = tree
	controller.agent_node = NodePath("../ObservationAgentProbe")
	controller.set_scene_root_hint(agent)
	controller.update_mode = ClassDB.class_get_integer_constant("BTPlayer", "MANUAL")
	add_child(controller)
	controller.get_blackboard().set_var("player", agent)
	controller.active = true
	controller.update(0.02)
	var ticks: int = agent.get_meta("fixture_bt_ticks", 0)
	controller.active = false
	controller.free()
	agent.free()
	return assert_eq(ticks, 1, "Real native agent can be an observation node rather than an authority actor")

func _data_only(value: Variant) -> bool:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING: return true
		TYPE_FLOAT: return is_finite(value)
		TYPE_ARRAY:
			for entry in value:
				if not _data_only(entry): return false
			return true
		TYPE_DICTIONARY:
			for key in value:
				if not key is String or not _data_only(value[key]): return false
			return true
	return false

func _frozen_bot() -> Node:
	await spawn_bot_at(Vector2i(7, 6))
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	bot_player.set_physics_process(false)
	bot_manager.refresh_public_observations(true)
	return bot_controller.get_blackboard().get_var("player")

func _item(tile: Vector2i) -> ServerPowerUp:
	var item: ServerPowerUp = game_instance.ServerPowerUpScene.instantiate()
	item.powerup_id = "observed-item"
	item.position = BotTestHelpers.tile_to_world_center(tile)
	game_instance.powerups[item.powerup_id] = item
	game_instance.add_child(item)
	return item

func test_roles_share_copy_isolated_json_safe_visibility() -> Variant:
	var agent = await _frozen_bot()
	await game_instance.add_player(701, "HumanFixture", BotTestHelpers.tile_to_world_center(Vector2i(9, 6)), false, "fixture")
	game_instance.players[701].set_physics_process(false)
	var first: Dictionary = game_instance.get_public_observation(bot_player.peer_id)
	var second: Dictionary = game_instance.get_public_observation(701)
	first.erase("viewer_id")
	second.erase("viewer_id")
	if not _data_only(first) or first != second:
		return "Human/bot visibility differs or exports contain engine/private objects"
	var view = bot_controller.get_blackboard().get_var("game_instance")
	var original: Dictionary = view.public_snapshot()
	first.terrain[6][7] = 99
	first.players[str(bot_player.peer_id)].position[0] = -999
	var record_data: Dictionary = agent.public_data()
	record_data.position[0] = -777
	if view.public_snapshot() != original or agent.position != bot_player.position or game_instance.game_map[6][7] != 0:
		return "Mutation of exported nested data reached authority or another view"
	var refused: Dictionary = game_instance.get_public_observation(123456)
	return assert_true(not refused.valid and not refused.has("players"), "Unknown viewers receive no arena data")

func test_hidden_items_inputs_and_sampled_fuses_do_not_change_native_choices() -> Variant:
	var agent = await _frozen_bot()
	var peer_id: int = bot_player.peer_id
	await game_instance.add_player(701, "OpponentFixture", BotTestHelpers.tile_to_world_center(Vector2i(11, 9)), false, "fixture")
	var opponent = game_instance.players[701]
	opponent.set_physics_process(false)
	var bomb = BotTestHelpers.place_bomb(Vector2i(2, 2), 5.01)
	bomb.fuse_lower_bound = 5.0
	bomb.set_physics_process(false)
	set_tile(9, 7, 2)
	var item := _item(Vector2i(9, 7))
	var board = bot_controller.get_blackboard()
	var experiments := []
	var frames := []
	for private_variant in [0, 1]:
		bomb.fuse_time = 5.01 if private_variant == 0 else 5.99
		item.powerup_type = ServerPowerUp.PowerUpType.BOMB_INCREASE if private_variant == 0 else ServerPowerUp.PowerUpType.SKULL
		opponent.input_direction = Vector2.LEFT if private_variant == 0 else Vector2.UP
		opponent.initialize_input_buffer()
		opponent.input_buffer.push_input({"input_x": private_variant, "place_bomb": true})
		game_instance.hurry_spawn_index = private_variant * 7
		game_instance.set_meta("private_drop_rng", private_variant)
		seed(9100 + private_variant)
		var expected := randi()
		seed(9100 + private_variant)
		frames.append(game_instance.get_public_observation(peer_id))
		if randi() != expected: return "Observation capture consumed the gameplay RNG"
		bot_manager.refresh_public_observations(true)
		var rng = board.get_var("policy_rng")
		rng.seed = 424242
		var task = preload("res://ai/tasks/actions/bt_wait_ambush.gd").new()
		task.wait_time = 0.0
		task.reevaluate_interval = 1000.0
		task.prefer_center = false
		task.initialize(agent, board, get_tree().current_scene)
		var decisions := []
		for index in range(32):
			decisions.append([task.execute(0.02), agent.input_direction])
		experiments.append(decisions)
	if frames[0] != frames[1] or experiments[0] != experiments[1]:
		return "Private authority perturbation changed public data/native choices"
	var unique := {}
	for choice in experiments[0]: unique[choice[1]] = true
	if unique.size() < 4: return "Decision control failed to exercise directional choices"
	if not frames[0].powerups.is_empty() or agent.get("input_buffer") != null or agent.get("fuse_time") != null:
		return "Hidden pickup or private actor state leaked"
	bomb.fuse_lower_bound = 4.0
	return assert_true(game_instance.get_public_observation(peer_id) != frames[0], "Public fuse bound change must remain observable")

func test_exposed_item_changes_actual_native_item_selection() -> Variant:
	var agent = await _frozen_bot()
	set_tile(9, 6, 2)
	var item := _item(Vector2i(9, 6))
	var board = bot_controller.get_blackboard()
	var condition = preload("res://ai/tasks/conditions/bt_has_powerup_available.gd").new()
	condition.max_distance = 4.0
	condition.initialize(agent, board, get_tree().current_scene)
	bot_manager.refresh_public_observations(true)
	if condition.execute(0.02) != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "Covered item entered native policy"
	set_tile(9, 6, 0)
	bot_manager.refresh_public_observations(true)
	if condition.execute(0.02) != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Exposed reachable item was not selected"
	var selected = board.get_var("nearest_powerup", null)
	return assert_true(selected != item and selected.position == item.position and selected.powerup_type == item.powerup_type, "Native condition uses public item record")

func test_stale_command_binding_cannot_control_reused_peer_id() -> Variant:
	var agent = await _frozen_bot()
	var peer_id: int = bot_player.peer_id
	var port = preload("res://shared/observations/command_port.gd").new(game_instance, bot_player, game_instance.get_observation_source())
	game_instance.remove_player(peer_id)
	await game_instance.add_player(peer_id, "ReplacementFixture", BotTestHelpers.tile_to_world_center(Vector2i(8, 6)), false, "fixture")
	var replacement = game_instance.players[peer_id]
	replacement.set_physics_process(false)
	var outcome: Dictionary = port.invoke({"action": "move", "x": 1, "y": 0})
	return assert_true(not outcome.accepted and outcome.reason == "unknown_player" and replacement.input_direction == Vector2.ZERO and port.contacts().is_empty(), "Stale original binding cannot command a replacement")

func test_unknown_mechanic_stops_native_policy_explicitly() -> Variant:
	var agent = await _frozen_bot()
	agent.set_input(1, 0)
	game_instance.game_map[3][3] = 77
	bot_manager._physics_process(0.02)
	var frame: Dictionary = game_instance.get_public_observation(bot_player.peer_id)
	return assert_true(frame.valid and not frame.bot_supported and "terrain" in frame.unsupported and not bot_controller.active and bot_player.input_direction == Vector2.ZERO and not bot_manager.observation_error.is_empty(), "Unknown terrain cannot silently enter supported bot play")

func test_queries_distinguish_overlap_airborne_and_typed_occupancy() -> Variant:
	var agent = await _frozen_bot()
	var peer_id: int = bot_player.peer_id
	var bomb = BotTestHelpers.place_bomb(Vector2i(7, 6), 10.0, peer_id)
	bomb.set_physics_process(false)
	bomb.add_collision_exception_with(bot_player)
	var queries = preload("res://shared/observations/queries.gd")
	var frame: Dictionary = game_instance.get_public_observation(peer_id)
	var entries: Array = queries.at_cell(frame, Vector2i(7, 6), peer_id)
	var bombs := entries.filter(func(row): return row.kind == "bomb")
	if bombs.size() != 1 or bombs[0].blocking: return "Actual overlap exemption was ignored"
	bomb.remove_collision_exception_with(bot_player)
	frame = game_instance.get_public_observation(peer_id)
	bombs = queries.at_cell(frame, Vector2i(7, 6), peer_id).filter(func(row): return row.kind == "bomb")
	if bombs.size() != 1 or not bombs[0].blocking: return "Ordinary bomb is not blocking"
	bomb.bomb_state = ServerBomb.BombState.THROWN
	frame = game_instance.get_public_observation(peer_id)
	entries = queries.at_cell(frame, Vector2i(7, 6), peer_id)
	bombs = entries.filter(func(row): return row.kind == "bomb")
	var airborne := entries.filter(func(row): return row.kind == "bomb_projectile")
	return assert_true(not bombs[0].blocking and airborne.size() == 1 and not airborne[0].blocking and queries.tile_of([-0.01, 16.0], 16) == Vector2i(-1, 1) and queries.terrain_at(frame, Vector2i(-1, 0)) == 1, "Typed air-bomb and negative tile-edge query contract")

func test_twelve_actor_native_observation_and_decision_timings() -> Variant:
	for index in range(12):
		await spawn_bot_at(Vector2i(1 + index % 6 * 2, 2 + index / 6 * 6))
		bot_player.set_physics_process(false)
	bot_manager.set_physics_process(false)
	var samples := []
	var capture := []
	for index in range(20):
		var started := Time.get_ticks_usec()
		bot_manager._physics_process(1.0 / 60.0)
		samples.append(Time.get_ticks_usec() - started)
		capture.append(bot_manager.observation_source.last_capture_usec)
	samples.sort()
	capture.sort()
	print("PUBLIC_OBSERVATION_TIMING=" + JSON.stringify({"actors": 12, "samples": samples.size(), "decision_usec_p50": samples[10], "decision_usec_p95": samples[18], "decision_usec_max": samples[-1], "capture_usec_p95": capture[18], "physics_frozen": true}))
	return assert_true(bot_manager.observation_error.is_empty() and samples.size() == 20 and samples[0] > 0, "Measured actual native tree updates, not a capacity guarantee")

func test_native_throw_faces_via_physics_before_validated_throw() -> Variant:
	var agent = await _frozen_bot()
	bot_player.has_power_glove = true
	var placement: Dictionary = bot_player.request_bomb_placement()
	if not placement.accepted: return "Throw fixture could not place a real bomb"
	var bomb = game_instance.bombs[placement.bomb_ids[0]]
	bomb.set_physics_process(false)
	if not bot_player.try_pickup_bomb(bomb): return "Throw fixture could not carry a real bomb"
	bot_player.last_move_direction = Vector2.DOWN
	bot_manager.refresh_public_observations(true)
	var board = bot_controller.get_blackboard()
	board.set_var("tactical_plan", "POWER_THROW")
	board.set_var("throw_direction", Vector2.RIGHT)
	var task = preload("res://ai/tasks/actions/bt_throw_bomb.gd").new()
	task.initialize(agent, board, get_tree().current_scene)
	var running: int = ClassDB.class_get_integer_constant("BT", "RUNNING")
	if task.execute(0.02) != running or task.execute(0.02) != running:
		return "Native throw did not wait while requesting facing intent"
	if bot_player.last_move_direction != Vector2.DOWN or not bot_player.is_carrying_bomb() or bot_player.input_direction != Vector2.RIGHT:
		return "Native throw directly changed facing or skipped movement intent"
	bot_player._physics_process(1.0 / 60.0)
	bot_manager.refresh_public_observations(true)
	if bot_player.last_move_direction != Vector2.RIGHT: return "Actual player physics did not apply requested facing"
	var status: int = task.execute(0.02)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and bomb.bomb_state == ServerBomb.BombState.THROWN and bomb.throw_direction == Vector2.RIGHT and bot_player.input_direction == Vector2.ZERO, "Native task issues validated ordinary throw after physics facing")
