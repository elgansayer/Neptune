extends "res://tests/bot_test_suite.gd"

var bomber: ServerPlayer
var victim: ServerPlayer
var companion: ServerPlayer

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	game_instance.active_explosion_tiles.clear()
	game_instance._flame_damage_sources.clear()
	game_instance._elimination_events.clear()
	game_instance._elimination_sequence = 0
	game_instance._discarded_eliminations = 0
	game_instance.current_time_msec = 100.0
	game_instance.simulation_tick = 7
	await game_instance.add_player(501, "Owner", _world(4, 4), false, "", "owner")
	await game_instance.add_player(502, "Victim", _world(10, 8), false, "", "victim")
	await game_instance.add_player(-503, "Bot", _world(12, 10), true, "BALANCED", "bot")
	bomber = game_instance.players[501]
	victim = game_instance.players[502]
	companion = game_instance.players[-503]
	for actor in [bomber, victim, companion]:
		actor.set_physics_process(false)
	game_instance.match_active = true

func teardown_test() -> void:
	if game_instance.elimination_recorded.is_connected(_mutate_signal):
		game_instance.elimination_recorded.disconnect(_mutate_signal)
	await super()

func _world(x: int, y: int) -> Vector2:
	return BotTestHelpers.tile_to_world_center(Vector2i(x, y))

func _bomb(actor: ServerPlayer, tile: Vector2i = Vector2i(4, 4)) -> ServerBomb:
	actor.position = _world(tile.x, tile.y)
	var receipt: Dictionary = game_instance.place_bomb(actor)
	if not receipt.accepted:
		push_error("Elimination fixture placement refused: " + str(receipt))
		return null
	var bomb: ServerBomb = game_instance.bombs[receipt.bomb_ids[0]]
	bomb.set_physics_process(false)
	return bomb

func _ignite(bomb: ServerBomb) -> void:
	bomb.explode()
	bomb._physics_process(0.1) # Actual progressive centre expansion and signal binding.

func _events() -> Array:
	return game_instance.get_elimination_event_state().events

func test_actual_progressive_blast_records_owner_victim_and_clock() -> Variant:
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	victim.position = _world(4, 4)
	_ignite(bomb)
	var events := _events()
	if events.size() != 1: return "Actual progressive blast must record one elimination"
	var event: Dictionary = events[0]
	return assert_true(victim.is_dead and event.schema == 1 and event.sequence == 1
		and event.simulation_tick == 7 and event.server_time_msec == 100.0
		and event.tile == [4, 4]
		and event.victim.peer_id == 502 and event.victim.type == "human"
		and event.source.bomb_id == bomb.bomb_id and event.source.owner.participant_id == "owner"
		and event.self_ko == false, "Real damage lost causal ownership, victim or simulation clock")

func test_own_bomb_is_a_self_ko_without_a_proximity_guess() -> Variant:
	var bomb := _bomb(bomber)
	_ignite(bomb)
	var events := _events()
	return assert_true(events.size() == 1 and events[0].self_ko == true
		and events[0].source.owner.incarnation == events[0].victim.incarnation,
		"An actual own-bomb hit must identify the same admitted actor")

func test_lingering_source_survives_bomb_and_owner_removal() -> Variant:
	var bomb := _bomb(bomber)
	var id := bomb.bomb_id
	bomber.position = _world(12, 4)
	_ignite(bomb)
	game_instance.remove_player(bomber.peer_id)
	bomb.queue_free()
	await get_tree().process_frame
	game_instance.current_time_msec = 250.0
	victim.position = _world(4, 4)
	game_instance._check_explosion_damage()
	var events := _events()
	return assert_true(events.size() == 1 and events[0].source.bomb_id == id
		and events[0].source.owner.participant_id == "owner" and events[0].self_ko == false,
		"Lingering flame must retain its source without a live owner or bomb node")

