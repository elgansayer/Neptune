extends Node

@onready var nakama_client = NakamaService
var grid_rendered = false

# --- State Variables ---
var game_state = {}
var player_scenes = {}
var bomb_scenes = {}
var explosion_scenes = {}
var powerup_scenes = {}
var character_data = {}
var my_user_id = ""

# --- Saturn Bomberman Movement System ---
const TILE_SIZE = 64.0  # Tile size is 64x64 pixels
const BASE_SPEED = 180.0  # Units per second (pixels/sec)
const WALK_MULTIPLIER = 0.5
const RUN_MULTIPLIER = 1.0
const WALK_RUN_THRESHOLD = 0.7
const INPUT_DEADZONE = 0.1
const PLAYER_HITBOX_RADIUS = 31.0  # Player bounding box is 62x62 (circular for collision)
const PLAYER_HALF_WIDTH = 28.0  # Half-width for square bounding box checks (56x56)
const CORNER_ASSIST_THRESHOLD = 0.5  # Corner assistance activates within 50% of tile alignment

var player_pixel_position = Vector2.ZERO  # Continuous floating-point position
var player_velocity = Vector2.ZERO
var player_facing_direction = "DOWN"

# Last input priority system
var last_input_direction = ""  # "up", "down", "left", "right", or ""

# Bomb passthrough tracking (Atomic Bomberman pattern)
var inside_bomb_tile = Vector2(-1, -1)  # Track which bomb tile we're inside (-1,-1 = none)
var inside_bomb_grace_frames = 0  # Grace period to wait for server confirmation

# Network sync
var input_sequence = 0
var last_network_sync_time = 0.0
const NETWORK_SYNC_RATE = 0.05  # Send updates every 50ms (20 Hz)

# Debug
var debug_slide_active = false

# --- Godot Lifecycle ---

func _ready():
	# Get session info if already authenticated
	if nakama_client.session:
		my_user_id = nakama_client.session.user_id
	else:
		nakama_client.authenticated.connect(_on_authenticated)
	
	nakama_client.match_data_received.connect(_on_match_data_received)
	_load_character_data()

func _on_authenticated(session, _is_new_user):
	my_user_id = session.user_id
func _load_character_data():
	var dir = DirAccess.open("res://characters")
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if not dir.current_is_dir() and file_name.ends_with(".json"):
				var file = FileAccess.open("res://characters/" + file_name, FileAccess.READ)
				var content = file.get_as_text()
				file.close()
				var json = JSON.parse_string(content)
				if json:
					character_data[json.name] = json
			file_name = dir.get_next()


