extends "res://tests/bot_test_suite.gd"

const Plan = preload("res://shared/ai/planning/throw_plan.gd")
const Trajectory = preload("res://shared/throw_trajectory.gd")
const TARGET_PEER := 971
var observed_actor
var original_dimensions: Vector2i

func make_game_instance() -> GameInstance:
	return preload("res://tests/support/throw_command_game.gd").new()

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	original_dimensions = Vector2i(GameConfig.map_width, GameConfig.map_height)
	GameConfig.map_width = default_map_width
	GameConfig.map_height = default_map_height
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(3, 3))
	bot_player.set_physics_process(false)
	# Acquire the ordinary item through its actual body-entered pickup path.
	game_instance.spawn_powerup_of_type(Vector2i(3, 3), ServerPowerUp.PowerUpType.POWER_GLOVE)
	await _frames(4)
	if not bot_player.has_power_glove: push_error("Glove fixture did not collect the real item")
	game_instance.add_player(TARGET_PEER, "ThrowTarget", BotTestHelpers.tile_to_world_center(Vector2i(6, 3)))
	game_instance.players[TARGET_PEER].set_physics_process(false)
	_refresh()
	observed_actor = bot_controller.get_blackboard().get_var("player")
	game_instance.command_trace.clear()

func teardown_test() -> void:
	for actor in game_instance.players.values(): actor.set_physics_process(false)
	for bomb in game_instance.bombs.values(): bomb.set_physics_process(false)
	GameConfig.map_width = original_dimensions.x
	GameConfig.map_height = original_dimensions.y
	await super()

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()
	bot_manager.opponent_tracker.update_from_players(bot_manager.perception_world.players.values())

func _frames(count: int, policy: bool = false) -> void:
	for frame in range(count):
		game_instance.current_time_msec += 1000.0 / Engine.physics_ticks_per_second
		game_instance.simulation_tick += 1
		_refresh()
		if policy: bot_controller.update(1.0 / Engine.physics_ticks_per_second)
		await get_tree().physics_frame
		await get_tree().process_frame
	_refresh()

func _start_policy() -> void:
	bot_player.set_physics_process(true)
	bot_controller.active = true
	bot_controller.restart()

func _until_thrown(frames: int = 90) -> ServerBomb:
	_start_policy()
	for frame in range(frames):
		await _frames(1, true)
		for bomb in game_instance.bombs.values():
			if str(bomb.owner_id) == str(bot_player.peer_id) and bomb.bomb_state == ServerBomb.BombState.THROWN:
				return bomb
	return null

func _own_commands(action: String, accepted: bool = true) -> Array:
	return game_instance.command_trace.filter(func(item: Dictionary) -> bool:
		return item.peer_id == bot_player.peer_id and item.action == action and item.accepted == accepted)

func test_production_policy_faces_then_places_picks_up_and_throws_in_one_validated_update() -> Variant:
	var started: Vector2 = bot_player.position
	var bomb := await _until_thrown()
	if bomb == null: return "Actual production tree never completed POWER_THROW"
	var placed := _own_commands("place_bomb")
	var picked := _own_commands("pickup_bomb")
	var thrown := _own_commands("throw_bomb")
	return assert_true(placed.size() == 1 and picked.size() == 1 and thrown.size() == 1
		and placed[0].tick == picked[0].tick and picked[0].tick == thrown[0].tick
		and placed[0].facing == Vector2.RIGHT and placed[0].position.distance_to(started) > 0.0
		and placed[0].position.distance_to(started) <= 2.0
		and bomb.throw_direction == Vector2.RIGHT and not bot_player.is_carrying_bomb()
		and bot_player.max_bombs == 1 and bot_player.bomb_range == 1 and bot_player.skate_count == 0
		and bomb.fuse_time == Constants.BOMB_TIMER,
		"The human command boundary and actual facing physics must supply the complete normal-inventory throw")

func test_actual_normal_throw_lands_two_tiles_away_using_the_shared_waypoints() -> Variant:
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(6, 3), Vector2.RIGHT)
	if not plan.get("supported", false): return "Normal two-tile preview was refused"
	var bomb := await _until_thrown()
	if bomb == null or bomb.bounce_waypoints != plan.waypoints: return "Authority and preview waypoints diverged"
	for frame in range(80):
		if bomb.bomb_state == ServerBomb.BombState.PLANTED: break
		await _frames(1)
	return assert_true(bomb.get_tile_position() == Vector2i(5, 3)
		and bomb.bomb_state == ServerBomb.BombState.PLANTED and not bomb.has_exploded,
		"Normal native flight must land at its actual two-tile destination")

