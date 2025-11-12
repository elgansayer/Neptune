extends Node2D
class_name GameInstance

# Server-side game instance
# Manages one game match with multiple players

const Constants = preload("res://shared/constants.gd")
const ServerPlayer = preload("res://shared/entities/server_player.gd")
const ServerBomb = preload("res://shared/entities/server_bomb.gd")
const ServerPowerUp = preload("res://shared/entities/server_powerup.gd")
const AIPlayerScript = preload("res://shared/entities/ai_player.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")
const MapGenerator = preload("res://shared/maps/map_generator.gd")
const MapPackLoader = preload("res://shared/maps/map_pack_loader.gd")

var game_id: String = ""
var players := {}  # peer_id -> ServerPlayer (includes AI bots)
var ai_bot_counter := 1000  # Start AI bot IDs from 1000
var bombs := {}  # bomb_id -> ServerBomb
var powerups := {}  # powerup_id -> ServerPowerUp
var next_powerup_id := 0
var explosions := []  # Array of {cells: Array, time: float} for visual effects
var game_map := []  # 2D array representing the map
var map_tiles := {}  # Dictionary of tile_key -> StaticBody2D for collision
var next_bomb_id := 0
var map_manager: Node  # MapManager instance
var spawn_points := []  # Available spawn points from map
var next_spawn_index := 0  # Track which spawn point to use next

# State sync
var last_sync_time := 0.0
const SYNC_INTERVAL = 1.0 / Constants.NETWORK_SEND_RATE
const EXPLOSION_DISPLAY_TIME = 0.5  # How long to show explosions

# Match timer
var match_duration := 180.0  # 3 minutes default
var match_time_remaining := match_duration
var match_active := true
var winner_id := ""

signal game_ended(winner_id: String)

func _ready():
	# Initialize map manager
	map_manager = load("res://shared/maps/map_manager.gd").new()
	add_child(map_manager)
	
	# Seed randomness with current time for unique maps each game
	randomize()
	
	# Load map from PCK file
	var map_data: Dictionary
	
	# Try to load PCK map first
	if FileAccess.file_exists("res://res/maps/stage1.pck"):
		print("[GameInstance] Loading map from PCK...")
		map_data = MapPackLoader.load_map_from_pck("res://res/maps/stage1.pck")
		
		if not map_data.is_empty():
			# Choose soft block pattern
			var pattern = map_data.metadata.get("soft_block_pattern", "RANDOM_70")
			var density = map_data.metadata.get("soft_block_density", 0.7)
			var active_soft_blocks = MapPackLoader.choose_soft_block_pattern(
				map_data.soft_slots, 
				pattern, 
				density
			)
			
			# Apply soft blocks to grid
			# First clear all soft slots
			for slot in map_data.soft_slots:
				map_data.grid[slot.y][slot.x] = 0
			
			# Then activate chosen slots
			for slot in active_soft_blocks:
				map_data.grid[slot.y][slot.x] = 2
			
			print("[GameInstance] Using PCK map with ", active_soft_blocks.size(), "/", 
				  map_data.soft_slots.size(), " soft blocks")
	
	# Fallback to procedural generation if PCK not found
	if map_data.is_empty():
		print("[GameInstance] PCK not found, generating procedural map...")
		map_data = map_manager.generate_procedural_map(MapGenerator.MapStyle.CLASSIC, 17, 11)
	
	if map_data.is_empty():
		push_error("[GameInstance] Failed to load any map!")
		return
	
	# Apply map data
	game_map = map_data.grid
	spawn_points = map_data.spawn_points
	
	# Load map configuration into GameConfig singleton
	GameConfig.load_map_config(map_data)
	
	print("[GameInstance] Loaded map '", map_data.get("name", "Unknown"), 
		  "' with ", spawn_points.size(), " spawn points")
	
	# Create physics collision bodies for walls and blocks
	create_map_collision()

