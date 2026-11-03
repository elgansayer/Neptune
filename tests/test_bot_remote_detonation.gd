extends "res://tests/bot_test_suite.gd"

var planted: ServerBomb
var observed

func setup_test() -> void:
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	await spawn_bot_at(Vector2i(4, 4))
	bot_player.set_physics_process(false)
	bot_player.bomb_type = ServerBomb.BOMB_TYPE_REMOTE
	var receipt: Dictionary = game_instance.place_bomb(bot_player)
	if not receipt.accepted:
		push_error("Remote fixture could not place an ordinary owned remote bomb")
		return
	planted = game_instance.bombs[receipt.bomb_ids[0]]
	planted.set_physics_process(false)
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i(10, 9))
	_refresh()
	observed = bot_controller.get_blackboard().get_var("player")

func _refresh() -> void:
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()

func _action():
	var action = preload("res://ai/tasks/actions/bt_detonate_remote.gd").new()
	action.initialize(observed, bot_controller.get_blackboard(), get_tree().current_scene)
	return action

func test_observed_actor_detonates_a_real_owned_bomb_from_refuge() -> Variant:
	var result: int = _action().execute(0.02)
	return assert_true(result == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and planted.has_exploded and observed.last_command_result.accepted,
		"Remote policy must invoke the ordinary validated command and actual bomb explosion")

func test_own_blast_lane_refuses_optional_detonation() -> Variant:
	bot_player.position = planted.position
	_refresh()
	return assert_true(_action().execute(0.02) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and not planted.has_exploded, "Remote action must not sacrifice its owner")

func test_another_observed_bomb_chain_lane_blocks_optional_detonation() -> Variant:
	var joined: Dictionary = game_instance.add_player(1991, "VisibleBombOwner", BotTestHelpers.tile_to_world_center(Vector2i(11, 9)))
	if not joined.accepted: return "Visible chain fixture admission failed"
	var other: ServerPlayer = game_instance.players[1991]
	other.set_physics_process(false)
	var receipt: Dictionary = game_instance.place_bomb(other)
	if not receipt.accepted: return "Visible chain fixture placement failed"
	game_instance.bombs[receipt.bomb_ids[0]].set_physics_process(false)
	_refresh()
	return assert_true(_action().execute(0.02) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and not planted.has_exploded, "An optional trigger needs a refuge outside all observed future blast lanes")

func test_no_matching_ability_or_owned_bomb_issues_no_detonation() -> Variant:
	bot_player.bomb_type = ServerBomb.BOMB_TYPE_NORMAL
	_refresh()
	if _action().execute(0.02) != ClassDB.class_get_integer_constant("BT", "FAILURE") or planted.has_exploded:
		return "Bot remotely triggered without its actual remote ability"
	bot_player.bomb_type = ServerBomb.BOMB_TYPE_REMOTE
	planted.owner_id = "another-player"
	_refresh()
	return assert_true(_action().execute(0.02) == ClassDB.class_get_integer_constant("BT", "FAILURE")
		and not planted.has_exploded, "Other players' remotes are never owned control targets")

func test_exploding_oldest_does_not_hide_the_next_live_owned_remote() -> Variant:
	bot_player.max_bombs = 2
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i(6, 4))
	var receipt: Dictionary = game_instance.place_bomb(bot_player)
	if not receipt.accepted: return "Second remote fixture admission failed"
	var second: ServerBomb = game_instance.bombs[receipt.bomb_ids[0]]
	second.set_physics_process(false)
	planted.explode()
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i(10, 9))
	_refresh()
	return assert_true(_action().execute(0.02) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and second.has_exploded, "Already exploding oldest remotes cannot consume another valid trigger")

func test_production_tree_uses_reaction_gate_then_triggers_from_refuge() -> Variant:
	var board = bot_controller.get_blackboard()
	board.set_var("reaction_time_ms", 100.0)
	bot_controller.restart()
	bot_controller.active = true
	bot_controller.update(0.02)
	if planted.has_exploded: return "Remote trigger bypassed the strategic reaction delay"
	game_instance.current_time_msec += 101.0
	_refresh()
	bot_controller.update(0.02)
	return assert_true(planted.has_exploded, "The actual production tree must consume remote inventory after retreat and reaction")
