extends Node2D
class_name GameInstance

# Server-side game instance
# Manages one game match with multiple players

const Constants = preload("res://shared/constants.gd")

# Entity scene files for instantiation
const ServerPlayerScene = preload("res://shared/entities/ServerPlayer.tscn")
const ServerBombScene = preload("res://shared/entities/ServerBomb.tscn")
const ServerPowerUpScene = preload("res://shared/entities/ServerPowerUp.tscn")

# AI System scaffolding (LimboAI-powered bot manager)
const _BOT_MANAGER_PATHS := [
	"res://ai/bot_manager.gd"
]
var ServerBotManagerScript: Script = _load_script_variant(_BOT_MANAGER_PATHS)
# AI System removed - preparing for rebuild
# const AIPlayerScript = preload("res://shared/entities/ai_player.gd")
# const AIPersonality = preload("res://shared/ai/ai_personalities.gd")

var game_id: String = ""
var players := {} # peer_id -> ServerPlayer
# AI System removed - preparing for rebuild
# var ai_bot_counter := 1000  # Start AI bot IDs from 1000
var bombs := {} # bomb_id -> ServerBomb
var powerups := {} # powerup_id -> ServerPowerUp
var next_powerup_id := 0
var explosions := [] # Array of {cells: Array, time: float} for visual effects
var game_map := [] # 2D array representing the map
var map_tiles := {} # Dictionary of tile_key -> StaticBody2D for collision
var next_bomb_id := 0
var map_manager: Node # MapManager instance
var spawn_points := [] # Available spawn points from map
var next_spawn_index := 0 # Track which spawn point to use next
var bot_manager: Node
var ai_manager: AIManager # Centralized AI brain with ThreatMatrix and pathfinding

# State sync
var last_sync_time := 0.0
var current_time_msec := 0.0 # Current physics frame time in milliseconds
const SYNC_INTERVAL = 1.0 / Constants.NETWORK_SEND_RATE
const EXPLOSION_DISPLAY_TIME = 0.5 # How long to show explosions

# Delta compression for map state
var last_sent_map := [] # Track last sent map state per client
var clients_received_full_map := {} # peer_id -> bool (have they received full map?)
var map_changes := [] # Array of {x: int, y: int, value: int} changes since last sync
var last_sent_hurry_block_count := {} # peer_id -> int (number of hurry blocks sent to this client)

# Match timer
var match_duration := 180.0 # 3 minutes default
var match_time_remaining := match_duration
var match_active := false # Start false, set true after countdown
var countdown_time := 1.0 # 1 second countdown before match starts
var winner_id := ""

# Hurry Up (Sudden Death) system
var hurry_mode_active := false
var hurry_trigger_time := 60.0  # Trigger hurry when this much time remains
var hurry_spawn_interval := 0.15  # Time between block spawns (faster = more pressure)
var hurry_spawn_timer := 0.0
var hurry_blocks: Array[Vector2i] = []  # Positions of spawned hurry blocks
var hurry_spawn_pattern: Array[Vector2i] = []  # Pre-calculated spiral pattern
var hurry_spawn_index := 0  # Current position in spawn pattern
var hurry_just_activated := false  # Flag for client notification

signal game_ended(winner_id: String)
signal hurry_mode_started()

func _ready():
	# Set process priority to run AFTER physics/bombs (0) but BEFORE bots (200)
	process_priority = 100
	
	# Initialize map manager
	map_manager = load("res://shared/maps/map_manager.gd").new()
	add_child(map_manager)
	
	# Seed randomness with current time for unique maps each game
	randomize()

	# FAST_HURRY test hook (accelerated sudden death for automated bot testing)
	var fast_hurry_env = OS.get_environment("FAST_HURRY")
	if fast_hurry_env != "":
		var enabled = fast_hurry_env == "1" or fast_hurry_env.to_lower() in ["true", "yes", "on"]
		if enabled:
			# Allow overriding individual parameters via environment variables
			var dur_env = OS.get_environment("FAST_HURRY_DURATION")
			var trig_env = OS.get_environment("FAST_HURRY_TRIGGER")
			var interval_env = OS.get_environment("FAST_HURRY_INTERVAL")

			if dur_env != "":
				match_duration = float(dur_env)
			if trig_env != "":
				# Trigger time is time remaining when hurry activates
				hurry_trigger_time = float(trig_env)
			if interval_env != "":
				hurry_spawn_interval = float(interval_env)

			# If user did not supply overrides, use a fast default profile
			if dur_env == "" and trig_env == "" and interval_env == "":
				match_duration = 30.0
				hurry_trigger_time = 25.0
				hurry_spawn_interval = 0.05

			# Reset remaining time to new duration
			match_time_remaining = match_duration
			print('[FAST_HURRY] Enabled: duration=%.2f trigger=%.2f interval=%.2f' % [match_duration, hurry_trigger_time, hurry_spawn_interval])
		else:
			# If FAST_HURRY specified but false-ish, log for clarity
			print('[FAST_HURRY] Present but disabled (value="%s")' % fast_hurry_env)
	elif FileAccess.file_exists('res://FAST_HURRY.flag'):
		match_duration = 30.0
		hurry_trigger_time = 25.0
		hurry_spawn_interval = 0.05
		match_time_remaining = match_duration
		print('[FAST_HURRY] Enabled via flag file: duration=%.2f trigger=%.2f interval=%.2f' % [match_duration, hurry_trigger_time, hurry_spawn_interval])
	
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
	
	# Initialize AI Manager (must happen after map is created)
	var grid_sampler = load("res://shared/ai/perception/grid_sampler.gd").new()
	grid_sampler.configure(self, null, GameConfig.TILE_SIZE)
	
	ai_manager = AIManager.new()
	var map_width = game_map[0].size() if game_map.size() > 0 else 0
	var map_height = game_map.size()
	ai_manager.configure(self, grid_sampler, map_width, map_height)
	print("[AIManager] Configured with ", map_width, "x", map_height, " grid")
	print("[GameInstance] AIManager initialized with ", map_width, "x", map_height, " grid")
	
	# Initialize bot manager; actual bot spawning will be triggered later.
	if ServerBotManagerScript == null:
		push_error("[GameInstance] Bot manager script missing; bots disabled")
	else:
		bot_manager = ServerBotManagerScript.new()
		bot_manager.auto_spawn_count = 3 # Auto-spawn 3 bots for testing
		bot_manager.configure(self)
		print("[GameInstance] BotManager configured to spawn ", bot_manager.auto_spawn_count, " bot(s)")
		add_child(bot_manager)