func create_map_collision():
	"""Create StaticBody2D collision shapes for all walls and destructible blocks"""
	for y in range(game_map.size()):
		for x in range(game_map[y].size()):
			var tile_type = game_map[y][x]
			
			if tile_type == 1 or tile_type == 2:  # Wall or destructible block
				var tile_body = StaticBody2D.new()
				tile_body.name = "Tile_%d_%d" % [x, y]
				
				# Set collision layers: walls are on layer 1, don't detect anything
				tile_body.collision_layer = Constants.COLLISION_LAYER_WALLS
				tile_body.collision_mask = 0  # Walls don't need to detect collisions
				
				# Create collision shape - USE CIRCLE to match player's circular hitbox!
				# This prevents getting stuck on corners
				var collision_shape = CollisionShape2D.new()
				var shape = CircleShape2D.new()
				shape.radius = GameConfig.TILE_SIZE / 2.0  # Circle fits inside tile
				collision_shape.shape = shape
				tile_body.add_child(collision_shape)
				
				# Position at tile center
				tile_body.position = Vector2(
					x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
					y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
				)
				
				add_child(tile_body)
				
				# Store reference for destructible blocks (so we can remove them)
				if tile_type == 2:
					var tile_key = "%d,%d" % [x, y]
					map_tiles[tile_key] = tile_body

func _physics_process(delta):
	# Update match timer if active
	if match_active:
		match_time_remaining -= delta
		if match_time_remaining <= 0:
			match_time_remaining = 0
			end_match()
	
	last_sync_time += delta
	
	# Process AI bot bomb requests
	for peer_id in players:
		var player = players[peer_id]
		if player.has_method("is_ai_bot") and player.is_ai_bot() and player.place_bomb_requested and player.can_place_bomb():
			place_bomb(player)
			player.place_bomb_requested = false
	
	# Send state updates to all clients
	if last_sync_time >= SYNC_INTERVAL:
		last_sync_time = 0.0
		sync_state_to_clients()

func get_next_spawn_point() -> Vector2:
	"""Get the next available spawn point from the map"""
	if spawn_points.is_empty():
		push_warning("[GameInstance] No spawn points available, using fallback")
		return Vector2(64, 64)
	
	var spawn_pos = spawn_points[next_spawn_index % spawn_points.size()]
	next_spawn_index += 1
	return spawn_pos

func add_player(peer_id: int, username: String, spawn_position: Vector2 = Vector2.ZERO):
	var player = ServerPlayer.new()
	player.player_id = str(peer_id)
	player.username = username
	
	# Use provided spawn position, or get next available spawn from map
	if spawn_position == Vector2.ZERO:
		spawn_position = get_next_spawn_point()
	
	player.position = spawn_position
	player.name = "Player_" + str(peer_id)
	
	players[peer_id] = player
	add_child(player)
	
	print("[Game] Player joined: ", username, " at ", spawn_position)

func add_ai_bot(personality: int = -1) -> int:
	"""Spawn an AI bot with specified personality (-1 = random)
	Returns the bot's peer_id
	"""
	if personality == -1:
		personality = randi() % 3  # Random: 0=Balanced, 1=Aggressive, 2=Timid
	
	var bot_id = ai_bot_counter
	ai_bot_counter += 1
	
	# Get spawn position
	var spawn_pos = get_next_spawn_point()
	
	# Create AI player
	var bot = AIPlayerScript.new()
	bot.player_id = str(bot_id)
	bot.position = spawn_pos
	bot.setup_ai(self, personality)
	
	players[bot_id] = bot
	add_child(bot)
	
	print("[Game] AI Bot spawned: ", bot.bot_name, " at ", spawn_pos)
	return bot_id

func remove_player(peer_id: int):
	if players.has(peer_id):
		var player = players[peer_id]
		player.queue_free()
		players.erase(peer_id)
		print("[Game] Player left: ", peer_id)

func end_match():
	"""End the match and determine winner"""
	if not match_active:
		return  # Already ended
	
	match_active = false
	winner_id = find_winner()
	
	print("[GameInstance] Match ended. Winner: ", winner_id if winner_id else "Draw")
	game_ended.emit(winner_id)
	
	# TODO: Add delay before returning to lobby
	# await get_tree().create_timer(5.0).timeout
	# Return players to lobby

func find_winner() -> String:
	"""Find the winner (last player alive)"""
	var alive_players = []
	for peer_id in players:
		if not players[peer_id].is_dead:
			alive_players.append(str(peer_id))
	
	# Return single survivor, or empty string if draw/no survivors
	if alive_players.size() == 1:
		return alive_players[0]
	return ""

func handle_player_input(peer_id: int, input_data: Dictionary):
	if not players.has(peer_id):
		return
	
	var player = players[peer_id]
	
	# Set movement input
	player.set_input(input_data.get("input_x", 0.0), input_data.get("input_y", 0.0))
	
	# Handle bomb placement
	if input_data.get("place_bomb", false) and player.can_place_bomb():
		place_bomb(player)

