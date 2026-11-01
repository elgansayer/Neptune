extends "res://tests/bot_test_suite.gd"

var first: ServerPlayer
var second: ServerPlayer
var third: ServerPlayer
var terminal_signals: Array[String] = []
var terminal_observations: Array[Dictionary] = []

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	# Each case owns a fresh production authority and its late physics publisher.
	await super.setup_suite()
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super.setup_test()
	# These are local simulation actors, with no invented human network peers.
	# The real publisher can therefore build snapshots at any render cadence.
	await game_instance.add_player(601, "First", _world(4, 4), true, "BALANCED")
	await game_instance.add_player(602, "Second", _world(10, 8), true, "BALANCED")
	await game_instance.add_player(-603, "Third", _world(12, 10), true, "BALANCED")
	first = game_instance.players[601]
	second = game_instance.players[602]
	third = game_instance.players[-603]
	for actor in [first, second, third]:
		actor.set_physics_process(false)
	terminal_signals.clear()
	terminal_observations.clear()
	game_instance.game_ended.connect(_record_result)
	game_instance.match_active = true
	game_instance.current_time_msec = 100.0
	game_instance.simulation_tick = 7
	game_instance.last_sync_time = 0.0

func teardown_test() -> void:
	await super.teardown_test()
	await super.teardown_suite()

func _record_result(winner: String) -> void:
	terminal_signals.append(winner)
	var alive := 0
	for actor in game_instance.players.values():
		if not actor.is_dead: alive += 1
	terminal_observations.append({"alive": alive, "events": game_instance.get_elimination_event_state().events.size()})

func _world(x: int, y: int) -> Vector2:
	return BotTestHelpers.tile_to_world_center(Vector2i(x, y))

func _bomb(actor: ServerPlayer, cell: Vector2i) -> ServerBomb:
	actor.position = _world(cell.x, cell.y)
	var receipt: Dictionary = game_instance.place_bomb(actor)
	if not receipt.accepted:
		push_error("Round fixture placement refused: " + str(receipt))
		return null
	var bomb: ServerBomb = game_instance.bombs[receipt.bomb_ids[0]]
	bomb.set_physics_process(false)
	return bomb

func _ignite(bomb: ServerBomb) -> void:
	bomb.explode()
	bomb._physics_process(0.1)

func _settle() -> void:
	# The existing production late publisher callback, including ticks with no send.
	game_instance._publish_due_state()

func test_one_blast_killing_everyone_emits_only_a_draw_after_the_tick() -> Variant:
	var bomb := _bomb(first, Vector2i(4, 4))
	second.position = first.position
	third.position = first.position
	_ignite(bomb)
	if not terminal_signals.is_empty(): return "One blast emitted an intermediate winner before all victims were processed"
	_settle()
	return assert_true(first.is_dead and second.is_dead and third.is_dead
		and terminal_signals == [""] and game_instance.winner_id == ""
		and not game_instance.match_active, "All same-blast victims must produce one draw")

func test_independent_bombs_in_one_tick_do_not_award_the_second_victim() -> Variant:
	game_instance.remove_player(-603)
	var left := _bomb(first, Vector2i(4, 4))
	var right := _bomb(second, Vector2i(10, 8))
	_ignite(left)
	if not terminal_signals.is_empty(): return "First of two same-tick blasts awarded a winner"
	_ignite(right)
	_settle()
	return assert_true(first.is_dead and second.is_dead and terminal_signals == [""])

func test_lingering_flames_settle_after_all_occupants() -> Variant:
	game_instance.active_explosion_tiles["4,4"] = 1000.0
	second.position = first.position
	third.position = first.position
	game_instance._check_explosion_damage()
	if not terminal_signals.is_empty(): return "Lingering-flame iteration emitted an intermediate winner"
	_settle()
	return assert_true(terminal_signals == [""] and game_instance.get_elimination_event_state().events.size() == 3)

func test_hurry_batch_finishes_all_crushes_before_settlement() -> Variant:
	game_instance.hurry_spawn_pattern.assign([Vector2i(4, 4), Vector2i(10, 8), Vector2i(12, 10)])
	game_instance._process_hurry_mode(game_instance.hurry_spawn_interval * 3.0 + 0.001)
	if not terminal_signals.is_empty(): return "Hurry batch awarded a survivor before later blocks crushed them"
	_settle()
	return assert_true(first.is_dead and second.is_dead and third.is_dead and terminal_signals == [""])