func _physics_process(delta):
	if not player_scenes.has(my_user_id):
		return
	
	# === PILLAR A: Dual-Speed Vector-Based Locomotion ===
	
	# Last input priority system - whichever direction was pressed most recently takes priority
	# Check for any new key press (these take immediate priority)
	if Input.is_action_just_pressed("ui_up"):
		last_input_direction = "up"
	elif Input.is_action_just_pressed("ui_down"):
		last_input_direction = "down"
	elif Input.is_action_just_pressed("ui_left"):
		last_input_direction = "left"
	elif Input.is_action_just_pressed("ui_right"):
		last_input_direction = "right"
	
	# Build input vector: start with last input if still held
	var input_vector = Vector2.ZERO
	if last_input_direction == "up" and Input.is_action_pressed("ui_up"):
		input_vector.y = -1
	elif last_input_direction == "down" and Input.is_action_pressed("ui_down"):
		input_vector.y = 1
	elif last_input_direction == "left" and Input.is_action_pressed("ui_left"):
		input_vector.x = -1
	elif last_input_direction == "right" and Input.is_action_pressed("ui_right"):
		input_vector.x = 1
	
	# If last input not held, check what IS held and use that
	if input_vector == Vector2.ZERO:
		if Input.is_action_pressed("ui_up"):
			input_vector.y = -1
			last_input_direction = "up"
		elif Input.is_action_pressed("ui_down"):
			input_vector.y = 1
			last_input_direction = "down"
		elif Input.is_action_pressed("ui_left"):
			input_vector.x = -1
			last_input_direction = "left"
		elif Input.is_action_pressed("ui_right"):
			input_vector.x = 1
			last_input_direction = "right"
		else:
			last_input_direction = ""
	
	# Normalize diagonal movement to prevent faster diagonal speed
	if input_vector.length() > 1.0:
		input_vector = input_vector.normalized()
	
	# Determine walk vs run based on input magnitude
	var speed_multiplier = RUN_MULTIPLIER
	if input_vector.length() < WALK_RUN_THRESHOLD:
		speed_multiplier = WALK_MULTIPLIER
	
	# Calculate desired velocity
	var desired_velocity = input_vector * BASE_SPEED * speed_multiplier
	
	# === PILLAR B: Assisted Cornering (Wall Hugging) ===
	
	# Calculate target position if we apply full velocity
	var target_position = player_pixel_position + desired_velocity * delta
	var final_velocity = desired_velocity
	
	# Check if trying to turn perpendicular to CURRENT facing direction (before updating it)
	var is_perpendicular_turn = false
	if (player_facing_direction == "UP" or player_facing_direction == "DOWN") and desired_velocity.x != 0:
		is_perpendicular_turn = true
	elif (player_facing_direction == "LEFT" or player_facing_direction == "RIGHT") and desired_velocity.y != 0:
		is_perpendicular_turn = true
	
	# If trying to turn perpendicular, check corner assistance FIRST
	if is_perpendicular_turn:
		var corner_velocity = _try_corner_assistance(desired_velocity, delta)
		
		if corner_velocity != Vector2.ZERO:
			# Diagonal is clear - buffer turn and continue current movement
			var corner_target = player_pixel_position + corner_velocity * delta
			if _is_position_walkable(corner_target, player_pixel_position):
				final_velocity = corner_velocity
				debug_slide_active = true
			else:
				# Facing direction blocked, just stop
				final_velocity = Vector2.ZERO
				debug_slide_active = false
		else:
			# Diagonal is blocked - stop moving and face the new direction
			final_velocity = Vector2.ZERO
			debug_slide_active = false
			
			# Update facing direction to the attempted turn direction
			if abs(desired_velocity.y) > abs(desired_velocity.x):
				if desired_velocity.y < 0:
					player_facing_direction = "UP"
				else:
					player_facing_direction = "DOWN"
			else:
				if desired_velocity.x < 0:
					player_facing_direction = "LEFT"
				else:
					player_facing_direction = "RIGHT"
	else:
		# Normal movement (continuing in same direction)
		if _is_position_walkable(target_position, player_pixel_position):
			# No collision - use full velocity
			final_velocity = desired_velocity
			debug_slide_active = false
		else:
			# Collision detected - try corner assistance
			var corner_velocity = _try_corner_assistance(desired_velocity, delta)
			
			if corner_velocity != Vector2.ZERO:
				# Corner assistance found a better path
				var corner_target = player_pixel_position + corner_velocity * delta
				if _is_position_walkable(corner_target, player_pixel_position):
					final_velocity = corner_velocity
					debug_slide_active = true
				else:
					# Corner path also blocked
					final_velocity = Vector2.ZERO
					debug_slide_active = false
			else:
				# No valid movement found - stop
				final_velocity = Vector2.ZERO
				debug_slide_active = false
	
	# === PILLAR C: Instantaneous Input Response ===
	# Update position immediately (no acceleration/deceleration)
	player_velocity = final_velocity
	player_pixel_position += player_velocity * delta
	
	# Update facing direction based on actual movement (final_velocity)
	# Only update if we actually moved
	if final_velocity.length() > INPUT_DEADZONE:
		# Vertical priority
		if abs(final_velocity.y) > abs(final_velocity.x):
			if final_velocity.y < 0:
				player_facing_direction = "UP"
			else:
				player_facing_direction = "DOWN"
		else:
			if final_velocity.x < 0:
				player_facing_direction = "LEFT"
			else:
				player_facing_direction = "RIGHT"
	# Note: facing direction may have been updated in perpendicular turn logic above
	# when diagonal is blocked (immediate stop + face new direction)
	
	# === Auto-centering: Gradually align to tile center when moving ===
	if final_velocity != Vector2.ZERO:
		var tile_x = int(floor(player_pixel_position.x / TILE_SIZE))
		var tile_y = int(floor(player_pixel_position.y / TILE_SIZE))
		var tile_center = Vector2(tile_x * TILE_SIZE + TILE_SIZE / 2, tile_y * TILE_SIZE + TILE_SIZE / 2)
		
		# When moving horizontally, center vertically
		if abs(final_velocity.x) > abs(final_velocity.y):
			var y_offset = tile_center.y - player_pixel_position.y
			if abs(y_offset) > 1.0:  # Only apply if offset is noticeable
				var centering_speed = min(abs(y_offset) * 3.0, BASE_SPEED * 0.3)  # Gentle centering
				player_pixel_position.y += sign(y_offset) * centering_speed * delta
		
		# When moving vertically, center horizontally
		elif abs(final_velocity.y) > abs(final_velocity.x):
			var x_offset = tile_center.x - player_pixel_position.x
			if abs(x_offset) > 1.0:
				var centering_speed = min(abs(x_offset) * 3.0, BASE_SPEED * 0.3)
				player_pixel_position.x += sign(x_offset) * centering_speed * delta
	
	# Update visual position
	var my_player = player_scenes[my_user_id]
	my_player.position = player_pixel_position
	
	# Update inside_bomb_tile - clear it if we're no longer colliding with that specific bomb
	if inside_bomb_tile != Vector2(-1, -1):
		print("[FLAG CHECK] Checking flag, grace_frames=", inside_bomb_grace_frames)
		# Decrement grace period counter
		if inside_bomb_grace_frames > 0:
			inside_bomb_grace_frames -= 1
			print("[FLAG CHECK] In grace period, frames remaining: ", inside_bomb_grace_frames)
			# Don't check for bomb existence during grace period
		elif game_state.has("bombs"):
			print("[FLAG CHECK] Grace period over, checking if we've exited bomb")
			print("[FLAG CHECK] inside_bomb_tile=", inside_bomb_tile)
			print("[FLAG CHECK] Number of bombs in game_state:", game_state.bombs.size())
			# Find the bomb we're supposedly inside
			var found_bomb = false
			for bomb in game_state.bombs:
				print("[FLAG CHECK] Checking bomb at tile (", bomb.position.x, ", ", bomb.position.y, ")")
				if bomb.position.x == inside_bomb_tile.x and bomb.position.y == inside_bomb_tile.y:
					found_bomb = true
					print("[FLAG CHECK] Found our bomb! Checking collision...")
					print("[FLAG CHECK] Player position: ", player_pixel_position)
					var bomb_center = Vector2(
						bomb.position.x * TILE_SIZE + TILE_SIZE / 2,
						bomb.position.y * TILE_SIZE + TILE_SIZE / 2
					)
					print("[FLAG CHECK] Bomb center: ", bomb_center)
					# Check if ANY part of player hitbox is still colliding with bomb
					var still_colliding = false
					var check_points = [
						player_pixel_position,  # Center
						player_pixel_position + Vector2(PLAYER_HALF_WIDTH, 0),  # Right
						player_pixel_position + Vector2(-PLAYER_HALF_WIDTH, 0),  # Left
						player_pixel_position + Vector2(0, PLAYER_HALF_WIDTH),  # Bottom
						player_pixel_position + Vector2(0, -PLAYER_HALF_WIDTH),  # Top
						player_pixel_position + Vector2(PLAYER_HALF_WIDTH, PLAYER_HALF_WIDTH),  # Bottom-Right
						player_pixel_position + Vector2(-PLAYER_HALF_WIDTH, PLAYER_HALF_WIDTH),  # Bottom-Left
						player_pixel_position + Vector2(PLAYER_HALF_WIDTH, -PLAYER_HALF_WIDTH),  # Top-Right
						player_pixel_position + Vector2(-PLAYER_HALF_WIDTH, -PLAYER_HALF_WIDTH)  # Top-Left
					]
					
					for point in check_points:
						var dx = abs(point.x - bomb_center.x)
						var dy = abs(point.y - bomb_center.y)
						if dx <= (PLAYER_HALF_WIDTH + 18.0) and dy <= (PLAYER_HALF_WIDTH + 18.0):
							still_colliding = true
							print("[FLAG CHECK] Point ", point, " STILL COLLIDING: dx=", dx, " dy=", dy, " threshold=", (PLAYER_HALF_WIDTH + 18.0))
							break
					
					if not still_colliding:
						print("[FLAG CHECK] NO collision detected - all points clear")
					print("[FLAG CHECK] still_colliding=", still_colliding)
					# Only clear flag if NO part of hitbox is colliding
					if not still_colliding:
						inside_bomb_tile = Vector2(-1, -1)
						inside_bomb_grace_frames = 0
						print("[INSIDE_BOMB] Flag cleared - fully exited bomb at ", bomb.position)
					break
			
			# If bomb no longer exists (exploded), clear flag
			if not found_bomb:
				inside_bomb_tile = Vector2(-1, -1)
				inside_bomb_grace_frames = 0
				print("[INSIDE_BOMB] Flag cleared - bomb no longer exists")
	
	# Handle bomb placement
	var place_bomb = Input.is_action_just_pressed("ui_accept")
	
	# === Network Sync ===
	last_network_sync_time += delta
	if last_network_sync_time >= NETWORK_SYNC_RATE:
		last_network_sync_time = 0.0
		
		# Send current state to server
		input_sequence += 1
		var input_data = {
			"input_x": input_vector.x,
			"input_y": input_vector.y,
			"position_x": player_pixel_position.x,
			"position_y": player_pixel_position.y,
			"place_bomb": place_bomb,
			"seq": input_sequence
		}
		nakama_client.send_player_input(input_data)
	
	if place_bomb:
		# Set inside_bomb_tile to current tile when placing bomb (Atomic Bomberman pattern)
		var player_tile = Vector2(
			floor(player_pixel_position.x / TILE_SIZE),
			floor(player_pixel_position.y / TILE_SIZE)
		)
		inside_bomb_tile = player_tile
		inside_bomb_grace_frames = 5  # Wait ~5 frames for server to confirm bomb placement
		print("[INSIDE_BOMB] Flag set to tile ", player_tile, " - bomb placed")
		
		# Send bomb placement immediately
		input_sequence += 1
		var bomb_input = {
			"input_x": 0,
			"input_y": 0,
			"position_x": player_pixel_position.x,
			"position_y": player_pixel_position.y,
			"place_bomb": true,
			"seq": input_sequence
		}
		nakama_client.send_player_input(bomb_input)