func spawn_bot(personality: String = "BALANCED") -> void:
	if bot_manager == null:
		push_warning("[GameInstance] Bot manager not ready; cannot spawn bot")
		return
	bot_manager.spawn_bot(personality)

func spawn_bots(count: int, personality: String = "BALANCED") -> void:
	if bot_manager == null:
		push_warning("[GameInstance] Bot manager not ready; cannot spawn bots")
		return
	bot_manager.spawn_bots(count, personality)

func test_farming_spot_search() -> void:
	print("[GameInstance] TEST: Forcing farming spot search on all bots")
	if bot_manager == null:
		print("[GameInstance] TEST: No bot manager")
		return
	for bot in bot_manager.get_children():
		if bot.has_method("test_farming_spot"):
			bot.test_farming_spot()
			print("[GameInstance] TEST: Called test_farming_spot on bot ", bot.name)
		else:
			print("[GameInstance] TEST: Bot missing test method: ", bot.name)

static func _load_script_variant(paths: Array) -> Script:
	for path in paths:
		if ResourceLoader.exists(path):
			return load(path)
	push_error("[GameInstance] Failed to load bot manager script. Checked paths: %s" % [paths])
	return null

func create_map_collision():
	"""Create StaticBody2D collision shapes for all walls and destructible blocks"""
	for y in range(game_map.size()):
		for x in range(game_map[y].size()):
			var tile_type = game_map[y][x]
			
			if tile_type == 1 or tile_type == 2: # Wall or destructible block
				var tile_body = StaticBody2D.new()
				tile_body.name = "Tile_%d_%d" % [x, y]
				
				# Set collision layers: walls are on layer 1, don't detect anything
				tile_body.collision_layer = Constants.COLLISION_LAYER_WALLS
				tile_body.collision_mask = 0 # Walls don't need to detect collisions
				
				# Create collision shape - USE CIRCLE to match player's circular hitbox!
				# This prevents getting stuck on corners
				var collision_shape = CollisionShape2D.new()
				var shape = CircleShape2D.new()
				shape.radius = GameConfig.TILE_SIZE / 2.0 # Circle fits inside tile
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
	# Update AI Manager's ThreatMatrix
	if ai_manager != null:
		current_time_msec = Time.get_ticks_msec()
		ai_manager.refresh_threat_matrix(current_time_msec)
	
	# Handle countdown before match starts
	if not match_active and countdown_time > 0.0:
		countdown_time -= delta
		if countdown_time <= 0.0:
			countdown_time = 0.0
			match_active = true
			print("[GameInstance] Match started! Countdown complete. Powerups in game: ", powerups.size())
			# Spawn test powerups if TEST_POWERUPS environment variable is set
			if OS.get_environment("TEST_POWERUPS") != "":
				spawn_test_powerups()
	
	# Update match timer if active
	if match_active:
		match_time_remaining -= delta
		
		# === PLAYER VIRUS UPDATES ===
		var current_time_msec = Time.get_ticks_msec()
		for peer_id in players:
			var player = players[peer_id]
			if not is_instance_valid(player) or player.is_dead:
				continue
			
			# Check virus expiration
			player.update_virus(current_time_msec)
			
			# DIARRHOEA virus: auto-place bombs constantly
			if player.should_auto_place_bomb() and player.can_place_bomb():
				place_bomb(player)
		
		# === VIRUS TRANSFER ON PLAYER COLLISION ===
		_process_virus_transfers()
		
		# Check for Hurry Up trigger
		if not hurry_mode_active and match_time_remaining <= hurry_trigger_time:
			_activate_hurry_mode()
		
		# Process Hurry Up block spawning
		if hurry_mode_active:
			_process_hurry_mode(delta)
		
		if match_time_remaining <= 0:
			match_time_remaining = 0
			end_match()
	
	last_sync_time += delta
	
	# AI System removed - preparing for rebuild
	# Process AI bot bomb requests when AI system is re-implemented
	# for peer_id in players:
	# 	var player = players[peer_id]
	# 	if player.has_method("is_ai_bot") and player.is_ai_bot() and player.place_bomb_requested and player.can_place_bomb():
	# 		place_bomb(player)
	# 		player.place_bomb_requested = false
	
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

