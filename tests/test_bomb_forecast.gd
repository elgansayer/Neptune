extends "res://tests/bot_test_suite.gd"

const OBSERVED_NOW_MSEC := 10000.0

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

func _bomb(tile: Vector2i, fuse: float, radius: int = 2, frozen: bool = true) -> ServerBomb:
	var bomb: ServerBomb = BotTestHelpers.place_bomb(tile, fuse)
	bomb.explosion_range = radius
	bomb.set_physics_process(not frozen)
	return bomb

func _key(tile: Vector2i) -> String:
	return "%d,%d" % [tile.x, tile.y]

func test_actual_short_fuse_deadline_agrees_between_consumers() -> Variant:
	var bomb := _bomb(Vector2i(4, 4), 1.0)
	bomb.explosion_timer = 0.25
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	game_instance.bot_manager.hazard_predictor.refresh(OBSERVED_NOW_MSEC / 1000.0)
	var ai: float = game_instance.ai_manager.threat_matrix[_key(Vector2i(4, 4))]
	var hazard: float = game_instance.bot_manager.hazard_predictor._threat_matrix[_key(Vector2i(4, 4))] * 1000.0
	print("FUSE_FORECAST=" + JSON.stringify({"ai_ms": ai, "hazard_ms": hazard, "expected_ms": 10750.0}))
	if not is_equal_approx(ai, 10750.0) or not is_equal_approx(hazard, 10750.0):
		return "Both consumers must use the observed remaining 0.75 seconds"
	return true

func test_hypothetical_incoming_chain_reaches_new_arm() -> Variant:
	_bomb(Vector2i(4, 4), 0.25, 2)
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	var forecast := game_instance.ai_manager.simulate_threat_matrix(Vector2i(6, 4), 3, OBSERVED_NOW_MSEC)
	var deadline: float = forecast.get(_key(Vector2i(6, 7)), INF)
	print("HYPOTHETICAL_CHAIN=" + JSON.stringify({"deadline_ms": deadline, "expected_ms": 10250.0}))
	return assert_eq(deadline, 10250.0, "Incoming chain must shorten the hypothetical bomb's entire new arm")

func test_chain_reorders_early_middle_and_late_bombs() -> Variant:
	# Insertion and original fuse order differ from the chained detonation order.
	_bomb(Vector2i(8, 4), 2.0, 2)
	_bomb(Vector2i(6, 4), 10.0, 2)
	_bomb(Vector2i(4, 4), 1.0, 2)
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	game_instance.bot_manager.hazard_predictor.refresh(OBSERVED_NOW_MSEC / 1000.0)
	var key := _key(Vector2i(8, 6))
	var ai: float = game_instance.ai_manager.threat_matrix.get(key, INF)
	var hazard: float = game_instance.bot_manager.hazard_predictor._threat_matrix.get(key, INF) * 1000.0
	if not is_equal_approx(ai, 11000.0) or not is_equal_approx(hazard, 11000.0):
		return "Both consumers must propagate the early source through the late middle bomb"
	return true

func test_hard_wall_prevents_chain() -> Variant:
	_bomb(Vector2i(4, 4), 1.0, 3)
	_bomb(Vector2i(6, 4), 10.0, 2)
	set_tile(5, 4, 1)
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	return assert_eq(game_instance.ai_manager.threat_matrix.get(_key(Vector2i(6, 6)), INF), 20000.0, "Hard wall must prevent the early chain")

func test_soft_block_stops_normal_chain_and_is_threatened() -> Variant:
	_bomb(Vector2i(4, 4), 1.0, 3)
	_bomb(Vector2i(6, 4), 10.0, 2)
	set_tile(5, 4, 2)
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	var threats: Dictionary = game_instance.ai_manager.threat_matrix
	if threats.get(_key(Vector2i(5, 4)), INF) != 11000.0 or threats.get(_key(Vector2i(6, 6)), INF) != 20000.0:
		return "Normal blast must include the soft block and stop before the next bomb"
	return true

func test_forecast_does_not_change_live_bomb_or_map() -> Variant:
	var bomb := _bomb(Vector2i(4, 4), 1.0)
	bomb.explosion_timer = 0.25
	var before := {"map": game_instance.game_map.duplicate(true), "position": bomb.position, "fuse": bomb.fuse_time, "timer": bomb.explosion_timer, "exploded": bomb.has_exploded}
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	game_instance.ai_manager.simulate_threat_matrix(Vector2i(6, 4), 3, OBSERVED_NOW_MSEC)
	var after := {"map": game_instance.game_map.duplicate(true), "position": bomb.position, "fuse": bomb.fuse_time, "timer": bomb.explosion_timer, "exploded": bomb.has_exploded}
	return assert_eq(after, before, "Forecast mutated actual simulation state")

func test_native_plant_condition_uses_actor_short_fuse() -> Variant:
	var tile := Vector2i(7, 6)
	await game_instance.add_player(-101, "FuseFixture", BotTestHelpers.tile_to_world_center(tile), true, "fixture")
	var player: ServerPlayer = game_instance.players[-101]
	var blackboard = ClassDB.instantiate("Blackboard")
	var values := {"player": player, "ai_manager": game_instance.ai_manager, "grid_sampler": game_instance.bot_manager.grid_sampler, "bomb_safety_checker": game_instance.bot_manager.bomb_safety_checker, "target_cell": tile}
	for key in values:
		blackboard.set_var(key, values[key])
	var task = preload("res://ai/tasks/conditions/bt_can_safely_plant.gd").new()
	task.initialize(player, blackboard, get_tree().current_scene)
	var normal_status: int = task.execute(1.0 / 60.0)
	if normal_status != ClassDB.class_get_integer_constant("BT", "SUCCESS"):
		return "Control case: normal fuse should permit the available escape"
	task.abort()
	player.apply_virus(ServerPlayer.VirusType.HASTY_FUSE)
	var status: int = task.execute(1.0 / 60.0)
	print("SHORT_FUSE_PLANT=" + JSON.stringify({"fuse_sec": player.get_bomb_fuse_lower_bound(), "normal_status": normal_status, "short_status": status}))
	return assert_eq(status, ClassDB.class_get_integer_constant("BT", "FAILURE"), "Short fuse must not get normal-fuse escape approval")

