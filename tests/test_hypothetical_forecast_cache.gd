extends "res://tests/bot_test_suite.gd"

class CountingManager extends AIManager:
	var builds := 0
	func _build_hypothetical_forecast(cell: Vector2i, radius: int, now: float, fuse: float) -> Dictionary:
		builds += 1
		return super(cell, radius, now, fuse)

func setup_test() -> void:
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	game_instance.match_active = true
	game_instance.current_time_msec = 10000.0

func _manager(raw: bool = false):
	bot_manager.refresh_public_observations(true)
	var manager := CountingManager.new()
	manager.configure(game_instance if raw else bot_manager.perception_world,
		bot_manager.grid_sampler, default_map_width, default_map_height)
	return manager

func test_identical_public_queries_build_once_and_return_detached_results() -> Variant:
	var manager = _manager()
	var first: Dictionary = manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0)
	var expected := first.duplicate(true)
	first["6,4"] = -999.0
	var second: Dictionary = manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0)
	second.clear()
	return assert_true(manager.builds == 1 and manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0) == expected,
		"Identical revision/time/geometry queries must reuse one forecast without exposing its stored dictionary")

func test_same_tick_actual_placement_and_terrain_change_invalidate_cached_chains() -> Variant:
	var manager = _manager()
	var initial: Dictionary = manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0)
	var joined: Dictionary = game_instance.add_player(741, "CacheBombOwner", BotTestHelpers.tile_to_world_center(Vector2i(4, 4)))
	if not joined.accepted: return "Cache chain fixture could not admit its real bomber"
	var actor: ServerPlayer = game_instance.players[741]
	actor.set_physics_process(false)
	actor.bomb_range = 2
	actor.active_virus = ServerPlayer.VirusType.HASTY_FUSE
	var placed: Dictionary = actor.request_bomb_placement()
	if not placed.accepted: return "Cache chain fixture failed actual validated bomb placement"
	game_instance.bombs[placed.bomb_ids[0]].set_physics_process(false)
	var chained: Dictionary = manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0)
	set_tile(5, 4, 1)
	var blocked: Dictionary = manager.simulate_threat_matrix(Vector2i(6, 4), 3, 10000.0, 3.0)
	return assert_true(manager.builds == 3 and initial["6,7"] == 13000.0
		and chained["6,7"] == 11000.0 and blocked["6,7"] == 13000.0,
		"Exact same-tick observation revisions must refresh both newly shortened chains and changed blocker geometry")

func test_exact_clock_cell_range_and_fuse_are_independent_cache_keys() -> Variant:
	var manager = _manager()
	for query in [[Vector2i(3, 3), 1, 10000.0, 3.0], [Vector2i(4, 3), 1, 10000.0, 3.0],
		[Vector2i(3, 3), 2, 10000.0, 3.0], [Vector2i(3, 3), 1, 10000.0, 3.000000001],
		[Vector2i(3, 3), 1, 10000.0000001, 3.0]]:
		manager.simulate_threat_matrix(query[0], query[1], query[2], query[3])
	return assert_eq(manager.builds, 5, "Clock/fuse keys must retain exact float distinctions and geometry must not collide")

func test_unversioned_authority_always_rebuilds_and_cache_is_bounded() -> Variant:
	var raw = _manager(true)
	raw.simulate_threat_matrix(Vector2i(3, 3), 1, 10000.0)
	raw.simulate_threat_matrix(Vector2i(3, 3), 1, 10000.0)
	if raw.builds != 2 or not raw._forecast_query_cache.is_empty():
		return "An unversioned authority cannot safely reuse cached assumptions"
	var manager = _manager()
	for index in range(140):
		manager.simulate_threat_matrix(Vector2i(1 + index % 13, 1 + index / 13), 1, 10000.0)
	if manager._forecast_query_cache.size() != 128: return "Hypothetical cache exceeded or omitted its explicit bound"
	var before: int = manager.builds
	manager.simulate_threat_matrix(Vector2i(1, 1), 1, 10000.0)
	manager.get_placement_capability(Vector2i(1, 1), 10000.0)
	return assert_true(manager.builds == before and manager._forecast_query_cache.size() == 128,
		"A full cache must preserve existing entries and bound capability entries too")

func test_capability_exports_are_isolated_and_share_the_same_observation_identity() -> Variant:
	var manager = _manager()
	var first: Dictionary = manager.get_placement_capability(Vector2i(3, 3), 10000.0)
	first.supported = false
	var second: Dictionary = manager.get_placement_capability(Vector2i(3, 3), 10000.0)
	if not second.supported or manager._forecast_query_cache.size() != 1:
		return "Placement capability cache leaked a mutable export"
	game_instance.invalidate_public_observation()
	manager.get_placement_capability(Vector2i(3, 3), 10000.0)
	return assert_eq(manager._forecast_query_cache.size(), 1,
		"A new public revision clears stale capability entries rather than retaining assumptions")