func add_player(peer_id: int, username: String, spawn_position: Vector2 = Vector2.ZERO, is_bot: bool = false, personality: String = ""):
	var player = ServerPlayerScene.instantiate()
	player.peer_id = peer_id # CRITICAL: Set actual peer_id (-1, -2, -3 for bots)
	player.player_id = str(peer_id)
	player.username = username
	if is_bot:
		player.set_bot_metadata(personality)
	
	# Use provided spawn position, or get next available spawn from map
	if spawn_position == Vector2.ZERO:
		spawn_position = get_next_spawn_point()
	
	player.position = spawn_position
	player.name = "Player_" + str(peer_id)
	
	# All players start with just 1 bomb and no special items
	# They must collect powerups during the match
	player.has_power_glove = false
	player.has_bomb_kicker = false
	player.max_bombs = 1
	
	if is_bot:
		print("[Game] Bot spawned with 1 bomb (no items)")
	else:
		print("[Game] Player spawned with 1 bomb (no items)")
	
	players[peer_id] = player
	add_child(player)
	
	# For bot players (negative peer_id), set multiplayer authority to server
	# Bots are not real network peers, so RPC calls should go through the server
	if is_bot and peer_id < 0:
		player.set_multiplayer_authority(1) # Server is always peer ID 1
	
	# Ensure the node is fully ready in the scene tree before anyone tries to access it
	if is_inside_tree():
		await get_tree().process_frame
	
	print("[Game] Player joined: ", username, " at ", spawn_position, " (Power Glove: ", player.has_power_glove, ")")

func remove_player(peer_id: int):
	if players.has(peer_id):
		var player = players[peer_id]
		player.queue_free()
		players.erase(peer_id)
		print("[Game] Player left: ", peer_id)

func end_match():
	"""End the match and determine winner"""
	if not match_active:
		return # Already ended
	
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

# ============================================================================
# HURRY UP (SUDDEN DEATH) SYSTEM
# ============================================================================

func _activate_hurry_mode():
	"""Activate hurry mode - walls start closing in!"""
	hurry_mode_active = true
	hurry_just_activated = true
	hurry_spawn_timer = 0.0
	hurry_spawn_index = 0
	
	# Generate the spiral spawn pattern
	hurry_spawn_pattern = _generate_hurry_spiral_pattern()
	
	print("[GameInstance] ⚠️ HURRY UP! %d blocks will spawn from edges!" % hurry_spawn_pattern.size())
	hurry_mode_started.emit()

func _generate_hurry_spiral_pattern() -> Array[Vector2i]:
	"""Generate a clockwise spiral pattern from edges inward.
	This creates the classic Bomberman 'closing walls' effect."""
	var pattern: Array[Vector2i] = []
	
	if game_map.is_empty():
		return pattern
	
	var map_height = game_map.size()
	var map_width = game_map[0].size()
	
	# Define bounds (start from inside the outer wall)
	var top = 1
	var bottom = map_height - 2
	var left = 1
	var right = map_width - 2
	
	# Spiral inward: top row -> right column -> bottom row -> left column -> repeat
	while top <= bottom and left <= right:
		# Top row (left to right)
		for x in range(left, right + 1):
			if _can_place_hurry_block(x, top):
				pattern.append(Vector2i(x, top))
		top += 1
		
		# Right column (top to bottom)
		for y in range(top, bottom + 1):
			if _can_place_hurry_block(right, y):
				pattern.append(Vector2i(right, y))
		right -= 1
		
		# Bottom row (right to left)
		if top <= bottom:
			for x in range(right, left - 1, -1):
				if _can_place_hurry_block(x, bottom):
					pattern.append(Vector2i(x, bottom))
			bottom -= 1
		
		# Left column (bottom to top)
		if left <= right:
			for y in range(bottom, top - 1, -1):
				if _can_place_hurry_block(left, y):
					pattern.append(Vector2i(left, y))
			left += 1
	
	return pattern

func _can_place_hurry_block(x: int, y: int) -> bool:
	"""Check if a hurry block can be placed at this position.
	Can't place on existing hard walls."""
	if y < 0 or y >= game_map.size():
		return false
	if x < 0 or x >= game_map[0].size():
		return false
	
	# Don't place on existing hard walls (type 1)
	var current_type = game_map[y][x]
	if current_type == 1:
		return false
	
	return true

func _process_hurry_mode(delta: float):
	"""Process hurry mode - spawn blocks at intervals"""
	if hurry_spawn_index >= hurry_spawn_pattern.size():
		return  # All blocks spawned
	
	hurry_spawn_timer += delta
	
	# Spawn blocks at regular intervals
	while hurry_spawn_timer >= hurry_spawn_interval and hurry_spawn_index < hurry_spawn_pattern.size():
		hurry_spawn_timer -= hurry_spawn_interval
		_spawn_hurry_block(hurry_spawn_pattern[hurry_spawn_index])
		hurry_spawn_index += 1

