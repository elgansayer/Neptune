extends "res://tests/bot_test_suite.gd"

const SafeToAttack = preload("res://ai/tasks/conditions/bt_is_safe_to_attack.gd")
const MovementTiming = preload("res://shared/ai/movement_timing.gd")

class RecordingSafety extends RefCounted:
	var result := {"safe": true, "margin_ms": 2500.0}
	var observed_speed := 0.0
	func check_plant_safety_detailed(_bot_pos, _plant_pos, _range, speed, _now, _dead_end, _fuse, _actor = null) -> Dictionary:
		observed_speed = speed
		return result.duplicate()

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true

func _actor() -> Node:
	await spawn_bot_at(Vector2i(7, 6))
	bot_player.set_physics_process(false)
	bot_controller.active = false
	bot_manager.refresh_perception()
	return bot_controller.get_blackboard().get_var("player")

func _condition(actor, safety):
	var board = bot_controller.get_blackboard()
	board.set_var("bomb_safety_checker", safety)
	board.set_var("was_safe_to_attack", false)
	board.set_var("in_danger", false)
	board.set_var("personality", "BALANCED")
	var task = SafeToAttack.new()
	task.initialize(actor, board, get_tree().current_scene)
	return task

func test_successful_but_small_margin_does_not_bypass_attack_safety() -> Variant:
	var actor = await _actor()
	var safety := RecordingSafety.new()
	safety.result = {"safe": true, "margin_ms": 500.0}
	var task = _condition(actor, safety)
	if task.execute(1.0 / 60.0) != ClassDB.class_get_integer_constant("BT", "FAILURE"):
		return "A positive reachability result bypassed the configured attack margin"
	safety.result = {"safe": true, "margin_ms": 2000.0}
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "SUCCESS"),
		"The sufficient-margin control must remain eligible for attack")

func test_failed_escape_is_a_hard_constraint_even_with_large_reported_margin() -> Variant:
	var actor = await _actor()
	var safety := RecordingSafety.new()
	safety.result = {"safe": false, "margin_ms": INF}
	var task = _condition(actor, safety)
	return assert_true(task.execute(1.0 / 60.0) == ClassDB.class_get_integer_constant("BT", "FAILURE"),
		"A failed escape proof must not be converted into permission by a margin")

func test_attack_planning_uses_public_skates_and_virus_speed() -> Variant:
	var actor = await _actor()
	var safety := RecordingSafety.new()
	for skates in [0, 4, 8]:
		for virus in [ServerPlayer.VirusType.NONE, ServerPlayer.VirusType.SLOWPOKE, ServerPlayer.VirusType.SPEEDSTER]:
			bot_player.skate_count = skates
			bot_player.active_virus = virus
			game_instance.invalidate_public_observation()
			bot_manager.refresh_public_observations(true)
			var task = _condition(actor, safety)
			task.execute(1.0 / 60.0)
			var expected: float = GameConfig.BASE_SPEED / float(GameConfig.TILE_SIZE) \
				* GameConfig.get_skate_speed_multiplier(skates) * bot_player.get_virus_speed_modifier()
			if not is_equal_approx(safety.observed_speed, expected):
				return "Attack safety ignored public inventory/virus movement speed"
	return assert_true(MovementTiming.tiles_per_second(actor) > 0.0,
		"The observed actor must expose usable authoritative movement stats")

func test_unavailable_inventory_avoids_pointless_hypothetical_searches() -> Variant:
	var actor = await _actor()
	var receipt: Dictionary = game_instance.place_bomb(bot_player)
	if not receipt.accepted: return "Inventory control could not place its real bomb"
	game_instance.bombs[receipt.bomb_ids[0]].set_physics_process(false)
	bot_player.position = BotTestHelpers.tile_to_world_center(Vector2i(11, 9))
	game_instance.invalidate_public_observation()
	bot_manager.refresh_perception()
	var safety := RecordingSafety.new()
	var task = _condition(actor, safety)
	if task.execute(0.02) != ClassDB.class_get_integer_constant("BT", "FAILURE") or safety.observed_speed != 0.0:
		return "Capacity-bound bot entered expensive hypothetical attack planning"
	bot_player.max_bombs = 2
	game_instance.invalidate_public_observation()
	bot_manager.refresh_public_observations(true)
	return assert_true(task.execute(0.02) == ClassDB.class_get_integer_constant("BT", "SUCCESS")
		and safety.observed_speed > 0.0, "A real available inventory slot must still permit safe attack planning")
