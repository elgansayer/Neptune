extends Node2D
class_name GameInstance

# Server-side game instance
# Manages one game match with multiple players

const Constants = preload("res://shared/constants.gd")
const ServerPlayer = preload("res://shared/entities/server_player.gd")
const ServerBomb = preload("res://shared/entities/server_bomb.gd")

var game_id: String = ""
var players := {}  # peer_id -> ServerPlayer
var bombs := {}  # bomb_id -> ServerBomb
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
	
	# Send state updates to all clients
	if last_sync_time >= SYNC_INTERVAL:
		last_sync_time = 0.0
		sync_state_to_clients()

func add_player(peer_id: int, username: String, spawn_position: Vector2 = Vector2.ZERO):
	var player = ServerPlayer.new()
	player.player_id = str(peer_id)
	player.username = username
	
	# Use provided spawn position, or get next available spawn from map
	if spawn_position == Vector2.ZERO:
		if spawn_points.is_empty():
			# Fallback spawn
			spawn_position = Vector2(64, 64)
			push_warning("[GameInstance] No spawn points available, using fallback")
		else:
			spawn_position = spawn_points[next_spawn_index % spawn_points.size()]
			next_spawn_index += 1
	
	player.position = spawn_position
	player.name = "Player_" + str(peer_id)
	
	players[peer_id] = player
	add_child(player)
	
	print("[Game] Player joined: ", username, " at ", spawn_position)

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
				game_map[cell.y][cell.x] = 0  # Clear the block from map data
				
				# Remove the physical collision body
				var tile_key = "%d,%d" % [cell.x, cell.y]
				if map_tiles.has(tile_key):
					var tile_body = map_tiles[tile_key]
					tile_body.queue_free()
					map_tiles.erase(tile_key)
				
				# TODO: Maybe spawn power-up
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
		"explosions": [],
		"map": game_map
	}
	
	for peer_id in players:
		state.players[str(peer_id)] = players[peer_id].get_state()
	
	for bomb_id in bombs:
		state.bombs[bomb_id] = bombs[bomb_id].get_state()
	
	# Add explosion cells for rendering
	for explosion in explosions:
		for cell in explosion.cells:
			state.explosions.append({"x": cell.x, "y": cell.y})
	
	# Send to all players in this game via ClientMain node
	for peer_id in players:
		get_node("/root/ClientMain").rpc_id(peer_id, "receive_game_state", state)