func test_direct_hurry_callback_also_uses_the_completed_tick() -> Variant:
	second.position = first.position
	third.position = first.position
	game_instance._spawn_hurry_block(Vector2i(4, 4))
	if not terminal_signals.is_empty(): return "Direct hurry lookup settled inside its victim loop"
	_settle()
	return assert_true(terminal_signals == [""])

func test_single_survivor_settles_without_waiting_for_network_send() -> Variant:
	var bomb := _bomb(first, Vector2i(4, 4))
	second.position = first.position
	third.position = _world(12, 10)
	_ignite(bomb)
	if not terminal_signals.is_empty(): return "Survivor result was emitted inside damage processing"
	_settle()
	return assert_true(terminal_signals == ["-603"] and game_instance.last_sync_time == 0.0,
		"Settlement must execute even while the network send interval is not due")

func test_timeout_and_final_blast_use_the_same_tick_roster() -> Variant:
	var bomb := _bomb(first, Vector2i(4, 4))
	second.position = first.position
	third.position = first.position
	game_instance.hurry_mode_active = true # Preserve the explicit empty hurry pattern.
	game_instance.match_time_remaining = 0.01
	game_instance._physics_process(0.02)
	if not terminal_signals.is_empty(): return "Timeout settled before this tick's bomb phase"
	_ignite(bomb)
	_settle()
	return assert_true(terminal_signals == [""] and first.is_dead and second.is_dead and third.is_dead
		and game_instance.get_elimination_event_state().events.size() == 3)

func test_timeout_with_multiple_survivors_is_one_draw() -> Variant:
	game_instance.hurry_mode_active = true
	game_instance.match_time_remaining = 0.01
	game_instance._physics_process(0.02)
	if not terminal_signals.is_empty(): return "Timer callback emitted a result before the late phase"
	_settle()
	_settle()
	game_instance.end_match()
	return assert_true(terminal_signals == [""] and game_instance.match_time_remaining == 0.0)

func test_disconnects_request_one_late_survivor_result() -> Variant:
	game_instance.remove_player(601)
	game_instance.remove_player(602)
	if not terminal_signals.is_empty(): return "Disconnect resolved before the tick boundary"
	_settle()
	game_instance.remove_player(-603)
	_settle()
	return assert_true(terminal_signals == ["-603"] and game_instance.winner_id == "-603",
		"A later disconnect must not replace the committed survivor result")

func test_all_players_disconnect_before_settlement_is_a_draw() -> Variant:
	for peer in [601, 602, -603]:
		game_instance.remove_player(peer)
	_settle()
	return assert_true(terminal_signals == [""])

func test_disconnect_after_a_same_tick_blast_does_not_leave_a_false_winner() -> Variant:
	game_instance.remove_player(601)
	_ignite(_bomb(second, Vector2i(10, 8)))
	if not terminal_signals.is_empty(): return "Blast resolved before the last survivor's same-tick disconnect"
	game_instance.remove_player(-603)
	_settle()
	return assert_true(second.is_dead and terminal_signals == [""])

func test_nonterminal_death_does_not_consume_a_later_end_request() -> Variant:
	_ignite(_bomb(first, Vector2i(4, 4)))
	_settle()
	if not game_instance.match_active or not terminal_signals.is_empty():
		return "Two remaining survivors ended the match"
	_ignite(_bomb(second, Vector2i(10, 8)))
	_settle()
	return assert_true(terminal_signals == ["-603"])

func test_explicit_stop_commits_before_a_reentrant_signal_listener() -> Variant:
	if not game_instance.has_method("get_round_result"): return "Missing terminal result snapshot"
	var observed: Array = []
	game_instance.game_ended.connect(func(_winner):
		observed.append(game_instance.call("get_round_result"))
		game_instance.end_match()
	, Object.CONNECT_ONE_SHOT)
	game_instance.end_match()
	game_instance.end_match()
	_settle()
	return assert_true(terminal_signals == [""] and observed.size() == 1
		and observed[0].reason == "stopped" and observed[0].survivors == ["-603", "601", "602"],
		"An explicit trusted stop commits once before notifying any consumer")

