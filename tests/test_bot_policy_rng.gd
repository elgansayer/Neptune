extends "res://tests/bot_test_suite.gd"

const Ambush = preload("res://ai/tasks/actions/bt_wait_ambush.gd")
const POLICY_SEED := 424242

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	# Decisions are in an active match; physics remains explicitly frozen.
	game_instance.match_active = true

func _board(player, rng: RandomNumberGenerator):
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", player)
	board.set_var("grid_sampler", bot_manager.grid_sampler)
	board.set_var("ai_manager", bot_manager.observed_ai_manager)
	board.set_var("policy_rng", rng)
	return board

func _ambush(player, board):
	var task = Ambush.new()
	task.wait_time = 0.0
	task.reevaluate_interval = 1000.0
	task.prefer_center = false
	task.initialize(player, board, get_tree().current_scene)
	return task

func _choices(task, player, noise: bool, count: int = 32) -> Array:
	var choices := []
	for index in range(count):
		if noise:
			for ignored in range(index + 1):
				randi()
		var status: int = task.execute(0.02)
		choices.append([status, player.input_direction])
	return choices

func _actor() -> Node:
	var tile := Vector2i(7, 6) if game_instance.players.is_empty() else Vector2i(9, 6)
	await spawn_bot_at(tile)
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	bot_player.set_physics_process(false)
	bot_manager.refresh_public_observations(true)
	return bot_controller.get_blackboard().get_var("player")

func test_native_ambush_does_not_consume_global_gameplay_rng() -> Variant:
	var player = await _actor()
	var rng := RandomNumberGenerator.new()
	rng.seed = POLICY_SEED
	var task = _ambush(player, _board(player, rng))
	seed(90125)
	var expected := randi()
	seed(90125)
	task.execute(0.02)
	return assert_eq(randi(), expected, "Native policy must not consume the gameplay RNG")

func test_native_ambush_choices_ignore_interleaved_global_draws() -> Variant:
	var player = await _actor()
	var experiments := []
	for noise in [false, true]:
		var rng := RandomNumberGenerator.new()
		rng.seed = POLICY_SEED
		var task = _ambush(player, _board(player, rng))
		seed(90125)
		experiments.append(_choices(task, player, noise))
	if experiments[0] != experiments[1]:
		return "The same seeded native policy changed its actions after unrelated RNG draws"
	var unique := {}
	for choice in experiments[0]:
		unique[choice[1]] = true
	return assert_true(unique.size() >= 4, "Control must exercise real directional decisions, not constant/no-op output")

func test_fixture_supplies_the_explicit_match_policy_seed() -> Variant:
	return assert_eq(bot_manager.get_policy_seed(), POLICY_SEED, "Owned fixtures must not rely on global seed() to seed policies")

func test_manager_provisions_distinct_independent_bot_streams() -> Variant:
	var first = await _actor()
	var first_controller = bot_controller
	var first_board = first_controller.get_blackboard()
	var first_task = _ambush(first, first_board)
	var saved: Dictionary = bot_manager.get_bot_policy_snapshot(first.peer_id)
	var expected := _choices(first_task, first, false)
	if not bot_manager.restore_bot_policy_snapshot(first.peer_id, saved):
		return "Cannot restore the first participant stream"
	var second = await _actor()
	var second_board = bot_controller.get_blackboard()
	var second_task = _ambush(second, second_board)
	var first_rng = first_board.get_var("policy_rng", null)
	var second_rng = second_board.get_var("policy_rng", null)
	if not first_rng is RandomNumberGenerator or not second_rng is RandomNumberGenerator or first_rng == second_rng:
		return "Manager did not give each native controller its own RNG"
	if first_rng.seed == second_rng.seed:
		return "Different bot identities received the same stream seed"
	var actual := []
	var other := []
	for index in range(expected.size()):
		other.append_array(_choices(second_task, second, true, index + 1))
		actual.append_array(_choices(first_task, first, false, 1))
	if actual != expected:
		return "Interleaving a second participant changed the first participant's policy sequence"
	return assert_true(other.slice(0, expected.size()) != expected, "Independent streams must exercise different choices")

func test_policy_snapshot_json_round_trip_resumes_the_native_actions() -> Variant:
	var player = await _actor()
	var board = bot_controller.get_blackboard()
	var task = _ambush(player, board)
	_choices(task, player, false, 7)
	var saved: Dictionary = bot_manager.get_bot_policy_snapshot(player.peer_id)
	var serialised := JSON.stringify(saved)
	var expected := _choices(task, player, false)
	var decoded = JSON.parse_string(serialised)
	if not decoded is Dictionary or not bot_manager.restore_bot_policy_snapshot(player.peer_id, decoded):
		return "JSON checkpoint lost or rejected exact stream state"
	var actual := _choices(task, player, true)
	if expected != actual:
		return "Restored policy RNG did not resume the next native actions"
	var after: Dictionary = bot_manager.get_bot_policy_snapshot(player.peer_id)
	if after.state == saved.state:
		return "Control did not advance the live participant RNG"
	return true

