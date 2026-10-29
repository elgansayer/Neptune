extends "res://tests/bot_test_suite.gd"

func test_owner_and_bystander_can_leave_new_bomb() -> Variant:
	var tile := Vector2i(3, 3)
	var position := BotTestHelpers.tile_to_world_center(tile)
	# Negative IDs avoid sending test state to nonexistent network peers.
	await game_instance.add_player(-101, "Owner", position, true, "fixture")
	await game_instance.add_player(-102, "Bystander", position, true, "fixture")
	var owner: ServerPlayer = game_instance.players[-101]
	var bystander: ServerPlayer = game_instance.players[-102]
	if owner.get_tile_position() != tile or bystander.get_tile_position() != tile:
		return "Players did not start on the same requested tile"
	game_instance.place_bomb(owner)
	if game_instance.bombs.size() != 1:
		return "Expected one real bomb"
	var bomb: ServerBomb = game_instance.bombs.values()[0]
	if not owner.get_collision_exceptions().has(bomb):
		return "Owner missing collision exception"
	if not bystander.get_collision_exceptions().has(bomb):
		return "Bystander missing collision exception"
	return true
