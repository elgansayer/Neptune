extends "res://tests/bot_test_suite.gd"

var server: Node
var saved := {}

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	await super.setup_suite()
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super.setup_test()
	server = get_node("/root/ServerMain")
	saved = {"games": server.active_games, "members": server.player_to_game,
		"pending": server._pending_content, "offer": server._content_offer_template,
		"archives": server._content_archives, "serial": server._finished_room_serial,
		"lobby": server.lobby_manager, "options": server._server_room_options}
	server._server_room_options = {}
	server.active_games = {"shared_game": game_instance}
	server.player_to_game = {}
	server._pending_content = {}
	server.lobby_manager = load("res://lobby/lobby_manager.gd").new()
	server.add_child(server.lobby_manager)

func teardown_test() -> void:
	for room in server.active_games.values():
		if room != game_instance and not room in saved.games.values():
			room.queue_free()
	server.active_games = saved.games
	server.player_to_game = saved.members
	server._pending_content = saved.pending
	server._content_offer_template = saved.offer
	server._content_archives = saved.archives
	server._finished_room_serial = saved.serial
	server._server_room_options = saved.options
	server.lobby_manager.queue_free()
	server.lobby_manager = saved.lobby
	await super.teardown_test()
	await super.teardown_suite()

func test_finished_empty_room_admits_a_new_visitor_with_fresh_authority() -> Variant:
	game_instance.end_match()
	var old_id := game_instance.get_instance_id()
	var admitted: Dictionary = server.quick_start_game(-901, "NextVisitor")
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	return assert_true(admitted.accepted and current.get_instance_id() != old_id
		and current.get_round_result().is_empty() and current.players.size() == 1
		and server.player_to_game[-901] == "shared_game"
		and current.countdown_time > 0.0,
		"A later visitor must get a clean joinable authority, not round_finished")

func test_hosted_default_fill_reaches_authority_and_respects_two_seat_capacity() -> Variant:
	game_instance.end_match()
	var options := preload("res://shared/runtime_config.gd").parse_arguments([
		"--room-map=res://maps/neptune_standard.json", "--room-seats=2"], "res://main_server.tscn")
	var prepared: Dictionary = server._prepare_shared_game(options)
	if not prepared.accepted: return "Default hosted fill could not prepare a two-seat room"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	var admitted: Dictionary = current.add_player(901, "DefaultFillVisitor")
	if not admitted.accepted or not current.start_room_countdown().accepted:
		return "Default hosted fill could not admit/start its human"
	current._physics_process(3.1)
	var state: Dictionary = current.get_room_capacity()
	var bot_id: int = current.bot_manager.next_bot_peer_id + 1
	return assert_true(current.match_active and state.seats == 2 and state.humans == 1
		and state.bots == 1 and state.bot_fill.target == 2 and state.bot_fill.applied
		and state.bot_fill.personality == "BALANCED"
		and is_instance_valid(current.bot_manager.get_bot_controller(bot_id)),
		"Hosted defaults must provision a real bot after resolving the selected map/room capacity")

func test_hosted_omitted_options_create_three_controllers_on_the_default_map() -> Variant:
	game_instance.end_match()
	var prepared: Dictionary = server._prepare_shared_game()
	if not prepared.accepted: return "The actual default map could not prepare its casual room"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	if not current.add_player(901, "DefaultVisitor").accepted or not current.start_room_countdown().accepted:
		return "The default casual room could not admit/start its human"
	current._physics_process(3.1)
	var state: Dictionary = current.get_room_capacity()
	if not current.match_active or state.humans != 1 or state.bots != 3 or state.bot_fill.target != 4:
		return "Omitted hosted options did not fill the actual default map to four participants"
	for peer_id in current.players:
		if peer_id >= 0: continue
		var controller = current.bot_manager.get_bot_controller(peer_id)
		if not is_instance_valid(controller) or current.players[peer_id].bot_personality != "BALANCED":
			return "A default bot lacks its real BALANCED policy controller"
	return true

