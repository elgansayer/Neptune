extends "res://tests/bot_test_suite.gd"

const STARTS := [Vector2i(2, 2), Vector2i(4, 2), Vector2i(6, 2)]

func setup_test() -> void:
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = false
	game_instance.spawn_points = []
	for cell in STARTS:
		game_instance.spawn_points.append(BotTestHelpers.tile_to_world_center(cell))

func teardown_test() -> void:
	await super()
	game_instance.reset_spawn_reservations()
	game_instance.active_explosion_tiles.clear()

func _admit(peer_id: int, username: String = "SpawnFixture") -> Variant:
	var receipt = await game_instance.add_player(peer_id, username, Vector2.ZERO, true, "fixture")
	if game_instance.players.has(peer_id): game_instance.players[peer_id].set_physics_process(false)
	return receipt

func test_declared_spawn_control_is_distinct() -> Variant:
	var positions := {}
	for peer_id in [-901, -902, -903]:
		await _admit(peer_id)
		if not game_instance.players.has(peer_id): return "Supported control failed to create an actor"
		positions[game_instance.players[peer_id].position] = true
	return assert_eq(positions.size(), 3, "Declared available starts must support three distinct actors")

func test_exhausted_spawn_list_refuses_before_actor_creation() -> Variant:
	for peer_id in [-901, -902, -903]: await _admit(peer_id)
	var receipt = await _admit(-904)
	if game_instance.players.has(-904): return "Exhausted admission reused an occupied declared spawn"
	return assert_true(receipt is Dictionary and not receipt.accepted and receipt.reason == "no_spawn_available", "No fallback/wrap when supported slots are exhausted")

func test_duplicate_peer_cannot_replace_a_live_actor() -> Variant:
	await _admit(-901)
	var original = game_instance.players[-901]
	var receipt = await _admit(-901, "Replacement")
	return assert_true(game_instance.players[-901] == original and receipt is Dictionary and not receipt.accepted and receipt.reason == "peer_in_use", "Duplicate peer must reject before mutating the live roster")

func test_admission_has_a_structured_receipt() -> Variant:
	var receipt = await _admit(-901)
	return assert_true(receipt is Dictionary and receipt.accepted and receipt.reason == "admitted", "Callers must distinguish admission from refusal")

func test_rejected_admission_does_not_advance_gameplay_rng() -> Variant:
	game_instance.spawn_points = []
	seed(112233)
	var expected := randi()
	seed(112233)
	var result = await _admit(-901)
	return assert_true(not result.accepted and randi() == expected and game_instance.players.is_empty(), "Refused allocation cannot create an actor or consume gameplay randomness")

func test_successful_admission_and_preview_do_not_advance_gameplay_rng() -> Variant:
	seed(112233)
	var expected := randi()
	seed(112233)
	var result = await _admit(-901)
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	game_instance.get_next_spawn_point()
	game_instance.get_next_spawn_point()
	return assert_true(result.accepted and randi() == expected and game_instance.get_spawn_reservation_state() == before, "Spawn seed/preview cannot consume gameplay RNG or reserve hidden slots")

func test_mixed_human_bot_admission_uses_distinct_slots_and_real_controller() -> Variant:
	var human: Dictionary = game_instance.add_player(701, "Human", Vector2.ZERO, false, "", "user:human")
	var bot: Dictionary = game_instance.spawn_bot("BALANCED")
	if not human.accepted or not bot.accepted: return "Mixed control admission failed"
	game_instance.players[701].set_physics_process(false)
	game_instance.players[bot.peer_id].set_physics_process(false)
	var controller = bot_manager.get_bot_controller(bot.peer_id)
	var receipt: Dictionary = game_instance.get_public_observation(701)
	return assert_true(is_instance_valid(controller) and human.cell != bot.cell and receipt.players[str(bot.peer_id)].is_bot and receipt.players["701"].position == human.position and receipt.players[str(bot.peer_id)].position == bot.position, "Public human/bot positions must match actual reserved admission")

