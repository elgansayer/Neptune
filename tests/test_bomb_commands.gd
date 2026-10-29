extends "res://tests/bot_test_suite.gd"

var actor: ServerPlayer

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	await game_instance.add_player(-501, "CommandFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	actor = game_instance.players[-501]
	actor.set_physics_process(false)
	game_instance.match_active = true
	game_instance.ai_manager.refresh_threat_matrix(game_instance.current_time_msec)

func teardown_test() -> void:
	if is_instance_valid(actor) and not game_instance.players.has(actor.peer_id):
		actor.queue_free()
	await super()

func _world_state() -> Dictionary:
	return {"bombs": game_instance.bombs.keys(), "next_id": game_instance.next_bomb_id,
		"count": actor.bombs_placed, "threats": game_instance.ai_manager.threat_matrix.duplicate(true)}

func _must_reject(reason: String) -> Variant:
	var before := _world_state()
	seed(90125)
	var expected := randf()
	seed(90125)
	var result = game_instance.place_bomb(actor)
	if _world_state() != before:
		return "Rejected %s placement mutated actual bomb/capacity/ID/forecast state" % reason
	if randf() != expected:
		return "Rejected %s placement consumed gameplay RNG" % reason
	if not result is Dictionary or result.get("accepted") != false or result.get("reason") != reason or result.get("bomb_ids") != []:
		return "Expected explicit %s rejection; got %s" % [reason, str(result)]
	return true

func test_dead_actor_cannot_place_directly() -> Variant:
	actor.is_dead = true
	return _must_reject("dead_player")

func test_constipation_cannot_be_bypassed_by_direct_placement() -> Variant:
	actor.active_virus = ServerPlayer.VirusType.CONSTIPATION
	return _must_reject("placement_disabled")

func test_capacity_is_enforced_at_the_authority() -> Variant:
	actor.bombs_placed = actor.max_bombs
	return _must_reject("capacity")

func test_existing_bomb_rejects_duplicate_at_same_tile() -> Variant:
	actor.max_bombs = 3
	game_instance.place_bomb(actor)
	if game_instance.bombs.size() != 1:
		return "Duplicate control did not place the real first bomb"
	return _must_reject("occupied_tile")

func test_hard_wall_rejects_placement() -> Variant:
	set_tile(7, 6, 1)
	return _must_reject("blocked_tile")

func test_soft_wall_rejects_placement() -> Variant:
	set_tile(7, 6, 2)
	return _must_reject("blocked_tile")

func test_hurry_wall_rejects_placement() -> Variant:
	game_instance.game_map[6][7] = 3
	return _must_reject("blocked_tile")

func test_unregistered_actor_cannot_place_in_the_room() -> Variant:
	game_instance.players.erase(actor.peer_id)
	return _must_reject("unknown_player")

func test_foreign_actor_authority_is_rejected() -> Variant:
	actor.game_instance = null
	var result = _must_reject("foreign_player")
	actor.game_instance = game_instance
	return result

func test_outside_map_rejects_placement() -> Variant:
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(-1, 6))
	return _must_reject("outside_map")

func test_inactive_match_returns_explicit_rejection() -> Variant:
	game_instance.match_active = false
	return _must_reject("match_inactive")

func test_valid_control_keeps_real_capacity_and_collision_hooks() -> Variant:
	game_instance.place_bomb(actor)
	if game_instance.bombs.size() != 1 or actor.bombs_placed != 1:
		return "Valid placement did not create exactly one real bomb"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	if bomb.owner_id != actor.player_id or bomb.get_tile_position() != actor.get_tile_position() or bomb.fuse_time != actor.get_bomb_fuse_lower_bound():
		return "Valid bomb lost its actor position/ownership/fuse rules"
	return assert_true(actor.get_collision_exceptions().has(bomb), "Owner must retain the production overlap escape exception")

func _plant_task() -> Dictionary:
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("game_instance", game_instance)
	board.set_var("grid_sampler", bot_manager.grid_sampler)
	board.set_var("bomb_safety_checker", null)
	board.set_var("opponent_tracker", null)
	board.set_var("target_cell", actor.get_tile_position())
	board.set_var("tactical_plan", "AGGRESSIVE_CHASE")
	board.set_var("last_bomb_placed_time", 123.0)
	board.set_var("in_danger", false)
	var task = preload("res://ai/tasks/actions/bt_place_bomb.gd").new()
	# These are policy prechecks, never authority permissions.
	task.check_capacity = false
	task.check_existing = false
	task.initialize(actor, board, get_tree().current_scene)
	return {"task": task, "board": board}

