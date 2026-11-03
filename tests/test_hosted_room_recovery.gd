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
		"lobby": server.lobby_manager}
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
	current._physics_process(1.1)
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
	current._physics_process(1.1)
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
	current._physics_process(1.1)
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
	first._physics_process(1.1)
	if first.get_room_capacity().bots != 3: return "First default round did not spawn its three bots"
	first.end_match()
	if not server._prepare_shared_game().accepted: return "Next default room could not prepare"
	var next = server.active_games["shared_game"]
	next.set_physics_process(false)
	next.bot_manager.set_physics_process(false)
	if not next.add_player(902, "NextVisitor").accepted or not next.start_room_countdown().accepted:
		return "Next default room could not start"
	next._physics_process(1.1)
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

func test_completed_clients_keep_their_result_and_membership() -> Variant:
	server.player_to_game[-901] = "shared_game"
	game_instance.end_match()
	var result: Dictionary = game_instance.get_round_result()
	var prepared: Dictionary = server._prepare_shared_game()
	var retired_id: String = server.player_to_game[-901]
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	return assert_true(prepared.accepted and retired_id != "shared_game"
		and server.active_games[retired_id] == game_instance
		and game_instance.game_id == retired_id
		and game_instance.get_round_result() == result,
		"A new room must preserve existing clients' terminal result")

func test_pending_content_transfer_prevents_room_replacement() -> Variant:
	game_instance.end_match()
	server._pending_content = {901: {"session_id": "fixture"}}
	var prepared: Dictionary = server._prepare_shared_game()
	return assert_true(prepared.accepted and server.active_games.size() == 1
		and server.active_games["shared_game"] == game_instance
		and server._pending_content[901].session_id == "fixture",
		"An in-flight exact-content transfer must not change authority beneath its client")

func test_retired_room_is_released_after_its_last_client_leaves() -> Variant:
	server.player_to_game[-901] = "shared_game"
	game_instance.end_match()
	var prepared: Dictionary = server._prepare_shared_game()
	var retired_id: String = server.player_to_game[-901]
	var current = server.active_games["shared_game"]
	current.set_physics_process(false)
	current.bot_manager.set_physics_process(false)
	server._on_player_disconnected(-901)
	return assert_true(prepared.accepted and not server.active_games.has(retired_id)
		and not server.player_to_game.has(-901) and server.active_games.size() == 1,
		"Disconnected completed clients must not leak retired authorities")

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