func place_bomb(player: ServerPlayer):
	var bomb = ServerBomb.new()
	bomb.bomb_id = str(next_bomb_id)
	next_bomb_id += 1
	bomb.owner_id = player.player_id
	bomb.explosion_range = player.bomb_range
	bomb.position = player.position
	bomb.name = "Bomb_" + bomb.bomb_id
	bomb.game_instance = self  # Give bomb reference for collision checking
	
	# Add collision exception so player can walk out
	player.add_bomb_collision_exception(bomb)
	
	bombs[bomb.bomb_id] = bomb
	add_child(bomb)
	
	player.bombs_placed += 1
	bomb.exploded.connect(func(b, pattern): _on_bomb_exploded(b, player, pattern))
	bomb.explosion_expanded.connect(func(tiles): _on_explosion_expanded(bomb, tiles))
	# Ensure dictionary entry is cleaned up when the bomb leaves the scene tree
	var cleanup_callable := func():
		if bombs.has(bomb.bomb_id):
			bombs.erase(bomb.bomb_id)
	bomb.tree_exited.connect(cleanup_callable, Object.CONNECT_ONE_SHOT)
	
	print("[Game] Bomb placed by ", player.username, " at tile ", bomb.get_tile_position())

func _on_bomb_exploded(bomb: ServerBomb, bomb_owner: ServerPlayer, explosion_pattern: Array):
	print("[Game] Bomb exploded: ", bomb.bomb_id, " with ", explosion_pattern.size(), " tiles")
	
	# Store explosion data for network sync
	var bomb_tile = bomb.get_tile_position()
	explosions.append({
		"bomb_id": bomb.bomb_id,
		"center": bomb_tile,
		"pattern": explosion_pattern,
		"start_time": Time.get_ticks_msec() / 1000.0,
		"owner_id": bomb_owner.username if bomb_owner else ""
	})
	
	# Decrement owner's bomb count
	if bomb_owner:
		bomb_owner.bombs_placed = max(0, bomb_owner.bombs_placed - 1)


func _on_explosion_expanded(bomb: ServerBomb, tiles: Array[Vector2i]):
	"""Handle damage/destruction for tiles as explosion expands progressively"""
	for tile_pos in tiles:
		# Check for player hits
		for peer_id in players:
			var player = players[peer_id]
			var player_tile = player.get_tile_position()
			
			if player_tile == tile_pos:
				player.die()
				print("[Game] Player ", player.username, " killed by explosion at ", tile_pos)
				
				# Check if match should end (only 1 or 0 players left alive)
				check_match_end_condition()
		
		# Check for destructible blocks
		if tile_pos.y >= 0 and tile_pos.y < game_map.size():
			if tile_pos.x >= 0 and tile_pos.x < game_map[0].size():
				if game_map[tile_pos.y][tile_pos.x] == 2:
					destroy_block(tile_pos)
		
		# Check for other bombs (chain reaction)
		for bomb_id in bombs:
			var other_bomb = bombs[bomb_id]
			if other_bomb != bomb and other_bomb.get_tile_position() == tile_pos:
				if not other_bomb.has_exploded:
					print("[Game] Chain reaction: bomb ", bomb_id, " triggered at ", tile_pos)
					other_bomb.explode()
		
		# Check for powerups (destroy them)
		for powerup_id in powerups:
			var powerup = powerups[powerup_id]
			if powerup.get_tile_position() == tile_pos:
				print("[Game] Powerup destroyed by explosion at ", tile_pos)
				powerup.destroy()
				break

func check_match_end_condition():
	"""Check if the match should end based on alive players"""
	if not match_active:
		return
	
	var alive_count = 0
	for peer_id in players:
		if not players[peer_id].is_dead:
			alive_count += 1
	
	# End match if 1 or fewer players alive
	if alive_count <= 1:
		end_match()

func destroy_block(cell: Vector2i):
	"""Destroy a destructible block and optionally spawn powerup"""
	var tile_key = "%d,%d" % [cell.x, cell.y]
	print("[Game] Destroying block at ", cell, " (tile_key: ", tile_key, ")")
	
	# Remove the physical collision body
	if map_tiles.has(tile_key):
		var tile_body = map_tiles[tile_key]
		if is_instance_valid(tile_body):
			tile_body.call_deferred("queue_free")
		map_tiles.erase(tile_key)
		print("[Game] Block collision removed: ", tile_key)
	
	# Clear from map data
	game_map[cell.y][cell.x] = 0
	
	# Spawn power-up (30% chance - TODO: make configurable)
	if randf() < 0.3:
		spawn_powerup(cell)

