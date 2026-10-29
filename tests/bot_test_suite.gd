extends Node
class_name BotTestSuite

var passed := 0
var failed := 0
var results := {}

var game_instance: GameInstance
var map_manager: MapManager
var bot_manager: Node
var bot_player: Node
var bot_controller: Node

# Configuration
var test_timeout := 5.0
var default_map_width := 15
var default_map_height := 13

func run_tests() -> void:
	print("Starting test suite: %s" % get_script().resource_path.get_file())
	await setup_suite()
	
	var all_methods = get_method_list()
	print("Methods found: %d" % all_methods.size())
	var test_methods = []
	for method in all_methods:
		if method.name.begins_with("test_"):
			test_methods.append(method.name)
	test_methods.sort()
			
	print("Test methods to run: %s" % str(test_methods))
	
	for method_name in test_methods:
		await run_single_test(method_name)
			
	await teardown_suite()

func run_single_test(method_name: String) -> void:
	print("  Running %s..." % method_name)
	
	# Reset state
	await setup_test()
	
	# Run test
	var result = await call(method_name)
	
	# Record result
	if result is bool and result == true:
		passed += 1
		results[method_name] = "PASS"
		print("    PASS")
	else:
		failed += 1
		results[method_name] = "FAIL: %s" % str(result)
		print("    FAIL: %s" % str(result))
		
	await teardown_test()

func setup_suite() -> void:
	# Create GameInstance
	game_instance = make_game_instance()
	game_instance.name = "TestGameInstance"
	
	# Mock ServerMain if needed or ensure it doesn't crash
	# GameInstance uses ServerMain.rpc for debug, which might fail if not running as server
	# But since we are running locally, it might just warn or do nothing
	
	add_child(game_instance)
	
	# Wait for ready
	await get_tree().process_frame
	await get_tree().process_frame
	
	# Force match start
	game_instance.countdown_time = 0.0
	game_instance.match_active = true
	
	map_manager = game_instance.map_manager
	bot_manager = game_instance.bot_manager
	seed(424242)
	
	# Disable auto-spawn in bot manager if possible, or just clear them
	if bot_manager:
		bot_manager.auto_spawn_count = 0
		# Clear any auto-spawned bots
		for peer_id in game_instance.players.keys():
			if peer_id < 0:
				game_instance.remove_player(peer_id)

func make_game_instance() -> GameInstance:
	return load("res://tests/support/fixture_game_instance.gd").new()

func teardown_suite() -> void:
	if is_instance_valid(game_instance):
		game_instance.queue_free()
	await get_tree().process_frame

func setup_test() -> void:
	# Default setup: Clear map
	clear_map()
	await get_tree().physics_frame
	await get_tree().physics_frame
	game_instance.ai_manager.configure(game_instance, game_instance.bot_manager.grid_sampler, default_map_width, default_map_height)

func teardown_test() -> void:
	# Remove all players/bots
	if is_instance_valid(game_instance):
		var peers = game_instance.players.keys().duplicate()
		for peer_id in peers:
			game_instance.remove_player(peer_id)
		
		# Clear bombs
		var bomb_ids = game_instance.bombs.keys().duplicate()
		for bomb_id in bomb_ids:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb):
				bomb.queue_free()
		game_instance.bombs.clear()

# --- Helpers ---

func clear_map() -> void:
	if not is_instance_valid(game_instance):
		return
		
	# Resize map if needed (initialize with 0)
	if game_instance.game_map.size() != default_map_height or (game_instance.game_map.size() > 0 and game_instance.game_map[0].size() != default_map_width):
		game_instance.game_map = []
		for y in range(default_map_height):
			var row = []
			for x in range(default_map_width):
				row.append(0)
			game_instance.game_map.append(row)
	
	# Clear all tiles using set_tile to ensure collision/AI update
	for y in range(default_map_height):
		for x in range(default_map_width):
			set_tile(x, y, 0)

