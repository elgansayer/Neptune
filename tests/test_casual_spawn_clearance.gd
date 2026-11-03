extends "res://tests/bot_test_suite.gd"

func setup_suite() -> void: pass
func teardown_suite() -> void: pass
func setup_test() -> void: pass
func teardown_test() -> void:
	if is_instance_valid(game_instance): game_instance.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame

func test_clearance_filters_only_optional_slots_and_respects_tile_size() -> Variant:
	var slots := [Vector2i(2, 2), Vector2i(4, 4), Vector2i(5, 5)]
	var before := slots.duplicate()
	var filtered := MapPackLoader.reserve_casual_spawn_clearance(slots, [Vector2(80, 80)], 32.0)
	return assert_true(slots == before and filtered == [Vector2i(5, 5)],
		"Casual clearance must filter optional slots in tile units without rewriting the source selection")

func test_dense_default_arena_supports_four_real_safe_plant_controllers() -> Variant:
	var map := MapPackLoader.load_map_from_pck("res://maps/stage1.pck")
	if map.is_empty(): return "Missing actual default PCK arena"
	var hard: Array = map.grid.duplicate(true)
	var active := MapPackLoader.reserve_casual_spawn_clearance(map.soft_slots, map.spawn_points, map.tile_size)
	for slot in map.soft_slots: map.grid[slot.y][slot.x] = 2 if slot in active else 0
	for y in range(hard.size()):
		for x in range(hard[y].size()):
			if hard[y][x] == 1 and map.grid[y][x] != 1: return "Casual clearance rewrote a hard wall"
	game_instance = preload("res://tests/support/profile_bot_game.gd").new()
	game_instance.room_map_snapshot = map
	game_instance.continuous_room = true
	game_instance.countdown_time = 0.0
	game_instance.room_capacity_request = {"seats": 4, "preset_limit": 4}
	game_instance.room_bot_fill_request = {"target": 0, "personality": "BALANCED"}
	game_instance.bot_policy_seed = 314159
	game_instance.spawn_seed = 314159
	add_child(game_instance)
	if not game_instance.room_setup_result.accepted: return "Dense actual arena did not initialize"
	var starts := {}
	for index in range(4):
		var receipt: Dictionary = game_instance.spawn_bot("BALANCED")
		if not receipt.accepted: return "Actual bot admission failed"
		starts[str(receipt.peer_id)] = game_instance.players[receipt.peer_id].position
	game_instance.match_active = true
	var start: float = game_instance.get_simulation_time_msec()
	var complete := false
	for frame in range(600):
		await get_tree().physics_frame
		await get_tree().process_frame
		complete = true
		for id in starts:
			if game_instance.participant_commands.get(id, {}).get("place_bomb", 0) < 1: complete = false
		if complete or game_instance.get_simulation_time_msec() - start >= 8000.0: break
	var moved := true
	for id in starts:
		var actor = game_instance.players[int(id)]
		moved = moved and actor.position.distance_to(starts[id]) >= 2.0
	print("CASUAL_START_EVIDENCE=", JSON.stringify({"commands": game_instance.participant_commands,
		"bombs": game_instance.next_bomb_id, "all_placed": complete, "all_moved": moved,
		"elapsed_msec": game_instance.get_simulation_time_msec() - start}))
	return assert_true(complete and moved and game_instance.next_bomb_id >= 4,
		"Every real controller must move and place a validated bomb on the densely filled original arena")