func _spawn_hurry_block(pos: Vector2i):
	"""Spawn a hurry block at the given position.
	Kills any player standing there, destroys bombs, and becomes impassable."""
	
	# First check for players at this position and kill them
	var world_pos = Vector2(pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
							pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0)
	
	for peer_id in players:
		var player = players[peer_id]
		if player.is_dead:
			continue
		
		var player_tile = player.get_tile_position()
		if player_tile == pos:
			print("[Hurry] 💀 Player %s crushed by hurry block at %s!" % [player.player_name, pos])
			player.die("Crushed by hurry block")
			
			# Check for match end
			_check_alive_players()
	
	# Destroy any bomb at this position
	var bombs_to_remove = []
	for bomb_id in bombs:
		var bomb = bombs[bomb_id]
		if is_instance_valid(bomb):
			var bomb_tile = bomb.get_tile_position()
			if bomb_tile == pos:
				bombs_to_remove.append(bomb_id)
	
	for bomb_id in bombs_to_remove:
		var bomb = bombs[bomb_id]
		if is_instance_valid(bomb):
			# Trigger explosion before removing
			bomb.explode()
	
	# Destroy any soft block at this position
	var tile_key = "%d,%d" % [pos.x, pos.y]
	if map_tiles.has(tile_key):
		var old_body = map_tiles[tile_key]
		if is_instance_valid(old_body):
			old_body.queue_free()
		map_tiles.erase(tile_key)
	
	# Update game_map to hurry block (type 3 = hurry block, visually distinct from wall)
	if pos.y >= 0 and pos.y < game_map.size() and pos.x >= 0 and pos.x < game_map[0].size():
		game_map[pos.y][pos.x] = 3  # 3 = hurry block (new type)
	
	# Create collision body for the hurry block
	var tile_body = StaticBody2D.new()
	tile_body.position = world_pos
	tile_body.name = "HurryBlock_%d_%d" % [pos.x, pos.y]
	
	var collision = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
	collision.shape = shape
	tile_body.add_child(collision)
	
	add_child(tile_body)
	map_tiles[tile_key] = tile_body
	
	# Track hurry blocks for state sync
	hurry_blocks.append(pos)
	
	# Add to map changes for delta compression
	map_changes.append({"x": pos.x, "y": pos.y, "value": 3})

func _check_alive_players():
	"""Check if match should end after a player death"""
	var alive_count = 0
	for peer_id in players:
		if not players[peer_id].is_dead:
			alive_count += 1
	
	if alive_count <= 1:
		end_match()

func handle_player_input(peer_id: int, input_data: Dictionary):
	if not players.has(peer_id):
		return
	
	var player = players[peer_id]
	
	# Set movement input
	player.set_input(input_data.get("input_x", 0.0), input_data.get("input_y", 0.0))
	
	var action_pressed = input_data.get("action_pressed", false)
	var action_released = input_data.get("action_released", false)

	# Branch logic based on whether player has Power Glove
	if player.has_power_glove:
		# Power Glove Logic: Place -> Pickup -> Throw, all on press
		if action_pressed:
			player.request_action_press()
			# If currently carrying, throw on press
			if player.is_carrying_bomb():
				player.throw_carried_bomb()
			else:
				# Not carrying: try to pick up a bomb underfoot
				var pickup_successful = _try_pickup_bomb_at_player(player)
				if not pickup_successful:
					# Only place a new bomb if NOT on an existing bomb
					var player_tile = player.get_tile_position()
					var bomb_at_position = false
					for bomb_id in bombs:
						var bomb = bombs[bomb_id]
						if is_instance_valid(bomb) and bomb.get_tile_position() == player_tile:
							bomb_at_position = true
							break
					# Place if no bomb here and allowed
					if not bomb_at_position and player.can_place_bomb():
						place_bomb(player)
		elif action_released:
			# Maintain state for completeness; no throw on release now
			player.request_action_release()
	elif player.bomb_type == ServerBomb.BOMB_TYPE_REMOTE:
		# REMOTE BOMB Logic: Action detonates oldest remote bomb
		if action_pressed:
			_detonate_oldest_remote_bomb(player)
		# Standard bomb placement still works
		if input_data.get("place_bomb", false) and player.can_place_bomb():
			place_bomb(player)
	else:
		# Standard Logic: Place bomb
		if input_data.get("place_bomb", false) and player.can_place_bomb():
			place_bomb(player)

func _try_pickup_bomb_at_player(player: ServerPlayer) -> bool:
	"""Try to pick up a bomb at the player's current tile. Returns true if successful."""
	var player_tile = player.get_tile_position()
	
	print("[DEBUG] Trying to pick up bomb at tile: ", player_tile)
	print("[DEBUG] Total bombs in game: ", bombs.size())
	
	# Find bomb at player's position
	for bomb_id in bombs:
		var bomb = bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		
		var bomb_tile = bomb.get_tile_position()
		print("[DEBUG] Checking bomb ", bomb_id, " at tile ", bomb_tile, " state=", bomb.bomb_state)
		
		if bomb_tile == player_tile:
			print("[DEBUG] Found bomb at player position! can_be_picked_up=", bomb.can_be_picked_up())
			# Attempt pickup
			if player.try_pickup_bomb(bomb):
				print("[Game] Player ", player.username, " picked up bomb ", bomb_id)
				return true # Bomb picked up
			else:
				print("[DEBUG] Pickup failed for bomb ", bomb_id)
	
	print("[DEBUG] No bomb found at player position")
	return false # No bomb picked up


