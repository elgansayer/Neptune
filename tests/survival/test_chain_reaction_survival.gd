extends "res://tests/support/legacy_bot_scenario.gd"

## Test: Bot must survive chain reactions by proper escape timing

var test_name := "chain_reaction_survival"

var bot: Node
var test_result := ""

func _init() -> void:
	test_timeout = 12.0

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	await get_tree().create_timer(1.0).timeout
	
	# Spawn bot
	var spawn_tile = Vector2i(10, 7)
	bot = await BotTestHelpers.spawn_bot(spawn_tile, "BALANCED", game_instance)
	
	if not bot:
		test_result = "FAIL: Bot failed to spawn"
		return
	
	# Clear large area
	BotTestHelpers.clear_area(spawn_tile, 5, game_instance)
	
	await get_tree().create_timer(0.5).timeout
	print("[TEST] Bot spawned for chain reaction test")

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	# Place bombs to create chain reaction
	var bot_tile = BotTestHelpers.world_to_tile(bot.position)
	for offset in range(2, 5):
		if BotTestHelpers.place_bomb(bot_tile + Vector2i(offset, 0), 2.0 + offset * 0.5) == null:
			test_result = "FAIL: Scenario bomb was not created"
			return
	
	print("[TEST] Placed 3 bombs for chain reaction")
	
	# Monitor for survival
	var start_time = Engine.get_physics_frames()
	var max_wait = int(test_timeout * Engine.physics_ticks_per_second)
	
	while Engine.get_physics_frames() - start_time < max_wait:
		if not is_instance_valid(bot):
			test_result = "FAIL: Bot was destroyed"
			return
		
		if bot.is_dead:
			test_result = "FAIL: Bot died in chain reaction"
			return
		
		await get_tree().create_timer(0.1).timeout
	
	if not is_instance_valid(bot):
		test_result = "FAIL: Bot destroyed"
		return
	
	if bot.is_dead:
		test_result = "FAIL: Bot died"
		return
	
	test_result = "PASS: Bot survived chain reaction"

func teardown() -> void:
	if is_instance_valid(bot):
		bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
