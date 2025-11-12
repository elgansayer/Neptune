extends Node

## Debug bot spawner for development
## Press F9 to spawn AI bots in the current game

const AIPlayerScript = preload("res://shared/entities/ai_player.gd")

var game_instance = null

func _ready():
	print("[DebugBotSpawner] Ready - Press F9 to spawn bots")

func _input(event):
	if event is InputEventKey and event.pressed and event.keycode == KEY_F9:
		spawn_bots()

func spawn_bots():
	# Find active game instance
	game_instance = null
	
	# Check if we're running as server
	var server_main = get_tree().root.get_node_or_null("ServerMain")
	if server_main and server_main.active_games.size() > 0:
		game_instance = server_main.active_games.values()[0]
	
	if not game_instance:
		print("[DebugBotSpawner] No active game found!")
		return
	
	print("[DebugBotSpawner] Spawning 4 AI bots...")
	
	var personalities = [0, 1, 2, 3]  # BALANCED, AGGRESSIVE, DEFENSIVE, GREEDY
	var spawn_points = [
		Vector2i(2, 2),
		Vector2i(18, 2),
		Vector2i(2, 12),
		Vector2i(18, 12)
	]
	
	for i in range(4):
		var bot_id = 1000 + i
		var personality = personalities[i]
		
		# Create AI bot
		var bot = AIPlayerScript.new()
		bot.player_id = str(bot_id)
		bot.username = _get_bot_name(personality, i)
		bot.name = "Player_" + str(bot_id)
		
		# Set spawn position
		var spawn_tile = spawn_points[i]
		var spawn_pos = Vector2(spawn_tile) * game_instance.TILE_SIZE + Vector2.ONE * (game_instance.TILE_SIZE / 2.0)
		bot.position = spawn_pos
		
		# Add to game
		game_instance.add_child(bot)
		game_instance.players[bot_id] = bot
		
		# Initialize AI
		# Note: setup_ai is a dynamic method call - parser warning can be ignored
		if bot.has_method("setup_ai"):
			bot.setup_ai(game_instance, personality)
		
		print("[DebugBotSpawner] Spawned bot: ", bot.username, " at ", spawn_tile)
	
	print("[DebugBotSpawner] ✓ 4 bots spawned successfully!")

func _get_bot_name(personality: int, index: int) -> String:
	var personality_names = ["Balanced", "Aggressive", "Timid", "Greedy"]
	var suffix = randi() % 1000
	return personality_names[personality] + "_Bot_" + str(suffix)