func test_malformed_or_incompatible_snapshot_leaves_live_state_unchanged() -> Variant:
	var player = await _actor()
	var saved: Dictionary = bot_manager.get_bot_policy_snapshot(player.peer_id)
	var mutations := []
	for key in ["format", "policy", "engine", "peer_id", "match_seed", "stream_seed"]:
		var changed := saved.duplicate()
		changed[key] = "different"
		mutations.append(changed)
	for state in [1, null, "1.5", "01", "-0", "+1", "9223372036854775808", "-9223372036854775809", "", "1e3"]:
		var changed := saved.duplicate()
		changed.state = state
		mutations.append(changed)
	var extra := saved.duplicate()
	extra["unexpected"] = "data"
	mutations.append(extra)
	var missing := saved.duplicate()
	missing.erase("state")
	mutations.append(missing)
	for changed in mutations:
		if bot_manager.restore_bot_policy_snapshot(player.peer_id, changed):
			return "Accepted malformed/incompatible snapshot: %s" % str(changed)
		if saved != bot_manager.get_bot_policy_snapshot(player.peer_id):
			return "Rejected restore changed the live RNG"
	if bot_manager.restore_bot_policy_snapshot(999, saved) or not bot_manager.get_bot_policy_snapshot(999).is_empty():
		return "Unknown participant acquired a policy stream"
	return true

func test_live_roster_refuses_reseed_without_changing_actions() -> Variant:
	if not bot_manager.configure_policy_seed(-9223372036854775807):
		return "Empty roster must accept an explicit signed match-policy seed"
	var player = await _actor()
	var saved: Dictionary = bot_manager.get_bot_policy_snapshot(player.peer_id)
	if bot_manager.configure_policy_seed(7) or bot_manager.get_policy_seed() != -9223372036854775807:
		return "Live roster was reseeded"
	return assert_eq(bot_manager.get_bot_policy_snapshot(player.peer_id), saved, "Rejected reseed preserves stream identity/state")

func test_native_missing_policy_rng_fails_without_random_fallback() -> Variant:
	var player = await _actor()
	var board = _board(player, null)
	var task = _ambush(player, board)
	player.set_input(1, 0)
	seed(90125)
	var expected := randi()
	seed(90125)
	var status: int = task.execute(0.02)
	if status != ClassDB.class_get_integer_constant("BT", "FAILURE") or player.input_direction != Vector2.ZERO:
		return "Missing policy stream failed to stop the native task safely"
	return assert_eq(randi(), expected, "Missing-stream failure must not fall back to global RNG")

func test_seed_configuration_and_provisioning_leave_global_rng_unchanged() -> Variant:
	seed(90125)
	var expected := randi()
	seed(90125)
	var manager = preload("res://ai/bot_manager.gd").new()
	manager.configure_policy_seed(123)
	manager.free()
	await _actor()
	return assert_eq(randi(), expected, "Policy construction/configuration/spawn must not consume global gameplay randomness")

func test_same_match_and_participant_reproduce_while_other_seeds_differ() -> Variant:
	var experiments := []
	var stream_seeds := []
	for match_seed in [POLICY_SEED, POLICY_SEED, POLICY_SEED + 1]:
		if not bot_manager.configure_policy_seed(match_seed):
			return "Clean fixture roster refused a match seed"
		# Explicit stable participant identity, as required by replay metadata.
		bot_manager.next_bot_peer_id = -900
		var player = await _actor()
		stream_seeds.append(bot_manager.get_bot_policy_snapshot(player.peer_id).stream_seed)
		var task = _ambush(player, bot_controller.get_blackboard())
		experiments.append(_choices(task, player, experiments.size() > 0))
		game_instance.remove_player(player.peer_id)
		await get_tree().process_frame
		await get_tree().process_frame
	if experiments[0] != experiments[1] or stream_seeds[0] != stream_seeds[1]:
		return "Same match seed and participant did not reproduce its native action sequence"
	if experiments[0] == experiments[2] or stream_seeds[0] == stream_seeds[2]:
		return "Different match seeds failed to exercise distinct streams"
	return true

func test_removed_participant_releases_its_policy_checkpoint() -> Variant:
	var player = await _actor()
	var peer_id: int = player.peer_id
	if bot_manager.get_bot_policy_snapshot(peer_id).is_empty():
		return "Participant never owned a stream"
	game_instance.remove_player(peer_id)
	await get_tree().process_frame
	await get_tree().process_frame
	return assert_true(bot_manager.get_bot_policy_snapshot(peer_id).is_empty(), "Removed bot must not retain checkpointable policy state")