# --- Signal Handlers ---

func _on_match_data_received(data):
	if data.op_code == 2: # State Sync
		game_state = data.data
		_reconcile_local_player(game_state.get("players", {}))
		_update_players(game_state.get("players", {}))
		_update_bombs(game_state.get("bombs", []))
		_update_explosions(game_state.get("explosions", []))
		_update_grid(game_state.get("grid", []))
		_update_powerups(game_state.get("powerUps", []))

# --- Private Update Functions ---

func _update_powerups(server_powerups):
	var current_client_powerups = powerup_scenes.keys()

	for i in range(server_powerups.size()):
		var powerup_data = server_powerups[i]
		var powerup_id = "%s_%s" % [powerup_data.position.x, powerup_data.position.y]
		var powerup_node

		if not powerup_scenes.has(powerup_id):
			powerup_node = Area2D.new()
			powerup_node.name = powerup_id
			
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")
			sprite.scale = Vector2(0.4, 0.4)
			
			# Color based on power-up type
			match powerup_data.type:
				0:  # ExtraBomb
					sprite.modulate = Color.YELLOW
				1:  # BombRadius
					sprite.modulate = Color.ORANGE_RED
				2:  # BombKick
					sprite.modulate = Color.BLUE
				3:  # SpeedUp
					sprite.modulate = Color.LIME_GREEN
				4:  # SpeedDown
					sprite.modulate = Color.PURPLE
				_:
					sprite.modulate = Color.WHITE
			
			powerup_node.add_child(sprite)
			
			# Add a CollisionShape2D for the Area2D
			var collision_shape = CollisionShape2D.new()
			var circle_shape = CircleShape2D.new()
			circle_shape.radius = 20.0
			collision_shape.shape = circle_shape
			powerup_node.add_child(collision_shape)
			
			add_child(powerup_node)
			powerup_scenes[powerup_id] = powerup_node
		else:
			powerup_node = powerup_scenes[powerup_id]
			current_client_powerups.erase(powerup_id)

		powerup_node.position = Vector2(powerup_data.position.x * TILE_SIZE + TILE_SIZE / 2, powerup_data.position.y * TILE_SIZE + TILE_SIZE / 2)

	for powerup_id in current_client_powerups:
		powerup_scenes[powerup_id].queue_free()
		powerup_scenes.erase(powerup_id)

