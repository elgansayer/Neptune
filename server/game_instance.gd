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

signal game_ended(winner_id: String)

func _ready():
	# Initialize map manager
	map_manager = load("res://shared/maps/map_manager.gd").new()
	add_child(map_manager)
	
	# Seed randomness with current time for unique maps each game
	randomize()
	
	# Load map - CLASSIC Bomberman style only (17x11 visible grid)
	var map_data: Dictionary
	
	# Always use CLASSIC style for traditional Bomberman gameplay
	# 17 columns x 11 rows (like original Bomberman)
	map_data = map_manager.generate_procedural_map(MapGenerator.MapStyle.CLASSIC, 17, 11)
	
	# Alternative options (uncomment to use):
	# Option A: Always use classic style
	# map_data = map_manager.generate_procedural_map(MapGenerator.MapStyle.CLASSIC)
	
	# Option B: Load random map file (static, same content each time)
	# map_data = map_manager.load_random_map_file()
	
	# Option C: Load specific map
	# map_data = map_manager.load_map(map_manager.MapSource.FILE, "res://res/maps/classic_arena.json")
	
	if map_data.is_empty():
		push_error("[GameInstance] Failed to load map, using fallback")
		# Fallback: generate a basic map
		map_data = map_manager.generate_procedural_map(MapGenerator.MapStyle.CLASSIC)
	
	# Apply map data
	game_map = map_data.grid
	spawn_points = map_data.spawn_points
	
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
				shape.radius = Constants.TILE_SIZE / 2.0  # Circle fits inside tile
				collision_shape.shape = shape
				tile_body.add_child(collision_shape)
				
				# Position at tile center
				tile_body.position = Vector2(
					x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
					y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
				)
				
				add_child(tile_body)
				
				# Store reference for destructible blocks (so we can remove them)
				if tile_type == 2:
					var tile_key = "%d,%d" % [x, y]
					map_tiles[tile_key] = tile_body

func _physics_process(delta):
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
	
	# Add collision exception so player can walk out
	player.add_bomb_collision_exception(bomb)
	
	bombs[bomb.bomb_id] = bomb
	add_child(bomb)
	
	player.bombs_placed += 1
	bomb.exploded.connect(func(b): _on_bomb_exploded(b, player))
	
	print("[Game] Bomb placed by ", player.username, " at tile ", bomb.get_tile_position())

func _on_bomb_exploded(bomb: ServerBomb, bomb_owner: ServerPlayer):
	print("[Game] Bomb exploded: ", bomb.bomb_id)
	
	# Process explosion damage
	var bomb_tile = bomb.get_tile_position()
	var explosion_cells = get_explosion_cells(bomb_tile, bomb.explosion_range)
	
	# Add explosion to tracking for visual display
	explosions.append({
		"cells": explosion_cells,
		"time": Time.get_ticks_msec() / 1000.0
	})
	
	# Check for player hits
	for peer_id in players:
		var player = players[peer_id]
		var player_tile = player.get_tile_position()
		
		if player_tile in explosion_cells:
			player.die()
			print("[Game] Player ", player.username, " killed by explosion!")
	
	# Remove bomb from tracking
	if bombs.has(bomb.bomb_id):
		bombs.erase(bomb.bomb_id)
	
	# Decrement owner's bomb count
	if bomb_owner:
		bomb_owner.bombs_placed = max(0, bomb_owner.bombs_placed - 1)
	
	# TODO: Destroy destructible blocks
	# TODO: Chain reaction with other bombs

func get_explosion_cells(center: Vector2i, explosion_range: int) -> Array:
	var cells = [center]
	
	# Check 4 directions
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for i in range(1, explosion_range + 1):
			var cell = center + dir * i
			
			# Check bounds
			if cell.y < 0 or cell.y >= game_map.size():
				break
			if cell.x < 0 or cell.x >= game_map[0].size():
				break
			
			# Check for wall
			if game_map[cell.y][cell.x] == 1:
				break  # Solid wall stops explosion
			
			cells.append(cell)
			
			# Destructible block stops explosion but gets destroyed
			if game_map[cell.y][cell.x] == 2:
				var tile_key = "%d,%d" % [cell.x, cell.y]
				print("[Game] Destroying block at ", cell, " (tile_key: ", tile_key, ")")
				
				# Remove the physical collision body FIRST
				if map_tiles.has(tile_key):
					var tile_body = map_tiles[tile_key]
					if is_instance_valid(tile_body):
						tile_body.call_deferred("queue_free")  # Safe deferred deletion
					map_tiles.erase(tile_key)
					print("[Game] Block collision removed: ", tile_key)
				else:
					print("[Game] WARNING: Block not in map_tiles dictionary: ", tile_key)
				
				# Clear from map data
				game_map[cell.y][cell.x] = 0
				
				# Spawn power-up (30% chance)
				if randf() < 0.3:
					spawn_powerup(cell)
				
				break
	
	return cells

func sync_state_to_clients():
	# Clean up old explosions
	var current_time = Time.get_ticks_msec() / 1000.0
	explosions = explosions.filter(func(explosion): return current_time - explosion.time < EXPLOSION_DISPLAY_TIME)
	
	# Build game state
	var state = {
		"players": {},
		"bombs": {},
		"powerups": {},
		"explosions": [],
		"map": game_map
	}
	
	for peer_id in players:
		state.players[str(peer_id)] = players[peer_id].get_state()
	
	for bomb_id in bombs:
		state.bombs[bomb_id] = bombs[bomb_id].get_state()
	
	for powerup_id in powerups:
		state.powerups[powerup_id] = powerups[powerup_id].get_state()
	
	# Add explosion cells for rendering
	for explosion in explosions:
		for cell in explosion.cells:
			state.explosions.append({"x": cell.x, "y": cell.y})
	
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
	
	# Random power-up type
	var rand_val = randf()
	if rand_val < 0.5:
		powerup.powerup_type = ServerPowerUp.PowerUpType.BOMB_INCREASE  # 50%
	elif rand_val < 0.8:
		powerup.powerup_type = ServerPowerUp.PowerUpType.RANGE_INCREASE  # 30%
	else:
		powerup.powerup_type = ServerPowerUp.PowerUpType.SPEED_INCREASE  # 20%
	
	powerup.position = Vector2(
tile_pos.x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
tile_pos.y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
)
	powerup.name = "PowerUp_" + powerup.powerup_id
	
	# Connect collection signal
	powerup.powerup_collected.connect(_on_powerup_collected)
	
	powerups[powerup.powerup_id] = powerup
	add_child(powerup)
	
	print("[Game] Spawned power-up ", powerup.powerup_type, " at ", tile_pos)

func _on_powerup_collected(powerup: ServerPowerUp):
	"""Called when a power-up is collected"""
	print("[Game] Power-up collected: ", powerup.powerup_id)
	
	if powerups.has(powerup.powerup_id):
		powerups.erase(powerup.powerup_id)
		powerup.queue_free()