func _detonate_oldest_remote_bomb(player: ServerPlayer):
	"""Detonate the oldest REMOTE bomb placed by this player"""
	var oldest_bomb: ServerBomb = null
	var oldest_time: float = INF
	
	for bomb_id in bombs:
		var bomb = bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		if bomb.owner_id != player.player_id:
			continue
		if bomb.bomb_type != ServerBomb.BOMB_TYPE_REMOTE:
			continue
		if bomb.bomb_state != ServerBomb.BombState.PLANTED:
			continue
		
		# Find the oldest bomb by checking timer (lower timer = older)
		# Note: explosion_timer counts UP from 0
		# Actually we need to track placement order, but for simplicity
		# we'll just detonate ALL remote bombs at once or use bomb_id as proxy for age
		if int(bomb.bomb_id) < oldest_time:
			oldest_time = int(bomb.bomb_id)
			oldest_bomb = bomb
	
	if oldest_bomb:
		print("[Game] Remote detonation by ", player.username, " - exploding bomb ", oldest_bomb.bomb_id)
		oldest_bomb.explode()


func place_bomb(player: ServerPlayer):
	# Prevent bomb placement during countdown
	if not match_active:
		print("[Game] place_bomb failed: match_active is false")
		return
	
	# LINE_BOMB: Place multiple bombs in facing direction
	if player.has_line_bomb:
		_place_line_bombs(player)
		return
	
	_place_single_bomb(player)


func _place_line_bombs(player: ServerPlayer):
	"""Place a line of bombs in the player's facing direction (LINE_BOMB ability)"""
	var facing = player.last_move_direction
	if facing.length() < 0.1:
		facing = Vector2.DOWN  # Default to down if no movement direction
	
	# Normalize to cardinal direction
	if abs(facing.x) > abs(facing.y):
		facing = Vector2(sign(facing.x), 0)
	else:
		facing = Vector2(0, sign(facing.y))
	
	var facing_v = Vector2i(int(facing.x), int(facing.y))
	var start_tile = player.get_tile_position()
	var bombs_placed_count = 0
	var max_to_place = player.max_bombs - player.bombs_placed
	
	print("[Game] LINE_BOMB: ", player.username, " placing up to ", max_to_place, " bombs in direction ", facing)
	
	# Place bombs from player position outward in facing direction
	for i in range(max_to_place):
		var tile_pos = start_tile + facing_v * i
		
		# Check if tile is valid and empty (no wall, no block, no existing bomb)
		if not _is_tile_valid_for_bomb(tile_pos):
			print("[Game] LINE_BOMB: Stopped at tile ", tile_pos, " (blocked)")
			break
		
		# Check if there's already a bomb at this position
		if _has_bomb_at_tile(tile_pos):
			print("[Game] LINE_BOMB: Stopped at tile ", tile_pos, " (bomb exists)")
			break
		
		_place_single_bomb_at_tile(player, tile_pos)
		bombs_placed_count += 1
	
	print("[Game] LINE_BOMB: Placed ", bombs_placed_count, " bombs")


func _is_tile_valid_for_bomb(tile_pos: Vector2i) -> bool:
	"""Check if a tile can have a bomb placed on it"""
	if tile_pos.x < 0 or tile_pos.y < 0:
		return false
	if tile_pos.y >= game_map.size() or tile_pos.x >= game_map[0].size():
		return false
	
	var tile_value = game_map[tile_pos.y][tile_pos.x]
	# 0 = empty, 1 = wall, 2 = block, 3+ = powerups
	return tile_value == 0 or tile_value >= 3  # Can place on empty or powerup tiles


func _has_bomb_at_tile(tile_pos: Vector2i) -> bool:
	"""Check if there's already a bomb at this tile position"""
	for bomb_id in bombs:
		var bomb = bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile_pos:
			return true
	return false


func _place_single_bomb_at_tile(player: ServerPlayer, tile_pos: Vector2i):
	"""Place a single bomb at a specific tile position"""
	var bomb = ServerBombScene.instantiate()
	bomb.bomb_id = str(next_bomb_id)
	next_bomb_id += 1
	bomb.owner_id = player.player_id
	bomb.explosion_range = player.get_effective_bomb_range()  # SMALL_FLAME virus forces range to 1
	bomb.bomb_type = player.bomb_type
	
	bomb.position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	bomb.name = "Bomb_" + bomb.bomb_id
	bomb.game_instance = self
	bomb.explosion_timer = 0.0
	bomb.fuse_time = player.get_bomb_fuse_time()
	
	bombs[bomb.bomb_id] = bomb
	add_child(bomb)
	
	# Add collision exception for ALL players standing on this bomb tile
	for peer_id in players:
		var p = players[peer_id]
		if not is_instance_valid(p) or p.is_dead:
			continue
		if p.get_tile_position() == tile_pos:
			p.add_bomb_collision_exception(bomb)
	
	player.bombs_placed += 1
	bomb.exploded.connect(_on_bomb_exploded)
	bomb.explosion_expanded.connect(func(tiles): _on_explosion_expanded(bomb, tiles))
	var cleanup_callable := func():
		if bombs.has(bomb.bomb_id):
			bombs.erase(bomb.bomb_id)
	bomb.tree_exited.connect(cleanup_callable, Object.CONNECT_ONE_SHOT)
	
	print("[Game] Bomb placed at tile ", tile_pos, " fuse=", bomb.fuse_time, "s")