func test_reused_peer_id_does_not_receive_old_bomb_identity() -> Variant:
	var bomb := _bomb(bomber)
	var old_incarnation: int = bomber.get_meta("combat_incarnation")
	bomber.position = _world(12, 4)
	_ignite(bomb)
	game_instance.remove_player(501)
	await get_tree().process_frame
	var joined: Dictionary = await game_instance.add_player(501, "Replacement", _world(8, 5), false, "", "replacement")
	if not joined.accepted: return "Peer-reuse control failed admission"
	var replacement: ServerPlayer = game_instance.players[501]
	replacement.set_physics_process(false)
	replacement.position = _world(4, 4)
	game_instance._check_explosion_damage()
	var events := _events()
	return assert_true(events.size() == 1 and events[0].victim.peer_id == 501
		and events[0].source.owner.peer_id == 501 and events[0].self_ko == false
		and events[0].source.owner.incarnation == old_incarnation
		and events[0].victim.incarnation != old_incarnation
		and events[0].source.owner.participant_id == "owner",
		"Peer reuse changed historical ownership or falsely classified a self-KO")

func test_invincibility_does_not_emit_an_elimination() -> Variant:
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	victim.position = _world(4, 4)
	victim.is_immortal = true
	_ignite(bomb)
	game_instance._check_explosion_damage()
	if victim.is_dead or not _events().is_empty(): return "Protected hit was reported as an elimination"
	victim.is_immortal = false
	game_instance._check_explosion_damage()
	return assert_true(victim.is_dead and _events().size() == 1, "Unprotected control must still die to the same real flame")

func test_mount_absorption_does_not_emit_an_elimination() -> Variant:
	var mount := Node2D.new() # Visual-free fixture; real ServerPlayer.dismount_tirra executes.
	victim.add_child(mount)
	victim.mounted_tirra = mount
	victim.is_mounted = true
	victim.last_move_direction = Vector2.DOWN
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	victim.position = _world(4, 4)
	_ignite(bomb)
	var protected := not victim.is_dead and not victim.is_mounted and victim.is_immortal and _events().is_empty()
	await get_tree().create_timer(1.05).timeout # Drain the production mount-removal callback.
	return assert_true(protected, "A real mount-protection transition must not count as player elimination")

func test_duplicate_callbacks_and_lingering_checks_emit_once() -> Variant:
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	victim.position = _world(4, 4)
	_ignite(bomb)
	game_instance._on_explosion_expanded(bomb, [Vector2i(4, 4)])
	game_instance._check_explosion_damage()
	return assert_true(_events().size() == 1, "Repeated actual damage callbacks duplicated an elimination")

func _overlapping_flames() -> Array:
	var first := _bomb(bomber)
	bomber.position = _world(12, 4)
	_ignite(first)
	game_instance.current_time_msec = 200.0
	var second := _bomb(companion, Vector2i(5, 4))
	companion.position = _world(12, 10)
	_ignite(second)
	second._physics_process(0.1) # Its actual left arm overlaps the first centre.
	return [first.bomb_id, second.bomb_id]

func test_overlapping_live_flames_use_earliest_observed_live_source() -> Variant:
	var ids := _overlapping_flames()
	game_instance.current_time_msec = 300.0
	victim.position = _world(4, 4)
	game_instance._check_explosion_damage()
	var events := _events()
	return assert_true(events.size() == 1 and events[0].source.bomb_id == ids[0], "Overlap source ordering is not deterministic")

func test_expired_overlap_source_cannot_steal_later_flame_credit() -> Variant:
	var ids := _overlapping_flames()
	game_instance.current_time_msec = 101.0 + GameConfig.EXPLOSION_DURATION * 1000.0
	victim.position = _world(4, 4)
	game_instance._check_explosion_damage()
	var events := _events()
	return assert_true(events.size() == 1 and events[0].source.bomb_id == ids[1]
		and events[0].source.owner.type == "bot", "Expired source hid a still-burning bot-owned flame")

func test_expired_flame_cannot_eliminate_or_retain_sources() -> Variant:
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	_ignite(bomb)
	game_instance.current_time_msec = 101.0 + GameConfig.EXPLOSION_DURATION * 1000.0
	victim.position = _world(4, 4)
	game_instance._check_explosion_damage()
	return assert_true(not victim.is_dead and _events().is_empty()
		and game_instance._flame_damage_sources.is_empty(), "Expired flames killed or leaked attribution state")

