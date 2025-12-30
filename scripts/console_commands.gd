extends Node
class_name ConsoleCommands

## Comprehensive console commands for Bomberman
## Registers all game commands with LimboConsole

var game_instance_ref = null # Optional pre-set reference

func register_all_commands(game_inst = null) -> void:
	game_instance_ref = game_inst
	
	LimboConsole.info("[Console] Registering Bomberman commands...")
	
	# Register all command categories
	_register_spawn_commands()
	_register_player_commands()
	_register_map_commands()
	_register_bomb_commands()
	_register_bot_commands()
	_register_item_commands()
	_register_tirra_commands()
	_register_game_commands()
	_register_debug_commands()
	_register_camera_commands()
	_register_network_commands()
	
	LimboConsole.info("[Console] ✅ All commands registered! Type 'commands' to see full list")

# Get game instance dynamically - works on both server and client
func _get_game_instance():
	# First try the stored reference
	if game_instance_ref and is_instance_valid(game_instance_ref):
		return game_instance_ref
	
	# Try to find it in the scene tree
	var game_view = get_tree().get_first_node_in_group("game_view")
	if game_view and game_view.has_method("get_game_instance"):
		return game_view.get_game_instance()
	
	# Try finding it directly
	for node in get_tree().root.get_children():
		if node.name == "GameInstance" or node.get_script() == load("res://_get_game_instance().gd"):
			game_instance_ref = node
			return node
	
	return null

# ============================================================================
# SPAWN COMMANDS (Legacy compatibility)
# ============================================================================

func _register_spawn_commands() -> void:
	LimboConsole.register_command(_cmd_spawn_bomb, "spawn bomb", "Spawn bomb at tile (x, y) [range] [fuse]")
	LimboConsole.register_command(_cmd_spawn_bot, "spawn bot", "Spawn AI bot [personality]")
	LimboConsole.register_command(_cmd_spawn_fakeplayer, "spawn fakeplayer", "Spawn fake player [name]")
	LimboConsole.register_command(_cmd_spawn_tirra, "spawn tirra", "Spawn Tirra mount [level: baby/teen/adult]")

func _cmd_spawn_bomb(x: int, y: int, range: int = 3, fuse: float = 3.0) -> void:
	if not _validate_game():
		return
	
	var game_instance = _get_game_instance()
	var tile_pos = Vector2i(x, y)
	if not _validate_tile(tile_pos):
		return
	
	var bomb = load("res://shared/entities/ServerBomb.tscn").instantiate()
	bomb.bomb_id = str(game_instance.next_bomb_id)
	game_instance.next_bomb_id += 1
	bomb.explosion_range = range
	bomb.fuse_time = fuse
	bomb.position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	bomb.name = "Bomb_" + bomb.bomb_id
	bomb.game_instance = game_instance
	
	game_instance.bombs[bomb.bomb_id] = bomb
	game_instance.add_child(bomb)
	bomb.exploded.connect(game_instance._on_bomb_exploded)
	
	LimboConsole.info("💣 Spawned bomb at (%d, %d) range=%d fuse=%.1fs" % [x, y, range, fuse])

func _cmd_spawn_bot(personality: String = "BALANCED") -> void:
	if not _validate_game():
		return
	
	personality = personality.to_upper()
	var valid_personalities = ["BALANCED", "AGGRESSIVE", "DEFENSIVE", "COMPETITIVE", "TRAPPER"]
	if personality not in valid_personalities:
		LimboConsole.error("❌ Invalid personality. Use: " + ", ".join(valid_personalities))
		return
	
	_get_game_instance().spawn_bot(personality)
	LimboConsole.info("🤖 Spawned %s bot" % personality)

func _cmd_spawn_fakeplayer(name: String = "FakePlayer") -> void:
	if not _validate_game():
		return
	
	var peer_id = -1000 - randi() % 9000
	var spawn_pos = _get_game_instance().get_next_spawn_point()
	_get_game_instance().add_player(peer_id, name, spawn_pos, false, "")
	LimboConsole.info("👤 Spawned fake player '%s' (ID: %d)" % [name, peer_id])

func _cmd_spawn_tirra(level: String = "baby") -> void:
	if not _validate_game():
		return
	
	var tirra_scene = load("res://tirra.tscn")
	if not tirra_scene:
		LimboConsole.error("❌ Failed to load tirra.tscn - ensure blue-tirra.pck is mounted")
		return
	
	var tirra = tirra_scene.instantiate()
	tirra.name = "Tirra_" + str(randi())
	
	# Set growth level
	var growth_level = 0
	match level.to_lower():
		"baby": growth_level = 0
		"teen": growth_level = 1
		"adult": growth_level = 2
		_:
			LimboConsole.warning("⚠️ Unknown level '%s', using 'baby'" % level)
	
	if tirra.has_method("set") and "current_level" in tirra:
		tirra.current_level = growth_level
	
	# Spawn at random location
	var spawn_pos = _get_game_instance().get_next_spawn_point()
	tirra.global_position = spawn_pos
	
	_get_game_instance().add_child(tirra)
	LimboConsole.info("🦎 Spawned %s Tirra at %s" % [level, spawn_pos])

# ============================================================================
# PLAYER COMMANDS
# ============================================================================