func test_obstacle_bounces_share_the_authority_forward_waypoints() -> Variant:
	set_tile(5, 3, 1)
	_refresh()
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(6, 3), Vector2.RIGHT)
	if not plan.get("supported", false): return "A supported forward-bounce attack was refused"
	var bomb := await _until_thrown()
	if bomb == null: return "Production policy did not execute the obstacle throw"
	return assert_true(bomb.bounce_waypoints == plan.waypoints and bomb.bounce_waypoints.size() == 3
		and bomb.bounce_waypoints.back() == BotTestHelpers.tile_to_world_center(Vector2i(7, 3)),
		"A wall and occupied nominal landing must use the same forward-bounce rule as the authority")

func test_first_wrap_flight_reports_the_actual_interpolated_interior_chain_cells() -> Variant:
	# A single initial wrapped waypoint is interpolated by current native
	# physics. It is not the instant teleport used by later wrap segments.
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i(default_map_width - 2, 3))
	game_instance.players[TARGET_PEER].position = BotTestHelpers.tile_to_world_center(Vector2i(1, 3))
	_refresh()
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(1, 3), Vector2.RIGHT)
	if not plan.get("supported", false): return "Supported first-wrap preview was refused"
	var interior: Array = [7, 3]
	if not plan.flight.trajectory_cells.has(interior): return "Wrapped first arc omitted its actual interior chain-contact cells"
	var bomb := await _until_thrown()
	if bomb == null: return "Production policy did not execute the wrap throw"
	if not bomb.get_public_flight().trajectory_cells.has(interior): return "Authority public flight omitted first-wrap interior"
	for frame in range(80):
		if bomb.bomb_state == ServerBomb.BombState.PLANTED: break
		await _frames(1)
	return assert_eq(bomb.get_tile_position(), Vector2i(0, 3), "Native initial-wrap flight must preserve the current landing rule")

func test_visible_fire_on_the_flight_corridor_refuses_the_throw_without_placing() -> Variant:
	game_instance.active_explosion_tiles["4,3"] = game_instance.get_simulation_time_msec() + 500.0
	_refresh()
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(6, 3), Vector2.RIGHT)
	return assert_true(not plan.get("supported", false) and game_instance.bombs.is_empty(),
		"A known chain ignition along the actual flight path must be rejected before creating a bomb")

func _normal_source(cell: Vector2i) -> ServerBomb:
	game_instance.add_player(972, "ChainSource", BotTestHelpers.tile_to_world_center(cell))
	var source_actor: ServerPlayer = game_instance.players[972]
	source_actor.set_physics_process(false)
	var placed: Dictionary = game_instance.submit_player_command(972, {"action": "place_bomb"})
	if not placed.accepted: return null
	source_actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	return game_instance.bombs.get(placed.bomb_ids[0])

func test_a_normal_native_bomb_igniting_the_flight_corridor_refuses_before_planting() -> Variant:
	var source := _normal_source(Vector2i(4, 4))
	if source == null: return "Could not legally place the normal chain source"
	# Age its ordinary fuse through real physics, without changing its timer,
	# range or fuse. Its next blast reaches (4,3) during a new throw's flight.
	await _frames(165)
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(6, 3), Vector2.RIGHT)
	var refused: bool = not plan.get("supported", false)
	await _frames(22)
	return assert_true(refused and source.has_exploded and _own_commands("place_bomb").is_empty()
		and source.fuse_time == Constants.BOMB_TIMER and source.explosion_range == 1,
		"A real normally timed source must confirm the predicted in-flight chain hazard")

func _commit_carried_recovery(deadline: float) -> bool:
	var world = bot_manager._observation_views[bot_player.peer_id]
	var placed: Dictionary = world.place_bomb(observed_actor)
	if not placed.accepted: return false
	var bomb = world.bombs[placed.bomb_ids[0]]
	if not observed_actor.try_pickup_bomb(bomb): return false
	_refresh()
	bot_controller.get_blackboard().set_var("throw_recovery", {"bomb_id": bomb.bomb_id,
		"direction": Vector2.RIGHT, "deadline": deadline, "attempts": 1})
	return true