func test_flame_remains_lethal_at_existing_inclusive_expiry_boundary() -> Variant:
	var bomb := _bomb(bomber)
	bomber.position = _world(12, 4)
	_ignite(bomb)
	game_instance.current_time_msec = 100.0 + GameConfig.EXPLOSION_DURATION * 1000.0
	victim.position = _world(4, 4)
	game_instance._check_explosion_damage()
	return assert_true(victim.is_dead and _events().size() == 1, "Attribution changed the existing inclusive flame boundary")

func test_unknown_fixture_flames_are_not_guessed_as_opponent_kills() -> Variant:
	var tile := victim.get_tile_position()
	game_instance.active_explosion_tiles["%d,%d" % [tile.x, tile.y]] = 500.0
	game_instance._check_explosion_damage()
	var events := _events()
	return assert_true(events.size() == 1 and events[0].source.kind == "unknown_flame"
		and events[0].self_ko == null, "Unknown provenance was fabricated as self/opponent credit")

func test_hurry_block_is_environmental_in_both_lookup_paths() -> Variant:
	var tile := victim.get_tile_position()
	game_instance._spawn_hurry_block(tile)
	var bot_tile := companion.get_tile_position()
	game_instance._spawn_hurry_block(bot_tile, {bot_tile: [companion]}, {})
	var events := _events()
	return assert_true(events.size() == 2 and events[0].source.kind == "hurry_block"
		and events[1].source.kind == "hurry_block" and events[0].self_ko == null
		and events[1].victim.type == "bot", "Hurry lookup paths must retain explicit environmental causes")

func test_one_blast_records_all_simultaneous_victims_once() -> Variant:
	var bomb := _bomb(bomber)
	victim.position = bomber.position
	companion.position = bomber.position
	_ignite(bomb)
	var events := _events()
	if events.size() != 3: return "One blast must retain all three deaths, including callbacks after round end"
	var peers := {}
	for event in events:
		peers[event.victim.peer_id] = true
		if event.simulation_tick != 7: return "Simultaneous events lost their common tick"
	return assert_true(peers.size() == 3 and events[0].sequence == 1 and events[2].sequence == 3,
		"Simultaneous deaths duplicated a victim or event sequence")

func _mutate_signal(event: Dictionary) -> void:
	event.source.kind = "tampered"
	event.victim.incarnation = -1

func test_signal_and_export_are_detached_from_retained_history() -> Variant:
	game_instance.elimination_recorded.connect(_mutate_signal, CONNECT_ONE_SHOT)
	var bomb := _bomb(bomber)
	_ignite(bomb)
	var events := _events()
	if events.size() != 1: return "Signal control did not observe a real elimination"
	events[0].source.owner.clear()
	var retained := _events()
	return assert_true(retained[0].source.kind == "bomb" and retained[0].victim.incarnation > 0
		and not retained[0].source.owner.is_empty(), "A diagnostic consumer changed authoritative history")

func test_history_is_bounded_and_reports_discarded_sequences() -> Variant:
	for index in range(game_instance.MAX_RETAINED_ELIMINATIONS + 3):
		victim.is_dead = false # Explicit repeated-life stress fixture, not a public respawn API.
		if not game_instance._apply_player_damage(victim, {"kind": "hurry_block", "owner": {}}):
			return "Actual living-to-dead stress transition was lost"
	var state: Dictionary = game_instance.get_elimination_event_state()
	return assert_true(state.events.size() == 256 and state.discarded == 3
		and state.last_sequence == 259 and state.events[0].sequence == 4,
		"Bounded history hid a gap or grew beyond its diagnostic budget")

func test_foreign_actor_cannot_impersonate_a_registered_peer() -> Variant:
	var foreign := ServerPlayer.new()
	foreign.peer_id = victim.peer_id
	var accepted := game_instance._apply_player_damage(foreign, {"kind": "hurry_block", "owner": {}})
	var intact := not accepted and not foreign.is_dead and not victim.is_dead and _events().is_empty()
	foreign.free()
	return assert_true(intact, "Foreign actor identity must not mutate the room or produce an elimination")