func _update_bombs(server_bombs):
	var current_client_bombs = bomb_scenes.keys()
	
	for bomb_data in server_bombs:
		# Use position as key instead of ID (more stable)
		var bomb_key = "bomb_%d_%d" % [bomb_data.position.x, bomb_data.position.y]
		var bomb_node
		
		if not bomb_scenes.has(bomb_key):
			bomb_node = Node2D.new()
			bomb_node.name = bomb_key
			
			# Create bomb sprite
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")  # Placeholder
			sprite.modulate = Color.BLACK
			sprite.scale = Vector2(0.5, 0.5)
			bomb_node.add_child(sprite)
			
			# Add timer label
			var new_label = Label.new()
			new_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			new_label.position = Vector2(-20, -40)
			bomb_node.add_child(new_label)
			
			add_child(bomb_node)
			bomb_scenes[bomb_key] = bomb_node
		else:
			bomb_node = bomb_scenes[bomb_key]
			current_client_bombs.erase(bomb_key)
		
		bomb_node.position = Vector2(bomb_data.position.x * TILE_SIZE + TILE_SIZE/2, bomb_data.position.y * TILE_SIZE + TILE_SIZE/2)
		
		# Update timer display
		var existing_label = bomb_node.get_child(1) as Label
		var seconds_left = ceil(bomb_data.timer / 20.0)
		existing_label.text = str(seconds_left)
	
	# Remove bombs that no longer exist
	for bomb_key in current_client_bombs:
		bomb_scenes[bomb_key].queue_free()
		bomb_scenes.erase(bomb_key)

