extends Node

## Auto-spawn AI bots for testing
## Add this as autoload in project settings

func _ready():
	# Wait a frame for server to initialize
	await get_tree().process_frame
	await get_tree().process_frame
	
	print("\n[BotSpawner] Checking for game instance...")
	
	# Find ServerMain node
	var server_main = get_tree().root.get_node_or_null("ServerMain")
	if not server_main:
		print("[BotSpawner] ERROR: ServerMain not found")
		return
	
	print("[BotSpawner] Found ServerMain")
	
	# Wait for game instance to be created
	for _i in range(50):  # Wait up to 5 seconds
		if server_main.active_games.size() > 0:
			print("[BotSpawner] Game instance found!")
			break
		await get_tree().create_timer(0.1).timeout
	
	if server_main.active_games.size() == 0:
		# Create a game instance manually
		print("[BotSpawner] No game found, creating one...")
		var game_id = "test_game"
		var game = load("res://game_instance.gd").new()
		game.name = "GameInstance_" + game_id
		server_main.add_child(game)
		server_main.active_games[game_id] = game
		
		# Wait for game to initialize and load map
		await get_tree().process_frame
		await get_tree().process_frame
		
		# Override soft block density to be more reasonable (40% instead of 71%)
		if not game.game_map.is_empty():
			print("[BotSpawner] Reducing soft blocks for better gameplay...")
			var soft_count = 0
			var total_soft_slots = 0
			
			# Count current soft blocks
			for y in range(game.game_map.size()):
				for x in range(game.game_map[y].size()):
					if game.game_map[y][x] == 2:
						total_soft_slots += 1
						soft_count += 1
			
			# Remove random soft blocks to reach 40% density
			var target_count = int(total_soft_slots * 0.4)
			while soft_count > target_count:
				var y = randi() % game.game_map.size()
				var x = randi() % game.game_map[y].size()
				if game.game_map[y][x] == 2:
					game.game_map[y][x] = 0  # Clear soft block
					soft_count -= 1
			
			print("[BotSpawner] Soft blocks reduced to ", soft_count, "/", total_soft_slots, " (", int(soft_count * 100.0 / total_soft_slots), "%)")
			
			# Rebuild collision after map modification
			# Remove old collision bodies
			for child in game.get_children():
				if child.name.begins_with("Tile_"):
					child.queue_free()
			await get_tree().process_frame
			
			# Recreate collision
			game.create_map_collision()
	
	# Get first game instance
	var game_instance = server_main.active_games.values()[0]
	print("[BotSpawner] Spawning 4 AI bots...")
	
	# Spawn 4 bots with different personalities
	for i in range(4):
		var personality = i  # 0=BALANCED, 1=AGGRESSIVE, 2=TIMID, 3=GREEDY
		game_instance.add_ai_bot(personality)
		await get_tree().create_timer(0.5).timeout  # Stagger spawns
	
	print("[BotSpawner] All bots spawned! Game starting...")