func test_no_controller_or_rng_stream_is_created_when_bot_slots_are_exhausted() -> Variant:
	game_instance.spawn_points = []
	var before: int = bot_manager.next_bot_peer_id
	var result: Dictionary = game_instance.spawn_bot("BALANCED")
	return assert_true(not result.accepted and game_instance.players.is_empty() and bot_manager.get_bot_controller(before) == null and bot_manager.get_bot_policy_snapshot(before).is_empty() and bot_manager.next_bot_peer_id == before, "Refused bot cannot leak a controller, stream, actor or identity")

func test_duplicate_stable_identity_rejects_before_roster_changes() -> Variant:
	var first: Dictionary = game_instance.add_player(-901, "A", Vector2.ZERO, true, "fixture", "stable:alice")
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	var duplicate: Dictionary = game_instance.add_player(-902, "B", Vector2.ZERO, true, "fixture", "stable:alice")
	return assert_true(first.accepted and not duplicate.accepted and duplicate.reason == "participant_in_use" and not game_instance.players.has(-902) and game_instance.get_spawn_reservation_state() == before, "An occupied participant identity cannot acquire a second actor")

func test_blocked_and_isolated_slots_do_not_count_as_reachable_capacity() -> Variant:
	game_instance.game_map[2][2] = 1
	for direction in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var neighbor: Vector2i = STARTS[1] + direction
		game_instance.game_map[neighbor.y][neighbor.x] = 1
	var capacity: Dictionary = game_instance.validate_spawn_capacity(2)
	var first = await _admit(-901)
	var refused = await _admit(-902)
	return assert_true(not capacity.accepted and capacity.reason == "insufficient_spawn_capacity" and capacity.available == 1 and first.accepted and first.cell == [6, 2] and not refused.accepted, "Geometry must reject solid and zero-exit starts before playing")

func test_malformed_map_and_spawn_definitions_fail_without_partial_roster() -> Variant:
	var positions: Array = [Vector2(NAN, 16), Vector2(INF, 16), Vector2(1e30, 16), Vector2(40.25, 40), Vector2(-8, 40), "bad"]
	for value in positions:
		game_instance.spawn_points = [value]
		var result = await _admit(-901)
		if result.accepted or not game_instance.players.is_empty(): return "Invalid declared spawn produced a live actor"
	game_instance.spawn_points = [BotTestHelpers.tile_to_world_center(STARTS[0])]
	game_instance.game_map = [[0, 0], [0]]
	var result = await _admit(-901)
	return assert_true(not result.accepted and result.reason == "invalid_spawn_map", "Ragged maps must fail clearly before allocation")

