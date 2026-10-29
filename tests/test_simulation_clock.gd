extends "res://tests/bot_test_suite.gd"

var actor: ServerPlayer

func make_game_instance() -> GameInstance:
	return preload("res://tests/support/clock_capture_game.gd").new()

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	game_instance.explosions.clear()
	await super()
	game_instance.add_to_group("bot_test_game")
	game_instance.set_meta("fixture_owner", self)
	await game_instance.add_player(-401, "ClockFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	actor = game_instance.players[-401]
	actor.set_physics_process(false)
	game_instance.current_time_msec = 0.0
	if game_instance.get("simulation_tick") != null:
		game_instance.set("simulation_tick", 0)

func _bomb() -> ServerBomb:
	var bomb: ServerBomb = BotTestHelpers.place_bomb(Vector2i(4, 4), 1.0)
	bomb.set_physics_process(false)
	return bomb

func test_clock_accumulates_physics_delta_and_counts_steps() -> Variant:
	for index in range(5):
		game_instance._physics_process(0.02)
	if not is_equal_approx(game_instance.current_time_msec, 100.0):
		return "Five 20ms simulation steps must total 100ms, independent of process uptime"
	return assert_eq(game_instance.get("simulation_tick"), 5, "Every authority physics step has one tick")

func test_flame_event_uses_the_authority_deadline_origin() -> Variant:
	game_instance.current_time_msec = 500.0
	game_instance._on_explosion_expanded(_bomb(), [Vector2i(2, 2)])
	return assert_eq(game_instance.active_explosion_tiles["2,2"], 500.0 + GameConfig.EXPLOSION_DURATION * 1000.0, "Flame expiry must share the simulation origin")

func test_wall_delay_does_not_expire_a_frozen_flame() -> Variant:
	game_instance.active_explosion_tiles["2,2"] = 20.0
	OS.delay_msec(40)
	game_instance._check_explosion_damage()
	if not game_instance.active_explosion_tiles.has("2,2"):
		return "Wall delay expired a flame without a simulation step"
	game_instance._physics_process(0.021)
	return assert_false(game_instance.active_explosion_tiles.has("2,2"), "Flame must expire once simulation crosses its deadline")

func test_zero_time_flame_is_a_real_threat() -> Variant:
	game_instance.active_explosion_tiles["2,2"] = 1000.0
	var predictor = game_instance.bot_manager.hazard_predictor
	predictor.refresh(0.0)
	if not predictor.is_tile_threatened(Vector2i(2, 2)) or predictor.is_tile_safe(Vector2i(2, 2), 0.0):
		return "Deadline zero is active fire, not a missing observation"
	return true

func test_mortal_danger_is_invariant_under_time_origin_shift() -> Variant:
	var bomb := _bomb()
	bomb.explosion_timer = 0.6
	var tile := Vector2i(4, 4)
	var predictor = game_instance.bot_manager.hazard_predictor
	predictor.refresh(0.0)
	var zero: bool = predictor.is_in_mortal_danger(tile, 0.0)
	predictor.refresh(100.0)
	var shifted: bool = predictor.is_in_mortal_danger(tile, 100.0)
	if not zero or shifted != zero:
		return "The same 0.4-second remaining fuse cannot become safer at a later clock origin"
	return true

func _temporal_task(path: String, last_plant_sec: float):
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("game_instance", game_instance)
	board.set_var("last_bomb_placed_time", last_plant_sec)
	var task = load(path).new()
	task.initialize(actor, board, get_tree().current_scene)
	return task

func test_native_plant_grace_and_mandatory_escape_use_simulation_time() -> Variant:
	var grace = _temporal_task("res://ai/tasks/conditions/bt_has_escape_grace_period.gd", 0.0)
	var escape = _temporal_task("res://ai/tasks/conditions/bt_must_escape_now.gd", 0.0)
	var failure: int = ClassDB.class_get_integer_constant("BT", "FAILURE")
	var success: int = ClassDB.class_get_integer_constant("BT", "SUCCESS")
	OS.delay_msec(30)
	if grace.execute(0.01) != failure or escape.execute(0.01) != success:
		return "Wall uptime bypassed a just-placed bomb's grace/escape windows"
	grace.abort()
	escape.abort()
	game_instance._physics_process(0.8)
	if grace.execute(0.01) != success or escape.execute(0.01) != success:
		return "Grace must end at 800ms while mandatory escape remains active"
	escape.abort()
	game_instance._physics_process(0.2)
	return assert_eq(escape.execute(0.01), failure, "Mandatory escape ends at 1000 simulation milliseconds")

func test_virus_expiry_and_immortality_share_authority_time() -> Variant:
	actor.apply_virus(ServerPlayer.VirusType.HASTY_FUSE)
	actor.set_immortal(true)
	if actor.virus_end_time != ServerPlayer.VIRUS_DURATION_MS or actor.immortal_end_time != ServerPlayer.IMMORTAL_DURATION_MS:
		return "Status expiry used process uptime instead of the room's zero origin"
	game_instance.match_active = true
	game_instance._physics_process(ServerPlayer.IMMORTAL_DURATION_MS / 1000.0)
	actor._process_immortality(0.0)
	if actor.is_immortal or actor.active_virus == ServerPlayer.VirusType.NONE:
		return "Immortality expiry changed the longer virus duration"
	game_instance._physics_process((ServerPlayer.VIRUS_DURATION_MS - ServerPlayer.IMMORTAL_DURATION_MS) / 1000.0)
	return assert_eq(actor.active_virus, ServerPlayer.VirusType.NONE, "Virus must end at the existing simulation duration")

func test_opponent_tracking_ignores_wall_pacing() -> Variant:
	var tracker = game_instance.bot_manager.opponent_tracker
	var results := []
	for delay_msec in [0, 40]:
		tracker.reset()
		for index in range(3):
			game_instance.current_time_msec = index * 100.0
			actor.position = Vector2(100 + index * 16, 100)
			OS.delay_msec(delay_msec)
			tracker.update_from_players([actor])
		var observation: Dictionary = tracker.get_opponent_by_id(actor.peer_id)
		results.append({"time": observation.time, "velocity": observation.velocity})
	if results[0] != results[1] or results[0].time != 0.2 or not results[0].velocity.is_equal_approx(Vector2(160, 0)):
		return "Identical observed motion acquired wall-dependent timestamps or velocity"
	return true

func test_real_native_callbacks_see_clock_before_decisions() -> Variant:
	await spawn_bot_at(Vector2i(7, 6))
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	var tree = ClassDB.instantiate("BehaviorTree")
	tree.root_task = preload("res://tests/support/record_bot_clock.gd").new()
	bot_controller.behavior_tree = tree
	bot_controller.restart()
	var observed_actor = bot_controller.get_blackboard().get_var("player")
	observed_actor.set_meta("clock_records", [])
	game_instance.current_time_msec = 0.0
	if game_instance.get("simulation_tick") != null:
		game_instance.set("simulation_tick", 0)
	game_instance.match_active = true
	var observed_bomb := _bomb()
	observed_bomb.set_physics_process(true)
	game_instance.set_physics_process(true)
	bot_manager.set_physics_process(true)
	for index in range(6):
		await get_tree().physics_frame
	await get_tree().process_frame
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	observed_bomb.set_physics_process(false)
	var records: Array = observed_actor.get_meta("clock_records")
	if records.size() < 5:
		return "Missing real native callback observations"
	for index in range(records.size()):
		var entry: Dictionary = records[index]
		if entry.tick != index + 1 or not is_equal_approx(entry.game_ms, (index + 1) * 1000.0 / Engine.physics_ticks_per_second) or not is_equal_approx(entry.board_sec * 1000.0, entry.game_ms):
			return "A native decision did not observe its authority's current physics tick"
		if not is_equal_approx(entry.bomb_elapsed * 1000.0, entry.game_ms) or not is_equal_approx(entry.bomb_deadline, 1000.0):
			return "Hazard publication drifted one physics step behind the live bomb"
	return true

func test_paused_tree_freezes_clock_bomb_and_native_grace() -> Variant:
	var previous_mode := process_mode
	process_mode = Node.PROCESS_MODE_ALWAYS
	game_instance.process_mode = Node.PROCESS_MODE_PAUSABLE
	game_instance.set_physics_process(true)
	var bomb := _bomb()
	bomb.set_physics_process(true)
	for index in range(3):
		await get_tree().physics_frame
	await get_tree().process_frame
	var grace = _temporal_task("res://ai/tasks/conditions/bt_has_escape_grace_period.gd", game_instance.current_time_msec / 1000.0)
	var before := {"time": game_instance.current_time_msec, "tick": game_instance.get("simulation_tick"), "fuse_elapsed": bomb.explosion_timer}
	get_tree().paused = true
	OS.delay_msec(40)
	for index in range(3):
		await get_tree().process_frame
	var status: int = grace.execute(0.0)
	var after := {"time": game_instance.current_time_msec, "tick": game_instance.get("simulation_tick"), "fuse_elapsed": bomb.explosion_timer}
	get_tree().paused = false
	game_instance.set_physics_process(false)
	bomb.set_physics_process(false)
	process_mode = previous_mode
	if before != after or status != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "Paused simulation advanced its clock, bomb or native grace window"
	return true

func test_public_clock_snapshot_uses_status_deadline_units() -> Variant:
	if not game_instance.has_method("get_clock_state"):
		return "No public authority clock snapshot"
	game_instance.current_time_msec = 500.0
	var before: Dictionary = game_instance.call("get_clock_state")
	game_instance._physics_process(0.02)
	var after: Dictionary = game_instance.call("get_clock_state")
	if before.server_time != 500.0 or after.server_time != 520.0 or after.simulation_tick != before.simulation_tick + 1:
		return "Public clock snapshot is stale, mutable or in the wrong units"
	return true

func test_repeated_physics_experiment_matches_with_wall_delays() -> Variant:
	var experiments := []
	for delay_msec in [0, 2]:
		game_instance.current_time_msec = 0.0
		if game_instance.get("simulation_tick") != null:
			game_instance.set("simulation_tick", 0)
		game_instance.match_active = true
		game_instance.match_time_remaining = 180.0
		game_instance.active_explosion_tiles.clear()
		game_instance.bot_manager.opponent_tracker.reset()
		actor.apply_virus(ServerPlayer.VirusType.HASTY_FUSE)
		actor.set_immortal(false)
		actor.set_immortal(true)
		var bomb := _bomb()
		game_instance._on_explosion_expanded(bomb, [Vector2i(2, 2)])
		var grace = _temporal_task("res://ai/tasks/conditions/bt_has_escape_grace_period.gd", 0.0)
		var states := []
		for index in range(40):
			OS.delay_msec(delay_msec)
			game_instance._physics_process(0.02)
			bomb._physics_process(0.02)
			game_instance.bot_manager._physics_process(0.02)
			actor._process_immortality(0.02)
			grace.abort()
			var status: int = grace.execute(0.02)
			var observation: Dictionary = game_instance.bot_manager.opponent_tracker.get_opponent_by_id(actor.peer_id)
			states.append({"tick": game_instance.get("simulation_tick"), "ms": game_instance.current_time_msec,
				"fuse_elapsed": bomb.explosion_timer, "flame_expiry": game_instance.active_explosion_tiles.get("2,2"),
				"virus_expiry": actor.virus_end_time, "immortal_expiry": actor.immortal_end_time, "grace": status,
				"opponent_time": observation.time, "opponent_velocity": observation.velocity,
				"threats": game_instance.ai_manager.threat_matrix.duplicate()})
		experiments.append(states)
		game_instance.bombs.erase(bomb.bomb_id)
		bomb.free()
	if experiments[0] != experiments[1]:
		return "Identical public physics experiment changed under wall pacing"
	print("SIMULATION_EXPERIMENT=" + JSON.stringify({"steps": 40, "delays_ms": [0, 2], "trace_sha256": JSON.stringify(experiments[0]).sha256_text()}))
	return true

func test_state_publication_follows_actual_actor_movement() -> Variant:
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(2, 8))
	var start_position := actor.position
	game_instance.match_active = true
	actor.set_input(1.0, 0.0)
	actor.add_child(preload("res://tests/support/observe_player_clock.gd").new())
	var publications: Array = game_instance.get("clock_publications")
	publications.clear()
	game_instance.last_sync_time = 0.0
	game_instance.match_active = true
	game_instance.set_physics_process(true)
	actor.set_physics_process(true)
	for index in range(7):
		await get_tree().physics_frame
	await get_tree().process_frame
	game_instance.set_physics_process(false)
	actor.set_physics_process(false)
	if actor.position.x <= start_position.x or publications.is_empty():
		return "Missing actual movement/publication observations"
	for snapshot: Dictionary in publications:
		if snapshot.time != snapshot.observed.time or snapshot.position != snapshot.observed.position:
			return "Published clock/tick described state before this tick's actor update"
	return true
