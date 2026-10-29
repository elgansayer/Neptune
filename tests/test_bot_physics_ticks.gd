extends "res://tests/bot_test_suite.gd"

func make_game_instance() -> GameInstance:
	var game := super()
	game.ServerBotManagerScript = preload("res://tests/support/counting_bot_manager.gd")
	return game

func test_manager_owns_exactly_one_update_per_physics_tick() -> Variant:
	await spawn_bot_at(Vector2i(7, 6))
	if bot_player == null or bot_controller == null:
		return "No real bot/controller"
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	var tree = ClassDB.instantiate("BehaviorTree")
	tree.root_task = preload("res://tests/support/count_bot_ticks.gd").new()
	bot_controller.behavior_tree = tree
	bot_controller.restart()
	bot_player.set_meta("fixture_bt_ticks", 0)
	bot_controller.active = true
	for index in range(6):
		await get_tree().physics_frame
	await get_tree().process_frame
	var paused_ticks: int = bot_player.get_meta("fixture_bt_ticks", 0)
	print("BOT_TICK_PAUSED=" + JSON.stringify({"native_ticks": paused_ticks, "mode": bot_controller.update_mode}))
	var previous_calls: int = bot_manager.observed_physics_calls
	bot_manager.set_physics_process(true)
	for index in range(20):
		await get_tree().physics_frame
	await get_tree().process_frame
	bot_manager.set_physics_process(false)
	bot_controller.active = false
	var calls: int = bot_manager.observed_physics_calls - previous_calls
	var native_ticks: int = int(bot_player.get_meta("fixture_bt_ticks", 0)) - paused_ticks
	print("BOT_TICK_ACTIVE=" + JSON.stringify({"manager_calls": calls, "native_ticks": native_ticks, "mode": bot_controller.update_mode}))
	if paused_ticks != 0:
		return "Manager paused but native behaviour tree updated %d times" % paused_ticks
	if calls <= 0 or native_ticks != calls:
		return "Expected one native tick per manager physics call: %d calls, %d native ticks" % [calls, native_ticks]
	return true
