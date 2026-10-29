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
	
	if tile.x <= 0 or tile.y <= 0 or tile.y >= game_instance.game_map.size() - 1 or tile.x >= game_instance.game_map[0].size() - 1:
		push_error("[TestHelpers] Spawn outside fixture interior: " + str(tile))
		return null
	var existing: Array = game_instance.players.keys()
	game_instance.spawn_bot(personality)
	var peer_id := 0
	for candidate in game_instance.players:
		if not candidate in existing:
			peer_id = candidate
	if peer_id == 0 or game_instance.bot_manager.get_bot_controller(peer_id) == null:
		push_error("[TestHelpers] Failed to spawn bot")
		return null
	
	var bot = game_instance.players[peer_id]
	var controller = game_instance.bot_manager.get_bot_controller(peer_id)
	controller.active = false
	controller.process_mode = Node.PROCESS_MODE_DISABLED
	bot.position = tile_to_world_center(tile)
	bot.set_meta("fixture_spawn", tile)
	await game_instance.get_tree().physics_frame
	await game_instance.get_tree().physics_frame
	if bot.get_tile_position() != tile or bot.is_dead:
		push_error("[TestHelpers] Bot did not start alive at requested tile")
		return null
	return bot

static func get_game_instance():
	"""Get the current game instance"""
	var tree = Engine.get_main_loop() as SceneTree
	if tree:
		var games := tree.get_nodes_in_group("bot_test_game")
		if games.size() == 1:
			return games[0]
	return null

static func tile_to_world_center(tile: Vector2i) -> Vector2:
	"""Convert tile coordinates to world position (center of tile)"""
	return Vector2(tile) * GameConfig.TILE_SIZE + Vector2.ONE * GameConfig.TILE_SIZE / 2.0

static func clear_tile(tile: Vector2i, game_instance = null) -> void:
	"""Clear a tile (remove any blocks)"""
	if not game_instance:
		game_instance = get_game_instance()
	
	if not game_instance or not game_instance.has_meta("fixture_owner"):
		return
	if tile.x <= 0 or tile.y <= 0 or tile.y >= game_instance.game_map.size() - 1 or tile.x >= game_instance.game_map[0].size() - 1:
		return
	game_instance.get_meta("fixture_owner").set_tile(tile.x, tile.y, 0)

static func place_bomb(tile: Vector2i, fuse_time := 3.0, owner_id := -999) -> Node:
	"""Place a bomb at a specific tile"""
	var game_instance = get_game_instance()
	if not game_instance:
		return null
	
	# Scenario adapter: real bomb scene and real explosion/damage callbacks.
	var bomb = game_instance.ServerBombScene.instantiate()
	bomb.bomb_id = str(game_instance.next_bomb_id)
	game_instance.next_bomb_id += 1
	bomb.owner_id = str(owner_id)
	bomb.fuse_time = fuse_time
	bomb.fuse_lower_bound = fuse_time
	bomb.explosion_timer = 0.0
	bomb.position = tile_to_world_center(tile)
	bomb.game_instance = game_instance
	game_instance.bombs[bomb.bomb_id] = bomb
	game_instance.add_child(bomb)
	bomb.exploded.connect(game_instance._on_bomb_exploded)
	bomb.explosion_expanded.connect(func(tiles): game_instance._on_explosion_expanded(bomb, tiles))
	bomb.tree_exited.connect(func(): game_instance.bombs.erase(bomb.bomb_id))
	return bomb

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
	return Vector2i(floori(pos.x / GameConfig.TILE_SIZE), floori(pos.y / GameConfig.TILE_SIZE))

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
	
	if not game_instance:
		return 0
	
	var count = 0
	for bomb in game_instance.bombs.values():
		if is_instance_valid(bomb) and not bomb.has_exploded and bomb.position.distance_to(pos) <= radius:
			count += 1
	
	return count
