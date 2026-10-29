extends "res://tests/bot_test_suite.gd"

func setup_test() -> void:
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	game_instance._room_capacity.clear()
	game_instance._room_round_started = false
	await super()
	game_instance.match_active = false
	game_instance.countdown_time = 0.0

func teardown_test() -> void:
	await super()
	game_instance.reset_spawn_reservations()

func _human(id: int) -> Dictionary:
	var receipt: Dictionary = game_instance.add_player(id, "Capacity%d" % id)
	if receipt.accepted: game_instance.players[id].set_physics_process(false)
	return receipt

func test_twelve_mixed_actors_use_real_distinct_admission() -> Variant:
	if not game_instance.configure_room_capacity(12).accepted: return "Twelve-seat setup failed"
	var positions := {}
	for id in range(701, 707):
		var result := _human(id)
		if not result.accepted: return "A supported human slot was refused"
		positions[str(result.cell)] = true
	for index in range(6):
		var result: Dictionary = game_instance.spawn_bot("BALANCED")
		if not result.accepted or not is_instance_valid(bot_manager.get_bot_controller(result.peer_id)):
			return "A supported bot slot/controller was refused"
		game_instance.players[result.peer_id].set_physics_process(false)
		positions[str(result.cell)] = true
	return assert_true(positions.size() == 12 and game_instance.players.size() == 12, "Twelve human/bot participants require distinct real actors and controllers")

func test_thirteenth_actor_is_refused_even_with_extra_map_spawns() -> Variant:
	for id in range(701, 713):
		if not _human(id).accepted: return "Twelve-player control failed"
	var result := _human(713)
	return assert_true(not result.accepted and not game_instance.players.has(713), "Map spawn abundance cannot bypass the twelve-seat protocol limit")

func test_preset_limit_is_independent_of_protocol_capacity() -> Variant:
	var refused: Dictionary = game_instance.configure_room_capacity(5, 4)
	var accepted: Dictionary = game_instance.configure_room_capacity(4, 4)
	var state: Dictionary = game_instance.get_room_capacity()
	return assert_true(not refused.accepted and refused.reason == "preset_capacity_exceeded" and accepted.accepted and state.protocol_limit == 12 and state.seats == 4 and state.preset_limit == 4 and state.transport_limit > state.protocol_limit, "A smaller preset cannot reduce the protocol ceiling or allow extra room seats")

func test_configured_room_limit_refuses_human_and_bot_without_partial_state() -> Variant:
	if not game_instance.configure_room_capacity(2).accepted: return "Two-seat control setup failed"
	if not _human(701).accepted or not _human(702).accepted: return "Two-seat control admission failed"
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	var next_id: int = bot_manager.next_bot_peer_id
	var human := _human(703)
	var bot: Dictionary = game_instance.spawn_bot("BALANCED")
	return assert_true(not human.accepted and human.reason == "room_full" and not bot.accepted and bot.reason == "room_full" and game_instance.players.size() == 2 and game_instance.get_spawn_reservation_state() == before and bot_manager.next_bot_peer_id == next_id and bot_manager.get_bot_controller(next_id) == null, "Refusal cannot consume a seat, bot controller or policy identity")

func test_map_with_insufficient_supported_starts_is_refused_before_countdown() -> Variant:
	game_instance.spawn_points = game_instance.spawn_points.slice(0, 3)
	var result: Dictionary = game_instance.configure_room_capacity(4)
	return assert_true(not result.accepted and result.reason == "insufficient_spawn_capacity" and not game_instance.match_active and game_instance.countdown_time == 0 and not game_instance.get_room_capacity().configured, "Explicit map/seat mismatch must fail before start rather than lowering the request")

func test_invalid_capacity_inputs_fail_atomically() -> Variant:
	if not game_instance.configure_room_capacity(4).accepted: return "Capacity control setup failed"
	var before: Dictionary = game_instance.get_room_capacity()
	for value in [null, true, "4", 4.0, 1.5, 0, -1, 13, 4294967300]:
		if game_instance.configure_room_capacity(value).accepted or game_instance.configure_room_capacity(4, value).accepted or game_instance.get_room_capacity() != before:
			return "Invalid configuration mutated or wrapped a capacity limit"
	return true

