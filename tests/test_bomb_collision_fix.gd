extends "res://tests/bot_test_suite.gd"

func test_owner_and_bystander_can_leave_new_bomb() -> Variant:
	var tile := Vector2i(3, 3)
	var position := BotTestHelpers.tile_to_world_center(tile)
	# Negative IDs avoid sending test state to nonexistent network peers.
	await game_instance.add_player(-101, "Owner", position, true, "fixture")
	await game_instance.add_player(-102, "Bystander", BotTestHelpers.tile_to_world_center(Vector2i(4, 3)), true, "fixture")
	var owner: ServerPlayer = game_instance.players[-101]
	var bystander: ServerPlayer = game_instance.players[-102]
	# Players can overlap through ordinary movement, not duplicate admission.
	bystander.set_input(-1, 0)
	for step in range(24):
		if bystander.position.distance_to(position) < 0.1: break
		await get_tree().physics_frame
		await get_tree().process_frame
	bystander.set_input(0, 0)
	if owner.get_tile_position() != tile or bystander.get_tile_position() != tile:
		return "Players did not reach the same tile before bomb placement"
	game_instance.place_bomb(owner)
	if game_instance.bombs.size() != 1:
		return "Expected one real bomb"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	if not owner.get_collision_exceptions().has(bomb):
		return "Owner missing collision exception"
	if not bystander.get_collision_exceptions().has(bomb):
		return "Bystander missing collision exception"
	return true