func test_new_imminent_native_hazard_preempts_a_committed_carried_recovery() -> Variant:
	var source := _normal_source(Vector2i(3, 4))
	if source == null: return "Could not legally place the normal emergency source"
	await _frames(165)
	if not _commit_carried_recovery(game_instance.get_simulation_time_msec() + 1000.0):
		return "Could not prepare legal carried recovery"
	_start_policy()
	await _frames(1, true)
	var board = bot_controller.get_blackboard()
	return assert_true(_own_commands("throw_bomb").is_empty() and bot_player.is_carrying_bomb()
		and board.get_var("in_danger", false) and not board.get_var("throw_recovery", {}, false).is_empty(),
		"A newly threatening external bomb must give the production survival branch priority over recovery")

func test_expired_carried_recovery_is_cleared_without_a_retry_or_duplicate_bomb() -> Variant:
	if not _commit_carried_recovery(game_instance.get_simulation_time_msec() - 1.0):
		return "Could not prepare legal carried recovery"
	_start_policy()
	await _frames(3, true)
	var board = bot_controller.get_blackboard()
	return assert_true(_own_commands("throw_bomb").is_empty() and _own_commands("place_bomb").size() == 1
		and board.get_var("throw_recovery", {}, false).is_empty()
		and board.get_var("last_throw_failure", "", false) == "throw_preparation_timeout",
		"Expired recovery must clear its bounded transaction: %s" % {
			"throws": _own_commands("throw_bomb").size(), "placed": _own_commands("place_bomb").size(),
			"recovery": board.get_var("throw_recovery", {}, false),
			"failure": board.get_var("last_throw_failure", "", false)})

func test_off_center_wrap_preparation_refuses_a_burning_facing_step() -> Variant:
	bot_player.position = Vector2((default_map_width - 1) * GameConfig.TILE_SIZE - 0.1,
		3.5 * GameConfig.TILE_SIZE)
	# Face left through real physics first, then freeze and set the test's
	# public off-center starting position. The proposed throw requires right.
	bot_player.set_input(-1, 0)
	bot_player.set_physics_process(true)
	await _frames(1)
	bot_player.set_physics_process(false)
	bot_player.set_input(0, 0)
	bot_player.position.x = (default_map_width - 1) * GameConfig.TILE_SIZE - 0.1
	game_instance.players[TARGET_PEER].position = BotTestHelpers.tile_to_world_center(Vector2i(1, 3))
	game_instance.active_explosion_tiles["14,3"] = game_instance.get_simulation_time_msec() + 500.0
	_refresh()
	var plan: Dictionary = Plan.choose(observed_actor, bot_manager._observation_views[bot_player.peer_id], bot_manager.grid_sampler, Vector2i(1, 3), Vector2.RIGHT)
	return assert_true(bot_player.last_move_direction == Vector2.LEFT
		and not plan.get("supported", false) and _own_commands("place_bomb").is_empty(),
		"A wrapped-left flight cannot hide a burning rightward facing footprint")

func test_refused_pickup_keeps_a_grounded_escape_and_does_not_claim_a_throw() -> Variant:
	game_instance.reject_once_action = "pickup_bomb"
	_start_policy()
	for frame in range(60):
		await _frames(1, true)
		if not _own_commands("pickup_bomb", false).is_empty(): break
	if _own_commands("place_bomb").size() != 1 or _own_commands("pickup_bomb", false).size() != 1:
		return "Fault control did not reach the real place-then-refused-pickup boundary"
	await _frames(8, true)
	return assert_true(_own_commands("throw_bomb").is_empty() and not bot_player.is_carrying_bomb()
		and not bot_player.is_dead and bot_controller.get_blackboard().get_var("in_danger", false),
		"Refused pickup must return to the normal public-hazard survival branch")

func test_refused_final_throw_resumes_the_same_carried_bomb_without_duplicate_placement() -> Variant:
	game_instance.reject_once_action = "throw_bomb"
	var bomb := await _until_thrown()
	return assert_true(bomb != null and _own_commands("place_bomb").size() == 1
		and _own_commands("pickup_bomb").size() == 1 and _own_commands("throw_bomb", false).size() == 1
		and _own_commands("throw_bomb").size() == 1 and not bot_player.is_carrying_bomb()
		and bot_controller.get_blackboard().get_var("throw_recovery", {}, false).is_empty(),
		"Bounded recovery must finish the observed carried transaction through normal commands")

func test_exhausted_waypoint_preview_is_an_explicit_refusal() -> Variant:
	var plan: Dictionary = Trajectory.plan(Vector2i(3, 3), Vector2.RIGHT,
		Vector2i(default_map_width, default_map_height), GameConfig.TILE_SIZE,
		func(_cell: Vector2i) -> bool: return true)
	return assert_true(not plan.complete and plan.waypoints.size() >= 20,
		"The authority's legacy bounce cap cannot become a claimed safe policy trajectory")