# Pixel-based collision detection (Saturn Bomberman style)
# Helper function: Check if a specific grid tile is walkable (no wall/block)
func _is_tile_walkable(grid_x: int, grid_y: int) -> bool:
	if not game_state.has("grid"):
		return true
	
	var grid = game_state.grid
	
	# Out of bounds check
	if grid_y < 0 or grid_y >= grid.size() or grid_x < 0 or grid_x >= grid[0].size():
		return false
	
	# Wall/block check (0 = empty, non-zero = blocked)
	if grid[grid_y][grid_x] != 0:
		return false

	# Treat bombs as blocking the destination tile as well
	if game_state.has("bombs"):
		for bomb in game_state.bombs:
			if bomb.position.x == grid_x and bomb.position.y == grid_y:
				# Allow movement if we're currently standing on this bomb
				var current_grid_x = int(floor(player_pixel_position.x / TILE_SIZE))
				var current_grid_y = int(floor(player_pixel_position.y / TILE_SIZE))
				print("[DEBUG] Bomb at (", grid_x, ",", grid_y, "), current pos (", current_grid_x, ",", current_grid_y, ")")
				if current_grid_x == grid_x and current_grid_y == grid_y:
					print("[DEBUG] Standing on bomb - allowing movement")
					continue
				print("[DEBUG] NOT on bomb - blocking movement")
				return false

	return true

func _is_position_walkable(pixel_pos: Vector2, _from_pos: Vector2 = Vector2.ZERO) -> bool:
	if not game_state.has("grid"):
		return true  # No grid loaded yet
	
	var grid = game_state.grid
	
	# Check collision using a SQUARE bounding box (not circular)
	# This prevents diagonal corners from catching on tiles
	var check_points = [
		pixel_pos,  # Center
		pixel_pos + Vector2(PLAYER_HALF_WIDTH, 0),  # Right edge
		pixel_pos + Vector2(-PLAYER_HALF_WIDTH, 0),  # Left edge
		pixel_pos + Vector2(0, PLAYER_HALF_WIDTH),  # Bottom edge
		pixel_pos + Vector2(0, -PLAYER_HALF_WIDTH),  # Top edge
		# Check all 4 corners of the square bounding box
		pixel_pos + Vector2(PLAYER_HALF_WIDTH, PLAYER_HALF_WIDTH),  # Bottom-Right corner
		pixel_pos + Vector2(-PLAYER_HALF_WIDTH, PLAYER_HALF_WIDTH),  # Bottom-Left corner
		pixel_pos + Vector2(PLAYER_HALF_WIDTH, -PLAYER_HALF_WIDTH),  # Top-Right corner
		pixel_pos + Vector2(-PLAYER_HALF_WIDTH, -PLAYER_HALF_WIDTH)  # Top-Left corner
	]
	
	for point in check_points:
		var grid_x = int(floor(point.x / TILE_SIZE))
		var grid_y = int(floor(point.y / TILE_SIZE))
		
		# Out of bounds check
		if grid_y < 0 or grid_y >= grid.size() or grid_x < 0 or grid_x >= grid[0].size():
			return false
		
		# Wall/block check
		if grid[grid_y][grid_x] != 0:
			return false
		
		# Bomb collision check using Atomic Bomberman's inside_bomb flag system
		if game_state.has("bombs"):
			for bomb in game_state.bombs:
				var bomb_center = Vector2(
					bomb.position.x * TILE_SIZE + TILE_SIZE / 2,
					bomb.position.y * TILE_SIZE + TILE_SIZE / 2
				)
				
				# If inside_bomb_tile matches this bomb's tile, we can pass through it
				if inside_bomb_tile == Vector2(bomb.position.x, bomb.position.y):
					continue
				
				# Check if target position collides with bomb
				var dx = abs(point.x - bomb_center.x)
				var dy = abs(point.y - bomb_center.y)
				if dx < (PLAYER_HALF_WIDTH + 18.0) and dy < (PLAYER_HALF_WIDTH + 18.0):
					return false
	
	return true

