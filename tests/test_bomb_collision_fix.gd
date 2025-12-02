extends Node

const GameInstanceScript = preload("res://game_instance.gd")
const ServerPlayerScript = preload("res://shared/entities/server_player.gd")
const ServerBombScript = preload("res://shared/entities/server_bomb.gd")
# Remove GameConfig preload to avoid shadowing the singleton

var game_instance: GameInstance
var player1: ServerPlayer
var player2: ServerPlayer

func _ready():
	print("Starting Bomb Collision Fix Verification Test...")
	
	# Wait for autoloads to be ready if any
	await get_tree().process_frame
	
	# Setup minimal game environment
	game_instance = GameInstanceScript.new()
	# Mock map data
	game_instance.game_map = []
	for y in range(5):
		var row = []
		for x in range(5):
			row.append(0) # Empty tiles
		game_instance.game_map.append(row)
	
	game_instance.match_active = true # Allow bomb placement
	add_child(game_instance)
	
	# Use Constants.TILE_SIZE if GameConfig is not available, or hardcode 64
	var tile_size = 16  # Saturn Bomberman native
	if has_node("/root/GameConfig"):
		tile_size = get_node("/root/GameConfig").TILE_SIZE
	
	# Spawn two players at the same location (1, 1)
	var spawn_pos = Vector2(1 * tile_size + tile_size / 2, 1 * tile_size + tile_size / 2)
	
	print("Spawning players at ", spawn_pos)
	game_instance.add_player(1, "Player1", spawn_pos)
	game_instance.add_player(2, "Player2", spawn_pos)
	
	player1 = game_instance.players[1]
	player2 = game_instance.players[2]
	
	# Wait for physics frame
	await get_tree().process_frame
	await get_tree().process_frame
	
	run_test()

func run_test():
	print("\n--- TEST: Player1 places bomb on top of Player2 ---")
	
	# Player 1 places bomb
	print("Player 1 placing bomb...")
	game_instance.place_bomb(player1)
	
	await get_tree().process_frame
	await get_tree().process_frame
	
	# Verify bomb exists
	if game_instance.bombs.size() == 0:
		print("FAIL: Bomb not placed")
		exit_test(1)
		return
		
	var bomb = game_instance.bombs.values()[0]
	print("Bomb placed at ", bomb.get_tile_position())
	
	# Check collision exceptions
	print("\nChecking collision exceptions...")
	var p1_exceptions = player1.get_collision_exceptions()
	var p2_exceptions = player2.get_collision_exceptions()
	
	var p1_safe = false
	for exception in p1_exceptions:
		if exception == bomb:
			p1_safe = true
			break
			
	var p2_safe = false
	for exception in p2_exceptions:
		if exception == bomb:
			p2_safe = true
			break
	
	if p1_safe:
		print("PASS: Player 1 has collision exception (Owner)")
	else:
		print("FAIL: Player 1 missing collision exception")
		
	if p2_safe:
		print("PASS: Player 2 has collision exception (Bystander)")
	else:
		print("FAIL: Player 2 missing collision exception")
	
	if p1_safe and p2_safe:
		print("\nSUCCESS: All players on tile have collision exceptions!")
		exit_test(0)
	else:
		print("\nFAILURE: Missing collision exceptions!")
		exit_test(1)

func exit_test(code):
	get_tree().quit(code)