func test_timeout_reason_wins_when_the_last_survivor_check_is_also_pending() -> Variant:
	if not game_instance.has_method("get_round_result"): return "Missing terminal result snapshot"
	game_instance.remove_player(601)
	game_instance.remove_player(602)
	game_instance.hurry_mode_active = true
	game_instance.match_time_remaining = 0.01
	game_instance._physics_process(0.02)
	_settle()
	return assert_true(terminal_signals == ["-603"] and game_instance.call("get_round_result").reason == "timeout")

func test_absent_disconnect_and_single_seat_start_do_not_end_a_round() -> Variant:
	game_instance.match_active = false
	game_instance.remove_player(602)
	game_instance.remove_player(-603)
	game_instance.match_active = true
	game_instance.remove_player(99999)
	_settle()
	game_instance._physics_process(0.02)
	_settle()
	return assert_true(terminal_signals.is_empty() and game_instance.match_active,
		"No roster change or death means no implicit last-survivor end in a single-seat room")

func test_invulnerable_hit_does_not_end_single_seat_play() -> Variant:
	game_instance.match_active = false
	game_instance.remove_player(602)
	game_instance.remove_player(-603)
	game_instance.match_active = true
	first.set_immortal(true)
	_ignite(_bomb(first, Vector2i(4, 4)))
	_settle()
	return assert_true(not first.is_dead and terminal_signals.is_empty() and game_instance.match_active)

func test_late_damage_cannot_kill_the_committed_winner_or_emit_more_events() -> Variant:
	game_instance.remove_player(601)
	game_instance.remove_player(602)
	game_instance.check_match_end_condition()
	_settle()
	if terminal_signals != ["-603"]: return "Fixture failed to commit its survivor"
	var sequence: int = game_instance.get_elimination_event_state().last_sequence
	game_instance.active_explosion_tiles["12,10"] = 1000.0
	game_instance._check_explosion_damage()
	var bomb: ServerBomb = game_instance.ServerBombScene.instantiate()
	bomb.bomb_id = "late"
	game_instance.add_child(bomb)
	bomb.set_physics_process(false)
	game_instance._on_explosion_expanded(bomb, [Vector2i(12, 10)])
	game_instance._spawn_hurry_block(Vector2i(12, 10))
	_settle()
	return assert_true(not third.is_dead and terminal_signals == ["-603"]
		and game_instance.get_elimination_event_state().last_sequence == sequence,
		"Delayed lingering/progressive/hurry damage must not mutate a finished round's survivor or events")

func test_terminal_snapshot_is_detached_and_captures_the_completed_tick() -> Variant:
	if not game_instance.has_method("get_round_result"): return "Missing terminal result snapshot"
	if not game_instance.call("get_round_result").is_empty(): return "A live round already has a terminal result"
	game_instance.remove_player(601)
	game_instance.remove_player(602)
	_settle()
	var result: Dictionary = game_instance.call("get_round_result")
	if result.schema != 1 or result.simulation_tick != 7 or result.server_time_msec != 100.0 \
		or result.winner_id != "-603" or result.survivors != ["-603"] or result.reason != "survivors":
		return "Committed result lost the completed tick, survivor roster or reason"
	result.survivors.clear()
	result.winner_id = "forged"
	return assert_true(game_instance.call("get_round_result").winner_id == "-603"
		and game_instance.call("get_round_result").survivors == ["-603"])

func test_actual_scene_tree_phases_settle_a_blast_at_the_timeout_tick() -> Variant:
	var bomb := _bomb(first, Vector2i(4, 4))
	second.position = first.position
	third.position = first.position
	game_instance.hurry_mode_active = true
	game_instance.match_time_remaining = 0.001
	bomb.explode()
	bomb.explosion_growth_timer = bomb.EXPLOSION_GROWTH_INTERVAL
	game_instance.set_physics_process(true)
	bomb.set_physics_process(true)
	await get_tree().physics_frame
	await get_tree().process_frame
	game_instance.set_physics_process(false)
	bomb.set_physics_process(false)
	return assert_true(first.is_dead and second.is_dead and third.is_dead and terminal_signals == [""]
		and game_instance.get_elimination_event_state().events.size() == 3
		and terminal_observations == [{"alive": 0, "events": 3}],
		"Actual -200 clock, -150 bomb and +100 settlement must expose all final-tick damage to signal observers")
