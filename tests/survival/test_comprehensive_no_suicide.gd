extends "res://tests/support/legacy_bot_scenario.gd"

## Multi-bot survival diagnostic; deaths are not automatically self-KOs.
## Tests multiple scenarios where bots might commit suicide

var test_name := "comprehensive_no_suicide_test"

var bots: Array = []
var test_result := ""
var death_detected := false
var bombs_planted_count := 0
var death_count := 0

func _init() -> void:
	test_timeout = 60.0

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	await get_tree().create_timer(1.0).timeout
	
	# Spawn 3 bots in different scenarios
	var spawn_positions = [
		Vector2i(5, 5),   # Corner-ish
		Vector2i(10, 7),  # Center
		Vector2i(15, 10)  # Edge
	]
	
	print("[TEST] Spawning 3 bots in different positions...")
	for i in range(3):
		var bot = await BotTestHelpers.spawn_bot(spawn_positions[i], "BALANCED", game_instance)
		if bot:
			bots.append(bot)
			# Clear area around each bot
			BotTestHelpers.clear_area(spawn_positions[i], 3, game_instance)
	
	if bots.size() < 3:
		test_result = "FAIL: Failed to spawn all 3 bots"
		return
	
	await get_tree().create_timer(0.5).timeout
	print("[TEST] All bots spawned successfully")

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match to start
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			print("[TEST] Waiting for match to start...")
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	await get_tree().create_timer(1.0).timeout
	
	print("[TEST] Observing bots for %d seconds..." % int(test_timeout))
	print("[TEST] Monitoring for suicides, bomb placements, and deaths")
	
	var start_time = Engine.get_physics_frames()
	var max_wait = int(test_timeout * Engine.physics_ticks_per_second)
	var last_report_time = start_time
	var report_interval = 5 * Engine.physics_ticks_per_second  # Report every 5 seconds
	
	while Engine.get_physics_frames() - start_time < max_wait:
		# Check each bot
		for i in range(bots.size()):
			var bot = bots[i]
			if not is_instance_valid(bot):
				if not death_detected:
					print("[TEST] ❌ Bot %d destroyed prematurely!" % i)
					death_detected = true
					death_count += 1
				continue
			
			# Check if dead
			if bot.is_dead:
				if not death_detected:
					var bot_tile = BotTestHelpers.world_to_tile(bot.position)
					print("[TEST] ❌ Bot %d DIED at tile %s - DEATH OBSERVED (cause unverified)" % [i, bot_tile])
					death_detected = true
					death_count += 1
		
		# Count total bombs
		var total_bombs = BotTestHelpers.count_bombs_near(Vector2(160, 112), 500.0, game_instance)
		if total_bombs > bombs_planted_count:
			var new_bombs = total_bombs - bombs_planted_count
			bombs_planted_count = total_bombs
			print("[TEST] 💣 +%d bomb(s) planted (total: %d)" % [new_bombs, bombs_planted_count])
		
		# Periodic status report
		var current_time = Engine.get_physics_frames()
		if current_time - last_report_time >= report_interval:
			last_report_time = current_time
			var alive_count = 0
			for bot in bots:
				if is_instance_valid(bot) and not bot.is_dead:
					alive_count += 1
			var elapsed_sec = (current_time - start_time) / float(Engine.physics_ticks_per_second)
			print("[TEST] Status @ %.1fs: %d/%d bots alive, %d bombs planted" % [elapsed_sec, alive_count, bots.size(), bombs_planted_count])
		
		await get_tree().create_timer(0.1).timeout
	
	# Final evaluation
	if death_detected:
		test_result = "FAIL: %d bot death(s) detected out of %d bots" % [death_count, bots.size()]
		return
	
	# Count surviving bots
	var survivors = 0
	for bot in bots:
		if is_instance_valid(bot) and not bot.is_dead:
			survivors += 1
	
	if survivors < bots.size():
		test_result = "FAIL: %d/%d bots died during test" % [bots.size() - survivors, bots.size()]
		return
	
	test_result = "PASS: All %d bots survived %d seconds (%d bombs planted, no observed deaths)" % [bots.size(), int(test_timeout), bombs_planted_count]

func teardown() -> void:
	for bot in bots:
		if is_instance_valid(bot):
			bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
