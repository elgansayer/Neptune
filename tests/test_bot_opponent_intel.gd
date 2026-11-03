extends "res://tests/bot_test_suite.gd"

const SUBJECT := 701

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	bot_manager.observed_ai_manager.opponent_profiles.clear()
	game_instance.add_player(SUBJECT, "ObservedOpponent", BotTestHelpers.tile_to_world_center(Vector2i(8, 6)))
	game_instance.players[SUBJECT].set_physics_process(false)
	game_instance.match_active = true

func _observe(position: Vector2i, observers: Dictionary, delta: float = 0.25):
	game_instance.players[SUBJECT].position = BotTestHelpers.tile_to_world_center(position)
	game_instance.invalidate_public_observation()
	bot_manager.refresh_public_observations(true)
	var manager: AIManager = bot_manager.observed_ai_manager
	manager.update_opponent_intel(observers, bot_manager.perception_world.players, delta)
	return manager.get_opponent_profile(SUBJECT)

func test_first_observation_is_neutral_and_approaching_then_fleeing_changes_score() -> Variant:
	var observers := {-1: Vector2i(3, 6)}
	var profile = _observe(Vector2i(8, 6), observers)
	if profile.aggression_score != 0.0:
		return "The first observation inferred movement from an unobserved origin"
	profile = _observe(Vector2i(7, 6), observers)
	if profile.aggression_score <= 0.0:
		return "An observed approach did not increase aggression"
	profile = _observe(Vector2i(8, 6), observers)
	return assert_true(profile.aggression_score < 0.0 and profile.last_seen_pos == Vector2i(8, 6), "An observed retreat must reduce aggression before storing the new position")

func test_shared_quadrant_time_is_once_per_tick_and_independent_of_bot_count() -> Variant:
	var profile = _observe(Vector2i(8, 6), {-1: Vector2i(3, 6), -2: Vector2i(2, 6), -3: Vector2i(1, 6)})
	var total := 0.0
	for value in profile._quadrant_time.values():
		total += value
	return assert_true(is_equal_approx(total, 0.25), "Shared profile time must not multiply by the number of observing bots")

func test_observer_movement_does_not_invent_opponent_aggression() -> Variant:
	_observe(Vector2i(8, 6), {-1: Vector2i(3, 6)})
	var profile = _observe(Vector2i(8, 6), {-1: Vector2i(5, 6)})
	return assert_eq(profile.aggression_score, 0.0, "Our movement toward a stationary opponent is not evidence of their aggression")

func test_equal_distance_observers_are_deterministic_across_dictionary_order() -> Variant:
	var scores := []
	for observers in [{-1: Vector2i(4, 6), -2: Vector2i(10, 6)}, {-2: Vector2i(10, 6), -1: Vector2i(4, 6)}]:
		bot_manager.observed_ai_manager.opponent_profiles.clear()
		_observe(Vector2i(8, 6), observers)
		var profile = _observe(Vector2i(7, 6), observers)
		scores.append(profile.aggression_score)
	return assert_true(scores[0] == scores[1] and scores[0] != 0.0, "Tied observer choice must have a stable identity order, not dictionary iteration order")

func test_no_observer_and_self_only_observer_do_not_create_intel() -> Variant:
	var manager: AIManager = bot_manager.observed_ai_manager
	bot_manager.refresh_public_observations(true)
	manager.update_opponent_intel({}, bot_manager.perception_world.players, 0.25)
	manager.update_opponent_intel({SUBJECT: Vector2i(8, 6)}, bot_manager.perception_world.players, 0.25)
	return assert_true(manager.opponent_profiles.is_empty(), "A player cannot contribute an opponent observation of itself")
