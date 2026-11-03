extends "res://tests/bot_test_suite.gd"

const Timeline = preload("res://shared/ai/perception/bomb_threat_forecast.gd")
var actor: ServerPlayer

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	await game_instance.add_player(401, "IntervalFixture", BotTestHelpers.tile_to_world_center(Vector2i(4, 4)))
	actor = game_instance.players[401]
	actor.bomb_range = 2
	actor.set_physics_process(false)
	game_instance.match_active = true

func _forecast() -> Dictionary:
	return Timeline.build_timeline(game_instance, bot_manager.grid_sampler, game_instance.get_simulation_time_msec())

func _bomb() -> ServerBomb:
	var receipt: Dictionary = game_instance.place_bomb(actor)
	if not receipt.accepted:
		return null
	var bomb: ServerBomb = game_instance.bombs[receipt.bomb_ids[0]]
	bomb.set_physics_process(false)
	return bomb

func test_observed_flame_expiry_remains_inclusive_and_finite() -> Variant:
	var now := game_instance.get_simulation_time_msec()
	game_instance.active_explosion_tiles["5,4"] = now + 500.0
	var forecast := _forecast()
	var windows: Array = forecast.intervals["5,4"]
	return assert_true(windows.size() == 1 and windows[0].x <= now and windows[0].y >= now + 500.0
		and not Timeline.is_window_safe(forecast.intervals, Vector2i(5, 4), now + 500.0, now + 500.0, 0.0)
		and Timeline.is_window_safe(forecast.intervals, Vector2i(5, 4), now + 501.1, now + 700.0, 0.0), "Current flame expiry must neither clear early nor become permanent")

func test_private_long_fuse_samples_cannot_change_public_hazard_windows() -> Variant:
	actor.active_virus = ServerPlayer.VirusType.LEISURELY_FUSE
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	bomb.fuse_time = 5.01
	var first := _forecast()
	bomb.fuse_time = 5.99
	var second := _forecast()
	var windows: Array = first.intervals["4,4"]
	return assert_true(first == second and bomb.fuse_lower_bound == 5.0 and bomb.fuse_upper_bound == 6.0
		and is_finite(windows[0].y) and windows[0].y >= game_instance.get_simulation_time_msec() + 6000.0,
		"Only deterministic public 5..6 second bounds may determine the long-fuse interval")

func test_remote_bombs_are_immediate_uncertain_hazards() -> Variant:
	actor.bomb_type = ServerBomb.BOMB_TYPE_REMOTE
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	var forecast := _forecast()
	var window: Vector2 = forecast.intervals["4,4"][0]
	return assert_true(window.x <= game_instance.get_simulation_time_msec() and window.y == INF, "A remotely triggered bomb has neither a guaranteed safe delay nor a finite automatic expiry")

func test_active_fire_shortens_a_bomb_without_waiting_for_its_private_fuse() -> Variant:
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	var now := game_instance.get_simulation_time_msec()
	game_instance.active_explosion_tiles["4,4"] = now + 100.0
	var forecast := _forecast()
	return assert_eq(forecast.deadlines["5,4"], now, "A bomb already touched by fire must threaten its whole cross immediately")

func test_exploded_bomb_retains_future_progressive_arms_before_they_are_visible() -> Variant:
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	bomb.explode()
	if not game_instance.active_explosion_tiles.is_empty(): return "Control unexpectedly expanded before its first bomb physics callback"
	var forecast := _forecast()
	return assert_true(forecast.intervals.has("6,4") and forecast.deadlines["6,4"] == game_instance.get_simulation_time_msec(), "A visible exploding actor must not lose unexpanded blast arms from the forecast")

func test_progressive_native_flame_lifetimes_fit_the_conservative_forecast() -> Variant:
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	bomb.explode()
	var forecast := _forecast()
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	var start := game_instance.get_simulation_time_msec()
	for frame in range(10):
		game_instance.current_time_msec = start + frame * 1000.0 / 60.0
		bomb._physics_process(1.0 / 60.0)
		for key in game_instance.active_explosion_tiles:
			if not forecast.intervals.has(key): return "Actual flame lies outside predicted geometry: " + str(key)
			var window: Vector2 = forecast.intervals[key][0]
			if window.x > game_instance.current_time_msec or window.y < game_instance.active_explosion_tiles[key]:
				return "Actual progressive flame lifetime escaped conservative window at " + str(key)
	return true

func test_overlapping_intervals_merge_without_erasing_a_real_safe_gap() -> Variant:
	var result := Timeline.merge_intervals([Vector2(100.0, 300.0), Vector2(200.0, 500.0), Vector2(800.0, 900.0)])
	return assert_eq(result, [Vector2(100.0, 500.0), Vector2(800.0, 900.0)])

func test_kicked_bomb_covers_future_stopping_crosses_until_its_public_latest_fuse() -> Variant:
	var bomb := _bomb()
	if bomb == null or not bomb.kick(Vector2.RIGHT): return "Native kick control failed"
	var forecast := _forecast()
	return assert_true(forecast.deadlines.has("8,4")
		and forecast.deadlines["8,4"] == game_instance.get_simulation_time_msec()
		and forecast.uncertain.has("conservative_kick_envelope")
		and is_finite(forecast.intervals["8,4"][0].y), "Kicked bombs must cover future possible blast origins, while their running fuse retains a finite public bound")

