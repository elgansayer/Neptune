extends "res://tests/bot_test_suite.gd"

func make_game_instance() -> GameInstance:
	return load("res://tests/support/fixture_bot_fill_game.gd").new()

func setup_test() -> void:
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	game_instance._room_capacity.clear()
	game_instance._room_round_started = false
	game_instance._room_bot_fill = {"target": 0, "personality": "BALANCED", "applied": false}
	game_instance.refuse_after = -1
	game_instance.provision_calls = 0
	await super()
	game_instance.match_active = false
	game_instance.countdown_time = 0
	if not game_instance.configure_room_capacity(4).accepted:
		push_error("Fill test's real four-seat geometry setup failed")

func teardown_test() -> void:
	await super()
	game_instance.reset_spawn_reservations()

func _human(id: int, identity: String = "") -> Dictionary:
	var result := game_instance.add_player(id, "Fill%d" % id, Vector2.ZERO, false, "", identity)
	if result.accepted: game_instance.players[id].set_physics_process(false)
	return result

func _start() -> Dictionary:
	var result := game_instance.start_room_countdown()
	if result.accepted: game_instance._physics_process(1.1)
	return result

func test_initial_boundary_creates_real_fair_bots_and_controllers() -> Variant:
	if not game_instance.configure_room_bot_fill(4, "DEFENSIVE").accepted: return "Fill configuration failed"
	if not _human(701).accepted or not _start().accepted: return "Human/start failed"
	if not game_instance.match_active or game_instance.players.size() != 4: return "Round did not fill and activate"
	var cells := {}
	for id in game_instance.players:
		var actor = game_instance.players[id]
		cells[str(actor.position)] = true
		if actor.max_bombs != 1 or actor.bomb_range != 1 or actor.skate_count != 0 or actor.has_bomb_kicker or actor.has_power_glove:
			return "Fill granted hidden starting stat/item boosts"
		if id < 0:
			var controller = bot_manager.get_bot_controller(id)
			if not is_instance_valid(controller) or actor.bot_personality != "DEFENSIVE" or bot_manager.get_bot_policy_snapshot(id).is_empty():
				return "Fill lacks real bot/controller/policy lineage"
	return assert_true(cells.size() == 4 and game_instance.last_bot_fill_result.added == 3, "Actual initial actors require distinct reserved starts")

func test_existing_humans_and_bots_count_without_replacement() -> Variant:
	game_instance.configure_room_bot_fill(4, "DEFENSIVE")
	_human(701)
	_human(702)
	var prior := game_instance.spawn_bot("AGGRESSIVE")
	var actor = game_instance.players[prior.peer_id]
	_start()
	return assert_true(game_instance.match_active and game_instance.last_bot_fill_result.added == 1 and game_instance.players[prior.peer_id] == actor and actor.bot_personality == "AGGRESSIVE" and game_instance.get_room_capacity().humans == 2, "Fill counts existing actors and preserves their identity/personality")

func test_retained_identity_counts_toward_target_and_rebinds_its_seat() -> Variant:
	game_instance.configure_room_bot_fill(4)
	var original := _human(701, "stable:fill-reserved")
	_human(702)
	game_instance.remove_player(701, true)
	_start()
	if game_instance.get_room_capacity().bots != 2 or game_instance.get_room_capacity().reserved != 4: return "Fill consumed retained human seat"
	var restored := _human(703, "stable:fill-reserved")
	return assert_true(restored.accepted and restored.reused and restored.cell == original.cell and game_instance.players.size() == 4, "Returning human owns the original reservation without evicting a bot")

func test_invalid_fill_configuration_rejects_atomically() -> Variant:
	game_instance.configure_room_bot_fill(3, "DEFENSIVE")
	var before: Dictionary = game_instance.get_room_capacity()
	for value in [null, true, "3", 3.0, -1, 5, 13]:
		if game_instance.configure_room_bot_fill(value).accepted or game_instance.get_room_capacity() != before: return "Invalid target mutated fill policy"
	for value in [null, 1, "", "unknown", "defensive"]:
		if game_instance.configure_room_bot_fill(3, value).accepted or game_instance.get_room_capacity() != before: return "Unknown profile silently fell back or mutated policy"
	return true

func test_live_policy_is_immutable_and_finished_round_never_refills() -> Variant:
	game_instance.configure_room_bot_fill(4)
	_human(701)
	if game_instance.configure_room_bot_fill(2).accepted: return "Live roster allowed fill policy change"
	_start()
	var removed_id: int = bot_manager.next_bot_peer_id + 1
	game_instance.remove_player(removed_id)
	game_instance._physics_process(0.1)
	if game_instance.players.size() != 3 or game_instance.configure_room_bot_fill(3).accepted: return "Active round silently refilled/changed policy"
	game_instance.end_match()
	var result := game_instance.start_room_countdown()
	return assert_true(not result.accepted and not game_instance.match_active and game_instance.players.size() == 3 and not game_instance._provision_initial_room_bots().accepted, "Refill requires an explicit later round boundary; this slice cannot restart finished rounds")

func test_partial_provision_failure_rolls_back_and_immediate_retry_survives_callbacks() -> Variant:
	game_instance.configure_room_bot_fill(4)
	_human(701)
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	var first_id: int = bot_manager.next_bot_peer_id
	game_instance.refuse_after = 1
	_start()
	if game_instance.match_active or game_instance.last_room_start_result.reason != "bot_fill_provision_failed" or game_instance.players.size() != 1 or game_instance.get_spawn_reservation_state() != before or bot_manager.next_bot_peer_id != first_id or not bot_manager._bot_players.is_empty() or not bot_manager._observation_views.is_empty() or not bot_manager._policy_rngs.is_empty():
		return "Failed batch left partial roster/reservation/controller/view/RNG state"
	game_instance.refuse_after = -1
	_start()
	await get_tree().process_frame
	await get_tree().process_frame
	for id in range(first_id, first_id - 3, -1):
		if not game_instance.players.has(id) or not is_instance_valid(bot_manager.get_bot_controller(id)): return "Old deferred cleanup removed a retry's new controller"
	return assert_true(game_instance.match_active and game_instance.players.size() == 4, "Failed start retries only after complete rollback")

func test_public_roster_and_fill_metadata_are_detached() -> Variant:
	game_instance.configure_room_bot_fill(2, "DEFENSIVE")
	_human(701)
	var bot_id: String = str(bot_manager.next_bot_peer_id)
	_start()
	var data: Dictionary = game_instance.get_room_capacity()
	if data.participants["701"].type != "human" or data.participants[bot_id].type != "bot" or data.participants[bot_id].personality != "DEFENSIVE" or data.bot_policy != bot_manager.POLICY_VERSION: return "Missing explicit public participant/policy metadata"
	data.bot_fill.target = 12
	data.participants[bot_id].personality = "altered"
	var actual: Dictionary = game_instance.get_room_capacity()
	return assert_true(actual.bot_fill.target == 2 and actual.participants[bot_id].personality == "DEFENSIVE" and actual.bot_fill.applied, "Client metadata must not change authority policy")

func test_disabled_policy_adds_no_bots_and_capacity_cannot_undercut_target() -> Variant:
	game_instance.configure_room_bot_fill(4)
	if game_instance.configure_room_capacity(3).accepted: return "Capacity undercut its fill target"
	game_instance.configure_room_bot_fill(0)
	_human(701)
	_start()
	return assert_true(game_instance.match_active and game_instance.players.size() == 1 and game_instance.last_bot_fill_result.added == 0, "Default/explicit zero preserves no-fill behavior")