func _register_player_commands() -> void:
	LimboConsole.register_command(_cmd_player_list, "player list", "List all players")
	LimboConsole.register_command(_cmd_player_kill, "player kill", "Kill player by peer_id")
	LimboConsole.register_command(_cmd_player_tp, "player tp", "Teleport player to tile (peer_id, x, y)")
	LimboConsole.register_command(_cmd_player_tp, "player teleport", "Teleport player to tile (peer_id, x, y)")
	LimboConsole.register_command(_cmd_player_god, "player god", "Toggle god mode (peer_id, on/off)")
	LimboConsole.register_command(_cmd_player_speed, "player speed", "Set player speed (peer_id, level 0-8)")
	LimboConsole.register_command(_cmd_player_bombs, "player bombs", "Set max bombs (peer_id, count 1-10)")
	LimboConsole.register_command(_cmd_player_range, "player range", "Set bomb range (peer_id, range 1-16)")
	LimboConsole.register_command(_cmd_player_respawn, "player respawn", "Respawn dead player (peer_id)")
	LimboConsole.register_command(_cmd_player_immortal, "player immortal", "Make player immortal (peer_id, seconds)")
	LimboConsole.register_command(_cmd_player_virus, "player virus", "Apply virus to player (peer_id, type 1-9)")
	LimboConsole.register_command(_cmd_player_maxout, "player maxout", "Give player max stats (peer_id)")
	
	# Add autocomplete for player IDs
	LimboConsole.add_argument_autocomplete_source("player kill", 1, 
		func(): return _get_player_ids())
	LimboConsole.add_argument_autocomplete_source("player tp", 1, 
		func(): return _get_player_ids())
	LimboConsole.add_argument_autocomplete_source("player god", 1, 
		func(): return _get_player_ids())

func _cmd_player_list() -> void:
	if not _validate_game():
		return
	
	if _get_game_instance().players.is_empty():
		LimboConsole.info("No players in game")
		return
	
	LimboConsole.info("=== Players (%d) ===" % _get_game_instance().players.size())
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		var status = "DEAD" if player.is_dead else "ALIVE"
		var bot_tag = " [BOT]" if player.is_bot else ""
		LimboConsole.info("  %d: %s - %s%s" % [peer_id, player.username, status, bot_tag])