# Relaxed collision detection with smaller square box for corner assistance
func _is_position_walkable_relaxed(pixel_pos: Vector2, shrink: float = 6.0) -> bool:
	if not game_state.has("grid"):
		return true

	var grid = game_state.grid
	var half_width = max(PLAYER_HALF_WIDTH - shrink, 10.0)

	# Only check 5 points (center + 4 cardinal directions) to avoid corner catching
	var check_points = [
		pixel_pos,
		pixel_pos + Vector2(half_width, 0),
		pixel_pos + Vector2(-half_width, 0),
		pixel_pos + Vector2(0, half_width),
		pixel_pos + Vector2(0, -half_width)
	]

	for point in check_points:
		var grid_x = int(floor(point.x / TILE_SIZE))
		var grid_y = int(floor(point.y / TILE_SIZE))
		if grid_y < 0 or grid_y >= grid.size() or grid_x < 0 or grid_x >= grid[0].size():
			return false
		if grid[grid_y][grid_x] != 0:
			return false
		if game_state.has("bombs"):
			for bomb in game_state.bombs:
				var bomb_center = Vector2(
					bomb.position.x * TILE_SIZE + TILE_SIZE / 2,
					bomb.position.y * TILE_SIZE + TILE_SIZE / 2
				)
				var dx = abs(point.x - bomb_center.x)
				var dy = abs(point.y - bomb_center.y)
				if dx < (half_width + 18.0) and dy < (half_width + 18.0):
					return false

	return true