func test_hypothetical_outgoing_chain_uses_requested_fuse_bound() -> Variant:
	_bomb(Vector2i(6, 4), 10.0, 3)
	var forecast := game_instance.ai_manager.simulate_threat_matrix(Vector2i(4, 4), 2, OBSERVED_NOW_MSEC, 0.5)
	return assert_eq(forecast.get(_key(Vector2i(6, 7)), INF), 10500.0, "Proposed short fuse must shorten connected live bombs")

func test_hypothetical_reads_fresh_observations_without_refresh_side_effects() -> Variant:
	game_instance.ai_manager.refresh_threat_matrix(OBSERVED_NOW_MSEC)
	_bomb(Vector2i(4, 4), 0.25, 2)
	var cached := game_instance.ai_manager.threat_matrix.duplicate()
	var forecast := game_instance.ai_manager.simulate_threat_matrix(Vector2i(6, 4), 3, OBSERVED_NOW_MSEC)
	if game_instance.ai_manager.threat_matrix != cached:
		return "What-if query mutated the current forecast cache"
	return assert_eq(forecast.get(_key(Vector2i(6, 7)), INF), 10250.0, "What-if query missed a newly observed bomb")

func test_long_fuse_planning_preserves_rng_and_private_sample() -> Variant:
	var tile := Vector2i(7, 6)
	await game_instance.add_player(-102, "LongFuseFixture", BotTestHelpers.tile_to_world_center(tile), true, "fixture")
	var player: ServerPlayer = game_instance.players[-102]
	player.apply_virus(ServerPlayer.VirusType.LEISURELY_FUSE)
	seed(12345)
	var expected_random := randf()
	seed(12345)
	if player.get_bomb_fuse_lower_bound() != 5.0 or randf() != expected_random:
		return "Planning changed the gameplay RNG or the public long-fuse bound"
	game_instance.match_active = true
	game_instance.place_bomb(player)
	if game_instance.bombs.size() != 1:
		return "Real long-fuse bomb was not placed"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	bomb.set_physics_process(false)
	if bomb.fuse_time < 5.0 or bomb.fuse_time > 6.0 or bomb.fuse_lower_bound != 5.0:
		return "Actual sampled fuse or public bound differs from actor rules"
	var public_state := bomb.get_state_minimal()
	if public_state.get("f") != 500 or public_state.has("fuse_time"):
		return "Public state must expose the bound, not the sampled long fuse"
	bomb.fuse_time = 5.01
	var early := game_instance.ai_manager.simulate_threat_matrix(Vector2i(3, 3), 1, OBSERVED_NOW_MSEC)
	bomb.fuse_time = 5.99
	var late := game_instance.ai_manager.simulate_threat_matrix(Vector2i(3, 3), 1, OBSERVED_NOW_MSEC)
	if early != late or early.get(_key(tile), INF) != 15000.0:
		return "Forecast learned the hidden sampled long-fuse duration"
	return true

func test_actual_short_fuse_chain_explodes_no_earlier_than_forecast() -> Variant:
	var source := _bomb(Vector2i(4, 4), 0.25, 2, false)
	var chained := _bomb(Vector2i(6, 4), 3.0, 2, false)
	game_instance.ai_manager.refresh_threat_matrix(0.0)
	var predicted_source: float = game_instance.ai_manager.threat_matrix[_key(Vector2i(4, 4))]
	var predicted_chain: float = game_instance.ai_manager.threat_matrix[_key(Vector2i(6, 4))]
	var start_tick := Engine.get_physics_frames()
	var explosions := {}
	source.exploded.connect(func(_bomb, _pattern): explosions["source"] = Engine.get_physics_frames() - start_tick)
	chained.exploded.connect(func(_bomb, _pattern): explosions["chained"] = Engine.get_physics_frames() - start_tick)
	game_instance.set_physics_process(true)
	for index in range(120):
		if explosions.size() == 2:
			break
		await get_tree().physics_frame
	if explosions.size() != 2:
		return "Did not observe both real explosions"
	var tick_ms := 1000.0 / Engine.physics_ticks_per_second
	var travel_ticks := 3 * ceili(ServerBomb.EXPLOSION_GROWTH_INTERVAL * Engine.physics_ticks_per_second) + 2
	print("ACTUAL_CHAIN=" + JSON.stringify({"predicted_source_ms": predicted_source, "predicted_chain_ms": predicted_chain, "observed_ticks": explosions, "travel_bound_ticks": travel_ticks}))
	if predicted_source > explosions.source * tick_ms or predicted_chain > explosions.chained * tick_ms:
		return "Forecast was later than an observed actual explosion"
	if explosions.source * tick_ms - predicted_source > tick_ms * 2 or explosions.chained * tick_ms - predicted_chain > tick_ms * travel_ticks:
		return "Forecast differs beyond explicit fuse/progressive-travel bounds"
	# Let both real explosions finish their progressive arms and delayed removal.
	# Freeing the fixture immediately would abandon ServerBomb's SceneTreeTimer.
	for index in range(Engine.physics_ticks_per_second * 2):
		if not is_instance_valid(source) and not is_instance_valid(chained):
			return true
		await get_tree().physics_frame
	return "Real bombs did not complete delayed removal within two seconds"
