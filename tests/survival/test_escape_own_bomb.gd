extends "res://tests/support/legacy_bot_scenario.gd"

## Test: Bot must escape from its own bomb in an open area

var test_name := "escape_own_bomb_open_area"

var bot: Node
var initial_tile: Vector2i
var bomb_planted := false
var bomb_node: Node
var test_result := ""

func _init() -> void:
	test_timeout = 8.0

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	# Wait for game to be ready
	await get_tree().create_timer(1.0).timeout
	
	# Spawn bot at center of map
	var map_center = Vector2i(10, 7)
	bot = await BotTestHelpers.spawn_bot(map_center, "BALANCED", game_instance)
	
	if not bot:
		test_result = "FAIL: Bot failed to spawn"
		return
	
	initial_tile = BotTestHelpers.world_to_tile(bot.position)
	
	# Clear 5x5 area around bot
	BotTestHelpers.clear_area(initial_tile, 3, game_instance)
	
	await get_tree().create_timer(0.5).timeout
	
	print("[TEST] Bot spawned at tile %s" % initial_tile)

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match to start
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			print("[TEST] Waiting for match to start...")
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	# Exercise the stated scenario instead of passing without a bomb.
	initial_tile = bot.get_tile_position()
	var previous_bombs: int = game_instance.next_bomb_id
	game_instance.place_bomb(bot)
	if game_instance.next_bomb_id != previous_bombs + 1:
		test_result = "FAIL: Controlled own bomb was not placed"
		return
	# Force bot to plant bomb by setting up farming scenario
	print("[TEST] Monitoring bot behavior...")
	
	var start_time = Engine.get_physics_frames()
	var bomb_detected = false
	var escape_detected = false
	var max_wait = int(test_timeout * Engine.physics_ticks_per_second)
	
	while Engine.get_physics_frames() - start_time < max_wait:
		if not is_instance_valid(bot):
			test_result = "FAIL: Bot was destroyed prematurely"
			return
		
		# Check if bot is dead
		if bot.is_dead:
			test_result = "FAIL: Bot died (SUICIDE)"
			return
		
		# Check for bombs near bot
		var bombs_near = BotTestHelpers.count_bombs_near(bot.position, 32.0, game_instance)
		if bombs_near > 0 and not bomb_detected:
			bomb_detected = true
			bomb_planted = true
			var bot_tile = BotTestHelpers.world_to_tile(bot.position)
			print("[TEST] Bomb detected near bot at tile %s" % bot_tile)
		
		# Check if bot moved away after planting
		if bomb_detected and not escape_detected:
			var current_tile = BotTestHelpers.world_to_tile(bot.position)
			var distance = initial_tile.distance_to(current_tile)
			if distance >= 2:
				escape_detected = true
				print("[TEST] Bot escaped to tile %s (distance: %.1f)" % [current_tile, distance])
		
		await get_tree().create_timer(0.1).timeout
	
	# Final checks
	if not is_instance_valid(bot):
		test_result = "FAIL: Bot was destroyed"
		return
	
	if bot.is_dead:
		test_result = "FAIL: Bot died from explosion (SUICIDE)"
		return
	
	if not bomb_detected:
		test_result = "FAIL: Bot did not plant a bomb (test inconclusive)"
		return
	
	if not escape_detected:
		test_result = "FAIL: Bot did not escape from bomb"
		return
	
	test_result = "PASS: Bot survived and escaped successfully"

func teardown() -> void:
	if is_instance_valid(bot):
		bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