func _cmd_player_kill(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	player.hit_by_explosion()
	LimboConsole.info("💀 Killed player %s" % player.username)

func _cmd_player_tp(peer_id: int, x: int, y: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	player.position = Vector2(
		x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	LimboConsole.info("📍 Teleported %s to (%d, %d)" % [player.username, x, y])

func _cmd_player_god(peer_id: int, enabled: String = "on") -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	var is_enabled = enabled.to_lower() in ["on", "true", "1", "yes"]
	player.is_immortal = is_enabled
	LimboConsole.info("⭐ God mode %s for %s" % ["ON" if is_enabled else "OFF", player.username])

func _cmd_player_speed(peer_id: int, level: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	level = clampi(level, 0, 8)
	player.skate_count = level
	player.speed_multiplier = GameConfig.get_skate_speed_multiplier(level)
	LimboConsole.info("⚡ Set %s speed to level %d (%.2fx)" % [player.username, level, player.speed_multiplier])

func _cmd_player_bombs(peer_id: int, count: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	count = clampi(count, 1, 10)
	player.max_bombs = count
	LimboConsole.info("💣 Set %s max bombs to %d" % [player.username, count])

func _cmd_player_range(peer_id: int, range: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	range = clampi(range, 1, 16)
	player.bomb_range = range
	LimboConsole.info("🔥 Set %s bomb range to %d" % [player.username, range])

func _cmd_player_respawn(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	player.is_dead = false
	player.is_spectator = false
	player.position = _get_game_instance().get_next_spawn_point()
	LimboConsole.info("♻️ Respawned %s" % player.username)

func _cmd_player_immortal(peer_id: int, seconds: float = 10.0) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	player.set_immortal(true)
	player.get_tree().create_timer(seconds).timeout.connect(
		func(): 
			if is_instance_valid(player):
				player.set_immortal(false)
	)
	LimboConsole.info("✨ %s is immortal for %.1f seconds" % [player.username, seconds])

func _cmd_player_virus(peer_id: int, virus_type: int = 1) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	virus_type = clampi(virus_type, 1, 9)
	player.active_virus = virus_type
	player.virus_end_time = Time.get_ticks_msec() + 12000.0
	
	var virus_names = ["", "SPEEDSTER", "SLOWPOKE", "DIARRHOEA", "CONSTIPATION", 
		"SMALL_FLAME", "UNSTOPPABLE", "REVERSE", "HASTY_FUSE", "LEISURELY_FUSE"]
	LimboConsole.info("☠️ Applied %s virus to %s" % [virus_names[virus_type], player.username])

func _cmd_player_maxout(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	player.max_bombs = 10
	player.bomb_range = 8
	player.skate_count = 8
	player.speed_multiplier = GameConfig.get_skate_speed_multiplier(8)
	player.has_bomb_kicker = true
	player.has_power_glove = true
	player.has_line_bomb = true
	LimboConsole.info("🌟 Maxed out %s stats!" % player.username)

# ============================================================================
# MAP COMMANDS
# ============================================================================

func _register_map_commands() -> void:
	LimboConsole.register_command(_cmd_map_clear, "map clear", "Clear all soft blocks")
	LimboConsole.register_command(_cmd_map_fill, "map fill", "Fill map with soft blocks")
	LimboConsole.register_command(_cmd_map_destroy, "map destroy", "Destroy block at tile (x, y)")
	LimboConsole.register_command(_cmd_map_wall, "map wall", "Create wall at tile (x, y)")
	LimboConsole.register_command(_cmd_map_cleararea, "map cleararea", "Clear area (x, y, radius)")
	LimboConsole.register_command(_cmd_map_info, "map info", "Show map information")

func _cmd_map_clear() -> void:
	if not _validate_game():
		return
	
	var cleared = 0
	for y in range(_get_game_instance().game_map.size()):
		for x in range(_get_game_instance().game_map[y].size()):
			if _get_game_instance().game_map[y][x] == 2:  # Soft block
				_get_game_instance().game_map[y][x] = 0
				cleared += 1
	
	LimboConsole.info("🧹 Cleared %d soft blocks" % cleared)

func _cmd_map_fill() -> void:
	if not _validate_game():
		return
	
	var filled = 0
	for y in range(_get_game_instance().game_map.size()):
		for x in range(_get_game_instance().game_map[y].size()):
			if _get_game_instance().game_map[y][x] == 0:  # Empty
				_get_game_instance().game_map[y][x] = 2  # Soft block
				filled += 1
	
	LimboConsole.info("🧱 Filled %d tiles with soft blocks" % filled)

func _cmd_map_destroy(x: int, y: int) -> void:
	if not _validate_game():
		return
	
	if not _validate_tile(Vector2i(x, y)):
		return
	
	_get_game_instance().game_map[y][x] = 0
	LimboConsole.info("💥 Destroyed block at (%d, %d)" % [x, y])

func _cmd_map_wall(x: int, y: int) -> void:
	if not _validate_game():
		return
	
	if not _validate_tile(Vector2i(x, y)):
		return
	
	_get_game_instance().game_map[y][x] = 1
	LimboConsole.info("🧱 Created wall at (%d, %d)" % [x, y])

func _cmd_map_cleararea(x: int, y: int, radius: int) -> void:
	if not _validate_game():
		return
	
	var cleared = 0
	for dy in range(-radius, radius + 1):
		for dx in range(-radius, radius + 1):
			var tx = x + dx
			var ty = y + dy
			if tx >= 0 and tx < _get_game_instance().game_map[0].size() and \
			   ty >= 0 and ty < _get_game_instance().game_map.size():
				if _get_game_instance().game_map[ty][tx] == 2:
					_get_game_instance().game_map[ty][tx] = 0
					cleared += 1
	
	LimboConsole.info("🧹 Cleared %d blocks in radius %d" % [cleared, radius])

func _cmd_map_info() -> void:
	if not _validate_game():
		return
	
	var width = _get_game_instance().game_map[0].size() if _get_game_instance().game_map.size() > 0 else 0
	var height = _get_game_instance().game_map.size()
	var soft_blocks = 0
	var hard_walls = 0
	var empty = 0
	
	for y in range(height):
		for x in range(width):
			match _get_game_instance().game_map[y][x]:
				0: empty += 1
				1: hard_walls += 1
				2: soft_blocks += 1
	
	LimboConsole.info("=== Map Info ===")
	LimboConsole.info("  Size: %dx%d tiles" % [width, height])
	LimboConsole.info("  Empty: %d" % empty)
	LimboConsole.info("  Hard Walls: %d" % hard_walls)
	LimboConsole.info("  Soft Blocks: %d" % soft_blocks)

# ============================================================================
# BOMB COMMANDS
# ============================================================================

func _register_bomb_commands() -> void:
	LimboConsole.register_command(_cmd_bomb_explode, "bomb explode", "Explode specific bomb (bomb_id)")
	LimboConsole.register_command(_cmd_bomb_explodeall, "bomb explodeall", "Explode all bombs")
	LimboConsole.register_command(_cmd_bomb_clear, "bomb clear", "Remove all bombs")
	LimboConsole.register_command(_cmd_bomb_rain, "bomb rain", "Spawn random bombs (count)")
	LimboConsole.register_command(_cmd_bomb_list, "bomb list", "List all bombs")
	LimboConsole.register_command(_cmd_bomb_settype, "bomb settype", "Set player bomb type (peer_id, type 0-3)")

func _cmd_bomb_explode(bomb_id: String) -> void:
	if not _validate_game():
		return
	
	if not _get_game_instance().bombs.has(bomb_id):
		LimboConsole.error("❌ Bomb %s not found" % bomb_id)
		return
	
	var bomb = _get_game_instance().bombs[bomb_id]
	if is_instance_valid(bomb):
		bomb.explode()
		LimboConsole.info("💥 Exploded bomb %s" % bomb_id)

func _cmd_bomb_explodeall() -> void:
	if not _validate_game():
		return
	
	var count = 0
	for bomb_id in _get_game_instance().bombs:
		var bomb = _get_game_instance().bombs[bomb_id]
		if is_instance_valid(bomb):
			bomb.explode()
			count += 1
	
	LimboConsole.info("💥 Exploded %d bombs" % count)

func _cmd_bomb_clear() -> void:
	if not _validate_game():
		return
	
	var count = 0
	for bomb_id in _get_game_instance().bombs.keys():
		var bomb = _get_game_instance().bombs[bomb_id]
		if is_instance_valid(bomb):
			bomb.queue_free()
			count += 1
	_get_game_instance().bombs.clear()
	
	LimboConsole.info("🧹 Removed %d bombs" % count)

func _cmd_bomb_rain(count: int = 10) -> void:
	if not _validate_game():
		return
	
	count = clampi(count, 1, 100)
	var spawned = 0
	
	for i in range(count):
		var x = randi() % _get_game_instance().game_map[0].size()
		var y = randi() % _get_game_instance().game_map.size()
		
		if _get_game_instance().game_map[y][x] == 0:  # Empty tile
			_cmd_spawn_bomb(x, y, randi() % 5 + 1, randf() * 3.0 + 1.0)
			spawned += 1
	
	LimboConsole.info("☔ Spawned %d random bombs" % spawned)

func _cmd_bomb_list() -> void:
	if not _validate_game():
		return
	
	if _get_game_instance().bombs.is_empty():
		LimboConsole.info("No bombs in game")
		return
	
	LimboConsole.info("=== Bombs (%d) ===" % _get_game_instance().bombs.size())
	for bomb_id in _get_game_instance().bombs:
		var bomb = _get_game_instance().bombs[bomb_id]
		if is_instance_valid(bomb):
			var tile = bomb.get_tile_position()
			LimboConsole.info("  %s: (%d, %d) range=%d timer=%.1f/%.1f" % 
				[bomb_id, tile.x, tile.y, bomb.explosion_range, bomb.explosion_timer, bomb.fuse_time])

func _cmd_bomb_settype(peer_id: int, bomb_type: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	bomb_type = clampi(bomb_type, 0, 3)
	player.bomb_type = bomb_type
	
	var type_names = ["NORMAL", "REMOTE", "POWER", "RUBBER"]
	LimboConsole.info("💣 Set %s bomb type to %s" % [player.username, type_names[bomb_type]])

# ============================================================================
# BOT COMMANDS
# ============================================================================

func _register_bot_commands() -> void:
	LimboConsole.register_command(_cmd_bot_kill, "bot kill", "Kill specific bot (peer_id)")
	LimboConsole.register_command(_cmd_bot_killall, "bot killall", "Kill all bots")
	LimboConsole.register_command(_cmd_bot_list, "bot list", "List all bots")
	
	# Add autocomplete for personalities
	LimboConsole.add_argument_autocomplete_source("spawn bot", 1,
		func(): return ["BALANCED", "AGGRESSIVE", "DEFENSIVE", "COMPETITIVE", "TRAPPER"])

func _cmd_bot_kill(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	if not player.is_bot:
		LimboConsole.error("❌ Player %d is not a bot" % peer_id)
		return
	
	player.hit_by_explosion()
	LimboConsole.info("🤖💀 Killed bot %s" % player.username)

func _cmd_bot_killall() -> void:
	if not _validate_game():
		return
	
	var killed = 0
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		if player.is_bot and not player.is_dead:
			player.hit_by_explosion()
			killed += 1
	
	LimboConsole.info("🤖💀 Killed %d bots" % killed)

func _cmd_bot_list() -> void:
	if not _validate_game():
		return
	
	var bots = []
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		if player.is_bot:
			bots.append(player)
	
	if bots.is_empty():
		LimboConsole.info("No bots in game")
		return
	
	LimboConsole.info("=== Bots (%d) ===" % bots.size())
	for bot in bots:
		var status = "DEAD" if bot.is_dead else "ALIVE"
		var personality = bot.get_meta("personality", "UNKNOWN")
		LimboConsole.info("  %d: %s - %s [%s]" % [bot.peer_id, bot.username, status, personality])

# ============================================================================
# ITEM/POWERUP COMMANDS
# ============================================================================

func _register_item_commands() -> void:
	LimboConsole.register_command(_cmd_give, "give", "Give item to player (peer_id, item_name)")
	LimboConsole.register_command(_cmd_item_spawn, "item spawn", "Spawn item at tile (x, y, type)")
	LimboConsole.register_command(_cmd_item_clear, "item clear", "Remove all items")
	LimboConsole.register_command(_cmd_item_rain, "item rain", "Spawn random items (count)")
	LimboConsole.register_command(_cmd_item_list, "item list", "List all items")
	LimboConsole.register_command(_cmd_item_spawnhere, "item spawnhere", "Spawn item at player location (peer_id, item)")
	LimboConsole.register_command(_cmd_item_giveall, "item giveall", "Give item to all players (item_name)")
	
	# Individual item shortcuts
	LimboConsole.register_command(_cmd_give_bomb, "givebomb", "Give bomb powerup (peer_id, count)")
	LimboConsole.register_command(_cmd_give_fire, "givefire", "Give fire powerup (peer_id, count)")
	LimboConsole.register_command(_cmd_give_speed, "givespeed", "Give speed powerup (peer_id, count)")
	LimboConsole.register_command(_cmd_give_kicker, "givekicker", "Give bomb kicker (peer_id)")
	LimboConsole.register_command(_cmd_give_glove, "giveglove", "Give power glove (peer_id)")
	
	# Add autocomplete for item types
	var item_types = ["bomb", "fire", "speed", "kicker", "glove", "line", "fullfire", 
		"heart", "egg", "virus", "remote", "power", "rubber", "pierce", "tirra"]
	LimboConsole.add_argument_autocomplete_source("give", 2,
		func(): return item_types)
	LimboConsole.add_argument_autocomplete_source("item spawn", 3,
		func(): return item_types)
	LimboConsole.add_argument_autocomplete_source("item spawnhere", 2,
		func(): return item_types)
	LimboConsole.add_argument_autocomplete_source("item giveall", 1,
		func(): return item_types)

func _cmd_give(peer_id: int, item_name: String) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	# Special case: tirra
	if item_name.to_lower() == "tirra":
		_cmd_give_tirra(peer_id)
		return
	
	var item_map = {
		"bomb": 0, "fire": 1, "speed": 2, "kicker": 3, "glove": 4,
		"line": 5, "fullfire": 6, "heart": 7, "egg": 8,
		"virus": 13, "skull": 13,
		"remote": 9, "power": 10, "rubber": 11, "pierce": 12
	}
	
	var item_type = item_map.get(item_name.to_lower(), -1)
	if item_type == -1:
		LimboConsole.error("❌ Unknown item: %s" % item_name)
		LimboConsole.info("Available: " + ", ".join(item_map.keys()) + ", tirra")
		return
	
	# Create fake powerup and collect it
	var powerup = load("res://shared/entities/ServerPowerUp.tscn").instantiate()
	powerup.powerup_type = item_type
	player.collect_powerup(powerup)
	powerup.queue_free()
	
	LimboConsole.info("🎁 Gave %s to %s" % [item_name.to_upper(), player.username])

func _cmd_item_spawn(x: int, y: int, item_name: String) -> void:
	if not _validate_game():
		return
	
	if not _validate_tile(Vector2i(x, y)):
		return
	
	var item_map = {
		"bomb": 0, "fire": 1, "speed": 2, "kicker": 3, "glove": 4,
		"line": 5, "fullfire": 6, "heart": 7, "egg": 8,
		"virus": 13, "remote": 9, "power": 10, "rubber": 11, "pierce": 12
	}
	
	var item_type = item_map.get(item_name.to_lower(), -1)
	if item_type == -1:
		LimboConsole.error("❌ Unknown item: %s" % item_name)
		return
	
	_get_game_instance().spawn_powerup_of_type(Vector2i(x, y), item_type)
	LimboConsole.info("🎁 Spawned %s at (%d, %d)" % [item_name.to_upper(), x, y])

func _cmd_item_clear() -> void:
	if not _validate_game():
		return
	
	var count = 0
	for powerup_id in _get_game_instance().powerups.keys():
		var powerup = _get_game_instance().powerups[powerup_id]
		if is_instance_valid(powerup):
			powerup.queue_free()
			count += 1
	_get_game_instance().powerups.clear()
	
	LimboConsole.info("🧹 Removed %d items" % count)

func _cmd_item_rain(count: int = 15) -> void:
	if not _validate_game():
		return
	
	count = clampi(count, 1, 100)
	var spawned = 0
	
	for i in range(count):
		var x = randi() % _get_game_instance().game_map[0].size()
		var y = randi() % _get_game_instance().game_map.size()
		
		if _get_game_instance().game_map[y][x] == 0:  # Empty tile
			var item_type = randi() % 14  # Random item type
			_get_game_instance().spawn_powerup_of_type(Vector2i(x, y), item_type)
			spawned += 1
	
	LimboConsole.info("🎁 Spawned %d random items" % spawned)

func _cmd_item_list() -> void:
	if not _validate_game():
		return
	
	if _get_game_instance().powerups.is_empty():
		LimboConsole.info("No items in game")
		return
	
	LimboConsole.info("=== Items (%d) ===" % _get_game_instance().powerups.size())
	for powerup_id in _get_game_instance().powerups:
		var powerup = _get_game_instance().powerups[powerup_id]
		if is_instance_valid(powerup):
			var tile = powerup.get_tile_position()
			var type_name = _get_powerup_type_name(powerup.powerup_type)
			LimboConsole.info("  %s: %s at (%d, %d)" % [powerup_id, type_name, tile.x, tile.y])

func _cmd_item_spawnhere(peer_id: int, item_name: String) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	var tile = player.get_tile_position()
	_cmd_item_spawn(tile.x, tile.y, item_name)

func _cmd_item_giveall(item_name: String) -> void:
	if not _validate_game():
		return
	
	var count = 0
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		if not player.is_dead:
			_cmd_give(peer_id, item_name)
			count += 1
	
	LimboConsole.info("🎁 Gave %s to %d players" % [item_name.to_upper(), count])

func _cmd_give_bomb(peer_id: int, count: int = 1) -> void:
	for i in range(count):
		_cmd_give(peer_id, "bomb")

func _cmd_give_fire(peer_id: int, count: int = 1) -> void:
	for i in range(count):
		_cmd_give(peer_id, "fire")

func _cmd_give_speed(peer_id: int, count: int = 1) -> void:
	for i in range(count):
		_cmd_give(peer_id, "speed")

func _cmd_give_kicker(peer_id: int) -> void:
	_cmd_give(peer_id, "kicker")

func _cmd_give_glove(peer_id: int) -> void:
	_cmd_give(peer_id, "glove")

# ============================================================================
# TIRRA COMMANDS
# ============================================================================

func _register_tirra_commands() -> void:
	print("[ConsoleCommands] 🦎 Registering Tirra commands...")
	LimboConsole.register_command(_cmd_tirra_mount, "tirra mount", "Mount player on nearest Tirra (peer_id)")
	LimboConsole.register_command(_cmd_tirra_dismount, "tirra dismount", "Dismount player (peer_id)")
	LimboConsole.register_command(_cmd_tirra_levelup, "tirra levelup", "Level up player's Tirra (peer_id)")
	LimboConsole.register_command(_cmd_tirra_kick, "tirra kick", "Trigger Tirra kick (peer_id)")
	LimboConsole.register_command(_cmd_give_tirra, "tirra give", "Give Tirra to player (peer_id, level)")
	LimboConsole.register_command(_cmd_tirra_upgrade, "tirra upgrade", "Upgrade player's Tirra to level (peer_id, level)")
	LimboConsole.register_command(_cmd_tirra_spawnhere, "tirra spawnhere", "Spawn Tirra at player location (peer_id, level)")
	LimboConsole.register_command(_cmd_tirra_list, "tirra list", "List all Tirras in game")
	LimboConsole.register_command(_cmd_tirra_clear, "tirra clear", "Remove all Tirras from game")
	print("[ConsoleCommands] ✅ Tirra commands registered")
	
	# Shortcuts
	LimboConsole.register_command(_cmd_give_tirra, "givetirra", "Give Tirra to player (peer_id, level)")
	
	# Add autocomplete for Tirra levels
	LimboConsole.add_argument_autocomplete_source("spawn tirra", 1,
		func(): return ["baby", "teen", "adult"])
	LimboConsole.add_argument_autocomplete_source("tirra give", 2,
		func(): return ["baby", "teen", "adult"])
	LimboConsole.add_argument_autocomplete_source("tirra upgrade", 2,
		func(): return ["baby", "teen", "adult"])
	LimboConsole.add_argument_autocomplete_source("tirra spawnhere", 2,
		func(): return ["baby", "teen", "adult"])

func _cmd_tirra_mount(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	# Find nearest Tirra
	var tirras = player.get_tree().get_nodes_in_group("tirras")
	if tirras.is_empty():
		LimboConsole.error("❌ No Tirras found. Spawn one with 'spawn tirra'")
		return
	
	var nearest = null
	var min_dist = INF
	for tirra in tirras:
		var dist = player.position.distance_to(tirra.position)
		if dist < min_dist:
			min_dist = dist
			nearest = tirra
	
	if nearest:
		player.mount_tirra(nearest)
		LimboConsole.info("🦎 Mounted %s on Tirra" % player.username)

func _cmd_tirra_dismount(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	if not player.is_mounted:
		LimboConsole.error("❌ %s is not mounted" % player.username)
		return
	
	player.dismount_tirra(false, false)
	LimboConsole.info("🦎 Dismounted %s from Tirra" % player.username)

func _cmd_tirra_levelup(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	if not player.is_mounted:
		LimboConsole.error("❌ %s is not mounted on a Tirra" % player.username)
		return
	
	if player.mounted_tirra and player.mounted_tirra.has_method("level_up"):
		player.mounted_tirra.level_up()
		player.tirra_growth_level = player.mounted_tirra.current_level
		LimboConsole.info("⬆️ Leveled up %s's Tirra to level %d" % [player.username, player.tirra_growth_level])
	else:
		LimboConsole.error("❌ Tirra doesn't support leveling")

func _cmd_tirra_kick(peer_id: int) -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	if not player.is_mounted:
		LimboConsole.error("❌ %s is not mounted on a Tirra" % player.username)
		return
	
	player.trigger_tirra_action()
	LimboConsole.info("👢 Triggered Tirra kick for %s" % player.username)

func _cmd_give_tirra(peer_id: int, level: String = "baby") -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	# Check if already mounted
	if player.is_mounted:
		LimboConsole.warning("⚠️ %s already has a Tirra, upgrading instead" % player.username)
		_cmd_tirra_upgrade(peer_id, level)
		return
	
	# Spawn Tirra at player location
	var tirra_scene = load("res://tirra.tscn")
	if not tirra_scene:
		LimboConsole.error("❌ Failed to load tirra.tscn - ensure blue-tirra.pck is mounted")
		return
	
	var tirra = tirra_scene.instantiate()
	tirra.name = "Tirra_" + str(randi())
	
	# Set growth level
	var growth_level = _get_tirra_level(level)
	if tirra.has_method("set") and "current_level" in tirra:
		tirra.current_level = growth_level
	
	# Spawn at player location
	tirra.global_position = player.global_position
	_get_game_instance().add_child(tirra)
	
	# Auto-mount player
	player.call_deferred("mount_tirra", tirra)
	
	LimboConsole.info("🦎 Gave %s Tirra (level: %s) to %s" % [level, growth_level, player.username])

func _cmd_tirra_upgrade(peer_id: int, level: String = "adult") -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	if not player.is_mounted:
		LimboConsole.error("❌ %s is not mounted on a Tirra" % player.username)
		return
	
	var target_level = _get_tirra_level(level)
	var current_level = player.tirra_growth_level
	
	if target_level <= current_level:
		LimboConsole.warning("⚠️ Tirra already at or above level %s" % level)
		return
	
	if player.mounted_tirra and "current_level" in player.mounted_tirra:
		player.mounted_tirra.current_level = target_level
		player.tirra_growth_level = target_level
		LimboConsole.info("⬆️ Upgraded %s's Tirra to %s (level %d)" % [player.username, level, target_level])
	else:
		LimboConsole.error("❌ Unable to upgrade Tirra")

func _cmd_tirra_spawnhere(peer_id: int, level: String = "baby") -> void:
	var player = _get_player(peer_id)
	if not player:
		return
	
	var tirra_scene = load("res://tirra.tscn")
	if not tirra_scene:
		LimboConsole.error("❌ Failed to load tirra.tscn")
		return
	
	var tirra = tirra_scene.instantiate()
	tirra.name = "Tirra_" + str(randi())
	
	var growth_level = _get_tirra_level(level)
	if "current_level" in tirra:
		tirra.current_level = growth_level
	
	tirra.global_position = player.global_position
	_get_game_instance().add_child(tirra)
	
	LimboConsole.info("🦎 Spawned %s Tirra at %s's location" % [level, player.username])

func _cmd_tirra_list() -> void:
	if not _validate_game():
		return
	
	var tirras = _get_game_instance().get_tree().get_nodes_in_group("tirras")
	if tirras.is_empty():
		LimboConsole.info("No Tirras in game")
		return
	
	LimboConsole.info("=== Tirras (%d) ===" % tirras.size())
	for tirra in tirras:
		var level = tirra.get("current_level") if "current_level" in tirra else 0
		var level_name = ["BABY", "TEEN", "ADULT"][level] if level < 3 else "UNKNOWN"
		var tile = Vector2i(
			int(tirra.position.x / GameConfig.TILE_SIZE),
			int(tirra.position.y / GameConfig.TILE_SIZE)
		)
		var owner_text = ""
		for peer_id in _get_game_instance().players:
			var player = _get_game_instance().players[peer_id]
			if player.mounted_tirra == tirra:
				owner_text = " [Mounted by %s]" % player.username
				break
		LimboConsole.info("  %s: %s at (%d, %d)%s" % [tirra.name, level_name, tile.x, tile.y, owner_text])

func _cmd_tirra_clear() -> void:
	if not _validate_game():
		return
	
	# Dismount all players first
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		if player.is_mounted:
			player.dismount_tirra(false, false)
	
	# Remove all Tirras
	var tirras = _get_game_instance().get_tree().get_nodes_in_group("tirras")
	var count = 0
	for tirra in tirras:
		if is_instance_valid(tirra):
			tirra.queue_free()
			count += 1
	
	LimboConsole.info("🧹 Removed %d Tirras" % count)

# ============================================================================
# GAME STATE COMMANDS
# ============================================================================

func _register_game_commands() -> void:
	LimboConsole.register_command(_cmd_game_start, "game start", "Start the match")
	LimboConsole.register_command(_cmd_game_end, "game end", "End the match")
	LimboConsole.register_command(_cmd_game_pause, "game pause", "Toggle pause")
	LimboConsole.register_command(_cmd_game_timescale, "game timescale", "Set time scale (0.1-10.0)")
	LimboConsole.register_command(_cmd_game_reset, "game reset", "Reset entire game")
	LimboConsole.register_command(_cmd_game_countdown, "game countdown", "Start countdown (seconds)")
	LimboConsole.register_command(_cmd_game_info, "game info", "Show game information")
	
	# Legacy aliases
	LimboConsole.register_command(_cmd_game_timescale, "timescale", "Set time scale (0.1-10.0)")
	LimboConsole.register_command(_cmd_game_start, "start", "Start the match")
	LimboConsole.register_command(_cmd_game_end, "end", "End the match")
	LimboConsole.register_command(_cmd_player_maxout, "maxout", "Give max stats to player (peer_id)")

func _cmd_game_start() -> void:
	if not _validate_game():
		return
	
	if _get_game_instance().has_method("start_match"):
		_get_game_instance().start_match()
		LimboConsole.info("▶️ Match started!")
	else:
		_get_game_instance().match_active = true
		LimboConsole.info("▶️ Match activated!")

func _cmd_game_end() -> void:
	if not _validate_game():
		return
	
	if _get_game_instance().has_method("end_match"):
		_get_game_instance().end_match()
	else:
		_get_game_instance().match_active = false
	LimboConsole.info("⏹️ Match ended!")

func _cmd_game_pause() -> void:
	var is_paused = _get_game_instance().get_tree().paused
	_get_game_instance().get_tree().paused = not is_paused
	LimboConsole.info("⏸️ Game %s" % ["UNPAUSED" if is_paused else "PAUSED"])

func _cmd_game_timescale(scale: float) -> void:
	scale = clampf(scale, 0.1, 10.0)
	Engine.time_scale = scale
	LimboConsole.info("⏱️ Time scale set to %.2fx" % scale)

func _cmd_game_reset() -> void:
	if not _validate_game():
		return
	
	# Clear all entities
	_cmd_bomb_clear()
	_cmd_item_clear()
	
	# Reset all players
	for peer_id in _get_game_instance().players:
		var player = _get_game_instance().players[peer_id]
		player.is_dead = false
		player.is_spectator = false
		player.position = _get_game_instance().get_next_spawn_point()
		player.max_bombs = 1
		player.bomb_range = 2
		player.skate_count = 1
		player.speed_multiplier = 1.0
	
	LimboConsole.info("♻️ Game reset complete")

func _cmd_game_countdown(seconds: int = 3) -> void:
	if not _validate_game():
		return
	
	_get_game_instance().countdown_time = float(seconds)
	_get_game_instance().match_active = false
	LimboConsole.info("⏳ Starting %d second countdown" % seconds)

func _cmd_game_info() -> void:
	if not _validate_game():
		return
	
	LimboConsole.info("=== Game Info ===")
	LimboConsole.info("  Match Active: %s" % _get_game_instance().match_active)
	LimboConsole.info("  Players: %d" % _get_game_instance().players.size())
	LimboConsole.info("  Bombs: %d" % _get_game_instance().bombs.size())
	LimboConsole.info("  Items: %d" % _get_game_instance().powerups.size())
	LimboConsole.info("  Time Scale: %.2fx" % Engine.time_scale)

# ============================================================================
# DEBUG/VISUALIZATION COMMANDS
# ============================================================================

func _register_debug_commands() -> void:
	LimboConsole.register_command(_cmd_debug_fps, "debug fps", "Show FPS counter")
	LimboConsole.register_command(_cmd_debug_info, "debug info", "Show debug information")
	LimboConsole.register_command(_cmd_debug_collisions, "debug collisions", "Toggle collision shape visualization")
	
	# Shortcuts
	LimboConsole.register_command(_cmd_debug_fps, "fps", "Show FPS counter")
	LimboConsole.register_command(_cmd_debug_collisions, "collisions", "Toggle collision shapes")

func _cmd_debug_fps() -> void:
	var fps = Engine.get_frames_per_second()
	LimboConsole.info("📊 FPS: %d (%.1f ms/frame)" % [fps, 1000.0 / fps if fps > 0 else 0])

func _cmd_debug_info() -> void:
	if not _validate_game():
		return
	
	LimboConsole.info("=== Debug Info ===")
	LimboConsole.info("  FPS: %d" % Engine.get_frames_per_second())
	LimboConsole.info("  Physics FPS: %d" % Engine.physics_ticks_per_second)
	LimboConsole.info("  Time Scale: %.2fx" % Engine.time_scale)
	LimboConsole.info("  Memory: %.1f MB" % (OS.get_static_memory_usage() / 1048576.0))
	
	var node_count = 0
	var root = _get_game_instance().get_tree().root
	node_count = _count_nodes(root)
	LimboConsole.info("  Total Nodes: %d" % node_count)

func _cmd_debug_collisions() -> void:
	var tree = get_tree()
	if tree:
		tree.debug_collisions_hint = not tree.debug_collisions_hint
		var status = "ENABLED" if tree.debug_collisions_hint else "DISABLED"
		LimboConsole.info("🔲 Collision shapes %s" % status)
	else:
		LimboConsole.error("❌ Failed to access scene tree")

# ============================================================================
# CAMERA COMMANDS
# ============================================================================

func _register_camera_commands() -> void:
	LimboConsole.register_command(_cmd_camera_zoom, "camera zoom", "Set camera zoom (0.5-3.0)")
	LimboConsole.register_command(_cmd_camera_reset, "camera reset", "Reset camera")

func _cmd_camera_zoom(zoom: float) -> void:
	zoom = clampf(zoom, 0.5, 3.0)
	
	# Find camera in scene
	var camera = _find_camera(_get_game_instance().get_tree().root)
	if camera:
		camera.zoom = Vector2(zoom, zoom)
		LimboConsole.info("📷 Camera zoom set to %.2fx" % zoom)
	else:
		LimboConsole.error("❌ No camera found")

func _cmd_camera_reset() -> void:
	var camera = _find_camera(_get_game_instance().get_tree().root)
	if camera:
		camera.zoom = Vector2(1.0, 1.0)
		camera.position = Vector2.ZERO
		LimboConsole.info("📷 Camera reset")
	else:
		LimboConsole.error("❌ No camera found")

# ============================================================================
# NETWORK COMMANDS
# ============================================================================

func _register_network_commands() -> void:
	LimboConsole.register_command(_cmd_net_info, "net info", "Show network information")

func _cmd_net_info() -> void:
	var peer = multiplayer.multiplayer_peer
	if peer:
		LimboConsole.info("=== Network Info ===")
		LimboConsole.info("  Peer ID: %d" % multiplayer.get_unique_id())
		LimboConsole.info("  Is Server: %s" % multiplayer.is_server())
		LimboConsole.info("  Connected Peers: %s" % multiplayer.get_peers())
	else:
		LimboConsole.info("Not connected to network")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

func _validate_game() -> bool:
	var game_instance = _get_game_instance()
	if not game_instance:
		LimboConsole.error("❌ Game instance not available")
		return false
	return true

func _validate_tile(tile: Vector2i) -> bool:
	var game_instance = _get_game_instance()
	if not game_instance:
		return false
	
	var width = _get_game_instance().game_map[0].size() if _get_game_instance().game_map.size() > 0 else 0
	var height = _get_game_instance().game_map.size()
	
	if tile.x < 0 or tile.x >= width or tile.y < 0 or tile.y >= height:
		LimboConsole.error("❌ Invalid tile position (%d, %d). Map is %dx%d" % [tile.x, tile.y, width, height])
		return false
	return true

func _get_player(peer_id: int):
	var game_instance = _get_game_instance()
	if not game_instance:
		return null
	
	if not _get_game_instance().players.has(peer_id):
		LimboConsole.error("❌ Player %d not found. Use 'player list' to see all players" % peer_id)
		return null
	
	return _get_game_instance().players[peer_id]

func _get_player_ids() -> PackedStringArray:
	var game_instance = _get_game_instance()
	if not game_instance:
		return PackedStringArray()
	
	var ids = PackedStringArray()
	for peer_id in _get_game_instance().players:
		ids.append(str(peer_id))
	return ids

func _get_powerup_type_name(type: int) -> String:
	var names = ["BOMB", "FIRE", "SPEED", "KICKER", "GLOVE", "LINE", "FULLFIRE", 
		"HEART", "EGG", "REMOTE", "POWER", "RUBBER", "PIERCE", "VIRUS"]
	return names[type] if type < names.size() else "UNKNOWN"

func _count_nodes(node: Node) -> int:
	var count = 1
	for child in node.get_children():
		count += _count_nodes(child)
	return count

func _find_camera(node: Node) -> Camera2D:
	if node is Camera2D:
		return node
	for child in node.get_children():
		var cam = _find_camera(child)
		if cam:
			return cam
	return null

func _get_tirra_level(level_name: String) -> int:
	"""Convert Tirra level name to integer"""
	match level_name.to_lower():
		"baby": return 0
		"teen": return 1
		"adult": return 2
		_: return 0
