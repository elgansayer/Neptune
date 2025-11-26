extends Node
class_name BotTestHelpers

## Helper utilities for bot testing

static func spawn_bot(tile: Vector2i, personality := "BALANCED", game_instance = null) -> Node:
	"""Spawn a bot at a specific tile position"""
	if not game_instance:
		game_instance = get_game_instance()
	
	if not game_instance:
		push_error("[TestHelpers] No game instance found")
		return null
	
	var peer_id = -1000 - randi() % 1000
	game_instance.add_player(peer_id, "TestBot_%d" % abs(peer_id), Vector2.ZERO, true, personality)
	
	if not game_instance.players.has(peer_id):
		push_error("[TestHelpers] Failed to spawn bot")
		return null
	
	var bot = game_instance.players[peer_id]
	bot.position = tile_to_world_center(tile)
	return bot

static func get_game_instance():
	"""Get the current game instance"""
	var tree = Engine.get_main_loop() as SceneTree
	if tree:
		for child in tree.root.get_children():
			if child.has_method("add_player"):
				return child
	return null

static func tile_to_world_center(tile: Vector2i) -> Vector2:
	"""Convert tile coordinates to world position (center of tile)"""
	return Vector2(tile.x * 16 + 8, tile.y * 16 + 8)

static func clear_tile(tile: Vector2i, game_instance = null) -> void:
	"""Clear a tile (remove any blocks)"""
	if not game_instance:
		game_instance = get_game_instance()
	
	if not game_instance or not game_instance.has_method("destroy_block_at"):
		return
	
	game_instance.destroy_block_at(tile)

static func place_bomb(tile: Vector2i, fuse_time := 3.0, owner_id := -999) -> Node:
	"""Place a bomb at a specific tile"""
	var game_instance = get_game_instance()
	if not game_instance:
		return null
	
	# Create bomb through game instance if possible
	if game_instance.has_method("create_bomb"):
		return game_instance.create_bomb(owner_id, tile, fuse_time)
	
	return null

static func wait_for_condition(condition: Callable, timeout: float) -> bool:
	"""Wait for a condition to become true, with timeout"""
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		return false
	
	var elapsed = 0.0
	while elapsed < timeout:
		if condition.call():
			return true
		await tree.create_timer(0.1).timeout
		elapsed += 0.1
	return false

static func measure_distance_traveled(bot: Node, duration: float) -> float:
	"""Measure how far a bot travels in a given duration"""
	if not is_instance_valid(bot):
		return 0.0
	
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		return 0.0
	
	var start_pos = bot.position
	await tree.create_timer(duration).timeout
	
	if not is_instance_valid(bot):
		return 0.0
	
	return bot.position.distance_to(start_pos)

static func is_bot_in_danger(bot: Node) -> bool:
	"""Check if bot is currently in danger"""
	if not is_instance_valid(bot):
		return false
	
	var game_instance = get_game_instance()
	if not game_instance or not game_instance.ai_manager:
		return false
	
	var tile = world_to_tile(bot.position)
	var threat_matrix = game_instance.ai_manager.threat_matrix
	var tile_key = "%d,%d" % [tile.x, tile.y]
	
	return threat_matrix.has(tile_key)

static func world_to_tile(pos: Vector2) -> Vector2i:
	"""Convert world position to tile coordinates"""
	return Vector2i(int(pos.x / 16), int(pos.y / 16))

static func get_safe_tiles_around(center: Vector2i, radius: int, game_instance = null) -> Array[Vector2i]:
	"""Get all safe (non-threatened) tiles around a center point"""
	if not game_instance:
		game_instance = get_game_instance()
	
	var safe_tiles: Array[Vector2i] = []
	
	if not game_instance or not game_instance.ai_manager:
		return safe_tiles
	
	var threat_matrix = game_instance.ai_manager.threat_matrix
	
	for dx in range(-radius, radius + 1):
		for dy in range(-radius, radius + 1):
			var tile = center + Vector2i(dx, dy)
			var tile_key = "%d,%d" % [tile.x, tile.y]
			if not threat_matrix.has(tile_key):
				safe_tiles.append(tile)
	
	return safe_tiles

static func clear_area(center: Vector2i, radius: int, game_instance = null) -> void:
	"""Clear all blocks in an area"""
	if not game_instance:
		game_instance = get_game_instance()
	
	for dx in range(-radius, radius + 1):
		for dy in range(-radius, radius + 1):
			clear_tile(center + Vector2i(dx, dy), game_instance)

static func count_bombs_near(pos: Vector2, radius: float, game_instance = null) -> int:
	"""Count bombs within radius of position"""
	if not game_instance:
		game_instance = get_game_instance()
	
	if not game_instance or not game_instance.has_node("Bombs"):
		return 0
	
	var count = 0
	var bombs_node = game_instance.get_node("Bombs")
	for bomb in bombs_node.get_children():
		if bomb.position.distance_to(pos) <= radius:
			count += 1
	
	return count
