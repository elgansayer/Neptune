extends "res://tests/bot_test_suite.gd"

class CountedBomb extends RefCounted:
	var has_exploded := false
	var reads := 0
	func get_forecast_observation() -> Dictionary:
		reads += 1
		return {"cell": Vector2i(4, 4), "range": 2, "fuse_lower_bound": 1.0,
			"fuse_upper_bound": 1.0, "elapsed": 0.25, "state": ServerBomb.BombState.PLANTED,
			"bomb_type": ServerBomb.BOMB_TYPE_NORMAL}

class CountedWorld extends Node:
	var active_explosion_tiles := {}
	var bombs := {}

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance.active_explosion_tiles.clear()
	await super()
	game_instance.add_to_group("bot_test_game")
	game_instance.set_meta("fixture_owner", self)
	game_instance.current_time_msec = 10000.0

func _predictor():
	var predictor = preload("res://tests/support/count_safety_map_builds.gd").new()
	predictor.configure(game_instance, bot_manager.grid_sampler)
	return predictor

func _bomb(fuse: float = 1.0):
	var bomb: ServerBomb = BotTestHelpers.place_bomb(Vector2i(4, 4), fuse)
	bomb.explosion_timer = 0.25
	bomb.set_physics_process(false)
	return bomb

func test_shared_forecast_converts_units_without_aliasing_or_mutating_source() -> Variant:
	_bomb()
	bot_manager.refresh_public_observations(true)
	bot_manager.observed_ai_manager.refresh_threat_matrix(10000.0)
	var original: Dictionary = bot_manager.observed_ai_manager.threat_matrix.duplicate(true)
	var shared = _predictor()
	var standalone = _predictor()
	shared.refresh(10.0, false, bot_manager.observed_ai_manager.threat_matrix, 10000.0)
	standalone.refresh(10.0)
	if shared._threat_matrix != standalone._threat_matrix or shared._threat_matrix.get("4,4") != 10.75:
		return "Shared public forecast differs from independently built actual bomb forecast"
	if bot_manager.observed_ai_manager.threat_matrix != original:
		return "Seconds conversion mutated the manager's millisecond forecast"
	shared._threat_matrix["4,4"] = -999.0
	return assert_true(bot_manager.observed_ai_manager.threat_matrix == original,
		"Predictor consumers must not alias the shared manager forecast")

func test_stale_shared_timestamp_rebuilds_against_current_observed_bombs() -> Variant:
	_bomb()
	var predictor = _predictor()
	predictor.refresh(10.0, false, {"4,4": -1000.0}, 9983.333333333)
	return assert_eq(predictor._threat_matrix.get("4,4"), 10.75,
		"A prior-tick forecast cannot replace current public hazard calculation")

func test_matching_empty_shared_forecast_remains_empty_without_mutating_it() -> Variant:
	var predictor = _predictor()
	var source := {}
	predictor.refresh(10.0, false, source, 10000.0)
	predictor._danger_cache["3,3"] = 99.0
	return assert_true(source.is_empty() and predictor._threat_matrix.is_empty(),
		"A genuinely empty public forecast must remain an isolated empty result")

func test_shared_path_avoids_rebuilding_and_forced_or_stale_calls_still_build() -> Variant:
	# This read-count probe verifies work selection only. The previous test uses
	# real native bombs to independently check forecast equivalence.
	var probe := CountedWorld.new()
	var bomb := CountedBomb.new()
	probe.bombs["counted"] = bomb
	var predictor = _predictor()
	predictor.configure(probe, bot_manager.grid_sampler)
	predictor.refresh(10.0, false, {"4,4": 10750.0}, 10000.0)
	var reads_after_shared: int = bomb.reads
	predictor.refresh(10.0, false, {"4,4": 10750.0}, 9983.0)
	var reads_after_stale: int = bomb.reads
	predictor.refresh(10.0, true, {"4,4": 10750.0}, 10000.0)
	var reads_after_force: int = bomb.reads
	probe.free()
	return assert_true(reads_after_shared == 0 and reads_after_stale == 1 and reads_after_force == 2,
		"Shared current-phase input must avoid forecast work; stale/forced observation paths must rebuild")

func test_safety_bfs_is_lazy_reused_and_invalidated_with_new_map() -> Variant:
	_bomb(3.0)
	var predictor = _predictor()
	predictor.refresh(10.0)
	if predictor.safety_map_builds != 0: return "Refresh did unused full-map safety work"
	var first: float = predictor.get_safety_time(Vector2i(4, 4))
	var first_danger: bool = predictor.is_in_mortal_danger(Vector2i(4, 4), 10.0)
	if predictor.safety_map_builds != 1 or not is_finite(first):
		return "Safety getters did not share one real BFS"
	for neighbor in [Vector2i(3, 4), Vector2i(5, 4), Vector2i(4, 3), Vector2i(4, 5)]:
		set_tile(neighbor.x, neighbor.y, 1)
	await get_tree().physics_frame
	predictor.refresh(10.0)
	var blocked: float = predictor.get_safety_time(Vector2i(4, 4))
	return assert_true(predictor.safety_map_builds == 2 and is_inf(blocked)
		and predictor.is_in_mortal_danger(Vector2i(4, 4), 10.0) and not first_danger,
		"A refreshed map must invalidate the lazy cache and retain trapped-danger semantics")