func test_duplicate_spawn_definitions_and_undeclared_overrides_are_rejected() -> Variant:
	game_instance.spawn_points.append(game_instance.spawn_points[0])
	var duplicate = await _admit(-901)
	if duplicate.accepted or duplicate.reason != "duplicate_spawn_definition": return "Duplicate slot definition was accepted"
	game_instance.spawn_points.pop_back()
	var outside: Dictionary = game_instance.add_player(-901, "NoOverride", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	return assert_true(not outside.accepted and outside.reason == "undeclared_spawn" and game_instance.players.is_empty(), "Explicit placement cannot bypass declared slot membership")

func test_fractional_body_overlap_is_refused_across_tile_edges() -> Variant:
	var first: Dictionary = game_instance.add_player(-901, "A", game_instance.spawn_points[0], true, "fixture")
	if not first.accepted: return "Body overlap control failed"
	var actor = game_instance.players[-901]
	actor.set_physics_process(false)
	actor.position = Vector2(4.0 * GameConfig.TILE_SIZE - 0.1, 2.5 * GameConfig.TILE_SIZE)
	var result: Dictionary = game_instance.add_player(-902, "B", game_instance.spawn_points[1], true, "fixture")
	return assert_true(not result.accepted and result.reason == "spawn_unavailable" and not game_instance.players.has(-902), "Floor-cell inequality alone cannot prove the new hitbox is clear")

func test_current_bombs_and_flames_refuse_the_requested_start() -> Variant:
	var bomb: ServerBomb = game_instance.ServerBombScene.instantiate()
	bomb.position = game_instance.spawn_points[0]
	bomb.bomb_id = "spawn-blocker"
	game_instance.bombs[bomb.bomb_id] = bomb
	game_instance.add_child(bomb)
	bomb.set_physics_process(false)
	var refused: Dictionary = game_instance.add_player(-901, "BombBlocked", bomb.position, true, "fixture")
	game_instance.active_explosion_tiles["4,2"] = game_instance.get_simulation_time_msec()
	var flame: Dictionary = game_instance.add_player(-902, "FlameBlocked", game_instance.spawn_points[1], true, "fixture")
	game_instance.active_explosion_tiles.clear()
	return assert_true(not refused.accepted and not flame.accepted and game_instance.players.is_empty(), "Current hitboxes and zero-time active flames cannot be ignored at admission")

func test_retained_reservation_rebinds_to_a_new_peer_identity() -> Variant:
	var first: Dictionary = game_instance.add_player(-901, "A", Vector2.ZERO, true, "fixture", "stable:alice")
	game_instance.remove_player(-901, true)
	var other: Dictionary = game_instance.add_player(-902, "B", Vector2.ZERO, true, "fixture", "stable:bob")
	var rebound: Dictionary = game_instance.add_player(-903, "A", Vector2.ZERO, true, "fixture", "stable:alice")
	return assert_true(first.accepted and other.accepted and rebound.accepted and rebound.reused and rebound.cell == first.cell and rebound.cell != other.cell, "Retained identity must own the same distinct slot without stealing another participant's actor")

func test_detached_state_restores_only_to_matching_empty_authority() -> Variant:
	var first = await _admit(-901)
	var exported: Dictionary = game_instance.get_spawn_reservation_state()
	var saved: Dictionary = JSON.parse_string(JSON.stringify(exported))
	exported.reservations.clear()
	if game_instance.get_spawn_reservation_state().reservations.is_empty(): return "Export aliases live reservations"
	if game_instance.restore_spawn_reservations(saved).accepted: return "Live roster was overwritten by a restored state"
	game_instance.remove_player(-901)
	var restored: Dictionary = game_instance.restore_spawn_reservations(saved)
	var rebound = await _admit(-901)
	return assert_true(first.accepted and restored.accepted and rebound.accepted and rebound.reused and rebound.cell == first.cell, "Matching JSON reservation state must preserve binding at trusted restoration")

func test_incompatible_or_wrapping_snapshot_is_rejected_atomically() -> Variant:
	await _admit(-901)
	var saved: Dictionary = game_instance.get_spawn_reservation_state()
	game_instance.remove_player(-901, true)
	var before: Dictionary = game_instance.get_spawn_reservation_state()
	for field in ["format", "seed", "layout_hash"]:
		var bad := saved.duplicate(true)
		bad[field] = "incompatible"
		if game_instance.restore_spawn_reservations(bad).accepted or game_instance.get_spawn_reservation_state() != before: return "Incompatible restore mutated authority"
	var wrapping := saved.duplicate(true)
	wrapping.reservations["peer:-901"] = [4294967298, 2]
	return assert_true(not game_instance.restore_spawn_reservations(wrapping).accepted and game_instance.get_spawn_reservation_state() == before, "Coordinate overflow cannot alias a valid native cell")

func test_seeded_placement_repeats_with_canonical_declaration_order() -> Variant:
	var experiments := []
	for reversed in [false, true]:
		if reversed: game_instance.spawn_points.reverse()
		var outcomes := []
		for peer_id in [-901, -902, -903]:
			var result = await _admit(peer_id)
			if not result.accepted: return "Seeded allocation control failed"
			outcomes.append(result.cell)
		experiments.append(outcomes)
		for peer_id in [-901, -902, -903]: game_instance.remove_player(peer_id)
	return assert_eq(experiments[0], experiments[1], "Equivalent declared map slots produce the same seeded authority allocation")

func test_nonintegral_and_nonfinite_snapshot_cells_fail_without_mutation() -> Variant:
	await _admit(-901)
	var saved: Dictionary = game_instance.get_spawn_reservation_state()
	game_instance.remove_player(-901, true)
	for coordinate in [true, NAN, INF, -1, 1.5, "2", 4294967298]:
		var bad := saved.duplicate(true)
		bad.reservations["peer:-901"] = [coordinate, 2]
		if game_instance.restore_spawn_reservations(bad).accepted or game_instance.get_spawn_reservation_state() != saved:
			return "Invalid cell cast changed or wrapped trusted restored reservations"
	return true

func test_live_reset_and_release_fail_but_retained_release_frees_capacity() -> Variant:
	await _admit(-901)
	var saved: Dictionary = game_instance.get_spawn_reservation_state()
	if game_instance.reset_spawn_reservations().accepted or game_instance.release_spawn_reservation("peer:-901").accepted or game_instance.get_spawn_reservation_state() != saved:
		return "Administrative reservation changes bypassed an active binding"
	game_instance.remove_player(-901, true)
	var released: Dictionary = game_instance.release_spawn_reservation("peer:-901")
	return assert_true(released.accepted and game_instance.get_spawn_reservation_state().reservations.is_empty(), "Only explicit release should free an unbound retained reservation")

func test_server_quick_start_does_not_record_a_refused_membership() -> Variant:
	var server = get_node("/root/ServerMain")
	var prior_games: Dictionary = server.active_games.duplicate()
	var prior_membership: Dictionary = server.player_to_game.duplicate()
	server.active_games = {"shared_game": game_instance}
	server.player_to_game = {}
	var accepted := true
	for peer_id in [-911, -912, -913]:
		var result: Dictionary = server.quick_start_game(peer_id, "User%d" % peer_id)
		accepted = accepted and result.accepted and server.player_to_game.has(peer_id)
		if game_instance.players.has(peer_id): game_instance.players[peer_id].set_physics_process(false)
	var refused: Dictionary = server.quick_start_game(-914, "TooMany")
	var correct: bool = accepted and not refused.accepted and not server.player_to_game.has(-914) and not game_instance.players.has(-914)
	server.active_games = prior_games
	server.player_to_game = prior_membership
	return assert_true(correct, "Actual ServerMain must not report or retain a rejected GameInstance admission as joined")

func test_dedicated_seed_changes_allocation_without_live_reseeding() -> Variant:
	var chosen := {}
	for value in [0, 1, 2, 3, 4, 5, 6, 7]:
		game_instance.spawn_seed = value
		var result = await _admit(-901)
		if not result.accepted: return "Dedicated spawn seed control failed"
		chosen[str(result.cell)] = true
		game_instance.remove_player(-901)
	game_instance.spawn_seed = 7
	await _admit(-901)
	game_instance.spawn_seed = 8
	var rejected = await _admit(-902)
	game_instance.spawn_seed = 7
	return assert_true(chosen.size() >= 2 and not rejected.accepted and rejected.reason == "spawn_configuration_changed", "Seed changes affect allocation but cannot silently replace a live plan")

func test_only_exit_blocked_by_bomb_refuses_the_requested_start() -> Variant:
	for direction in [Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]:
		var cell: Vector2i = STARTS[0] + direction
		game_instance.game_map[cell.y][cell.x] = 1
	var bomb: ServerBomb = game_instance.ServerBombScene.instantiate()
	bomb.position = BotTestHelpers.tile_to_world_center(STARTS[0] + Vector2i.RIGHT)
	bomb.bomb_id = "blocked-exit"
	game_instance.bombs[bomb.bomb_id] = bomb
	game_instance.add_child(bomb)
	bomb.set_physics_process(false)
	var result: Dictionary = game_instance.add_player(-901, "NoExit", game_instance.spawn_points[0], true, "fixture")
	return assert_true(not result.accepted and game_instance.players.is_empty(), "An empty spawn cell is insufficient when its only current exit is blocked")

func test_idempotent_leave_releases_bookkeeping_after_a_trusted_roster_removal() -> Variant:
	await _admit(-901)
	var actor = game_instance.players[-901]
	game_instance.players.erase(-901)
	actor.queue_free()
	game_instance.remove_player(-901)
	game_instance.remove_player(-901)
	await get_tree().process_frame
	var state: Dictionary = game_instance.get_spawn_reservation_state()
	var replacement = await _admit(-901)
	return assert_true(state.reservations.is_empty() and replacement.accepted, "Canonical leave must clean stale bookkeeping idempotently before future admission")
