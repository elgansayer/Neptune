extends Node

## Test: Bot must not commit suicide when spawned in a corner

var test_name := "no_suicide_corner"
var test_timeout := 10.0
var bot: Node
var initial_tile: Vector2i
var test_result := ""
var game_instance

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	await get_tree().create_timer(1.0).timeout
	
	# Spawn bot in a corner
	var corner_tile = Vector2i(2, 2)
	bot = BotTestHelpers.spawn_bot(corner_tile, "BALANCED", game_instance)
	
	if not bot:
		test_result = "FAIL: Bot failed to spawn"
		return
	
	initial_tile = BotTestHelpers.world_to_tile(bot.position)
	
	# Clear area but leave walls to create corner
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			if abs(dx) + abs(dy) <= 1:  # Only clear adjacent tiles
				BotTestHelpers.clear_tile(initial_tile + Vector2i(dx, dy), game_instance)
	
	await get_tree().create_timer(0.5).timeout
	print("[TEST] Bot spawned in corner at tile %s" % initial_tile)

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match to start
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	await get_tree().create_timer(1.0).timeout
	
	print("[TEST] Monitoring bot in corner for %d seconds..." % int(test_timeout))
	
	var start_time = Time.get_ticks_msec()
	var max_wait = test_timeout * 1000
	var bomb_count = 0
	
	while Time.get_ticks_msec() - start_time < max_wait:
		if not is_instance_valid(bot):
			test_result = "FAIL: Bot was destroyed"
			return
		
		if bot.has_method("is_dead") and bot.is_dead:
			test_result = "FAIL: Bot committed suicide in corner"
			return
		
		# Count bomb placements
		var bombs_near = BotTestHelpers.count_bombs_near(bot.position, 32.0, game_instance)
		if bombs_near > bomb_count:
			bomb_count = bombs_near
			print("[TEST] Bot planted bomb #%d" % bomb_count)
		
		await get_tree().create_timer(0.1).timeout
	
	if not is_instance_valid(bot):
		test_result = "FAIL: Bot was destroyed during test"
		return
	
	if bot.has_method("is_dead") and bot.is_dead:
		test_result = "FAIL: Bot died (SUICIDE)"
		return
	
	test_result = "PASS: Bot survived corner position for %d seconds" % int(test_timeout)

func teardown() -> void:
	if is_instance_valid(bot):
		bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
