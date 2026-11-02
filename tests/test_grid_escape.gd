extends "res://tests/bot_test_suite.gd"

func setup_test() -> void:
	# These independent movement experiments reuse the suite authority, not a
	# live round whose roster was removed by the preceding case's teardown.
	game_instance.match_active = false
	await super()
	game_instance.match_active = true

func _overlap_players() -> bool:
	var center := BotTestHelpers.tile_to_world_center(Vector2i(3, 3))
	await game_instance.add_player(-101, "Owner", center, true, "fixture")
	await game_instance.add_player(-102, "Bystander", BotTestHelpers.tile_to_world_center(Vector2i(4, 3)), true, "fixture")
	var bystander: ServerPlayer = game_instance.players[-102]
	bystander.set_input(-1, 0)
	for step in range(24):
		if bystander.position.distance_to(center) < 0.1:
			break
		await get_tree().physics_frame
		await get_tree().process_frame
	bystander.set_input(0, 0)
	return bystander.get_tile_position() == Vector2i(3, 3)

func test_overlapping_bystander_cannot_block_departure() -> Variant:
	if not await _overlap_players():
		return "Real players did not overlap through ordinary movement"
	var owner: ServerPlayer = game_instance.players[-101]
	var path: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), Vector2i(3, 5), 30, owner)
	return not path.is_empty() and path.back() == Vector2i(3, 5)

func test_overlapping_bomb_bystander_keeps_a_legal_escape() -> Variant:
	if not await _overlap_players():
		return "Real players did not overlap through ordinary movement"
	var owner: ServerPlayer = game_instance.players[-101]
	game_instance.place_bomb(owner)
	if game_instance.bombs.size() != 1:
		return "Expected a real bomb at the overlapping start"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	if not owner.get_collision_exceptions().has(bomb):
		return "Owner lacks the actual departure collision exception"
	var path: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), Vector2i(3, 5), 30, owner)
	return not path.is_empty() and path.back() == Vector2i(3, 5)

func test_other_occupied_tiles_still_require_a_detour() -> Variant:
	await game_instance.add_player(-101, "Owner", BotTestHelpers.tile_to_world_center(Vector2i(3, 3)), true, "fixture")
	await game_instance.add_player(-102, "Obstacle", BotTestHelpers.tile_to_world_center(Vector2i(4, 3)), true, "fixture")
	var owner: ServerPlayer = game_instance.players[-101]
	var path: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), Vector2i(5, 3), 30, owner)
	return not path.is_empty() and path.back() == Vector2i(5, 3) and not path.has(Vector2i(4, 3))

func test_static_wall_start_stays_blocked() -> Variant:
	set_tile(3, 3, 1)
	var path: Array[Vector2i] = bot_manager.grid_sampler.find_path(Vector2i(3, 3), Vector2i(3, 5))
	return path.is_empty()