# Automatic corner assistance - keeps moving in facing direction until past obstacle
# Example: Facing UP, block to the right. Press RIGHT when >50% past the block.
# Result: Continue moving UP automatically until fully past, then turn RIGHT.
func _try_corner_assistance(desired_velocity: Vector2, _delta: float) -> Vector2:
	if not game_state.has("grid"):
		return Vector2.ZERO
	
	# Calculate player's bounding box edges
	var player_left = player_pixel_position.x - PLAYER_HALF_WIDTH
	var player_right = player_pixel_position.x + PLAYER_HALF_WIDTH
	var player_top = player_pixel_position.y - PLAYER_HALF_WIDTH
	var player_bottom = player_pixel_position.y + PLAYER_HALF_WIDTH
	
	# Determine desired movement direction
	var moving_right = desired_velocity.x > 0
	var moving_left = desired_velocity.x < 0
	var moving_up = desired_velocity.y < 0
	var moving_down = desired_velocity.y > 0
	
	# SCENARIO 1: Facing UP, trying to move LEFT/RIGHT
	if player_facing_direction == "UP" and (moving_left or moving_right):
		# Get current tile and the tile we're trying to turn into
		var current_tile_x = int(floor(player_pixel_position.x / TILE_SIZE))
		var turn_dir = 1 if moving_right else -1
		var turn_tile_x = current_tile_x + turn_dir
		
		# Find all tile rows that our vertical span covers
		var top_tile_y = int(floor(player_top / TILE_SIZE))
		var bottom_tile_y = int(floor(player_bottom / TILE_SIZE))
		
		# Check if ANY tile in the turn column overlaps with our vertical span
		var obstacle_found = false
		var obstacle_tile_y = -1  # Track which row has the obstacle
		for check_y in range(top_tile_y, bottom_tile_y + 1):
			if not _is_tile_walkable(turn_tile_x, check_y):
				obstacle_found = true
				obstacle_tile_y = check_y  # Remember the obstacle's row
				break
		
		if obstacle_found:
			# Check if we can move around this obstacle by going UP
			var diagonal_y = obstacle_tile_y - 1
			var is_diag_walkable = _is_tile_walkable(turn_tile_x, diagonal_y)
			if is_diag_walkable:
				# Diagonal CLEAR - buffer turn by continuing UP
				return Vector2(0, -BASE_SPEED)
		
		return Vector2.ZERO
	
	# SCENARIO 2: Facing DOWN, trying to move LEFT/RIGHT
	elif player_facing_direction == "DOWN" and (moving_left or moving_right):
		var current_tile_x = int(floor(player_pixel_position.x / TILE_SIZE))
		var turn_dir = 1 if moving_right else -1
		var turn_tile_x = current_tile_x + turn_dir
		
		var top_tile_y = int(floor(player_top / TILE_SIZE))
		var bottom_tile_y = int(floor(player_bottom / TILE_SIZE))
		
		var obstacle_found = false
		var obstacle_tile_y = -1
		for check_y in range(top_tile_y, bottom_tile_y + 1):
			if not _is_tile_walkable(turn_tile_x, check_y):
				obstacle_found = true
				obstacle_tile_y = check_y
				break
		
		if obstacle_found:
			# Check if we can move around by going DOWN
			var diagonal_y = obstacle_tile_y + 1
			if _is_tile_walkable(turn_tile_x, diagonal_y):
				# Diagonal CLEAR - buffer turn by continuing DOWN
				return Vector2(0, BASE_SPEED)
		
		return Vector2.ZERO
	
	# SCENARIO 3: Facing LEFT, trying to move UP/DOWN
	elif player_facing_direction == "LEFT" and (moving_up or moving_down):
		var current_tile_y = int(floor(player_pixel_position.y / TILE_SIZE))
		var turn_dir = 1 if moving_down else -1
		var turn_tile_y = current_tile_y + turn_dir
		
		var left_tile_x = int(floor(player_left / TILE_SIZE))
		var right_tile_x = int(floor(player_right / TILE_SIZE))
		
		var obstacle_found = false
		var obstacle_tile_x = -1
		for check_x in range(left_tile_x, right_tile_x + 1):
			if not _is_tile_walkable(check_x, turn_tile_y):
				obstacle_found = true
				obstacle_tile_x = check_x
				break
		
		if obstacle_found:
			# Check if we can move around by going LEFT
			var diagonal_x = obstacle_tile_x - 1
			if _is_tile_walkable(diagonal_x, turn_tile_y):
				# Diagonal CLEAR - buffer turn by continuing LEFT
				return Vector2(-BASE_SPEED, 0)
		
		return Vector2.ZERO
	
	# SCENARIO 4: Facing RIGHT, trying to move UP/DOWN
	elif player_facing_direction == "RIGHT" and (moving_up or moving_down):
		var current_tile_y = int(floor(player_pixel_position.y / TILE_SIZE))
		var turn_dir = 1 if moving_down else -1
		var turn_tile_y = current_tile_y + turn_dir
		
		var left_tile_x = int(floor(player_left / TILE_SIZE))
		var right_tile_x = int(floor(player_right / TILE_SIZE))
		
		var obstacle_found = false
		var obstacle_tile_x = -1
		for check_x in range(left_tile_x, right_tile_x + 1):
			if not _is_tile_walkable(check_x, turn_tile_y):
				obstacle_found = true
				obstacle_tile_x = check_x
				break
		
		if obstacle_found:
			# Check if we can move around by going RIGHT
			var diagonal_x = obstacle_tile_x + 1
			if _is_tile_walkable(diagonal_x, turn_tile_y):
				# Diagonal CLEAR - buffer turn by continuing RIGHT
				return Vector2(BASE_SPEED, 0)
		
		return Vector2.ZERO
	
	return Vector2.ZERO

func _update_explosions(server_explosions):
	# Clear old explosions
	for explosion_id in explosion_scenes.keys():
		explosion_scenes[explosion_id].queue_free()
	explosion_scenes.clear()
	
	# Create new explosions
	for i in range(server_explosions.size()):
		var explosion_data = server_explosions[i]
		var explosion_id = "explosion_" + str(i)
		
		var explosion_container = Node2D.new()
		explosion_container.name = explosion_id
		
		for tile in explosion_data.tiles:
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")  # Placeholder
			sprite.modulate = Color(1.0, 0.5, 0.0, 0.7)  # Orange with transparency
			sprite.position = Vector2(tile.x * TILE_SIZE + TILE_SIZE/2, tile.y * TILE_SIZE + TILE_SIZE/2)
			sprite.scale = Vector2(0.8, 0.8)
			explosion_container.add_child(sprite)
		
		add_child(explosion_container)
		explosion_scenes[explosion_id] = explosion_container