func test_hosted_explicit_zero_remains_human_only_after_authority_configuration() -> Variant:
	game_instance.end_match()
	var options := preload("res://shared/runtime_config.gd").parse_arguments([
		"--room-fill-to=0"], "res://main_server.tscn")
	var prepared: Dictionary = server._prepare_shared_game(options)
	if not prepared.accepted: return "Explicit zero could not prepare its room"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	if not current.add_player(901, "HumanOnlyVisitor").accepted or not current.start_room_countdown().accepted:
		return "The explicit human-only room could not start"
	current._physics_process(3.1)
	var state: Dictionary = current.get_room_capacity()
	return assert_true(current.match_active and state.humans == 1 and state.bots == 0
		and state.bot_fill.target == 0 and current.bot_manager._bot_players.is_empty(),
		"Explicit zero must reach the authority without falling back to four")

func test_fresh_room_after_a_finished_bot_round_applies_the_default_again() -> Variant:
	game_instance.end_match()
	if not server._prepare_shared_game().accepted: return "First default room could not prepare"
	var first = server.active_games["shared_game"]
	first.set_physics_process(false)
	first.bot_manager.set_physics_process(false)
	if not first.add_player(901, "FirstVisitor").accepted or not first.start_room_countdown().accepted:
		return "First default room could not start"
	first._physics_process(3.1)
	if first.get_room_capacity().bots != 3: return "First default round did not spawn its three bots"
	first.end_match()
	if not server._prepare_shared_game().accepted: return "Next default room could not prepare"
	var next = server.active_games["shared_game"]
	next.set_physics_process(false)
	next.bot_manager.set_physics_process(false)
	if not next.add_player(902, "NextVisitor").accepted or not next.start_room_countdown().accepted:
		return "Next default room could not start"
	next._physics_process(3.1)
	var state: Dictionary = next.get_room_capacity()
	return assert_true(next.get_instance_id() != first.get_instance_id() and next.match_active
		and state.humans == 1 and state.bots == 3 and state.bot_fill.applied,
		"A completed bot roster must not suppress filling in the next fresh authority")

func test_live_room_is_never_replaced_by_a_new_join() -> Variant:
	var old_id := game_instance.get_instance_id()
	var prepared: Dictionary = server._prepare_shared_game()
	return assert_true(prepared.accepted and server.active_games.size() == 1
		and server.active_games["shared_game"].get_instance_id() == old_id
		and game_instance.match_active,
		"New visitors must not reset an active match")

func test_completed_clients_keep_their_result_until_authoritative_handoff() -> Variant:
	if not game_instance.add_player(-901, "ExistingVisitor").accepted: return "Fixture admission failed"
	server.player_to_game[-901] = "shared_game"
	game_instance.end_match()
	var result: Dictionary = game_instance.get_round_result()
	var prepared: Dictionary = server._prepare_shared_game()
	return assert_true(prepared.accepted and server.active_games["shared_game"] == game_instance
		and server.player_to_game[-901] == "shared_game" and game_instance.get_round_result() == result,
		"A late arrival must not strand connected clients in a retired terminal room")

func test_pending_content_transfer_prevents_room_replacement() -> Variant:
	game_instance.end_match()
	server._pending_content = {901: {"session_id": "fixture"}}
	var prepared: Dictionary = server._prepare_shared_game()
	return assert_true(prepared.accepted and server.active_games.size() == 1
		and server.active_games["shared_game"] == game_instance
		and server._pending_content[901].session_id == "fixture",
		"An in-flight exact-content transfer must not change authority beneath its client")

func test_last_client_leave_releases_all_bots_and_returns_to_waiting() -> Variant:
	game_instance.end_match()
	if not server.quick_start_game(-901, "ExistingVisitor").accepted: return "Fixture admission failed"
	var previous = server.active_games["shared_game"]
	previous.set_physics_process(false)
	previous.bot_manager.set_physics_process(false)
	previous._physics_process(3.1)
	if previous.get_room_capacity().bots != 3 or previous.bot_manager._bot_players.size() != 3:
		return "Control room did not contain the real three-bot roster"
	server._on_player_disconnected(-901)
	if previous.process_mode != Node.PROCESS_MODE_DISABLED: return "An empty room kept simulating"
	server._clear_empty_shared_room(previous)
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	return assert_true(current != previous and not server.player_to_game.has(-901)
		and current.get_round_state().phase == "waiting" and current.players.is_empty()
		and current.bot_manager._bot_players.is_empty() and previous.bot_manager._bot_players.is_empty(),
		"Last departure must clean the complete old world and leave no bot-only countdown")

