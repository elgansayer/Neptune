extends "res://tests/bot_test_suite.gd"

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.countdown_time = 0.0
	game_instance.set_physics_process(false)
	game_instance.bot_manager.set_physics_process(false)
	await super()
	for entry in [[-301, Vector2i(4, 4)], [-302, Vector2i(6, 4)], [-303, Vector2i(8, 4)]]:
		await game_instance.add_player(entry[0], "HurryFixture", BotTestHelpers.tile_to_world_center(entry[1]), true, "fixture")
		game_instance.players[entry[0]].set_physics_process(false)

func test_hurry_overlap_calls_real_death_api_and_leaves_bystanders_alive() -> Variant:
	var victim: ServerPlayer = game_instance.players[-301]
	victim.set_input(1.0, 0.0)
	game_instance._spawn_hurry_block(Vector2i(4, 4))
	if not victim.is_dead or not victim.is_spectator or victim.input_direction != Vector2.ZERO:
		return "Unprotected overlapped player must enter the real stopped/dead spectator state"
	if game_instance.players[-302].is_dead or game_instance.players[-303].is_dead:
		return "Hurry overlap incorrectly killed a bystander"
	return assert_eq(game_instance.get_tile_type(Vector2i(4, 4)), 3, "Hurry block did not complete after death handling")

func test_hurry_uses_existing_death_protection_without_a_new_rule() -> Variant:
	var victim: ServerPlayer = game_instance.players[-301]
	victim.is_immortal = true
	game_instance._spawn_hurry_block(Vector2i(4, 4))
	if victim.is_dead:
		return "API repair changed the existing die() immortality rule"
	return assert_eq(game_instance.get_tile_type(Vector2i(4, 4)), 3, "Protected overlap still must complete block creation")