func _reconcile_local_player(server_players):
	if not server_players.has(my_user_id):
		return

	var my_server_state = server_players[my_user_id]
	
	# Server sends pixel positions, accept them with some smoothing
	if my_server_state.has("pixel_position"):
		var server_pixel_pos = Vector2(
			my_server_state.pixel_position.x,
			my_server_state.pixel_position.y
		)
		
		# If server position differs significantly, snap to it (anti-cheat)
		var position_error = player_pixel_position.distance_to(server_pixel_pos)
		if position_error > 100.0:  # More than ~1.5 tiles off
			player_pixel_position = server_pixel_pos
			push_warning("Position corrected by server: error was ", position_error)
	else:
		# Fallback: server sends grid position, convert to pixels
		var server_pixel_pos = Vector2(
			my_server_state.position.x * TILE_SIZE + TILE_SIZE / 2,
			my_server_state.position.y * TILE_SIZE + TILE_SIZE / 2
		)
		player_pixel_position = server_pixel_pos

func _update_players(server_players):
	var current_client_players = player_scenes.keys()

	for player_id in server_players:
		var player_data = server_players[player_id]
		var player_node

		if not player_scenes.has(player_id):
			player_node = Node2D.new()
			player_node.name = player_id
			
			# Create a simple sprite for the player
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")
			sprite.scale = Vector2(0.5, 0.5)
			
			# Color players differently - you vs others
			if player_id == my_user_id:
				sprite.modulate = Color.GREEN
			else:
				sprite.modulate = Color.RED
			
			player_node.add_child(sprite)
			
			# Add username label
			var label = Label.new()
			label.text = player_data.username
			label.position = Vector2(-30, -50)
			label.add_theme_color_override("font_color", Color.WHITE)
			player_node.add_child(label)
			
			add_child(player_node)
			player_scenes[player_id] = player_node
		else:
			player_node = player_scenes[player_id]
			current_client_players.erase(player_id)

		player_node.visible = player_data.isAlive

		# Update positions
		if player_id == my_user_id:
			# Initialize our pixel position if not set
			if player_pixel_position == Vector2.ZERO:
				if player_data.has("pixel_position"):
					player_pixel_position = Vector2(
						player_data.pixel_position.x,
						player_data.pixel_position.y
					)
				else:
					player_pixel_position = Vector2(
						player_data.position.x * TILE_SIZE + TILE_SIZE / 2,
						player_data.position.y * TILE_SIZE + TILE_SIZE / 2
					)
			# Position is updated in _physics_process
		else:
			# Other players: use server position directly
			if player_data.has("pixel_position"):
				player_node.position = Vector2(
					player_data.pixel_position.x,
					player_data.pixel_position.y
				)
			else:
				player_node.position = Vector2(
					player_data.position.x * TILE_SIZE + TILE_SIZE / 2,
					player_data.position.y * TILE_SIZE + TILE_SIZE / 2
				)

	for player_id in current_client_players:
		player_scenes[player_id].queue_free()
		player_scenes.erase(player_id)

func _update_grid(grid_data):
	if grid_rendered:
		return
	
	if grid_data.size() == 0:
		push_warning("Grid data is empty!")
		return
	
	grid_rendered = true
	
	var tiles_created = 0
	for y in range(grid_data.size()):
		for x in range(grid_data[y].size()):
			var tile_type = grid_data[y][x]
			if tile_type > 0:
				tiles_created += 1
				var tile_sprite = Sprite2D.new()
				tile_sprite.texture = load("res://icon.svg")
				tile_sprite.position = Vector2(x * TILE_SIZE + TILE_SIZE/2, y * TILE_SIZE + TILE_SIZE/2)
				tile_sprite.scale = Vector2(0.5, 0.5)
				tile_sprite.z_index = -10  # Render behind everything else
				
				# Color based on tile type
				if tile_type == 1:  # Soft block
					tile_sprite.modulate = Color(0.6, 0.4, 0.2)  # Brown
				elif tile_type == 2:  # Hard block
					tile_sprite.modulate = Color(0.3, 0.3, 0.3)  # Dark gray
				
				add_child(tile_sprite)
	
	if tiles_created > 0:
		print("Grid loaded: ", tiles_created, " tiles")