func _place_single_bomb(player: ServerPlayer):
	# Prevent bomb placement during countdown
	if not match_active:
		print("[Game] place_bomb failed: match_active is false")
		return
	
	var bomb = ServerBombScene.instantiate()
	bomb.bomb_id = str(next_bomb_id)
	next_bomb_id += 1
	bomb.owner_id = player.player_id
	bomb.explosion_range = player.get_effective_bomb_range()  # SMALL_FLAME virus forces range to 1
	bomb.bomb_type = player.bomb_type  # Copy player's current bomb type
	
	print("[Game] Creating bomb ", bomb.bomb_id, " for ", player.username, " type=", player.bomb_type)
	
	# CRITICAL: Place bomb at tile CENTER, not top-left corner
	# This prevents collision/snapping issues when player is slightly off-center
	var player_tile = player.get_tile_position()
	bomb.position = Vector2(
		player_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		player_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	bomb.name = "Bomb_" + bomb.bomb_id
	bomb.game_instance = self # Give bomb reference for collision checking
	# Start fuse from zero on placement (count-up logic)
	# Apply SHORT_FUSE curse if active
	bomb.explosion_timer = 0.0
	bomb.fuse_time = player.get_bomb_fuse_time()  # 1s if cursed, 3s otherwise
	
	bombs[bomb.bomb_id] = bomb
	add_child(bomb)
	
	# CRITICAL: Add collision exception AFTER bomb is in tree to avoid race condition
	# Check ALL players (not just owner) to see if they are standing on the bomb
	# If so, disable collision until they walk off
	var bomb_tile = bomb.get_tile_position()
	for peer_id in players:
		var p = players[peer_id]
		if not is_instance_valid(p) or p.is_dead:
			continue
			
		if p.get_tile_position() == bomb_tile:
			p.add_bomb_collision_exception(bomb)
			print("[Game] Added collision exception for player ", p.username, " on bomb ", bomb.bomb_id)
	
	player.bombs_placed += 1
	bomb.exploded.connect(_on_bomb_exploded)
	bomb.explosion_expanded.connect(func(tiles): _on_explosion_expanded(bomb, tiles))
	# Ensure dictionary entry is cleaned up when the bomb leaves the scene tree
	var cleanup_callable := func():
		if bombs.has(bomb.bomb_id):
			bombs.erase(bomb.bomb_id)
	bomb.tree_exited.connect(cleanup_callable, Object.CONNECT_ONE_SHOT)
	
	print("[Game] Bomb placed by ", player.username, " at tile ", bomb.get_tile_position(), " fuse=", bomb.fuse_time, "s")
	
	# CRITICAL: Immediately update threat matrix so AI can react to newly placed bomb
	if ai_manager:
		ai_manager.refresh_threat_matrix(Time.get_ticks_msec())
		print("[Game] Threat matrix refreshed immediately after bomb placement")
	
	# Also refresh BotManager's perception (HazardPredictor)
	if bot_manager and bot_manager.has_method("refresh_perception"):
		bot_manager.refresh_perception()

	# Broadcast AI debug data (throttled)
	if bot_manager and Engine.get_physics_frames() % 6 == 0: # Every 6 frames (10Hz at 60fps)
		for child in bot_manager.get_children():
			if child.has_method("get_debug_payload"):
				var payload = child.get_debug_payload()
				if payload.size() > 0:
					ServerMain.rpc("ai_debug_update", payload)

func _on_bomb_exploded(bomb, explosion_pattern: Array) -> void:
	# Bomb now passes itself and explosion pattern directly
	if not is_instance_valid(bomb):
		push_warning("[Game] Bomb exploded callback with invalid bomb reference")
		return
	
	var bomb_id = bomb.bomb_id
	if not bombs.has(bomb_id):
		push_warning("[Game] Bomb exploded callback for unknown bomb: ", bomb_id)
		return
	
	print("[Game] Bomb exploded: ", bomb.bomb_id, " with ", explosion_pattern.size(), " tiles")
	
	# Find owner from bomb.owner_id
	var bomb_owner = null
	if bomb.owner_id and players.has(int(bomb.owner_id)):
		bomb_owner = players[int(bomb.owner_id)]
	
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
			
			# Skip dead players - they cannot be killed again
			if player.is_dead:
				continue
			
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
	"""Destroy a destructible block and optionally spawn powerup (server-side only)"""
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
	
	# Track map change for delta compression
	map_changes.append({"x": cell.x, "y": cell.y, "value": 0})
	
	# Update AI pathfinder (soft wall destroyed = new path opened)
	if ai_manager != null:
		ai_manager.on_wall_destroyed(cell)
	
	# Server-side random powerup spawn (synced to clients via state updates)
	# Uses configurable drop rate from Constants
	# IMPORTANT: Defer to next frame so the powerup doesn't get destroyed by the same explosion
	if randf() < Constants.POWERUP_DROP_CHANCE:
		call_deferred("spawn_powerup", cell)

func get_tile_type(grid_pos: Vector2i) -> int:
	"""Get tile type at grid position (0=empty, 1=wall, 2=destructible)"""
	if grid_pos.y < 0 or grid_pos.y >= game_map.size():
		return 1 # Treat out of bounds as wall
	if grid_pos.x < 0 or grid_pos.x >= game_map[0].size():
		return 1 # Treat out of bounds as wall
	
	return game_map[grid_pos.y][grid_pos.x]

func sync_state_to_clients():
	# Clean up old explosions (keep for progressive display duration)
	var current_time = Time.get_ticks_msec() / 1000.0
	var explosion_duration = 0.02 * 20 # ~20 expansion steps max
	explosions = explosions.filter(func(explosion): return current_time - explosion["start_time"] < explosion_duration)
	
	# Build compact game state for unreliable updates (uses short keys to reduce size)
	# Full player/bomb data is sent via reliable channel when stats change
	var state = {
		"p": {},  # players (minimal movement state)
		"b": {},  # bombs (minimal state)
		"t": int(match_time_remaining),  # match timer (seconds as int)
		"a": match_active,  # active
		"c": countdown_time if countdown_time > 0 else null,  # countdown (only when active)
		"w": winner_id if winner_id != "" else null,  # winner (only when set)
		"h": hurry_mode_active,  # hurry mode
	}
	
	# Use minimal player state (position, velocity, facing, dead, carried_bomb)
	for peer_id in players:
		state.p[str(peer_id)] = players[peer_id].get_state_minimal()
	
	# Use minimal bomb state (id, position, timer, state)
	for bomb_id in bombs:
		state.b[bomb_id] = bombs[bomb_id].get_state_minimal()
	
	# Powerups rarely change - only include count, client can request full data
	if powerups.size() > 0:
		state["pu"] = powerups.size()
	
	# Compact explosion data - essential for rendering
	# Format: [center_x, center_y, pattern, owner_id, bomb_id, start_time]
	if explosions.size() > 0:
		var exp_data := []
		for explosion in explosions:
			exp_data.append([
				int(explosion["center"].x),  # [0] center x
				int(explosion["center"].y),  # [1] center y  
				explosion["pattern"],        # [2] pattern dict
				explosion["owner_id"],       # [3] owner for kill attribution
				explosion["bomb_id"],        # [4] bomb_id for linking to bomb node
				explosion["start_time"]      # [5] start_time for animation timing
			])
		state["e"] = exp_data
	
	# NOTE: Threat matrix removed from regular state sync to reduce packet size
	# It was causing MTU exceeded warnings (3320 > 1392 bytes)
	# If debug visualization is needed, send via separate reliable RPC at lower frequency
	
	# Send to all players in this game via ClientMain autoload
	# Use delta compression for map - only send full map to new clients
	var changes_to_send = map_changes.duplicate()
	map_changes.clear() # Clear changes after capturing them
	
	for peer_id in players:
		var player = players[peer_id]
		if player.has_method("is_ai_bot") and player.is_ai_bot():
			continue
		
		# Create per-client state copy for delta compression
		var client_state = state.duplicate()
		
		# Delta compression for hurry_blocks - only send new blocks
		var last_sent_count = last_sent_hurry_block_count.get(peer_id, 0)
		if hurry_blocks.size() > last_sent_count:
			# Only send new blocks since last sync
			var new_blocks: Array = []
			for i in range(last_sent_count, hurry_blocks.size()):
				new_blocks.append(hurry_blocks[i])
			client_state["hb"] = new_blocks  # hurry blocks (short key)
			last_sent_hurry_block_count[peer_id] = hurry_blocks.size()
		# else: No new hurry blocks - don't include key (saves bytes)
		
		# Check if this client needs the full map
		if not clients_received_full_map.get(peer_id, false):
			# First sync for this client - send map data via RELIABLE channel
			# This handles the larger payload without MTU issues
			var packed_map := PackedByteArray()
			for row in game_map:
				for cell in row:
					packed_map.append(cell)
			var map_data = {
				"map_packed": packed_map,
				"map_width": game_map[0].size() if game_map.size() > 0 else 0,
				"map_height": game_map.size(),
				"map_config": {
					"tile_size": GameConfig.TILE_SIZE,
					"width": GameConfig.map_width,
					"height": GameConfig.map_height,
					"name": GameConfig.map_name
				}
			}
			# Send map reliably (TCP) to avoid MTU issues on first sync
			get_tree().root.get_node("ClientMain").rpc_id(peer_id, "receive_initial_map", map_data)
			clients_received_full_map[peer_id] = true
			# Also reset hurry block count for new clients (they'll get full map changes via initial_map)
			last_sent_hurry_block_count[peer_id] = hurry_blocks.size()
		elif changes_to_send.size() > 0:
			# Send only map changes (delta compression)
			client_state["map_changes"] = changes_to_send
		# else: No changes - don't include map data (already not in base state)
		
		# Send regular state update (without map) via unreliable channel
		get_tree().root.get_node("ClientMain").rpc_id(peer_id, "receive_state", client_state)
func spawn_powerup(tile_pos: Vector2i):
	"""Spawn a power-up at the given tile position (server-side, synced to clients)"""
	var powerup = ServerPowerUpScene.instantiate()
	powerup.powerup_id = str(next_powerup_id)
	next_powerup_id += 1
	
	# Random power-up type using weighted distribution from Constants
	var rand_val = randf()
	var cumulative = 0.0
	var weights = Constants.POWERUP_WEIGHTS
	
	# Mapping from weight key names to PowerUpType enum values
	var type_mapping = {
		"BOMB_INCREASE": ServerPowerUp.PowerUpType.BOMB_INCREASE,
		"RANGE_INCREASE": ServerPowerUp.PowerUpType.RANGE_INCREASE,
		"SPEED_INCREASE": ServerPowerUp.PowerUpType.SPEED_INCREASE,
		"BOMB_KICKER": ServerPowerUp.PowerUpType.BOMB_KICKER,
		"POWER_GLOVE": ServerPowerUp.PowerUpType.POWER_GLOVE,
		"LINE_BOMB": ServerPowerUp.PowerUpType.LINE_BOMB,
		"FULL_FIRE": ServerPowerUp.PowerUpType.FULL_FIRE,
		"HEART": ServerPowerUp.PowerUpType.HEART,
		"GETA": ServerPowerUp.PowerUpType.GETA,
		"REMOTE_BOMB": ServerPowerUp.PowerUpType.REMOTE_BOMB,
		"POWER_BOMB": ServerPowerUp.PowerUpType.POWER_BOMB,
		"RUBBER_BOMB": ServerPowerUp.PowerUpType.RUBBER_BOMB,
		"PIERCE_BOMB": ServerPowerUp.PowerUpType.PIERCE_BOMB,
		"SKULL": ServerPowerUp.PowerUpType.SKULL,
		"VIRUS": ServerPowerUp.PowerUpType.SKULL  # Alias
	}
	
	# Use cumulative probability to select type based on weights
	var selected_type = ServerPowerUp.PowerUpType.BOMB_INCREASE  # Default fallback
	for type_name in weights:
		cumulative += weights[type_name]
		if rand_val < cumulative:
			if type_mapping.has(type_name):
				selected_type = type_mapping[type_name]
			break
	
	powerup.powerup_type = selected_type
	
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

func spawn_powerup_of_type(tile_pos: Vector2i, type: int):
	"""Spawn a specific power-up type at the given tile position"""
	var powerup = ServerPowerUpScene.instantiate()
	powerup.powerup_id = str(next_powerup_id)
	next_powerup_id += 1
	powerup.powerup_type = type
	
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
	
	var type_names = ["BOMB", "FIRE", "SKATE", "KICK", "GLOVE", "VIRUS"]
	var type_name = type_names[type] if type < type_names.size() else str(type)
	print("[Game] Spawned %s power-up at %s" % [type_name, tile_pos])

func spawn_test_powerups():
	"""Spawn a power-up for every soft block for testing"""
	print("[Game] Spawning test power-ups for ALL soft blocks...")
	
	var spawned_count := 0
	var map_height = game_map.size()
	
	for y in range(map_height):
		var map_width = game_map[y].size()
		for x in range(map_width):
			# Check if this is a soft block (type 2)
			if game_map[y][x] == 2:
				# Destroy the soft block first
				game_map[y][x] = 0
				
				# Spawn a random powerup type using weighted distribution
				spawn_powerup(Vector2i(x, y))
				spawned_count += 1
	
	print("[Game] Spawned %d test power-ups" % spawned_count)

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

func get_bomb_at_tile(tile_pos: Vector2i):
	"""Get the bomb at a specific tile position, or null if none exists"""
	for bomb_id in bombs:
		var bomb = bombs[bomb_id]
		if bomb.get_tile_position() == tile_pos:
			return bomb
	return null

func stop_nearby_kicked_bombs(player: ServerPlayer):
	"""Stop any kicked bombs near the player"""
	var player_tile = player.get_tile_position()
	
	# Check bombs in a 3x3 area around the player
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			var check_tile = player_tile + Vector2i(dx, dy)
			var bomb = get_bomb_at_tile(check_tile)
			
			if bomb and bomb.is_kicked:
				bomb.stop_kick()
				print("[Game] Player ", player.username, " stopped kicked bomb at ", check_tile)

# RPC: Forward bomb safety data to a specific client
@rpc("any_peer", "call_remote", "unreliable")
func bomb_safety_update(_safety_data: Dictionary) -> void:
	# This is called on game_instance but we need to forward to clients via their game_view
	# The bot_controller will call this directly on clients via rpc_id
	pass

# === SATURN BOMBERMAN VIRUS TRANSFER SYSTEM ===
# Players can transfer their virus to other players by touching them (tag mechanic)
func _process_virus_transfers() -> void:
	"""Check for player collisions and transfer viruses between them"""
	var player_list = players.values()
	var transfer_distance = GameConfig.TILE_SIZE * 0.6  # Players must be close to transfer
	
	for i in range(player_list.size()):
		var player_a = player_list[i]
		if not is_instance_valid(player_a) or player_a.is_dead:
			continue
		if player_a.active_virus == player_a.VirusType.NONE:
			continue  # No virus to transfer
		
		for j in range(i + 1, player_list.size()):
			var player_b = player_list[j]
			if not is_instance_valid(player_b) or player_b.is_dead:
				continue
			if player_b.active_virus != player_b.VirusType.NONE:
				continue  # Already has a virus
			
			# Check distance
			var distance = player_a.position.distance_to(player_b.position)
			if distance < transfer_distance:
				# Transfer virus from A to B
				player_a.transfer_virus_to(player_b)
				# Notify clients about the transfer
				_notify_virus_transfer(player_a.peer_id, player_b.peer_id)
				break  # Only transfer once per frame

func _notify_virus_transfer(from_peer_id: int, to_peer_id: int) -> void:
	"""Notify all clients about a virus transfer for visual/audio effects"""
	# RPC to all clients
	rpc_virus_transfer.rpc(from_peer_id, to_peer_id)

@rpc("authority", "call_remote", "reliable")
func rpc_virus_transfer(from_peer_id: int, to_peer_id: int) -> void:
	"""Client receives notification of virus transfer"""
	# This is called on clients - they handle visuals/audio locally
	print("[Client] Virus transferred from player ", from_peer_id, " to ", to_peer_id)