func set_tile(x: int, y: int, type: int) -> void:
	if x < 0 or x >= default_map_width or y < 0 or y >= default_map_height:
		return
		
	# Update data
	if game_instance.game_map.size() > y and game_instance.game_map[y].size() > x:
		game_instance.game_map[y][x] = type
	
	game_instance.invalidate_public_observation()

	# Update collision
	var tile_name = "Tile_%d_%d" % [x, y]
	var existing_body = game_instance.get_node_or_null(tile_name)
	if existing_body:
		existing_body.queue_free()
		# Force process to ensure it's removed before adding new one? 
		# No, queue_free is enough if we don't add immediately with same name.
		# But we might add immediately. So rename old one to be safe.
		existing_body.name = "Deleted_" + tile_name
	
	if type == 1 or type == 2: # Wall or Soft Block
		var tile_body = StaticBody2D.new()
		tile_body.name = tile_name
		tile_body.collision_layer = 1 # Constants.COLLISION_LAYER_WALLS
		tile_body.collision_mask = 0
		
		var collision_shape = CollisionShape2D.new()
		var shape = RectangleShape2D.new() # Use Rectangle for tiles
		var tile_size = GameConfig.TILE_SIZE
		shape.size = Vector2(tile_size, tile_size)
		collision_shape.shape = shape
		tile_body.add_child(collision_shape)
		
		tile_body.position = Vector2(
			x * tile_size + tile_size / 2.0,
			y * tile_size + tile_size / 2.0
		)
		
		game_instance.add_child(tile_body)
		
	# Update AIManager pathfinder
	# GridSampler uses PhysicsServer2D, so updating collision bodies is enough.
	# No need to manually update AStarGrid2D if it's not exposed.
	pass

func spawn_bot_at(tile: Vector2i) -> Node:
	if not is_instance_valid(game_instance):
		return null
		
	# Get initial player count
	var initial_players = game_instance.players.keys()
	var was_active: bool = game_instance.match_active
	var manager_processing: bool = game_instance.bot_manager.is_physics_processing()
	game_instance.match_active = false
	game_instance.bot_manager.set_physics_process(false)
	
	# Spawn bot using GameInstance (which uses BotManager)
	print("Spawning bot... Initial players: ", initial_players)
	print("GameConfig.TILE_SIZE: ", GameConfig.TILE_SIZE)
	game_instance.spawn_bot("BALANCED")
	for pid in game_instance.players:
		if not pid in initial_players:
			var controller = bot_manager.get_bot_controller(pid)
			controller.active = false
			controller.process_mode = Node.PROCESS_MODE_DISABLED
	print("Spawned. Current players: ", game_instance.players.keys())
	
	# Find the new player
	var new_peer_id = 0
	for pid in game_instance.players:
		if not pid in initial_players:
			new_peer_id = pid
			break
			
	print("New peer ID: ", new_peer_id)
			
	if new_peer_id != 0:
		bot_player = game_instance.players[new_peer_id]
		
		# Wait for any initialization to complete (e.g. GameInstance resetting position)
		await get_tree().process_frame
		
		# Move to target tile
		var tile_size = GameConfig.TILE_SIZE
		var spawn_pos = Vector2(tile.x * tile_size + tile_size / 2.0, tile.y * tile_size + tile_size / 2.0)
		bot_player.position = spawn_pos
		print("Moved bot to %s (Tile %s). Actual pos: %s" % [spawn_pos, tile, bot_player.position])
		
		# Force physics update?
		if bot_player is CharacterBody2D:
			bot_player.move_and_slide() # Force update? No, just set position.
			
		# Clear any bombs placed by AI during the wait
		if not game_instance.bombs.is_empty():
			print("Clearing auto-placed bombs...")
			for b_id in game_instance.bombs.keys():
				var b = game_instance.bombs[b_id]
				if is_instance_valid(b):
					b.queue_free()
			game_instance.bombs.clear()
			# Reset bot cooldown?
			# bot_player.bomb_cooldown = 0.0
		
		# Get controller
		if bot_manager:
			bot_controller = bot_manager.get_bot_controller(new_peer_id)
		await get_tree().physics_frame
		if bot_player.get_tile_position() != tile or bot_controller == null:
			push_error("Fixture did not create a controlled bot at the requested tile")
		game_instance.match_active = was_active
		game_instance.bot_manager.set_physics_process(manager_processing)
		bot_controller.process_mode = Node.PROCESS_MODE_INHERIT
		bot_controller.active = was_active
			
		return bot_player
		
	game_instance.match_active = was_active
	game_instance.bot_manager.set_physics_process(manager_processing)
	return null

func wait_for_condition(condition_func: Callable, timeout: float = 2.0) -> bool:
	var time = 0.0
	while time < timeout:
		if condition_func.call():
			return true
		await get_tree().process_frame
		time += get_process_delta_time()
	return false

func assert_true(condition: bool, message: String = "Assertion failed") -> Variant:
	if not condition:
		return message
	return true

func assert_false(condition: bool, message: String = "Assertion failed") -> Variant:
	if condition:
		return message
	return true

func assert_eq(actual, expected, message: String = "") -> Variant:
	if actual != expected:
		return "%s (Expected %s, got %s)" % [message, str(expected), str(actual)]
	return true