func test_exploding_pattern_survives_a_new_wall_that_appears_after_detonation() -> Variant:
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	bomb.explode()
	set_tile(5, 4, 1)
	var forecast := _forecast()
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	for frame in range(3):
		bomb._physics_process(0.1)
	return assert_true(game_instance.active_explosion_tiles.has("6,4") and forecast.intervals.has("6,4"), "The original public explosion pattern must survive later terrain edits; reprojection against a new wall hides real progressive fire")

func test_later_bomb_forecasts_past_a_blocker_an_earlier_bomb_can_destroy() -> Variant:
	var first := _bomb()
	if first == null: return "First fixture placement failed"
	first.explosion_range = 1
	first.fuse_lower_bound = 1.0
	first.fuse_upper_bound = 1.0
	set_tile(5, 4, 2)
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(6, 4))
	actor.max_bombs = 2
	actor.bomb_range = 3
	var later := _bomb()
	if later == null: return "Later fixture placement failed"
	var forecast := _forecast()
	return assert_true(forecast.intervals.has("3,4") and forecast.deadlines["3,4"] <= game_instance.get_simulation_time_msec() + 3000.0,
		"A soft block that can disappear before the later detonation cannot conceal that bomb's extended blast")

func test_one_uncertain_bomb_cannot_assume_it_removed_its_own_blocker() -> Variant:
	actor.active_virus = ServerPlayer.VirusType.LEISURELY_FUSE
	actor.bomb_range = 3
	var bomb := _bomb()
	if bomb == null: return "Fixture placement failed"
	set_tile(5, 4, 2)
	return assert_true(not _forecast().intervals.has("6,4"), "Fuse uncertainty must not let one normal bomb clear a blocker before calculating its own explosion pattern")

func _throw_fixture() -> ServerBomb:
	var bomb := _bomb()
	if bomb == null: return null
	actor.has_power_glove = true
	if not bomb.pick_up(actor) or not bomb.throw_bomb(Vector2.RIGHT): return null
	return bomb

func test_native_throw_forecasts_landing_cross_and_paused_then_reset_fuse() -> Variant:
	var bomb := _throw_fixture()
	if bomb == null: return "Native throw failed"
	bomb.fuse_time = 0.1
	bomb.fuse_lower_bound = 0.1
	bomb.fuse_upper_bound = 0.1
	bomb.explosion_timer = 0.09
	var initial_time := game_instance.get_simulation_time_msec()
	var forecast := _forecast()
	if not forecast.intervals.has("8,4"): return "Flight landing cross beyond the old ground-origin cross was omitted"
	if forecast.deadlines["8,4"] < initial_time + 400.0: return "Flight must pause the timer and restart the complete fuse on landing"
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	for frame in range(80):
		game_instance.current_time_msec = initial_time + (frame + 1) * 1000.0 / 60.0
		bomb._physics_process(1.0 / 60.0)
		for key in game_instance.active_explosion_tiles:
			if not forecast.intervals.has(key): return "Native thrown blast escaped the predicted landing envelope: " + str(key)
			var window: Vector2 = forecast.intervals[key][0]
			if window.x > game_instance.current_time_msec or window.y < game_instance.active_explosion_tiles[key]: return "Native thrown flame escaped its predicted interval"
	return assert_true(bomb.has_exploded and game_instance.active_explosion_tiles.has("8,4"), "Real throw must land and expand from the observed destination")

func test_chain_triggered_airborne_bomb_keeps_landing_envelope() -> Variant:
	var bomb := _throw_fixture()
	if bomb == null: return "Native throw failed"
	actor.max_bombs = 2
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(4, 6))
	var source := _bomb()
	if source == null: return "Native chain source placement failed"
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	source.explode()
	for frame in range(3):
		source._physics_process(0.1)
	if not bomb.has_exploded: return "Native mid-air chain control did not trigger"
	var forecast := _forecast()
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(12, 10))
	for frame in range(60):
		game_instance.current_time_msec += 1000.0 / 60.0
		bomb._physics_process(1.0 / 60.0)
	return assert_true(forecast.intervals.has("8,4") and game_instance.active_explosion_tiles.has("8,4"), "A chain-triggered airborne actor continues flying before native expansion; its landing cross must remain predicted")

func test_carried_uncertainty_blocks_nearby_planting_but_preserves_distant_play() -> Variant:
	var bomb := _bomb()
	if bomb == null or not bomb.pick_up(actor): return "Native pickup failed"
	var near := Timeline.placement_capability(game_instance, bot_manager.grid_sampler, Vector2i(5, 4))
	var far := Timeline.placement_capability(game_instance, bot_manager.grid_sampler, Vector2i(13, 11))
	return assert_true(not near.supported and near.reason == "unresolved_nearby_projectile_choice" and far.supported,
		"Unknown private throw direction must restrict nearby intentional planting without disabling the whole arena")

func test_public_flight_windows_ignore_hidden_sample_and_are_copy_isolated() -> Variant:
	actor.active_virus = ServerPlayer.VirusType.LEISURELY_FUSE
	var bomb := _throw_fixture()
	if bomb == null: return "Native throw failed"
	bomb.fuse_time = 5.01
	var first := _forecast()
	bomb.fuse_time = 5.99
	var second := _forecast()
	var observation := bomb.get_forecast_observation()
	observation.flight.remaining_waypoints.clear()
	return assert_true(first == second and not bomb.get_forecast_observation().flight.remaining_waypoints.is_empty(),
		"Public flight geometry must neither expose private sampled fuse values nor alias the authoritative trajectory")