func test_same_connected_human_receives_two_fresh_rounds() -> Variant:
	game_instance.end_match()
	server._server_room_options = {"room_countdown": 1, "room_duration": 12, "room_intermission": 1}
	if not server.quick_start_game(-901, "ContinuousVisitor").accepted: return "First admission failed"
	var first = server.active_games["shared_game"]
	first.set_physics_process(false)
	first.bot_manager.set_physics_process(false)
	var original_map: Array = first.game_map.duplicate(true)
	var first_epoch: int = first.round_epoch
	for cycle in range(2):
		var current = server.active_games["shared_game"]
		current.set_physics_process(false)
		current.bot_manager.set_physics_process(false)
		current._physics_process(1.1)
		if not current.match_active or current.get_room_capacity().bots != 3: return "A cycle did not start with accepted real bots"
		current.game_map[1][1] = 3
		current.hurry_mode_active = true
		current.hurry_blocks.append(Vector2i(1, 1))
		current.active_explosion_tiles["1,1"] = 90000.0
		current.players[-901].die()
		current.end_match("timeout")
		if current.get_round_state().phase != "results": return "No authoritative results phase"
		current._physics_process(current.results_duration + 0.01)
		var advanced: Dictionary = server._advance_shared_round(current)
		if not advanced.accepted: return "Fresh authority handoff refused"
		var next = server.active_games["shared_game"]
		next.set_physics_process(false)
		next.bot_manager.set_physics_process(false)
		if next == current or next.round_epoch != first_epoch + cycle + 1: return "Fresh authority/epoch missing"
		if server.player_to_game[-901] != "shared_game" or not next.players.has(-901) or next.players[-901].is_dead: return "Same connected human was not restored"
		if next.game_map != original_map or not next.bombs.is_empty() or not next.eggs.is_empty() or not next.tirras.is_empty() or not next.hurry_blocks.is_empty() or not next.active_explosion_tiles.is_empty() or next.hurry_mode_active: return "Stale world state survived the handoff"
		if not next.get_round_result().is_empty() or next.get_round_state().phase != "countdown": return "Result/start state was not reset"
	return true

func test_late_human_spectates_then_replaces_bot_seat_at_next_countdown() -> Variant:
	game_instance.end_match()
	server._server_room_options = {"room_seats": 4, "room_countdown": 1}
	if not server.quick_start_game(-901, "FirstHuman").accepted: return "First admission failed"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	current._physics_process(1.1)
	var arrival: Dictionary = server.quick_start_game(-902, "LaterHuman")
	if not arrival.accepted or not arrival.get("spectator", false) or current.players.has(-902) or not current.spectators.has(-902): return "Late visitor entered a live blast/was rejected by a bot-filled roster"
	current.end_match()
	current._physics_process(current.results_duration + 0.01)
	var advanced: Dictionary = server._advance_shared_round(current)
	if not advanced.accepted: return "Handoff failed"
	var next = server.active_games["shared_game"]
	next.set_physics_process(false)
	next.bot_manager.set_physics_process(false)
	next._physics_process(1.1)
	return assert_true(next.players.has(-901) and next.players.has(-902) and next.spectators.is_empty()
		and next.get_room_capacity().humans == 2 and next.get_room_capacity().bots == 2,
		"Next countdown must admit connected waiting humans before filling remaining bot seats")

func test_stale_authority_cannot_advance_or_reset_the_current_room() -> Variant:
	game_instance.end_match()
	server._prepare_shared_game()
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	var result: Dictionary = server._advance_shared_round(game_instance)
	return assert_true(not result.accepted and result.reason == "stale_authority" and server.active_games["shared_game"] == current)