func test_native_task_cannot_report_an_inactive_placement_as_success() -> Variant:
	var fixture := _plant_task()
	game_instance.match_active = false
	var before := _world_state()
	var status: int = fixture.task.execute(0.02)
	if status != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "Native task reported success although the inactive authority placed no bomb"
	if _world_state() != before or fixture.board.get_var("last_bomb_placed_time") != 123.0 or fixture.board.get_var("in_danger"):
		return "Rejected native planting fabricated plant time/escape state or mutated the world"
	return true

func test_native_policy_flags_cannot_disable_authority_capacity() -> Variant:
	actor.bombs_placed = actor.max_bombs
	var fixture := _plant_task()
	var before := _world_state()
	var status: int = fixture.task.execute(0.02)
	if status != ClassDB.class_get_integer_constant("BT", "FAILURE") or _world_state() != before:
		return "Native policy precheck flags bypassed authority capacity"
	return true

func test_valid_placement_returns_the_actual_created_id() -> Variant:
	var result: Dictionary = game_instance.place_bomb(actor)
	if not result.accepted or result.reason != "placed" or result.bomb_ids.size() != 1:
		return "Valid placement lacks its explicit accepted result and actual bomb ID"
	return assert_eq(result.bomb_ids, game_instance.bombs.keys(), "Result must name the created authoritative bomb")

func test_null_actor_rejection_has_no_side_effects() -> Variant:
	var before := _world_state()
	var result: Dictionary = game_instance.place_bomb(null)
	return assert_true(not result.accepted and result.reason == "unknown_player" and result.bomb_ids.is_empty() and _world_state() == before, "Null actors must fail without allocating a bomb")

func test_all_map_boundaries_reject_before_allocating() -> Variant:
	for tile in [Vector2i(-1, 6), Vector2i(7, -1), Vector2i(default_map_width, 6), Vector2i(7, default_map_height)]:
		actor.position = BotTestHelpers.tile_to_world_center(tile)
		var result = _must_reject("outside_map")
		if result is not bool or not result:
			return result
	return true

func test_nonfinite_actor_position_rejects_before_grid_conversion() -> Variant:
	for position in [Vector2(NAN, 0), Vector2(INF, 0), Vector2(0, -INF)]:
		actor.position = position
		var result = _must_reject("invalid_position")
		if result is not bool or not result:
			return result
	return true

func test_rejected_long_fuse_does_not_sample_a_private_timer() -> Variant:
	actor.active_virus = ServerPlayer.VirusType.LEISURELY_FUSE
	actor.bombs_placed = actor.max_bombs
	return _must_reject("capacity")

func test_line_placement_is_bounded_and_publishes_all_real_hazards() -> Variant:
	actor.has_line_bomb = true
	actor.max_bombs = 3
	actor.last_move_direction = Vector2.RIGHT
	var result: Dictionary = game_instance.place_bomb(actor)
	if not result.accepted or result.bomb_ids.size() != 3 or actor.bombs_placed != 3:
		return "Line placement did not stop at the actor's actual capacity"
	for index in range(3):
		var bomb: ServerBomb = game_instance.bombs[result.bomb_ids[index]]
		if bomb.get_tile_position() != Vector2i(7 + index, 6) or bomb.owner_id != actor.player_id or bomb.fuse_time != 3.0:
			return "Line bomb position/order/owner/fuse differs from the live actor rules"
	var key := "10,6"
	var predictor = bot_manager.hazard_predictor
	if not game_instance.ai_manager.threat_matrix.has(key) or not predictor.is_tile_threatened(Vector2i(10, 6)):
		return "Accepted line did not immediately publish every bomb to both actual hazard caches"
	return _must_reject("capacity")

func test_line_stops_before_a_hurry_wall() -> Variant:
	actor.has_line_bomb = true
	actor.max_bombs = 5
	actor.last_move_direction = Vector2.RIGHT
	game_instance.game_map[6][9] = 3
	var result: Dictionary = game_instance.place_bomb(actor)
	if not result.accepted or result.bomb_ids.size() != 2 or game_instance.bombs.size() != 2 or actor.bombs_placed != 2:
		return "Line crossed a hurry wall or reported incorrect partial placement"
	return assert_true(not game_instance._has_bomb_at_tile(Vector2i(9, 6)), "Hurry block is solid terrain, not a powerup slot")

func test_line_stops_before_an_existing_bomb() -> Variant:
	actor.max_bombs = 5
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(9, 6))
	game_instance.place_bomb(actor)
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(7, 6))
	actor.has_line_bomb = true
	actor.last_move_direction = Vector2.RIGHT
	var result: Dictionary = game_instance.place_bomb(actor)
	return assert_true(result.accepted and result.bomb_ids.size() == 2 and game_instance.bombs.size() == 3 and actor.bombs_placed == 3, "Line must preserve existing bomb and consume only two remaining seats")