func get_tile_type(grid_pos: Vector2i) -> int:
	"""Get tile type at grid position (0=empty, 1=wall, 2=destructible)"""
	if grid_pos.y < 0 or grid_pos.y >= game_map.size():
		return 1  # Treat out of bounds as wall
	if grid_pos.x < 0 or grid_pos.x >= game_map[0].size():
		return 1  # Treat out of bounds as wall
	
	return game_map[grid_pos.y][grid_pos.x]

func sync_state_to_clients():
	# Clean up old explosions (keep for progressive display duration)
	var current_time = Time.get_ticks_msec() / 1000.0
	var explosion_duration = 0.02 * 20  # ~20 expansion steps max
	explosions = explosions.filter(func(explosion): return current_time - explosion["start_time"] < explosion_duration)
	
	# Build game state
	var state = {
		"players": {},
		"bombs": {},
		"powerups": {},
		"explosions": [],
		"map": game_map,
		"map_config": {
			"tile_size": GameConfig.TILE_SIZE,
			"width": GameConfig.map_width,
			"height": GameConfig.map_height,
			"name": GameConfig.map_name
		},
		"match_timer": match_time_remaining,
		"match_active": match_active,
		"winner_id": winner_id
	}
	
	for peer_id in players:
		state.players[str(peer_id)] = players[peer_id].get_state()
	
	for bomb_id in bombs:
		state.bombs[bomb_id] = bombs[bomb_id].get_state()
	
	for powerup_id in powerups:
		state.powerups[powerup_id] = powerups[powerup_id].get_state()
	
	# Send progressive explosion data to clients
	for explosion in explosions:
		state.explosions.append({
			"bomb_id": explosion["bomb_id"],
			"center": {"x": explosion["center"].x, "y": explosion["center"].y},
			"pattern": explosion["pattern"],
			"start_time": explosion["start_time"],
			"owner_id": explosion["owner_id"]
		})
	
	# Send to all REAL players in this game via ClientMain autoload
	# Skip AI bots (they don't have network connections)
	for peer_id in players:
		var player = players[peer_id]
		if player.has_method("is_ai_bot") and player.is_ai_bot():
			continue  # Skip AI bots
		get_tree().root.get_node("ClientMain").rpc_id(peer_id, "receive_state", state)
func spawn_powerup(tile_pos: Vector2i):
	"""Spawn a power-up at the given tile position"""
	var powerup = ServerPowerUp.new()
	powerup.powerup_id = str(next_powerup_id)
	next_powerup_id += 1
	
	# Random power-up type (weighted distribution)
	# TODO: Make drop rates configurable via Constants
	var rand_val = randf()
	if rand_val < 0.35:
		powerup.powerup_type = ServerPowerUp.PowerUpType.BOMB_INCREASE  # 35%
	elif rand_val < 0.65:
		powerup.powerup_type = ServerPowerUp.PowerUpType.RANGE_INCREASE  # 30%
	elif rand_val < 0.85:
		powerup.powerup_type = ServerPowerUp.PowerUpType.SPEED_INCREASE  # 20%
	elif rand_val < 0.92:
		powerup.powerup_type = ServerPowerUp.PowerUpType.BOMB_KICKER  # 7%
	elif rand_val < 0.97:
		powerup.powerup_type = ServerPowerUp.PowerUpType.POWER_GLOVE  # 5%
	else:
		powerup.powerup_type = ServerPowerUp.PowerUpType.VIRUS  # 3%
	
	powerup.position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	powerup.name = "PowerUp_" + powerup.powerup_id
	
	# Connect signals
	powerup.powerup_collected.connect(_on_powerup_collected)
	powerup.powerup_destroyed.connect(_on_powerup_destroyed)
	
	powerups[powerup.powerup_id] = powerup
	add_child(powerup)
	
	print("[Game] Spawned power-up ", powerup.powerup_type, " at ", tile_pos)

func _on_powerup_collected(powerup: ServerPowerUp):
	"""Called when a power-up is collected"""
	print("[Game] Power-up collected: ", powerup.powerup_id)
	
	if powerups.has(powerup.powerup_id):
		powerups.erase(powerup.powerup_id)
		powerup.queue_free()

func _on_powerup_destroyed(powerup: ServerPowerUp):
	"""Called when a power-up is destroyed by explosion"""
	print("[Game] Power-up destroyed by explosion: ", powerup.powerup_id)
	
	if powerups.has(powerup.powerup_id):
		powerups.erase(powerup.powerup_id)
		powerup.queue_free()