func test_console_registration_survives_room_replacement_without_duplicate_commands() -> Variant:
	game_instance._do_register_console_commands()
	var commands := server.get_node("ConsoleCommands")
	var before := LimboConsole.get_command_names()
	game_instance.end_match()
	server._prepare_shared_game()
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	current._do_register_console_commands()
	return assert_true(server.get_node("ConsoleCommands") == commands
		and commands.game_instance_ref == current
		and LimboConsole.get_command_names() == before,
		"Global console callables must stay valid and target the new authority")

func test_stale_round_input_cannot_drive_the_fresh_same_peer_actor() -> Variant:
	game_instance.end_match()
	if not server.quick_start_game(-901, "InputVisitor").accepted: return "Admission failed"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	current._physics_process(3.1)
	var stale: Dictionary = server._dispatch_room_input(-901, {"round_epoch": current.round_epoch - 1, "input_x": 1.0, "place_bomb": true})
	if stale.accepted or stale.reason != "stale_round" or not current.bombs.is_empty() or current.players[-901].input_direction != Vector2.ZERO:
		return "A stale previous-round packet reached the new actor"
	var accepted: Dictionary = server._dispatch_room_input(-901, {"round_epoch": current.round_epoch, "input_x": 1.0, "place_bomb": true})
	return assert_true(accepted.accepted and current.bombs.size() == 1 and current.players[-901].input_direction.x > 0.0,
		"A current-round packet must still drive real authoritative movement and placement")

func test_new_arrival_during_deferred_empty_cleanup_gets_a_live_fresh_countdown() -> Variant:
	game_instance.end_match()
	if not server.quick_start_game(-901, "LeavingVisitor").accepted: return "First admission failed"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	current._physics_process(3.1)
	server._on_player_disconnected(-901)
	if not server.quick_start_game(-902, "RacingVisitor").accepted: return "Racing admission failed"
	server._clear_empty_shared_room(current)
	var next = server.active_games["shared_game"]
	next.set_physics_process(false)
	next.bot_manager.set_physics_process(false)
	return assert_true(next != current and next.process_mode != Node.PROCESS_MODE_DISABLED
		and next.players.has(-902) and next.get_round_state().phase == "countdown",
		"An arrival between last departure and deferred teardown must not remain in a disabled authority")

func test_results_interval_and_pending_content_gate_the_actual_next_epoch() -> Variant:
	game_instance.end_match()
	if not server.quick_start_game(-901, "TransferVisitor").accepted: return "Admission failed"
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	current._physics_process(3.1)
	current.end_match()
	var early: Dictionary = server._advance_shared_round(current)
	if early.accepted or early.reason != "intermission_active" or server.active_games["shared_game"] != current:
		return "A handoff bypassed the authoritative result interval"
	server._pending_content = {902: {"session_id": "fixture", "deadline": Time.get_ticks_msec() + 10000}}
	current.set_content_waiting(902, true)
	current._physics_process(current.results_duration + 0.01)
	var pending: Dictionary = server._advance_shared_round(current)
	if pending.accepted or pending.reason != "content_not_ready" or current._restart_requested:
		return "Pending exact content did not hold/rearm the actual handoff"
	server._pending_content.clear()
	current.set_content_waiting(902, false)
	var advanced: Dictionary = server._advance_shared_round(current)
	var next = server.active_games["shared_game"]
	next.set_physics_process(false)
	next.bot_manager.set_physics_process(false)
	return assert_true(advanced.accepted and next != current and next.players.has(-901)
		and next.round_epoch == current.round_epoch + 1 and next.get_round_state().phase == "countdown",
		"Completing the bounded content wait must resume the same human in a fresh authority")

func test_short_battles_keep_hurry_in_the_final_third() -> Variant:
	for duration in [12, 20, 180, 300]:
		var built: Dictionary = server._build_shared_game({"room_duration": duration})
		if not built.accepted: return "Could not configure trusted battle duration"
		var room = built.game
		room.set_physics_process(false)
		room.bot_manager.set_physics_process(false)
		var correct: bool = is_equal_approx(room.hurry_trigger_time, minf(60.0, duration / 3.0))
		room.queue_free()
		if not correct: return "Short battle started in hurry or changed the normal final-minute rule"
	return true
