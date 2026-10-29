extends "res://tests/support/legacy_bot_scenario.gd"

## Test: Bot must not commit suicide when spawned in a corner

var test_name := "no_suicide_corner"

var bot: Node
var initial_tile: Vector2i
var test_result := ""

func _init() -> void:
	test_timeout = 10.0

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	await get_tree().create_timer(1.0).timeout
	
	# Spawn bot in a corner
	var corner_tile = Vector2i(2, 2)
	bot = await BotTestHelpers.spawn_bot(corner_tile, "BALANCED", game_instance)
	
	if not bot:
		test_result = "FAIL: Bot failed to spawn"
		return
	
	initial_tile = BotTestHelpers.world_to_tile(bot.position)
	
	# Author an actual corner, with two open escape directions.
	set_tile(initial_tile.x - 1, initial_tile.y, 1)
	set_tile(initial_tile.x, initial_tile.y - 1, 1)
	
	await get_tree().create_timer(0.5).timeout
	print("[TEST] Bot spawned in corner at tile %s" % initial_tile)

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match to start
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	var previous_bombs: int = game_instance.next_bomb_id
	game_instance.place_bomb(bot)
	if game_instance.next_bomb_id != previous_bombs + 1:
		test_result = "FAIL: Controlled corner bomb was not placed"
		return
	
	print("[TEST] Monitoring bot in corner for %d seconds..." % int(test_timeout))
	
	var start_time = Engine.get_physics_frames()
	var max_wait = int(test_timeout * Engine.physics_ticks_per_second)
	var bomb_count = 0
	
	while Engine.get_physics_frames() - start_time < max_wait:
		if not is_instance_valid(bot):
			test_result = "FAIL: Bot was destroyed"
			return
		
		if bot.is_dead:
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
	
	if bot.is_dead:
		test_result = "FAIL: Bot died (SUICIDE)"
		return
	
	test_result = "PASS: Bot survived corner position for %d seconds" % int(test_timeout)

func teardown() -> void:
	if is_instance_valid(bot):
		bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
