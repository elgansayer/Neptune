extends Node

## 4-BOT BATTLE ROYALE - Ultimate suicide prevention test
## All 4 bots compete, testing all edge cases

var test_name := "4_bot_battle_royale"
var test_timeout := 120.0  # 2 minutes
var bots: Array = []
var test_result := ""
var game_instance
var initial_bot_count := 4
var max_deaths_allowed := 2  # Allow some combat deaths, but track suicides
var suicide_count := 0
var combat_deaths := 0

func setup() -> void:
	game_instance = BotTestHelpers.get_game_instance()
	if not game_instance:
		test_result = "FAIL: No game instance found"
		return
	
	await get_tree().create_timer(1.0).timeout
	
	# Spawn 4 bots with different personalities in corner positions
	var spawn_configs = [
		{"tile": Vector2i(2, 2), "personality": "AGGRESSIVE"},
		{"tile": Vector2i(18, 2), "personality": "DEFENSIVE"},
		{"tile": Vector2i(2, 11), "personality": "BALANCED"},
		{"tile": Vector2i(18, 11), "personality": "TRAPPER"}
	]
	
	print("[TEST] Spawning 4-bot battle royale...")
	for i in range(spawn_configs.size()):
		var config = spawn_configs[i]
		var bot = BotTestHelpers.spawn_bot(config["tile"], config["personality"], game_instance)
		if bot:
			bots.append(bot)
			bot.set_meta("bot_id", i)
			bot.set_meta("personality", config["personality"])
			bot.set_meta("last_known_tile", config["tile"])
			# Clear spawn area
			BotTestHelpers.clear_area(config["tile"], 2, game_instance)
	
	if bots.size() < initial_bot_count:
		test_result = "FAIL: Failed to spawn all bots"
		return
	
	await get_tree().create_timer(0.5).timeout
	print("[TEST] Battle royale ready: %d bots spawned" % bots.size())

func execute() -> void:
	if test_result != "":
		return
	
	# Wait for match
	if game_instance.has_method("start_match"):
		if not game_instance.match_active:
			await BotTestHelpers.wait_for_condition(func(): return game_instance.match_active, 10.0)
	
	await get_tree().create_timer(1.0).timeout
	
	print("[TEST] ⚔️  BATTLE ROYALE STARTED - %d seconds" % int(test_timeout))
	
	var start_time = Time.get_ticks_msec()
	var max_wait = test_timeout * 1000
	var last_report = start_time
	var bot_states = {}
	
	# Initialize bot tracking
	for bot in bots:
		if is_instance_valid(bot):
			var bot_id = bot.get_meta("bot_id")
			bot_states[bot_id] = {
				"alive": true,
				"bombs_planted": 0,
				"tiles_traveled": 0,
				"last_pos": bot.position
			}
	
	while Time.get_ticks_msec() - start_time < max_wait:
		var current_time = Time.get_ticks_msec()
		
		# Check each bot
		for bot in bots:
			if not is_instance_valid(bot):
				continue
			
			var bot_id = bot.get_meta("bot_id")
			var state = bot_states.get(bot_id, {})
			
			if not state.get("alive", false):
				continue
			
			# Check death
			if bot.has_method("is_dead") and bot.is_dead:
				state["alive"] = false
				var personality = bot.get_meta("personality", "UNKNOWN")
				var last_tile = bot.get_meta("last_known_tile", Vector2i(-1, -1))
				
				# Try to determine if suicide or combat death
				# Suicide = died from own bomb (no other bots nearby)
				var nearby_bots = 0
				for other_bot in bots:
					if other_bot != bot and is_instance_valid(other_bot):
						if other_bot.position.distance_to(bot.position) < GameConfig.TILE_SIZE * 4.0:
							nearby_bots += 1
				
				if nearby_bots == 0:
					suicide_count += 1
					print("[TEST] 💀 Bot %d (%s) SUICIDE at %s" % [bot_id, personality, last_tile])
				else:
					combat_deaths += 1
					print("[TEST] ⚔️  Bot %d (%s) killed in combat" % [bot_id, personality])
			else:
				# Update position tracking
				var current_tile = BotTestHelpers.world_to_tile(bot.position)
				bot.set_meta("last_known_tile", current_tile)
				
				# Track movement
				var distance = bot.position.distance_to(state.get("last_pos", bot.position))
				if distance > 1.0:
					state["tiles_traveled"] += distance / 16.0
					state["last_pos"] = bot.position
		
		# Periodic report
		if current_time - last_report >= 10000:  # Every 10 seconds
			last_report = current_time
			var alive = 0
			for bot_id in bot_states:
				if bot_states[bot_id].get("alive", false):
					alive += 1
			var elapsed = (current_time - start_time) / 1000.0
			print("[TEST] @ %.0fs: %d alive, %d suicides, %d combat deaths" % [elapsed, alive, suicide_count, combat_deaths])
		
		await get_tree().create_timer(0.1).timeout
	
	# Final evaluation
	if suicide_count > 0:
		test_result = "FAIL: %d SUICIDES detected in battle royale (combat deaths: %d)" % [suicide_count, combat_deaths]
		return
	
	var survivors = 0
	for bot_id in bot_states:
		if bot_states[bot_id].get("alive", false):
			survivors += 1
	
	test_result = "PASS: 0 suicides in %ds battle (%d survivors, %d combat deaths)" % [int(test_timeout), survivors, combat_deaths]

func teardown() -> void:
	for bot in bots:
		if is_instance_valid(bot):
			bot.queue_free()
	
	print("[TEST] %s: %s" % [test_name, test_result])
