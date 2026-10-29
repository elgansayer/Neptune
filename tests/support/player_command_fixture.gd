extends "res://tests/bot_test_suite.gd"

var actor: ServerPlayer

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	await game_instance.add_player(-601, "ActionFixture", BotTestHelpers.tile_to_world_center(Vector2i(7, 6)), true, "fixture")
	actor = game_instance.players[-601]
	actor.set_physics_process(false)
	game_instance.match_active = true

func own_bomb(tile: Vector2i = Vector2i(7, 6)) -> ServerBomb:
	actor.position = BotTestHelpers.tile_to_world_center(tile)
	var result: Dictionary = game_instance.place_bomb(actor)
	if not result.accepted:
		push_error("Valid command fixture failed to place: " + result.reason)
		return null
	var bomb: ServerBomb = game_instance.bombs[result.bomb_ids[0]]
	bomb.set_physics_process(false)
	return bomb

func snapshot() -> Dictionary:
	var observed := {}
	for key in game_instance.bombs:
		var bomb: ServerBomb = game_instance.bombs[key]
		observed[key] = [bomb.bomb_state, bomb.position, bomb.carrier_id, bomb.has_exploded]
	return {"input": actor.input_direction, "pressed": actor.action_button_pressed,
		"bombs": observed, "placed": actor.bombs_placed, "next_id": game_instance.next_bomb_id,
		"carried": actor.carried_bomb, "cooldown": actor.tirra_action_cooldown}