func test_live_and_retained_rosters_prevent_capacity_changes() -> Variant:
	game_instance.configure_room_capacity(2)
	_human(701)
	if game_instance.configure_room_capacity(3).accepted: return "Live actor allowed capacity change"
	game_instance.remove_player(701, true)
	return assert_true(not game_instance.configure_room_capacity(1).accepted, "An absent but reserved participant still owns a room seat")

func test_retained_human_is_counted_and_can_rebind_without_stealing_capacity() -> Variant:
	game_instance.configure_room_capacity(2)
	var first: Dictionary = game_instance.add_player(701, "Reserved", Vector2.ZERO, false, "", "stable:reserved")
	game_instance.players[701].set_physics_process(false)
	_human(702)
	game_instance.remove_player(701, true)
	var outsider := _human(703)
	var returning: Dictionary = game_instance.add_player(704, "Reserved", Vector2.ZERO, false, "", "stable:reserved")
	if returning.accepted: game_instance.players[704].set_physics_process(false)
	return assert_true(first.accepted and not outsider.accepted and outsider.reason == "room_full" and returning.accepted and returning.reused and returning.cell == first.cell and game_instance.get_room_capacity().reserved == 2, "A retained reconnect reservation cannot be taken by a new participant")

func test_empty_or_changed_map_cannot_start_and_countdown_rechecks_geometry() -> Variant:
	game_instance.configure_room_capacity(2)
	if game_instance.start_room_countdown().accepted: return "Empty room began countdown"
	_human(701)
	if not game_instance.start_room_countdown().accepted: return "Supported control could not begin countdown"
	for position in game_instance.spawn_points:
		var cell := Vector2i(position / GameConfig.TILE_SIZE)
		game_instance.game_map[cell.y][cell.x] = 1
	game_instance._physics_process(1.1)
	return assert_true(not game_instance.match_active and game_instance.countdown_time == 0 and not game_instance.last_room_start_result.accepted, "A map changed during countdown must fail final pre-start validation")

func test_valid_countdown_starts_once_and_never_implicitly_restarts_finished_round() -> Variant:
	game_instance.configure_room_capacity(2)
	_human(701)
	var first: Dictionary = game_instance.start_room_countdown()
	game_instance._physics_process(0.25)
	var remaining: float = game_instance.countdown_time
	var repeated: Dictionary = game_instance.start_room_countdown()
	if not first.accepted or not repeated.accepted or game_instance.countdown_time != remaining: return "Repeated join reset the countdown"
	game_instance._physics_process(remaining)
	if not game_instance.match_active: return "Valid prepared room never began its round"
	game_instance.end_match()
	return assert_true(not game_instance.start_room_countdown().accepted and not game_instance.match_active, "Finished rounds need the explicit future round lifecycle, not an implicit restart")

func test_room_metadata_is_detached_and_matches_real_occupancy() -> Variant:
	game_instance.configure_room_capacity(4, 4)
	_human(701)
	var state: Dictionary = game_instance.get_room_capacity()
	state.seats = 12
	state.occupied = 0
	var real: Dictionary = game_instance.get_room_capacity()
	return assert_true(real.seats == 4 and real.occupied == 1 and real.reserved == 1, "Metadata cannot mutate authority configuration or hide occupancy")

func test_oversized_restored_reservations_do_not_bypass_room_limit() -> Variant:
	for id in [701, 702, 703]: _human(id)
	var saved: Dictionary = game_instance.get_spawn_reservation_state()
	for id in [701, 702, 703]: game_instance.remove_player(id)
	if not game_instance.configure_room_capacity(2).accepted: return "Reduced-capacity restore control failed"
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	var result: Dictionary = game_instance.restore_spawn_reservations(saved)
	return assert_true(not result.accepted and result.reason == "reservation_capacity_exceeded" and game_instance.get_spawn_reservation_state() == before, "Restore must validate room capacity atomically as well as layout/provenance")