func test_native_accepted_placement_records_the_authority_time() -> Variant:
	var fixture := _plant_task()
	game_instance.current_time_msec = 500.0
	var status: int = fixture.task.execute(0.02)
	return assert_true(status == ClassDB.class_get_integer_constant("BT", "SUCCESS") and game_instance.bombs.size() == 1 and fixture.board.get_var("last_bomb_placed_time") == 0.5 and fixture.board.get_var("in_danger") and fixture.board.get_var("target_cell") == null, "Native success must follow a real accepted bomb and preserve immediate escape bookkeeping")

func test_native_glove_and_throw_do_not_advance_after_rejection() -> Variant:
	actor.has_power_glove = true
	game_instance.match_active = false
	var fixture := _plant_task()
	fixture.board.set_var("action_pressed", true)
	fixture.board.set_var("last_action", "prior")
	var glove = preload("res://ai/tasks/actions/bt_process_power_glove.gd").new()
	glove.initialize(actor, fixture.board, get_tree().current_scene)
	var failure: int = ClassDB.class_get_integer_constant("BT", "FAILURE")
	if glove.execute(0.02) != failure or fixture.board.get_var("last_action") != "prior":
		return "Native glove reported a placement/action after the authority refused it"
	fixture.board.set_var("tactical_plan", "POWER_THROW")
	fixture.board.set_var("throw_direction", Vector2.RIGHT)
	var throwing = preload("res://ai/tasks/actions/bt_throw_bomb.gd").new()
	throwing.initialize(actor, fixture.board, get_tree().current_scene)
	if throwing.execute(0.02) != ClassDB.class_get_integer_constant("BT", "RUNNING"):
		return "Throw control did not reach its real PLACING phase"
	if throwing.execute(0.02) != failure or game_instance.bombs.size() != 0:
		return "Native throw advanced to pickup after rejected placement"
	return true

func test_human_glove_placement_returns_the_shared_authority_rejection() -> Variant:
	actor.has_power_glove = true
	game_instance.match_active = false
	var before := _world_state()
	var result: Dictionary = game_instance.handle_player_input(actor.peer_id, {"action_pressed": true})
	return assert_true(not result.accepted and result.reason == "match_inactive" and _world_state() == before, "Human glove placement must return the same authority rejection")

func test_human_packet_and_direct_bot_follow_the_same_placement_trace() -> Variant:
	await game_instance.add_player(-502, "HumanFixture", BotTestHelpers.tile_to_world_center(Vector2i(4, 4)), false)
	var human: ServerPlayer = game_instance.players[-502]
	human.set_physics_process(false)
	if human.is_bot or not actor.is_bot:
		return "Trace fixture did not contain actual distinct human/bot participant metadata"
	var trace := []
	for expected in ["placed", "capacity", "placement_disabled", "dead_player", "match_inactive"]:
		if expected == "placement_disabled":
			actor.active_virus = ServerPlayer.VirusType.CONSTIPATION
			human.active_virus = ServerPlayer.VirusType.CONSTIPATION
		elif expected == "dead_player":
			actor.is_dead = true
			human.is_dead = true
		elif expected == "match_inactive":
			game_instance.match_active = false
		var bot_result: Dictionary = game_instance.place_bomb(actor)
		var human_result: Dictionary = game_instance.handle_player_input(human.peer_id, {"place_bomb": true})
		var bot_entry := [bot_result.accepted, bot_result.reason, bot_result.bomb_ids.size(), actor.bombs_placed]
		var human_entry := [human_result.accepted, human_result.reason, human_result.bomb_ids.size(), human.bombs_placed]
		if bot_entry != human_entry or bot_result.reason != expected:
			return "Human/bot authoritative trace diverged at %s: %s / %s" % [expected, str(bot_entry), str(human_entry)]
		trace.append(bot_entry)
	if game_instance.bombs.size() != 2:
		return "Rejected steps changed the actual bombs after two accepted placements"
	for player in [actor, human]:
		var owned := 0
		for bomb: ServerBomb in game_instance.bombs.values():
			if bomb.owner_id == player.player_id:
				owned += 1
				if bomb.get_tile_position() != player.get_tile_position() or bomb.fuse_time != 3.0:
					return "Human/bot trace changed bomb position or actual fuse"
		if owned != 1:
			return "Accepted placement did not belong to the correct participant"
	print("COMMAND_EQUIVALENCE_TRACE=", JSON.stringify(trace))
	return true
